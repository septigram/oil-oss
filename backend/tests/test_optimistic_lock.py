"""楽観ロックヘルパの単体テスト。"""

from __future__ import annotations

import pytest

from app.repository.optimistic import OptimisticLockError, ensure_updated


def test_ensure_updated_success() -> None:
    ensure_updated(1, lambda: None)


def test_ensure_updated_conflict() -> None:
    with pytest.raises(OptimisticLockError) as exc_info:
        ensure_updated(0, lambda: {"incident_id": "INC-1", "row_version": 3})
    assert exc_info.value.current["row_version"] == 3


def test_ensure_updated_not_found() -> None:
    with pytest.raises(OptimisticLockError) as exc_info:
        ensure_updated(0, lambda: None)
    assert exc_info.value.current["detail"] == "not_found"
