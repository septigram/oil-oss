"""Slack 通知サービス。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.logging_config import log_event
from app.repository.incident import IncidentRepository
from app.repository.notification_channel import NotificationChannelRepository

logger = logging.getLogger(__name__)

DESCRIPTION_PREVIEW_LEN = 200


class NotificationService:
    def __init__(
        self,
        channels: NotificationChannelRepository | None = None,
        incidents: IncidentRepository | None = None,
    ) -> None:
        self._channels = channels or NotificationChannelRepository()
        self._incidents = incidents or IncidentRepository()
        self._settings = get_settings()

    def _incident_detail_url(self, incident_id: str) -> str:
        return f"{self._settings.base_url}/incidents/{incident_id}"

    def build_payload(self, detail: dict[str, Any]) -> dict[str, Any]:
        incident = detail["incident"]
        incident_id = incident["incident_id"]
        description = incident.get("description") or ""
        preview = description[:DESCRIPTION_PREVIEW_LEN]
        if len(description) > DESCRIPTION_PREVIEW_LEN:
            preview += "..."
        text = (
            f"*[oil] 新規インシデント* `{incident_id}`\n"
            f"*タイトル:* {incident.get('title', '')}\n"
            f"*重要度:* {incident.get('severity', '')}  "
            f"*状態:* {incident.get('status', '')}\n"
            f"*発生日時:* {incident.get('occurred_at', '')}\n"
            f"*概要:* {preview}\n"
            f"<{self._incident_detail_url(incident_id)}|詳細を開く>"
        )
        return {"text": text}

    def _post_webhook(self, channel: dict[str, Any], payload: dict[str, Any], incident_id: str) -> None:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(channel["webhook_url"], json=payload)
                response.raise_for_status()
            log_event(
                logger,
                event="notification_sent",
                incident_id=incident_id,
                channel_id=channel["channel_id"],
                channel_name=channel.get("name"),
            )
        except Exception as exc:
            log_event(
                logger,
                event="notification_failed",
                incident_id=incident_id,
                channel_id=channel["channel_id"],
                channel_name=channel.get("name"),
                error=str(exc),
            )

    def notify_incident(
        self,
        incident_id: str,
        *,
        channel_ids: list[str] | None = None,
    ) -> int:
        detail = self._incidents.get_detail(incident_id)
        if not detail:
            return 0
        type_id = detail["incident"]["type_id"]
        if channel_ids:
            channels = []
            for channel_id in channel_ids:
                ch = self._channels.get_by_id(channel_id)
                if ch and ch["is_active"]:
                    channels.append(ch)
        else:
            try:
                channels = self._channels.list_active_for_type(type_id)
            except Exception as exc:
                log_event(
                    logger,
                    event="notification_skipped",
                    incident_id=incident_id,
                    reason=str(exc),
                )
                return 0
        if not channels:
            return 0
        payload = self.build_payload(detail)
        sent = 0
        for channel in channels:
            self._post_webhook(channel, payload, incident_id)
            sent += 1
        return sent

    def notify_incident_created(self, incident_id: str) -> int:
        return self.notify_incident(incident_id)
