"""API 応答時間計測・request_id ミドルウェア。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.logging_config import log_event
from app.log_noise import should_log_api_timing
from app.metrics import record_metric
from app.request_context import (
    clear_request_id,
    generate_request_id,
    get_request_id,
    is_valid_request_id,
    set_request_id,
)

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-Id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        if incoming and is_valid_request_id(incoming):
            request_id = incoming.strip()
        else:
            request_id = generate_request_id()
        request.state.request_id = request_id
        set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            clear_request_id()


class TimingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._api_prefix = f"{get_settings().context_path}/api"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        if request.url.path.startswith(self._api_prefix):
            entry = {
                "event": "api_timing",
                "path": request.url.path,
                "method": request.method,
                "duration_ms": duration_ms,
                "status_code": response.status_code,
            }
            request_id = get_request_id()
            if request_id:
                entry["request_id"] = request_id
            record_metric(entry)
            if should_log_api_timing(request.url.path):
                log_event(logger, **entry)
            try:
                from app.observability.prometheus_metrics import observe_http_request

                observe_http_request(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_seconds=duration_ms / 1000.0,
                )
            except ImportError:
                pass
        return response
