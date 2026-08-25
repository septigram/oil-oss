"""Prometheus メトリクスの単体テスト。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.observability.prometheus_metrics import observe_http_request, render_metrics
from tests.conftest import API_PREFIX, CONTEXT_PATH


def test_observe_http_request_increments_counter() -> None:
    observe_http_request(
        method="GET",
        path=f"{CONTEXT_PATH}/api/incidents",
        status_code=200,
        duration_seconds=0.05,
    )
    body = render_metrics().decode("utf-8")
    assert "http_requests_total" in body
    assert f'path_template="{CONTEXT_PATH}/api/incidents"' in body


def test_metrics_endpoint(client: TestClient) -> None:
    client.get(f"{API_PREFIX}/config/ui")
    r = client.get(f"{CONTEXT_PATH}/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")
    assert "http_requests_total" in r.text
