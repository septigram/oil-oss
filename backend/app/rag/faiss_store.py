"""FAISS インデックスストア。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from app.config import AppConfig, get_settings
from app.rag.embedding import EmbeddingClient, create_embedding_client


class FaissStore:
    def __init__(
        self,
        settings: AppConfig | None = None,
        embedding: EmbeddingClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._faiss_dir = self._settings.paths.faiss_dir
        self._embedding = embedding or create_embedding_client()
        self._index: faiss.IndexFlatIP | None = None
        self._metadata: dict[str, dict[str, Any]] = {}
        self._doc_id_to_idx: dict[str, int] = {}

    @property
    def index_path(self) -> Path:
        return self._faiss_dir / "index.faiss"

    @property
    def metadata_path(self) -> Path:
        return self._faiss_dir / "metadata.json"

    @property
    def manifest_path(self) -> Path:
        return self._faiss_dir / "manifest.json"

    def exists(self) -> bool:
        return self.index_path.exists() and self.metadata_path.exists()

    def load(self) -> None:
        if not self.exists():
            raise FileNotFoundError(
                "FAISS index not found. Run: python tools/build_faiss_index.py"
            )
        self._index = faiss.read_index(str(self.index_path))
        with self.metadata_path.open(encoding="utf-8") as f:
            data = json.load(f)
        self._metadata = data["documents"]
        self._doc_id_to_idx = {doc_id: meta["faiss_idx"] for doc_id, meta in self._metadata.items()}
        try:
            from app.observability.prometheus_metrics import set_faiss_index_loaded

            set_faiss_index_loaded(True)
        except ImportError:
            pass

    def is_loaded(self) -> bool:
        return self._index is not None

    def _ensure_loaded(self) -> faiss.IndexFlatIP:
        if self._index is None:
            self.load()
        assert self._index is not None
        return self._index

    def save(self, index: faiss.IndexFlatIP, documents: dict[str, dict[str, Any]], total: int) -> None:
        self._faiss_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_path))
        with self.metadata_path.open("w", encoding="utf-8") as f:
            json.dump({"documents": documents}, f, ensure_ascii=False, indent=2)
        manifest = {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "total_documents": total,
            "embedding_model": self._embedding.model_name,
            "dimension": self._embedding.dimension,
        }
        with self.manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        self._index = index
        self._metadata = documents
        self._doc_id_to_idx = {doc_id: meta["faiss_idx"] for doc_id, meta in documents.items()}

    def build_index(
        self,
        entries: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        """entries: (doc_id, text, metadata)"""
        texts = [e[1] for e in entries]
        vectors = self._embedding.embed_texts(texts)
        dim = vectors.shape[1] if len(vectors) else self._embedding.dimension
        index = faiss.IndexFlatIP(dim)
        if len(vectors):
            index.add(vectors)
        documents: dict[str, dict[str, Any]] = {}
        for idx, (doc_id, text, meta) in enumerate(entries):
            documents[doc_id] = {**meta, "text": text, "faiss_idx": idx}
        self.save(index, documents, len(entries))

    def _rebuild_index_from_metadata(self) -> None:
        entries: list[tuple[str, str, dict[str, Any]]] = []
        for doc_id, meta in sorted(self._metadata.items(), key=lambda item: item[1]["faiss_idx"]):
            payload = {k: v for k, v in meta.items() if k not in ("text", "faiss_idx")}
            entries.append((doc_id, meta["text"], payload))
        self.build_index(entries)

    def upsert(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None:
        self._ensure_loaded()
        if doc_id in self._metadata:
            self._metadata[doc_id] = {
                **self._metadata[doc_id],
                **metadata,
                "text": text,
            }
            self._rebuild_index_from_metadata()
            return
        index = self._ensure_loaded()
        vec = self._embedding.embed_texts([text])
        new_idx = index.ntotal
        index.add(vec)
        metadata_entry = {**metadata, "text": text, "faiss_idx": new_idx}
        self._metadata[doc_id] = metadata_entry
        self._doc_id_to_idx[doc_id] = new_idx
        faiss.write_index(index, str(self.index_path))
        with self.metadata_path.open("w", encoding="utf-8") as f:
            json.dump({"documents": self._metadata}, f, ensure_ascii=False, indent=2)

    def search(
        self,
        query: str,
        top_k: int,
        *,
        doc_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        import time

        start = time.perf_counter()
        index = self._ensure_loaded()
        qvec = self._embedding.embed_texts([query])
        fetch_k = min(max(top_k * 10, 50), index.ntotal)
        scores, indices = index.search(qvec, fetch_k)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        idx_to_doc = {meta["faiss_idx"]: (doc_id, meta) for doc_id, meta in self._metadata.items()}
        results: list[dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            doc_id, meta = idx_to_doc.get(int(idx), (None, None))
            if meta is None:
                continue
            if doc_types and meta.get("doc_type") not in doc_types:
                continue
            results.append(
                {
                    "doc_id": doc_id,
                    "score": float(score),
                    "text": meta.get("text", ""),
                    "metadata": {k: v for k, v in meta.items() if k not in ("text", "faiss_idx")},
                    "rag_search_ms": elapsed_ms,
                }
            )
            if len(results) >= top_k:
                break
        return results

    def remove(self, doc_id: str) -> None:
        if doc_id not in self._metadata:
            return
        del self._metadata[doc_id]
        self._doc_id_to_idx = {
            did: meta["faiss_idx"] for did, meta in self._metadata.items()
        }
        if self._metadata:
            self._rebuild_index_from_metadata()
        else:
            dim = self._embedding.dimension
            index = faiss.IndexFlatIP(dim)
            self.save(index, {}, 0)
