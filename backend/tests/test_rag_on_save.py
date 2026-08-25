"""RAG 保存連動の単体テスト。"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import API_PREFIX, override_current_user


def _create_patches(rag: MagicMock, incident_id: str = "INC-2020-99999"):
    return (
        patch("app.api.incidents._rag", rag),
        patch(
            "app.services.incident_create_service.IncidentRepository.create",
            return_value=incident_id,
        ),
        patch("app.services.incident_create_service.CustomerLinkRepository.replace"),
        patch(
            "app.services.incident_create_service.NotificationService.notify_incident_created",
        ),
    )


def test_incident_create_triggers_rag_update() -> None:
    client = TestClient(app)
    rag = MagicMock()
    body = {
        "incident": {
            "type_id": "ITYP-001",
            "occurred_at": "2020-05-15T10:00:00+09:00",
            "title": "RAG trigger test",
            "description": "desc",
            "location_name": "loc",
            "affected_service_ids": ["SVC-001"],
            "detector_employee_id": "EMP-00001",
            "detector_department_id": "DEPT-OPS",
            "severity": "LOW",
            "status": "OPEN",
            "detection_source": "OPS_MONITORING",
        },
        "customer_ids": [],
    }
    with ExitStack() as stack:
        stack.enter_context(override_current_user())
        for p in _create_patches(rag):
            stack.enter_context(p)
        r = client.post(f"{API_PREFIX}/incidents", json=body)
    assert r.status_code == 201
    rag.upsert_incident_document.assert_called_once_with("INC-2020-99999", "RAG trigger test", "desc")
    rag.rebuild_summaries_only.assert_called_once()


def test_incident_create_logs_rag_sync_events() -> None:
    from app.log_buffer import get_logs_after, reset_for_tests

    reset_for_tests()
    client = TestClient(app)
    rag = MagicMock()
    rag.rebuild_summaries_only.return_value = 4
    body = {
        "incident": {
            "type_id": "ITYP-001",
            "occurred_at": "2020-05-15T10:00:00+09:00",
            "title": "RAG log test",
            "description": "desc",
            "location_name": "loc",
            "affected_service_ids": ["SVC-001"],
            "detector_employee_id": "EMP-00001",
            "detector_department_id": "DEPT-OPS",
            "severity": "LOW",
            "status": "OPEN",
            "detection_source": "OPS_MONITORING",
        },
        "customer_ids": [],
    }
    with ExitStack() as stack:
        stack.enter_context(override_current_user())
        for p in _create_patches(rag):
            stack.enter_context(p)
        r = client.post(f"{API_PREFIX}/incidents", json=body)
    assert r.status_code == 201
    items, _ = get_logs_after(0)
    events = [item["event"] for item in items]
    assert "rag_sync_start" in events
    assert "rag_sync_complete" in events
    complete = next(item for item in items if item["event"] == "rag_sync_complete")
    assert complete["incident_id"] == "INC-2020-99999"
    assert complete["summary_count"] == 4


def test_response_update_triggers_summary_rebuild() -> None:
    client = TestClient(app)
    rag = MagicMock()
    responses = MagicMock()
    responses.exists.return_value = True
    incidents = MagicMock()
    incidents.get_by_id.return_value = {
        "incident_id": "INC-2020-00001",
        "title": "Test title",
        "description": "Test description",
    }
    with ExitStack() as stack:
        stack.enter_context(override_current_user())
        stack.enter_context(patch("app.api.responses._rag", rag))
        stack.enter_context(patch("app.api.responses._responses", responses))
        stack.enter_context(patch("app.api.responses._incidents", incidents))
        r = client.put(
            f"{API_PREFIX}/incidents/INC-2020-00001/responses/RSP-00001",
            json={
                "response_type": "SECONDARY",
                "summary": "updated",
                "detail": "updated detail",
                "started_at": "2020-05-15T11:00:00+09:00",
                "row_version": 1,
            },
        )
    assert r.status_code == 200
    rag.upsert_incident_document.assert_called_once_with(
        "INC-2020-00001", "Test title", "Test description"
    )
    rag.rebuild_summaries_only.assert_called_once()
