"""logging_config の単体テスト。"""

import json
import logging
from unittest.mock import patch

from app.logging_config import JsonFormatter, log_event


def test_json_formatter_includes_timestamp() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert "ts" in payload
    assert "T" in payload["ts"]


def test_json_formatter_includes_exception_info() -> None:
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="app.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="failed",
        args=(),
        exc_info=exc_info,
    )
    payload = json.loads(formatter.format(record))
    assert payload["exception_type"] == "ValueError"
    assert payload["exception_message"] == "boom"
    assert "traceback" in payload


def test_log_event_adds_ts_to_extra() -> None:
    from app.log_buffer import reset_for_tests

    reset_for_tests()
    logger = logging.getLogger("app.test.logging")
    with patch.object(logger, "info") as mock_info:
        log_event(logger, event="test_event", foo="bar")
    extra = mock_info.call_args.kwargs["extra"]["extra_data"]
    assert extra["event"] == "test_event"
    assert extra["foo"] == "bar"
    assert extra["service"] == "oil"
    assert extra["env"] == "development"
    assert "version" in extra
    assert "ts" in extra


def test_log_event_appends_llm_event_to_buffer() -> None:
    from app.log_buffer import get_logs_after, reset_for_tests

    reset_for_tests()
    logger = logging.getLogger("app.test.logging.buffer")
    with patch.object(logger, "info"):
        log_event(logger, event="chat_timing", duration_ms=100.0)
    items, _ = get_logs_after(0)
    assert len(items) == 1
    assert items[0]["duration_ms"] == 100.0


def test_setup_logging_writes_oil_log_file_without_verbose(tmp_path, monkeypatch) -> None:
    import app.logging_config as lc

    from app.runtime_flags import set_verbose

    log_path = tmp_path / "oil.jsonl"
    monkeypatch.setenv("OIL_LOG_FILE", str(log_path))
    set_verbose(False)
    lc.setup_logging(force=True)
    logger = logging.getLogger("app.test.file")
    log_event(logger, event="rag_sync_start", incident_id="INC-2020-00001")
    for h in logging.getLogger("app").handlers:
        h.flush()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event"] == "rag_sync_start"
    monkeypatch.delenv("OIL_LOG_FILE", raising=False)
    lc.setup_logging(force=True)


def test_setup_logging_writes_api_timing_for_normal_path_without_verbose(
    tmp_path, monkeypatch
) -> None:
    import app.logging_config as lc

    from app.runtime_flags import set_verbose

    log_path = tmp_path / "oil.jsonl"
    monkeypatch.setenv("OIL_LOG_FILE", str(log_path))
    set_verbose(False)
    lc.setup_logging(force=True)
    logger = logging.getLogger("app.test.file")
    log_event(logger, event="api_timing", path="/oil/api/incidents", duration_ms=12.3)
    for h in logging.getLogger("app").handlers:
        h.flush()
    payload = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[0])
    assert payload["event"] == "api_timing"
    monkeypatch.delenv("OIL_LOG_FILE", raising=False)
    lc.setup_logging(force=True)


def test_timing_middleware_skips_api_timing_in_log_file_for_logs_recent(
    tmp_path, monkeypatch
) -> None:
    import asyncio

    import app.logging_config as lc
    from app.middleware import TimingMiddleware
    from app.runtime_flags import set_verbose
    from starlette.requests import Request
    from starlette.responses import Response

    log_path = tmp_path / "oil.jsonl"
    monkeypatch.setenv("OIL_LOG_FILE", str(log_path))
    set_verbose(False)
    lc.setup_logging(force=True)

    async def call_next(_request: Request) -> Response:
        return Response(status_code=200)

    middleware = TimingMiddleware(app=None)
    request = Request(
        scope={
            "type": "http",
            "method": "GET",
            "path": "/oil/api/logs/recent",
            "headers": [],
        }
    )
    asyncio.run(middleware.dispatch(request, call_next))
    for h in logging.getLogger("app").handlers:
        h.flush()
    assert log_path.read_text(encoding="utf-8").strip() == ""
