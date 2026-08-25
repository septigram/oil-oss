"""受信 Webhook API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.auth.api_key import WebhookApiKeyContext, verify_webhook_api_key
from app.domain.models import IncidentCreateRequest
from app.services.incident_create_service import IncidentCreateService

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

_create_service = IncidentCreateService()


class WebhookIncidentCreateRequest(IncidentCreateRequest):
    auto_triage: bool = False
    recovery_minutes: int | None = None
    external_cause: bool | None = None


@router.post("/incidents", status_code=201)
def create_incident_via_webhook(
    body: WebhookIncidentCreateRequest,
    background_tasks: BackgroundTasks,
    api_key: Annotated[WebhookApiKeyContext, Depends(verify_webhook_api_key)],
) -> dict:
    from app.api.incidents import _sync_rag_after_incident_save

    incident_id = _create_service.create(
        body,
        operator_id=api_key.operator_employee_id,
        background_tasks=background_tasks,
        auto_triage=body.auto_triage,
        recovery_minutes=body.recovery_minutes,
        external_cause=body.external_cause,
        source="webhook",
        api_key_id=api_key.key_id,
        rag_sync_fn=_sync_rag_after_incident_save,
    )
    return {"incident_id": incident_id}
