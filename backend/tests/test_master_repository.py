"""MasterRepository DECIMAL リテラル helper の単体テスト。"""

from __future__ import annotations

import pytest

from app.repository.master import _decimal_sql_literal


def test_decimal_sql_literal_default() -> None:
    assert _decimal_sql_literal(1.0) == "1.0000"


def test_decimal_sql_literal_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        _decimal_sql_literal(-0.1)
