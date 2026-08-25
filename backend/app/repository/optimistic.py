"""楽観ロックヘルパ。"""

from __future__ import annotations

from typing import Any, Callable


class OptimisticLockError(Exception):
    def __init__(self, current: dict[str, Any]) -> None:
        self.current = current
        super().__init__("conflict")


def ensure_updated(updated_rows: int, fetch_current: Callable[[], dict[str, Any] | None]) -> None:
    if updated_rows > 0:
        return
    current = fetch_current()
    if current is None:
        raise OptimisticLockError({"detail": "not_found"})
    raise OptimisticLockError(current)
