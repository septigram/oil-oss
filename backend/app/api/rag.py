"""RAG 管理 API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_admin
from app.auth.models import CurrentUser

from app.rag.index_service import RagIndexService

router = APIRouter(prefix="/api/rag", tags=["rag"])
_rag = RagIndexService()


@router.post("/reindex-summaries")
def reindex_summaries(
    _user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    try:
        count = _rag.rebuild_summaries_only()
        return {"status": "ok", "summaries_updated": count}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/reindex-full")
def reindex_full(_user: Annotated[CurrentUser, Depends(require_admin())]) -> dict:
    count = _rag.build_full_index()
    return {"status": "ok", "total_documents": count}
