"""対応手順書 API。"""

from __future__ import annotations

import logging
import time

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.auth.dependencies import require_any_authenticated, require_operator_or_admin
from app.auth.models import CurrentUser
from app.domain.models import (
    PaginatedResponse,
    ProcedureCreateRequest,
    ProcedureUpdateRequest,
)
from app.logging_config import log_event
from app.observability.rag_sync_metrics import record_rag_sync_complete
from app.rag.index_service import RagIndexService
from app.repository.optimistic import OptimisticLockError
from app.repository.procedure import ProcedureRepository, ProcedureSearchParams
from app.services.list_rag_search_service import ListRagSearchService
from app.services.procedure_service import ProcedureService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/procedures", tags=["procedures"])

_procedures = ProcedureRepository()
_service = ProcedureService(_procedures)
_rag = RagIndexService()
_list_rag = ListRagSearchService(procedures=_procedures, rag=_rag)


def _procedure_to_dict(body: ProcedureCreateRequest | ProcedureUpdateRequest) -> dict:
    exclude = {"row_version"} if isinstance(body, ProcedureUpdateRequest) else set()
    data = body.model_dump(exclude=exclude)
    if data.get("importance") is not None:
        data["importance"] = data["importance"].value
    return data


def _sync_rag_after_procedure_save(procedure_id: str, is_active: bool) -> None:
    log_event(logger, event="rag_sync_start", procedure_id=procedure_id)
    start = time.perf_counter()
    try:
        if is_active:
            proc = _procedures.get_by_id(procedure_id)
            if proc:
                _rag.upsert_procedure_document(proc)
        else:
            _rag.remove_procedure_document(procedure_id)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(
            logger,
            event="rag_sync_complete",
            procedure_id=procedure_id,
            duration_ms=duration_ms,
        )
        record_rag_sync_complete(duration_ms=duration_ms)
    except FileNotFoundError:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(
            logger,
            event="rag_sync_complete",
            procedure_id=procedure_id,
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
            procedure_id=procedure_id,
            duration_ms=duration_ms,
            error=str(exc),
        )
        record_rag_sync_complete(duration_ms=duration_ms, error=str(exc))
        raise


@router.get("")
def list_procedures(
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
    keyword: str | None = None,
    procedure_id: str | None = None,
    type_id: str | None = None,
    tags: str | None = None,
    is_active: bool | None = Query(default=True),
    page: int = 1,
    page_size: int = 20,
    sort: str = "-updated_at",
    rag: bool = False,
) -> PaginatedResponse:
    if rag:
        if not keyword or not keyword.strip():
            raise HTTPException(status_code=400, detail="RAG 検索にはキーワードが必要です")
        try:
            items, total = _list_rag.search_procedures(
                keyword.strip(),
                type_id=type_id,
                tags=tags,
                is_active=is_active,
                page=page,
                page_size=page_size,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail="RAG インデックスがありません") from exc
        return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)

    params = ProcedureSearchParams(
        keyword=keyword,
        procedure_id=procedure_id,
        type_id=type_id,
        tags=tags,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort=sort,
    )
    items, total = _procedures.search(params)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/similar")
def similar_procedures(
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
    title: str = Query(default=""),
    description: str = Query(default=""),
) -> dict:
    items = _service.search_similar(title, description)
    return {"items": items}


@router.get("/{procedure_id}")
def get_procedure(
    procedure_id: str,
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    proc = _procedures.get_by_id(procedure_id)
    if not proc:
        raise HTTPException(status_code=404, detail="手順書が見つかりません")
    return proc


@router.post("", status_code=201)
def create_procedure(
    body: ProcedureCreateRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    data = _procedure_to_dict(body)
    procedure_id = _procedures.create(data, operator_id=user.employee_id)
    if data.get("is_active", True):
        background_tasks.add_task(
            _sync_rag_after_procedure_save,
            procedure_id,
            True,
        )
    return {"procedure_id": procedure_id}


@router.put("/{procedure_id}")
def update_procedure(
    procedure_id: str,
    body: ProcedureUpdateRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    if not _procedures.exists(procedure_id):
        raise HTTPException(status_code=404, detail="手順書が見つかりません")
    data = _procedure_to_dict(body)
    try:
        _procedures.update(
            procedure_id,
            data,
            row_version=body.row_version,
            operator_id=user.employee_id,
        )
    except OptimisticLockError:
        raise
    background_tasks.add_task(
        _sync_rag_after_procedure_save,
        procedure_id,
        data.get("is_active", True),
    )
    return {"procedure_id": procedure_id}


@router.get("/{procedure_id}/incidents")
def list_procedure_incidents(
    procedure_id: str,
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    if not _procedures.exists(procedure_id):
        raise HTTPException(status_code=404, detail="手順書が見つかりません")
    items = _procedures.list_incidents_by_procedure(procedure_id)
    return {"items": items}
