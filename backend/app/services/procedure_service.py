"""対応手順書サービス（推奨・類似検索）。"""

from __future__ import annotations

import re
from typing import Any

from app.domain.models import status_display_label
from app.rag.index_service import RagIndexService
from app.repository.incident import IncidentRepository
from app.repository.procedure import ProcedureRepository

SIMILARITY_THRESHOLD = 0.7
RECOMMENDED_TOP_K = 5
SIMILAR_INCIDENTS_TOP_K = 10


def _strip_markdown(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"```[\s\S]*?```", " ", text)
    t = re.sub(r"`[^`]+`", " ", t)
    t = re.sub(r"[#*_>\[\]()]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _procedure_embed_text(proc: dict[str, Any]) -> str:
    parts = [
        proc.get("title") or "",
        _strip_markdown(proc.get("problem_description") or ""),
        _strip_markdown(proc.get("procedure_steps") or ""),
    ]
    return "\n".join(p for p in parts if p)


class ProcedureService:
    def __init__(
        self,
        procedures: ProcedureRepository | None = None,
        incidents: IncidentRepository | None = None,
        rag: RagIndexService | None = None,
    ) -> None:
        self._procedures = procedures or ProcedureRepository()
        self._incidents = incidents or IncidentRepository()
        self._rag = rag or RagIndexService()

    def _incident_query_text(self, incident_id: str) -> str:
        detail = self._incidents.get_detail(incident_id)
        if not detail:
            return ""
        inc = detail["incident"]
        parts = [inc.get("title") or "", inc.get("description") or ""]
        inv = detail.get("investigation")
        if inv:
            parts.append(inv.get("root_cause_summary") or "")
            parts.append(inv.get("investigation_detail") or "")
        return "\n".join(p for p in parts if p)

    def search_similar(
        self,
        title: str,
        description: str,
        *,
        top_k: int = RECOMMENDED_TOP_K,
    ) -> list[dict[str, Any]]:
        query = f"{title}\n{description}".strip()
        if len(query) < 20:
            return []
        try:
            hits = self._rag.search_procedures(query, top_k=top_k * 2)
        except FileNotFoundError:
            return []
        results: list[dict[str, Any]] = []
        for hit in hits:
            if hit.get("score", 0) < SIMILARITY_THRESHOLD:
                continue
            pid = hit.get("metadata", {}).get("procedure_id")
            if not pid:
                continue
            proc = self._procedures.get_by_id(pid)
            if not proc or not proc.get("is_active"):
                continue
            results.append(
                {
                    "procedure_id": pid,
                    "title": proc["title"],
                    "score": round(hit["score"] * 100, 1),
                    "success_rate": proc.get("success_rate"),
                    "usage_count": proc.get("usage_count", 0),
                    "type_id": proc.get("type_id"),
                }
            )
            if len(results) >= top_k:
                break
        return results

    def get_recommended(self, incident_id: str) -> dict[str, Any]:
        query = self._incident_query_text(incident_id)
        similar_incidents = self._find_similar_incidents(query, incident_id)
        procedure_hits = self._vector_procedure_hits(query)
        reranked = self._rerank_procedures(procedure_hits, similar_incidents)
        return {
            "recommended_procedures": reranked[:RECOMMENDED_TOP_K],
            "similar_incidents": similar_incidents[:RECOMMENDED_TOP_K],
        }

    def _vector_procedure_hits(self, query: str) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        try:
            hits = self._rag.search_procedures(query, top_k=10)
        except FileNotFoundError:
            return []
        out: list[dict[str, Any]] = []
        for hit in hits:
            if hit.get("score", 0) < SIMILARITY_THRESHOLD:
                continue
            meta = hit.get("metadata") or {}
            pid = meta.get("procedure_id")
            if not pid:
                continue
            proc = self._procedures.get_by_id(pid)
            if not proc or not proc.get("is_active"):
                continue
            out.append(
                {
                    "procedure_id": pid,
                    "title": proc["title"],
                    "score": hit["score"],
                    "success_rate": proc.get("success_rate"),
                    "usage_count": proc.get("usage_count", 0),
                    "type_id": proc.get("type_id"),
                }
            )
        return out

    def _find_similar_incidents(
        self,
        query: str,
        exclude_incident_id: str,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        try:
            hits = self._rag.search_incidents(query, top_k=SIMILAR_INCIDENTS_TOP_K)
        except FileNotFoundError:
            return []

        incident_ids: list[str] = []
        scored: dict[str, float] = {}
        for hit in hits:
            meta = hit.get("metadata") or {}
            iid = meta.get("incident_id")
            if not iid or iid == exclude_incident_id:
                continue
            if iid in scored:
                scored[iid] = max(scored[iid], hit.get("score", 0))
            else:
                scored[iid] = hit.get("score", 0)
                incident_ids.append(iid)

        proc_map = self._procedures.get_procedure_ids_for_incidents(incident_ids)
        results: list[dict[str, Any]] = []
        for iid in incident_ids:
            inc = self._incidents.get_by_id(iid)
            if not inc:
                continue
            detail = self._incidents.get_detail(iid)
            summary = ""
            if detail and detail.get("responses"):
                summary = detail["responses"][0].get("summary") or ""
            results.append(
                {
                    "incident_id": iid,
                    "title": inc.get("title") or "",
                    "score": round(scored.get(iid, 0) * 100, 1),
                    "status": inc.get("status"),
                    "status_label": status_display_label(inc.get("status", "")),
                    "applied_procedure_ids": proc_map.get(iid, []),
                    "response_summary": summary[:200] if summary else None,
                }
            )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def _rerank_procedures(
        self,
        vector_hits: list[dict[str, Any]],
        similar_incidents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        scores: dict[str, dict[str, Any]] = {}
        for hit in vector_hits:
            pid = hit["procedure_id"]
            scores[pid] = {
                **hit,
                "score": round(hit["score"] * 100, 1),
                "_rank": hit["score"],
            }

        for sim in similar_incidents:
            for pid in sim.get("applied_procedure_ids") or []:
                proc = self._procedures.get_by_id(pid)
                if not proc or not proc.get("is_active"):
                    continue
                bonus = (proc.get("success_rate") or 0) / 100.0 * 0.3
                base = 0.5 + bonus
                if pid in scores:
                    scores[pid]["_rank"] = max(scores[pid]["_rank"], base)
                else:
                    scores[pid] = {
                        "procedure_id": pid,
                        "title": proc["title"],
                        "score": round(base * 100, 1),
                        "success_rate": proc.get("success_rate"),
                        "usage_count": proc.get("usage_count", 0),
                        "type_id": proc.get("type_id"),
                        "_rank": base,
                    }

        ranked = sorted(scores.values(), key=lambda x: x["_rank"], reverse=True)
        for item in ranked:
            item.pop("_rank", None)
        return ranked
