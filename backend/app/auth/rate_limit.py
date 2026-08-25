"""ログイン失敗レートリミット（インメモリ）。"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

_WINDOW_SEC = 60
_MAX_ATTEMPTS = 5

_lock = Lock()
_attempts: dict[tuple[str, str], list[float]] = defaultdict(list)


def is_rate_limited(client_ip: str, login_name: str) -> bool:
    key = (client_ip, login_name.lower())
    now = time.monotonic()
    with _lock:
        window = _attempts[key]
        _attempts[key] = [t for t in window if now - t < _WINDOW_SEC]
        return len(_attempts[key]) >= _MAX_ATTEMPTS


def record_failed_attempt(client_ip: str, login_name: str) -> None:
    key = (client_ip, login_name.lower())
    now = time.monotonic()
    with _lock:
        window = _attempts[key]
        window.append(now)
        _attempts[key] = [t for t in window if now - t < _WINDOW_SEC]
