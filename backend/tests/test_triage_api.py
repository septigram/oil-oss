"""トリアージ API テスト。"""

from __future__ import annotations

import pytest

from tests.conftest import API_PREFIX, tsurugi_available


@pytest.mark.skipif(not tsurugi_available(), reason="Tsurugi not available")
def test_triage_proposals_not_found(client):
    res = client.post(f"{API_PREFIX}/incidents/INC-2099-99999/triage/proposals", json={})
    assert res.status_code == 404


@pytest.mark.skipif(not tsurugi_available(), reason="Tsurugi not available")
def test_triage_proposals_existing_incident(client):
    list_res = client.get(f"{API_PREFIX}/incidents", params={"page_size": 1})
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    if not items:
        pytest.skip("no incidents in seed data")
    incident_id = items[0]["incident_id"]
    res = client.post(
        f"{API_PREFIX}/incidents/{incident_id}/triage/proposals",
        json={"external_cause": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["incident_id"] == incident_id
    assert "proposals" in body
    assert "suggested_severity" in body
