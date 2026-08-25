"""スキーマ互換（マイグレーション前 DB 向け）。"""

from __future__ import annotations

from functools import lru_cache

from app.repository.tsurugi_conn import TsurugiConnection


@lru_cache
def has_column(table: str, column: str) -> bool:
    db = TsurugiConnection()
    try:
        db.fetchone(f"SELECT {column} FROM {table}")
        return True
    except Exception:
        return False
