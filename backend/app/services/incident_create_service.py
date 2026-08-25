"""インシデント作成オーケストレーション。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import BackgroundTasks

from app.domain.models import IncidentCreateRequest
from app.logging_config import log_event
from app.repository.customer_link import CustomerLinkRepository
from app.repository.incident import IncidentRepository
from app.services.notification_service import NotificationService
from app.services.triage_service import TriageService

logger = logging.getLogger(__name__)


class IncidentCreateService:
    def __init__(
        self,
        incidents: IncidentRepository | None = None,
        customers: CustomerLinkRepository | None = None,
        triage: TriageService | None = None,
        notifications: NotificationService | None = None,
    ) -> None:
        self._incidents = incidents or IncidentRepository()
        self._customers = customers or CustomerLinkRepository()
        self._triage = triage or TriageService(self._incidents)
        self._notifications = notifications or NotificationService()

    @staticmethod
    def incident_to_dict(
        body: IncidentCreateRequest,
    ) -> dict[str, Any]:
        data = body.incident.model_dump()
        data["severity"] = data["severity"].value
        data["status"] = data["status"].value
        data["detection_source"] = data["detection_source"].value
        if body.detected_at is not None:
            data["detected_at"] = body.detected_at
        return data

    def create(
        self,
        body: IncidentCreateRequest,
        *,
        operator_id: str,
        background_tasks: BackgroundTasks,
        auto_triage: bool = False,
        recovery_minutes: int | None = None,
        external_cause: bool | None = None,
        source: str = "ui",
        api_key_id: str | None = None,
        rag_sync_fn: Any | None = None,
    ) -> str:
        data = self.incident_to_dict(body)
        incident_id = self._incidents.create(data, operator_id=operator_id)
        self._customers.replace(incident_id, body.customer_ids)

        if auto_triage:
            triage_result = self._triage.apply_auto_severity(
                incident_id,
                recovery_minutes=recovery_minutes,
                external_cause=external_cause,
                operator_id=operator_id,
            )
            if triage_result:
                log_event(
                    logger,
                    event="webhook_auto_triage",
                    incident_id=incident_id,
                    before=triage_result["before"],
                    after=triage_result["after"],
                    rule_hits=triage_result["rule_hits"],
                )

        event = "webhook_incident_create" if source == "webhook" else "incident_create"
        log_event(
            logger,
            event=event,
            incident_id=incident_id,
            source=source,
            auto_triage=auto_triage,
            api_key_id=api_key_id,
        )

        if rag_sync_fn is not None:
            background_tasks.add_task(
                rag_sync_fn,
                incident_id,
                data["title"],
                data["description"],
            )
        background_tasks.add_task(self._notifications.notify_incident_created, incident_id)
        return incident_id
