"""未捕捉例外ハンドラの単体テスト。"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.logging_config import log_event
from app.middleware import REQUEST_ID_HEADER, RequestIdMiddleware

logger = logging.getLogger(__name__)


def _create_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestIdMiddleware)

    @test_app.get("/boom")
    def boom() -> None:
        raise RuntimeError("test boom")

    @test_app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        log_event(
            logger,
            event="unhandled_exception",
            exception_type=type(exc).__name__,
            message=str(exc),
            request_id=request_id,
        )
        response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
        if request_id:
            response.headers[REQUEST_ID_HEADER] = request_id
        return response

    return test_app


def test_unhandled_exception_returns_500() -> None:
    client = TestClient(_create_test_app(), raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 500
    assert r.json()["detail"] == "Internal server error"
    assert REQUEST_ID_HEADER in r.headers
