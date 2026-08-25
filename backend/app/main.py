"""FastAPI アプリケーションエントリ。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    admin,
    admin_webhook_keys,
    auth,
    chat,
    health,
    incidents,
    masters,
    notification_channels,
    procedures,
    prometheus,
    rag,
    responses,
    system,
    triage,
    webhooks,
)
from app.config import get_settings
from app.logging_config import log_event, setup_logging
from app.middleware import REQUEST_ID_HEADER, RequestIdMiddleware, TimingMiddleware
from app.observability.tracing import instrument_app, setup_tracing, shutdown_tracing
from app.repository.optimistic import OptimisticLockError
from app.request_context import get_request_id
from app.runtime_flags import init_runtime_flags

logger = logging.getLogger(__name__)

init_runtime_flags()
setup_logging()


def _frontend_dist_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_runtime_flags()
    setup_logging(force=True)
    setup_tracing(app_version=app.version)
    instrument_app(app)
    from app.slack.bot import start_slack_bot_if_configured, stop_slack_bot

    slack_task = start_slack_bot_if_configured()
    yield
    await stop_slack_bot(slack_task)
    shutdown_tracing()


app = FastAPI(title="Ops Incident Ledger", version="0.1.0", lifespan=lifespan)

# Starlette: 後から add したミドルウェアがリクエストで先に実行される
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_settings = get_settings()
_context_path = _settings.context_path
_context_router = APIRouter(prefix=_context_path)

_context_router.include_router(health.router)
_context_router.include_router(prometheus.router)
_context_router.include_router(auth.router)
_context_router.include_router(admin.router)
_context_router.include_router(admin_webhook_keys.router)
_context_router.include_router(system.router)
_context_router.include_router(masters.router)
_context_router.include_router(incidents.router)
_context_router.include_router(procedures.router)
_context_router.include_router(triage.router)
_context_router.include_router(responses.router)
_context_router.include_router(chat.router)
_context_router.include_router(rag.router)
_context_router.include_router(webhooks.router)
_context_router.include_router(notification_channels.router)

app.include_router(_context_router)


@app.exception_handler(OptimisticLockError)
async def optimistic_lock_handler(_request: Request, exc: OptimisticLockError) -> JSONResponse:
    from app.api.conflict import CONFLICT_MESSAGE

    current = {
        k: (v.isoformat() if hasattr(v, "isoformat") else v)
        for k, v in exc.current.items()
    }
    return JSONResponse(
        status_code=409,
        content={
            "detail": "conflict",
            "message": CONFLICT_MESSAGE,
            "current": current,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    log_event(
        logger,
        event="unhandled_exception",
        path=str(request.url.path),
        method=request.method,
        exception_type=type(exc).__name__,
        message=str(exc),
        request_id=request_id,
    )
    logger.exception("Unhandled exception", exc_info=exc)
    response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


_dist_dir = _frontend_dist_dir()
if _dist_dir.is_dir():
    app.mount(_context_path, StaticFiles(directory=_dist_dir, html=True), name="spa")
