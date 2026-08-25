"""RAG インデックス管理サービス。"""

from __future__ import annotations

import json
import logging
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.config import AppConfig, get_settings
from app.logging_config import log_event
from app.rag.embedding import create_embedding_client
from app.rag.faiss_store import FaissStore
from app.repository.ai_sql_context import is_ai_agent_logging_enabled
from app.services.summary_template import SummaryTemplateService

logger = logging.getLogger(__name__)


def _strip_markdown(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"```[\s\S]*?```", " ", text)
    t = re.sub(r"`[^`]+`", " ", t)
    t = re.sub(r"[#*_>\[\]()]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def procedure_embed_text(proc: dict[str, Any]) -> str:
    parts = [
        proc.get("title") or "",
        _strip_markdown(proc.get("problem_description") or ""),
        _strip_markdown(proc.get("procedure_steps") or ""),
    ]
    return "\n".join(p for p in parts if p)


def log_ai_rag(
    query: str,
    *,
    top_k: int,
    duration_ms: float,
    results: list[dict[str, Any]],
) -> None:
    log_event(
        logger,
        event="ai_rag",
        query=query,
        top_k=top_k,
        duration_ms=round(duration_ms, 2),
        result_count=len(results),
        doc_ids=[r.get("doc_id") for r in results],
        scores=[round(float(r.get("score", 0)), 4) for r in results],
    )


class RagIndexService:
    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or get_settings()
        self._store = FaissStore(self._settings)
        self._summary = SummaryTemplateService(self._settings)

    @property
    def store(self) -> FaissStore:
        return self._store

    def ensure_index(self) -> None:
        if not self._store.exists():
            raise FileNotFoundError(
                "FAISS index not found. Run: python tools/build_faiss_index.py"
            )

    def load_corpus_entries(self) -> list[tuple[str, str, dict[str, Any]]]:
        corpus_path = self._settings.paths.corpus_jsonl
        entries: list[tuple[str, str, dict[str, Any]]] = []
        with corpus_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                doc = json.loads(line)
                doc_id = doc["id"]
                meta = {
                    "doc_id": doc_id,
                    "doc_type": doc.get("doc_type", "incident_report"),
                    "incident_id": doc.get("incident_id"),
                    "title": doc.get("title", ""),
                    "source": "corpus",
                }
                entries.append((doc_id, doc["text"], meta))
        return entries

    def build_full_index(self, allow_db_fallback: bool = False) -> int:
        entries = self.load_corpus_entries()
        for doc in self._summary.build_all_summaries(allow_db_fallback=allow_db_fallback):
            entries.append((doc.doc_id, doc.text, doc.metadata))
        entries.extend(self.load_procedure_entries(allow_db_fallback=allow_db_fallback))
        embedding = create_embedding_client(self._settings)
        store = FaissStore(self._settings, embedding)
        store.build_index(entries)
        return len(entries)

    def load_procedure_entries(
        self,
        allow_db_fallback: bool = False,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        try:
            from app.repository.procedure import ProcedureRepository

            procs = ProcedureRepository().load_all_active()
        except Exception:
            if allow_db_fallback:
                return []
            raise
        entries: list[tuple[str, str, dict[str, Any]]] = []
        for proc in procs:
            doc_id = f"DOC-PRC-{proc['procedure_id']}"
            text = procedure_embed_text(proc)
            usage = proc.get("usage_count", 0)
            success = proc.get("success_count", 0)
            success_rate = round(success / usage * 100, 1) if usage > 0 else None
            meta = {
                "doc_id": doc_id,
                "doc_type": "procedure",
                "procedure_id": proc["procedure_id"],
                "type_id": proc.get("type_id"),
                "usage_count": usage,
                "success_rate": success_rate,
                "title": proc.get("title", ""),
                "source": "procedure",
            }
            entries.append((doc_id, text, meta))
        return entries

    def rebuild_summaries_only(self) -> int:
        self.ensure_index()
        self._store.load()
        summaries = list(self._summary.build_all_summaries())
        for doc in summaries:
            self._store.upsert(doc.doc_id, doc.text, doc.metadata)
        return len(summaries)

    def upsert_incident_document(self, incident_id: str, title: str, description: str) -> None:
        self.ensure_index()
        self._store.load()
        doc_id = f"DOC-INC-UPD-{incident_id}"
        text = f"{title}\n{description}"
        meta = {
            "doc_id": doc_id,
            "doc_type": "incident_report",
            "incident_id": incident_id,
            "title": title,
            "source": "corpus",
        }
        self._store.upsert(doc_id, text, meta)

    def upsert_procedure_document(self, proc: dict[str, Any]) -> None:
        if not proc.get("is_active", True):
            self.remove_procedure_document(proc["procedure_id"])
            return
        self.ensure_index()
        self._store.load()
        procedure_id = proc["procedure_id"]
        doc_id = f"DOC-PRC-{procedure_id}"
        text = procedure_embed_text(proc)
        usage = proc.get("usage_count", 0)
        success = proc.get("success_count", 0)
        success_rate = round(success / usage * 100, 1) if usage > 0 else None
        meta = {
            "doc_id": doc_id,
            "doc_type": "procedure",
            "procedure_id": procedure_id,
            "type_id": proc.get("type_id"),
            "usage_count": usage,
            "success_rate": success_rate,
            "title": proc.get("title", ""),
            "source": "procedure",
        }
        self._store.upsert(doc_id, text, meta)

    def remove_procedure_document(self, procedure_id: str) -> None:
        if not self._store.exists():
            return
        self._store.load()
        doc_id = f"DOC-PRC-{procedure_id}"
        self._store.remove(doc_id)

    def search(
        self,
        query: str,
        top_k: int | None = None,
        *,
        doc_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_index()
        self._store.load()
        k = top_k or self._settings.rag.top_k
        start = time.perf_counter()
        with self._trace_search():
            results = self._store.search(query, k, doc_types=doc_types)
        elapsed = time.perf_counter() - start
        try:
            from app.observability.prometheus_metrics import observe_rag_search

            observe_rag_search(duration_seconds=elapsed)
        except ImportError:
            pass
        if is_ai_agent_logging_enabled():
            log_ai_rag(
                query,
                top_k=k,
                duration_ms=elapsed * 1000,
                results=results,
            )
        return results

    @staticmethod
    @contextmanager
    def _trace_search():
        try:
            from app.observability.tracing import trace_span

            with trace_span("faiss.search"):
                yield
        except ImportError:
            yield

    def search_procedures(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        return self.search(query, top_k=top_k, doc_types=["procedure"])

    def search_incidents(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        return self.search(
            query,
            top_k=top_k,
            doc_types=["incident_report", "investigation", "response"],
        )
