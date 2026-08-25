"""対応 API。"""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.auth.dependencies import require_operator_or_admin
from app.auth.models import CurrentUser
from app.domain.models import ResponseCreateRequest, ResponseUpdateRequest
from app.logging_config import log_event
from app.observability.rag_sync_metrics import record_rag_sync_complete
from app.rag.index_service import RagIndexService
from app.repository.incident import IncidentRepository
from app.repository.optimistic import OptimisticLockError
from app.repository.response import ResponseRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents/{incident_id}/responses", tags=["responses"])

_incidents = IncidentRepository()
_responses = ResponseRepository()
_rag = RagIndexService()


def _sync_rag_after_response_save(incident_id: str) -> None:
    """対応保存後の RAG 更新（HTTP 応答後に実行）。"""
    log_event(logger, event="rag_sync_start", incident_id=incident_id)
    start = time.perf_counter()
    try:
        incident = _incidents.get_by_id(incident_id)
        if incident:
            _rag.upsert_incident_document(incident_id, incident["title"], incident["description"])
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


@router.post("", status_code=201)
def create_response(
    incident_id: str,
    body: ResponseCreateRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    if not _incidents.get_by_id(incident_id):
        raise HTTPException(status_code=404, detail="インシデントが見つかりません")
    data = body.model_dump()
    data["response_type"] = data["response_type"].value
    result = _responses.create(incident_id, data, operator_id=user.employee_id)
    background_tasks.add_task(_sync_rag_after_response_save, incident_id)
    return result


@router.put("/{response_id}")
def update_response(
    incident_id: str,
    response_id: str,
    body: ResponseUpdateRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    if not _responses.exists(incident_id, response_id):
        raise HTTPException(status_code=404, detail="対応が見つかりません")
    data = body.model_dump()
    data["response_type"] = data["response_type"].value
    try:
        _responses.update(
            incident_id,
            response_id,
            data,
            row_version=body.row_version,
            operator_id=user.employee_id,
        )
    except OptimisticLockError:
        raise
    background_tasks.add_task(_sync_rag_after_response_save, incident_id)
    return {"response_id": response_id}
