"""ProcedureRepository の紐づけ解除テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.repository.procedure import ProcedureRepository


def _repo_with_link(
    *,
    incident_id: str = "INC-2020-00001",
    procedure_id: str = "PRC-00001",
    was_successful: bool | None = True,
) -> ProcedureRepository:
    db = MagicMock()
    db.fetchone.return_value = (incident_id, procedure_id, 1 if was_successful else 0)
    repo = ProcedureRepository()
    repo._db = db  # noqa: SLF001
    return repo


def test_unlink_decrements_usage_and_success_count() -> None:
    repo = _repo_with_link(was_successful=True)
    repo.unlink_from_incident("INC-2020-00001", 1)
    sqls = [str(c.args[0]) for c in repo._db.execute.call_args_list]  # noqa: SLF001
    assert any("DELETE FROM oil_incident_procedures" in s for s in sqls)
    assert sum(1 for s in sqls if "usage_count" in s) == 1
    assert sum(1 for s in sqls if "success_count" in s) == 1


def test_unlink_skips_success_decrement_when_not_successful() -> None:
    repo = _repo_with_link(was_successful=False)
    repo.unlink_from_incident("INC-2020-00001", 1)
    sqls = [str(c.args[0]) for c in repo._db.execute.call_args_list]  # noqa: SLF001
    assert any("DELETE FROM oil_incident_procedures" in s for s in sqls)
    assert any("usage_count" in s for s in sqls)
    assert not any("success_count" in s for s in sqls)


def test_unlink_raises_when_link_missing() -> None:
    db = MagicMock()
    db.fetchone.return_value = None
    repo = ProcedureRepository()
    repo._db = db  # noqa: SLF001
    with pytest.raises(ValueError, match="link not found"):
        repo.unlink_from_incident("INC-2020-00001", 99)


def test_unlink_raises_when_incident_mismatch() -> None:
    repo = _repo_with_link(incident_id="INC-2020-00002")
    with pytest.raises(ValueError, match="link not found"):
        repo.unlink_from_incident("INC-2020-00001", 1)
