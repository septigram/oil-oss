"""マスタ CRUD API テスト（ADMIN）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.models import Role
from app.repository.tsurugi_conn import TsurugiConnection
from tests.conftest import API_PREFIX, master_write_available, override_current_user, tsurugi_available

INTEG_TYPE_NAME = "INTEG-TEST-TYPE-RFC005"


@pytest.fixture(autouse=True)
def _cleanup_master() -> None:
    yield
    if not tsurugi_available():
        return
    db = TsurugiConnection()
    row = db.fetchone(
        "SELECT type_id FROM oil_incident_types WHERE type_name = ?",
        (INTEG_TYPE_NAME,),
    )
    if row:
        db.execute("DELETE FROM oil_incident_types WHERE type_id = ?", (row[0],))


@pytest.mark.skipif(not master_write_available(), reason="マスタ row_version 未適用")
def test_admin_create_incident_type(client: TestClient) -> None:
    with override_current_user(Role.ADMIN):
        r = client.post(
            f"{API_PREFIX}/masters/incident-types",
            json={
                "type_name": INTEG_TYPE_NAME,
                "avg_detection_minutes": 15,
                "severity_default": "LOW",
                "detection_source": "OPS_MONITORING",
                "description": "integration test",
            },
        )
    assert r.status_code == 201
    body = r.json()
    assert body["type_id"]
    assert body["row_version"] == 1

    type_id = body["type_id"]
    with override_current_user(Role.ADMIN):
        r2 = client.put(
            f"{API_PREFIX}/masters/incident-types/{type_id}",
            json={
                "type_name": INTEG_TYPE_NAME,
                "avg_detection_minutes": 20,
                "severity_default": "LOW",
                "detection_source": "OPS_MONITORING",
                "description": "updated",
                "row_version": 1,
            },
        )
    assert r2.status_code == 200
    assert r2.json()["row_version"] == 2


def test_operator_denied_master_post(client: TestClient) -> None:
    with override_current_user(Role.OPERATOR):
        r = client.post(
            f"{API_PREFIX}/masters/incident-types",
            json={
                "type_name": "DENIED",
                "avg_detection_minutes": 10,
                "severity_default": "LOW",
                "detection_source": "OPS_MONITORING",
            },
        )
    assert r.status_code == 403
