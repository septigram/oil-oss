"""RBAC 単体テスト（依存上書き）。"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.models import Role
from tests.conftest import API_PREFIX, auth_tables_available, override_current_user


def test_viewer_can_get_incidents(client: TestClient) -> None:
    with (
        patch("app.api.incidents._incidents.search", return_value=([], 0)),
        override_current_user(Role.VIEWER),
    ):
        r = client.get(f"{API_PREFIX}/incidents", params={"page": 1, "page_size": 1})
    assert r.status_code == 200


def test_viewer_cannot_post_incident(client: TestClient) -> None:
    with override_current_user(Role.VIEWER):
        r = client.post(
            f"{API_PREFIX}/incidents",
            json={
                "incident": {
                    "type_id": "ITYP-001",
                    "occurred_at": "2020-05-15T10:00:00+09:00",
                    "title": "rbac test",
                    "description": "x",
                    "location_name": "loc",
                    "affected_service_ids": ["SVC-001"],
                    "detector_employee_id": "EMP-00001",
                    "detector_department_id": "DEPT-OPS",
                    "severity": "LOW",
                    "status": "OPEN",
                    "detection_source": "OPS_MONITORING",
                },
                "customer_ids": [],
            },
        )
    assert r.status_code == 403


def test_viewer_cannot_post_master(client: TestClient) -> None:
    with override_current_user(Role.VIEWER):
        r = client.post(
            f"{API_PREFIX}/masters/incident-types",
            json={
                "type_name": "RBAC-TEST",
                "avg_detection_minutes": 10,
                "severity_default": "LOW",
                "detection_source": "OPS_MONITORING",
            },
        )
    assert r.status_code == 403


def test_operator_can_post_incident(client: TestClient) -> None:
    with (
        patch("app.api.incidents._sync_rag_after_incident_save"),
        patch(
            "app.services.incident_create_service.IncidentRepository.create",
            return_value="INC-2020-99999",
        ),
        patch("app.services.incident_create_service.CustomerLinkRepository.replace"),
        patch(
            "app.services.incident_create_service.NotificationService.notify_incident_created",
        ),
        override_current_user(Role.OPERATOR),
    ):
        r = client.post(
            f"{API_PREFIX}/incidents",
            json={
                "incident": {
                    "type_id": "ITYP-001",
                    "occurred_at": "2020-05-15T10:00:00+09:00",
                    "title": "rbac operator",
                    "description": "x",
                    "location_name": "loc",
                    "affected_service_ids": ["SVC-001"],
                    "detector_employee_id": "EMP-00001",
                    "detector_department_id": "DEPT-OPS",
                    "severity": "LOW",
                    "status": "OPEN",
                    "detection_source": "OPS_MONITORING",
                },
                "customer_ids": [],
            },
        )
    assert r.status_code == 201


def test_admin_can_list_users(client: TestClient) -> None:
    if not auth_tables_available():
        pytest.skip("oil_users 未作成（RFC005 マイグレーション未適用）")
    with override_current_user(Role.ADMIN):
        r = client.get(f"{API_PREFIX}/admin/users")
    assert r.status_code == 200
    assert "items" in r.json()


def test_operator_cannot_list_users(client: TestClient) -> None:
    with override_current_user(Role.OPERATOR):
        r = client.get(f"{API_PREFIX}/admin/users")
    assert r.status_code == 403
