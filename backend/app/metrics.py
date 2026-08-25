"""性能計測メトリクスのリングバッファ。"""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any

_MAX_ENTRIES = 100
_buffer: deque[dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)
_lock = Lock()


def record_metric(entry: dict[str, Any]) -> None:
    with _lock:
        _buffer.append(entry)


def get_recent_metrics() -> list[dict[str, Any]]:
    with _lock:
        return list(_buffer)
