"""インシデント API。"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, time as time_of_day
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.auth.dependencies import require_any_authenticated, require_operator_or_admin
from app.auth.models import CurrentUser
from app.config import get_settings
from app.domain.models import (
    IncidentCreateRequest,
    IncidentStatus,
    IncidentUpdateRequest,
    PaginatedResponse,
    ProcedureApplyRequest,
    ProcedureSuccessUpdateRequest,
)
from app.logging_config import log_event
from app.observability.rag_sync_metrics import record_rag_sync_complete
from app.rag.index_service import RagIndexService
from app.repository.customer_link import CustomerLinkRepository
from app.repository.incident import IncidentRepository, IncidentSearchParams
from app.repository.optimistic import OptimisticLockError
from app.repository.procedure import ProcedureRepository
from app.services.list_rag_search_service import ListRagSearchService
from app.services.procedure_generation_service import ProcedureGenerationService
from app.services.procedure_service import ProcedureService
from app.services.reference_date import ReferenceDateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

_incidents = IncidentRepository()
_customers = CustomerLinkRepository()
_procedures = ProcedureRepository()
_procedure_service = ProcedureService(_procedures, _incidents)
_procedure_generation = ProcedureGenerationService(procedures=_procedures)
_rag = RagIndexService()
_list_rag = ListRagSearchService(_incidents, _procedures, _rag)
_ref = ReferenceDateService()


def _parse_date_bound(d: date, end_of_day: bool = False) -> datetime:
    tz = ZoneInfo(get_settings().timezone)
    if end_of_day:
        return datetime.combine(d, time_of_day(23, 59, 59, 999000), tzinfo=tz)
    return datetime.combine(d, time_of_day.min, tzinfo=tz)


def _incident_to_dict(inc: IncidentCreateRequest | IncidentUpdateRequest) -> dict:
    data = inc.incident.model_dump()
    data["severity"] = data["severity"].value
    data["status"] = data["status"].value
    data["detection_source"] = data["detection_source"].value
    if inc.detected_at is not None:
        data["detected_at"] = inc.detected_at
    return data


def _sync_rag_after_incident_save(incident_id: str, title: str, description: str) -> None:
    """インシデント保存後の RAG 更新（HTTP 応答後に実行）。"""
    log_event(logger, event="rag_sync_start", incident_id=incident_id)
    start = time.perf_counter()
    try:
        _rag.upsert_incident_document(incident_id, title, description)
        summary_count = _rag.rebuild_summaries_only()
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(
            logger,
            event="rag_sync_complete",
            incident_id=incident_id,
            duration_ms=duration_ms,
            summary_count=summary_count,
        )
        record_rag_sync_complete(duration_ms=duration_ms)
    except FileNotFoundError:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(
            logger,
            event="rag_sync_complete",
            incident_id=incident_id,
            duration_ms=duration_ms,
            skipped=True,
            reason="FAISS index not found",
        )
        record_rag_sync_complete(duration_ms=duration_ms, skipped=True)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(
            logger,
            event="rag_sync_complete",
            incident_id=incident_id,
            duration_ms=duration_ms,
            error=str(exc),
        )
        record_rag_sync_complete(duration_ms=duration_ms, error=str(exc))
        raise


@router.get("")
def list_incidents(
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
    keyword: str | None = None,
    occurred_from: date | None = None,
    occurred_to: date | None = None,
    status: Annotated[list[str] | None, Query()] = None,
    severity: Annotated[list[str] | None, Query()] = None,
    type_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort: str = "-occurred_at",
    initial: bool = False,
    rag: bool = False,
) -> PaginatedResponse:
    if rag:
        if not keyword or not keyword.strip():
            raise HTTPException(status_code=400, detail="RAG 検索にはキーワードが必要です")
        occurred_from_dt = _parse_date_bound(occurred_from) if occurred_from else None
        occurred_to_dt = _parse_date_bound(occurred_to, end_of_day=True) if occurred_to else None
        try:
            items, total = _list_rag.search_incidents(
                keyword.strip(),
                occurred_from=occurred_from_dt,
                occurred_to=occurred_to_dt,
                statuses=status,
                severities=severity,
                type_id=type_id,
                page=page,
                page_size=page_size,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail="RAG インデックスがありません") from exc
        return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)

    if initial:
        past = _ref.past_one_month()
        occurred_from_dt = past.start
        occurred_to_dt = past.end
        if not status:
            status = [IncidentStatus.OPEN, IncidentStatus.IN_PROGRESS]
    else:
        occurred_from_dt = _parse_date_bound(occurred_from) if occurred_from else None
        occurred_to_dt = _parse_date_bound(occurred_to, end_of_day=True) if occurred_to else None

    params = IncidentSearchParams(
        keyword=keyword,
        occurred_from=occurred_from_dt,
        occurred_to=occurred_to_dt,
        statuses=status,
        severities=severity,
        type_id=type_id,
        page=page,
        page_size=page_size,
        sort=sort,
    )
    items, total = _incidents.search(params)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{incident_id}")
def get_incident(
    incident_id: str,
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    detail = _incidents.get_detail(incident_id)
    if not detail:
        raise HTTPException(status_code=404, detail="インシデントが見つかりません")
    return detail


@router.post("", status_code=201)
def create_incident(
    body: IncidentCreateRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    from app.services.incident_create_service import IncidentCreateService

    create_service = IncidentCreateService()
    incident_id = create_service.create(
        body,
        operator_id=user.employee_id,
        background_tasks=background_tasks,
        source="ui",
        rag_sync_fn=_sync_rag_after_incident_save,
    )
    return {"incident_id": incident_id}


@router.put("/{incident_id}")
def update_incident(
    incident_id: str,
    body: IncidentUpdateRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    if not _incidents.get_by_id(incident_id):
        raise HTTPException(status_code=404, detail="インシデントが見つかりません")
    data = _incident_to_dict(body)
    try:
        _incidents.update(
            incident_id,
            data,
            row_version=body.row_version,
            operator_id=user.employee_id,
        )
    except OptimisticLockError:
        raise
    _customers.replace(incident_id, body.customer_ids)
    background_tasks.add_task(
        _sync_rag_after_incident_save,
        incident_id,
        data["title"],
        data["description"],
    )
    return {"incident_id": incident_id}


@router.get("/{incident_id}/procedures")
def list_incident_procedures(
    incident_id: str,
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    if not _incidents.get_by_id(incident_id):
        raise HTTPException(status_code=404, detail="インシデントが見つかりません")
    items = _procedures.list_by_incident(incident_id)
    return {"items": items}


@router.post("/{incident_id}/procedures", status_code=201)
def apply_procedure(
    incident_id: str,
    body: ProcedureApplyRequest,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    if not _incidents.get_by_id(incident_id):
        raise HTTPException(status_code=404, detail="インシデントが見つかりません")
    try:
        result = _procedures.apply_to_incident(
            incident_id,
            body.procedure_id,
            body.notes,
            operator_id=user.employee_id,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="手順書が見つかりません") from None
    return result


@router.get("/{incident_id}/recommended-procedures")
def recommended_procedures(
    incident_id: str,
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    if not _incidents.get_by_id(incident_id):
        raise HTTPException(status_code=404, detail="インシデントが見つかりません")
    return _procedure_service.get_recommended(incident_id)


@router.post("/{incident_id}/procedures/from-incident")
def build_procedure_from_incident(
    incident_id: str,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    try:
        preview, meta = _procedure_generation.generate_preview_for_incident(incident_id)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail="インシデントが見つかりません") from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    return {"preview": preview, "meta": meta}


@router.patch("/{incident_id}/procedures/{link_id}")
def update_procedure_success(
    incident_id: str,
    link_id: int,
    body: ProcedureSuccessUpdateRequest,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    if not _incidents.get_by_id(incident_id):
        raise HTTPException(status_code=404, detail="インシデントが見つかりません")
    try:
        _procedures.update_was_successful(link_id, body.was_successful, body.notes)
    except ValueError:
        raise HTTPException(status_code=404, detail="適用記録が見つかりません") from None
    return {"id": link_id, "was_successful": body.was_successful}


@router.delete("/{incident_id}/procedures/{link_id}", status_code=204)
def unlink_procedure(
    incident_id: str,
    link_id: int,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> None:
    if not _incidents.get_by_id(incident_id):
        raise HTTPException(status_code=404, detail="インシデントが見つかりません")
    try:
        _procedures.unlink_from_incident(incident_id, link_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="適用記録が見つかりません") from None
