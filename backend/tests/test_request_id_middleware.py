"""request_id ミドルウェアの単体テスト。"""

from __future__ import annotations

import logging
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.middleware import REQUEST_ID_HEADER
from app.request_context import clear_request_id, generate_request_id, is_valid_request_id, set_request_id
from tests.conftest import API_PREFIX


def test_is_valid_request_id() -> None:
    rid = generate_request_id()
    assert is_valid_request_id(rid)
    assert not is_valid_request_id("not-a-uuid")


def test_x_request_id_generated(client: TestClient) -> None:
    r = client.get(f"{API_PREFIX}/config/ui")
    assert r.status_code == 200
    assert REQUEST_ID_HEADER in r.headers
    assert is_valid_request_id(r.headers[REQUEST_ID_HEADER])


def test_x_request_id_respected(client: TestClient) -> None:
    custom_id = generate_request_id()
    r = client.get(f"{API_PREFIX}/config/ui", headers={REQUEST_ID_HEADER: custom_id})
    assert r.headers[REQUEST_ID_HEADER] == custom_id


def test_log_event_includes_request_id() -> None:
    logger = logging.getLogger("app.test.request_id")
    with patch.object(logger, "info") as mock_info:
        from app.logging_config import log_event

        rid = generate_request_id()
        set_request_id(rid)
        try:
            log_event(logger, event="test_event")
        finally:
            clear_request_id()
    payload = mock_info.call_args.kwargs["extra"]["extra_data"]
    assert payload["request_id"] == rid
    assert payload["service"] == "oil"


def test_api_timing_includes_request_id(client: TestClient) -> None:
    from app.metrics import get_recent_metrics

    client.get(f"{API_PREFIX}/config/ui")
    items = get_recent_metrics()
    assert items
    assert "request_id" in items[-1]
    assert is_valid_request_id(items[-1]["request_id"])
