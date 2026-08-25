"""ProcedureRepository 検索の単体テスト。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from app.repository.procedure import ProcedureRepository, ProcedureSearchParams

TZ = ZoneInfo("Asia/Tokyo")


def _sample_row() -> tuple:
    return (
        "PRC-00001",
        "title",
        "problem",
        "ITYP-001",
        "HIGH",
        "steps",
        None,
        None,
        None,
        None,
        "tag",
        1,
        1,
        1,
        "EMP-00001",
        datetime(2020, 5, 1, tzinfo=TZ),
        "EMP-00001",
        datetime(2020, 5, 2, tzinfo=TZ),
        1,
    )


def test_search_uses_limit_literal() -> None:
    db = MagicMock()
    db.fetchone.return_value = (1,)
    db.fetchall.return_value = [_sample_row()]
    repo = ProcedureRepository(db=db)

    repo.search(ProcedureSearchParams(page=2, page_size=10))

    list_sql = db.fetchall.call_args[0][0]
    assert "LIMIT 20" in list_sql
    assert "OFFSET" not in list_sql.upper()


def test_search_procedure_ids_filter() -> None:
    db = MagicMock()
    db.fetchone.return_value = (1,)
    db.fetchall.return_value = [_sample_row()]
    repo = ProcedureRepository(db=db)

    repo.search(ProcedureSearchParams(procedure_ids=["PRC-00001"], skip_pagination=True))

    count_sql, values = db.fetchone.call_args[0]
    assert "procedure_id IN (?)" in count_sql
    assert "PRC-00001" in values
