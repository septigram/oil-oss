"""通知サービスの単体テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.notification_service import NotificationService


def test_build_payload_contains_incident_id() -> None:
    svc = NotificationService()
    detail = {
        "incident": {
            "incident_id": "INC-2020-00001",
            "title": "テスト障害",
            "severity": "HIGH",
            "status": "OPEN",
            "occurred_at": "2020-05-15T10:00:00+09:00",
            "description": "説明文",
        }
    }
    payload = svc.build_payload(detail)
    assert "INC-2020-00001" in payload["text"]
    assert "テスト障害" in payload["text"]


@patch("app.services.notification_service.httpx.Client")
def test_notify_failure_does_not_raise(mock_client_cls: MagicMock) -> None:
    incidents = MagicMock()
    incidents.get_detail.return_value = {
        "incident": {
            "incident_id": "INC-2020-00001",
            "type_id": "ITYP-001",
            "title": "t",
            "severity": "LOW",
            "status": "OPEN",
            "occurred_at": "2020-05-15T10:00:00+09:00",
            "description": "d",
        }
    }
    channels = MagicMock()
    channels.list_active_for_type.return_value = [
        {"channel_id": "CHN-00001", "name": "test", "webhook_url": "https://example.com/hook"}
    ]
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = RuntimeError("network")

    svc = NotificationService(channels=channels, incidents=incidents)
    sent = svc.notify_incident_created("INC-2020-00001")
    assert sent == 1
