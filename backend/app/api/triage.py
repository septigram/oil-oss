"""トリアージ API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_operator_or_admin
from app.auth.models import CurrentUser
from pydantic import BaseModel, Field

from app.services.triage_service import TRIAGE_FIELDS, TriageService

router = APIRouter(prefix="/api/incidents", tags=["triage"])

_triage = TriageService()


class TriageProposalsRequest(BaseModel):
    focus_fields: list[str] | None = Field(
        default=None,
        description=f"提案対象フィールド。省略時は全対象: {', '.join(TRIAGE_FIELDS)}",
    )
    recovery_minutes: int | None = None
    external_cause: bool | None = None


@router.post("/{incident_id}/triage/proposals")
def create_triage_proposals(
    incident_id: str,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
    body: TriageProposalsRequest | None = None,
) -> dict:
    req = body or TriageProposalsRequest()
    result = _triage.build_proposals(
        incident_id,
        focus_fields=req.focus_fields,
        recovery_minutes=req.recovery_minutes,
        external_cause=req.external_cause,
    )
    if not result:
        raise HTTPException(status_code=404, detail="インシデントが見つかりません")
    return result
