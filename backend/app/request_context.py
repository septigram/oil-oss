"""リクエストスコープの相関 ID。"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def generate_request_id() -> str:
    return str(uuid.uuid4())


def is_valid_request_id(value: str) -> bool:
    return bool(_UUID_RE.match(value.strip()))


def set_request_id(request_id: str) -> None:
    _REQUEST_ID.set(request_id)


def get_request_id() -> str | None:
    return _REQUEST_ID.get()


def clear_request_id() -> None:
    _REQUEST_ID.set(None)
