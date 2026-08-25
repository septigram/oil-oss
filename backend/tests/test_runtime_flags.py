"""runtime_flags と api_timing ログ出力のテスト。"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from app.runtime_flags import init_runtime_flags, is_verbose, set_verbose


@pytest.fixture(autouse=True)
def reset_verbose(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OIL_VERBOSE", raising=False)
    set_verbose(False)


def test_is_verbose_default_false() -> None:
    assert is_verbose() is False


def test_set_verbose_true() -> None:
    set_verbose(True)
    assert is_verbose() is True


def test_init_runtime_flags_enables_uvicorn_access_log() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.disabled = True
    set_verbose(False)
    init_runtime_flags()
    assert access_logger.disabled is False


@patch("app.middleware.log_event")
@patch("app.middleware.record_metric")
def test_timing_middleware_skips_log_event_for_logs_recent_when_not_verbose(
    mock_record: patch,
    mock_log_event: patch,
) -> None:
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    from app.middleware import TimingMiddleware

    set_verbose(False)

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

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 200
    mock_record.assert_called_once()
    mock_log_event.assert_not_called()


@patch("app.middleware.log_event")
@patch("app.middleware.record_metric")
def test_timing_middleware_logs_api_timing_for_normal_path_when_not_verbose(
    mock_record: patch,
    mock_log_event: patch,
) -> None:
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    from app.middleware import TimingMiddleware

    set_verbose(False)

    async def call_next(_request: Request) -> Response:
        return Response(status_code=200)

    middleware = TimingMiddleware(app=None)
    request = Request(
        scope={
            "type": "http",
            "method": "GET",
            "path": "/oil/api/health",
            "headers": [],
        }
    )

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 200
    mock_record.assert_called_once()
    mock_log_event.assert_called_once()


@patch("app.middleware.log_event")
@patch("app.middleware.record_metric")
def test_timing_middleware_logs_logs_recent_when_verbose(
    mock_record: patch,
    mock_log_event: patch,
) -> None:
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    from app.middleware import TimingMiddleware

    set_verbose(True)

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

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 200
    mock_record.assert_called_once()
    mock_log_event.assert_called_once()
