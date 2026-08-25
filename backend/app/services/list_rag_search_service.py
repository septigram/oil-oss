"""一覧 API 向け RAG 検索サービス。"""

from __future__ import annotations

from typing import Any

from app.rag.index_service import RagIndexService
from app.repository.incident import IncidentRepository, IncidentSearchParams
from app.repository.procedure import ProcedureRepository, ProcedureSearchParams
from app.services.procedure_service import SIMILARITY_THRESHOLD

LIST_RAG_TOP_K = 50


def _collect_incident_scores(hits: list[dict[str, Any]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for hit in hits:
        raw = float(hit.get("score", 0))
        if raw < SIMILARITY_THRESHOLD:
            continue
        meta = hit.get("metadata") or {}
        incident_id = meta.get("incident_id")
        if not incident_id:
            continue
        scores[incident_id] = max(scores.get(incident_id, 0.0), raw)
    return scores


def _collect_procedure_scores(hits: list[dict[str, Any]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for hit in hits:
        raw = float(hit.get("score", 0))
        if raw < SIMILARITY_THRESHOLD:
            continue
        meta = hit.get("metadata") or {}
        procedure_id = meta.get("procedure_id")
        if not procedure_id:
            continue
        scores[procedure_id] = max(scores.get(procedure_id, 0.0), raw)
    return scores


def _attach_scores(
    items: list[dict[str, Any]],
    id_key: str,
    scores: dict[str, float],
) -> list[dict[str, Any]]:
    for item in items:
        raw = scores.get(item[id_key], 0.0)
        item["score"] = round(raw * 100, 1)
    return items


def _paginate(
    items: list[dict[str, Any]],
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    total = len(items)
    offset = (max(1, page) - 1) * page_size
    return items[offset : offset + page_size], total


class ListRagSearchService:
    def __init__(
        self,
        incidents: IncidentRepository | None = None,
        procedures: ProcedureRepository | None = None,
        rag: RagIndexService | None = None,
    ) -> None:
        self._incidents = incidents or IncidentRepository()
        self._procedures = procedures or ProcedureRepository()
        self._rag = rag or RagIndexService()

    def search_incidents(
        self,
        keyword: str,
        *,
        occurred_from=None,
        occurred_to=None,
        statuses: list[str] | None = None,
        severities: list[str] | None = None,
        type_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "-occurred_at",
    ) -> tuple[list[dict[str, Any]], int]:
        hits = self._rag.search_incidents(keyword, top_k=LIST_RAG_TOP_K)
        scores = _collect_incident_scores(hits)
        if not scores:
            return [], 0

        ordered_ids = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
        params = IncidentSearchParams(
            incident_ids=ordered_ids,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            statuses=statuses,
            severities=severities,
            type_id=type_id,
            skip_pagination=True,
        )
        items, _ = self._incidents.search(params)
        items = _attach_scores(items, "incident_id", scores)
        items.sort(key=lambda x: scores.get(x["incident_id"], 0.0), reverse=True)
        return _paginate(items, page, page_size)

    def search_procedures(
        self,
        keyword: str,
        *,
        type_id: str | None = None,
        tags: str | None = None,
        is_active: bool | None = True,
        page: int = 1,
        page_size: int = 20,
        sort: str = "-updated_at",
    ) -> tuple[list[dict[str, Any]], int]:
        hits = self._rag.search_procedures(keyword, top_k=LIST_RAG_TOP_K)
        scores = _collect_procedure_scores(hits)
        if not scores:
            return [], 0

        ordered_ids = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
        params = ProcedureSearchParams(
            procedure_ids=ordered_ids,
            type_id=type_id,
            tags=tags,
            is_active=is_active,
            skip_pagination=True,
        )
        items, _ = self._procedures.search(params)
        items = _attach_scores(items, "procedure_id", scores)
        items.sort(key=lambda x: scores.get(x["procedure_id"], 0.0), reverse=True)
        return _paginate(items, page, page_size)
