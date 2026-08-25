"""API 結合テスト（Tsurugi 接続可能時）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.reference_date import ReferenceDateService
from tests.conftest import API_PREFIX, CONTEXT_PATH, HEALTH_PATH, SeedExpectations


def test_health(client: TestClient) -> None:
    r = client.get(HEALTH_PATH)
    assert r.status_code == 200


def test_spa_index_when_dist_exists(client: TestClient) -> None:
    from pathlib import Path

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        pytest.skip("frontend/dist not built")
    r = client.get(f"{CONTEXT_PATH}/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_ui_config(client: TestClient) -> None:
    settings = get_settings()
    ref = ReferenceDateService(settings)
    r = client.get(f"{API_PREFIX}/config/ui")
    assert r.status_code == 200
    data = r.json()
    assert data["reference_date"] == ref.get_reference_date().isoformat()
    assert data["operator_name"] == "運用 一郎"
    assert data["reference_date_mode"] == settings.reference_date.mode


def test_metrics(client: TestClient) -> None:
    client.get(f"{API_PREFIX}/config/ui")
    r = client.get(f"{API_PREFIX}/metrics/recent")
    assert r.status_code == 200
    assert "items" in r.json()


def test_logs_recent(client: TestClient) -> None:
    import logging
    from unittest.mock import patch

    from app.log_buffer import reset_for_tests
    from app.logging_config import log_event

    reset_for_tests()
    r = client.get(f"{API_PREFIX}/logs/recent")
    assert r.status_code == 200
    data = r.json()
    assert data == {"items": [], "next_cursor": 0}

    logger = logging.getLogger("app.test.api")
    with patch.object(logger, "info"):
        log_event(logger, event="chat_request", user_message="test")
    r2 = client.get(f"{API_PREFIX}/logs/recent")
    assert r2.status_code == 200
    data2 = r2.json()
    assert len(data2["items"]) == 1
    assert data2["items"][0]["event"] == "chat_request"
    assert data2["next_cursor"] == 1

    r3 = client.get(f"{API_PREFIX}/logs/recent", params={"after": 1})
    assert r3.json() == {"items": [], "next_cursor": 1}


@pytest.mark.integration
def test_incidents_list_initial(
    tsurugi_client: TestClient, seed_expectations: SeedExpectations
) -> None:
    """API-01: 一覧初期表示（過去1カ月×未完了）。"""
    r = tsurugi_client.get(f"{API_PREFIX}/incidents", params={"initial": True})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == seed_expectations.initial_unresolved_in_past_month
    for item in data["items"]:
        assert item["status"] in ("OPEN", "IN_PROGRESS")


@pytest.mark.integration
def test_incidents_quick_filters(
    tsurugi_client: TestClient, seed_expectations: SeedExpectations
) -> None:
    """API-02: 今月・先月・未解決フィルタ。"""
    ref = ReferenceDateService()
    cur = ref.current_month()
    prev = ref.previous_month()

    current_month = tsurugi_client.get(
        f"{API_PREFIX}/incidents",
        params={
            "occurred_from": cur.start.date().isoformat(),
            "occurred_to": cur.end.date().isoformat(),
        },
    )
    assert current_month.status_code == 200
    assert current_month.json()["total"] == seed_expectations.current_month_all

    previous_month = tsurugi_client.get(
        f"{API_PREFIX}/incidents",
        params={
            "occurred_from": prev.start.date().isoformat(),
            "occurred_to": prev.end.date().isoformat(),
        },
    )
    assert previous_month.status_code == 200
    assert previous_month.json()["total"] == seed_expectations.previous_month_all

    unresolved = tsurugi_client.get(
        f"{API_PREFIX}/incidents",
        params=[("status", "OPEN"), ("status", "IN_PROGRESS")],
    )
    assert unresolved.status_code == 200
    assert unresolved.json()["total"] == seed_expectations.unresolved_all


@pytest.mark.integration
def test_incident_create_with_customer(tsurugi_client: TestClient, integration_incident: str) -> None:
    """API-03: インシデント新規 + 顧客紐づけ。"""
    incident_id = integration_incident
    assert incident_id.startswith("INC-2020-")

    detail = tsurugi_client.get(f"{API_PREFIX}/incidents/{incident_id}")
    assert detail.status_code == 200
    customer_ids = [c["customer_id"] for c in detail.json()["customers"]]
    assert "CUST-0001" in customer_ids


@pytest.mark.integration
def test_response_inline_create(tsurugi_client: TestClient, integration_incident: str) -> None:
    """API-04: 対応インライン登録（assignee 固定）。"""
    r = tsurugi_client.post(
        f"{API_PREFIX}/incidents/{integration_incident}/responses",
        json={
            "response_type": "SECONDARY",
            "summary": "INTEG-TEST response",
            "detail": "integration test response detail",
            "started_at": "2020-05-15T11:00:00+09:00",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["response_id"].startswith("RSP-")
    assert data["assignee_employee_id"] == "EMP-00001"
    assert data["sequence_no"] >= 1


@pytest.mark.integration
def test_rag_reindex_summaries(tsurugi_client: TestClient) -> None:
    """API-05: サマリ再インデックス。"""
    r = tsurugi_client.post(f"{API_PREFIX}/rag/reindex-summaries")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["summaries_updated"] == 4
