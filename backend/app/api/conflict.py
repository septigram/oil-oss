"""409 Conflict レスポンス。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi.responses import JSONResponse

from app.repository.optimistic import OptimisticLockError

CONFLICT_MESSAGE = "他のユーザによって更新されました。最新の内容を読み込んでください。"


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def conflict_json_response(exc: OptimisticLockError) -> JSONResponse:
    current = {k: _serialize_value(v) for k, v in exc.current.items()}
    return JSONResponse(
        status_code=409,
        content={
            "detail": "conflict",
            "message": CONFLICT_MESSAGE,
            "current": current,
        },
    )
