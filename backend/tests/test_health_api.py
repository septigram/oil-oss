"""ヘルス API の単体テスト。"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services.health_service import HealthCheck, HealthResult
from tests.conftest import CONTEXT_PATH, HEALTH_PATH


def test_health_legacy(client: TestClient) -> None:
    r = client.get(HEALTH_PATH)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_live(client: TestClient) -> None:
    r = client.get(f"{CONTEXT_PATH}/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_ready_ok(client: TestClient) -> None:
    ok = HealthResult(status="ready", checks=[HealthCheck("tsurugi", True, "connected")])
    with patch("app.api.health._service.check_readiness", return_value=ok):
        r = client.get(f"{CONTEXT_PATH}/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_health_ready_503(client: TestClient) -> None:
    ng = HealthResult(
        status="not_ready",
        checks=[HealthCheck("tsurugi", False, "connection refused")],
    )
    with patch("app.api.health._service.check_readiness", return_value=ng):
        r = client.get(f"{CONTEXT_PATH}/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "not_ready"


@pytest.mark.integration
def test_ready_returns_503_when_tsurugi_down(client: TestClient) -> None:
    """結合試験（後続）: Tsurugi 停止時に Readiness が 503。"""
    pytest.skip("requires Tsurugi stopped — run in integration phase")
