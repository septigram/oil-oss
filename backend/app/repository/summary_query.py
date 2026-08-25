"""集計 SQL 実行リポジトリ。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.repository.tsurugi_conn import TsurugiConnection


class SummaryQueryRepository:
    def __init__(self, db: TsurugiConnection | None = None) -> None:
        self._db = db or TsurugiConnection()

    def execute_sql_file(
        self,
        sql_path: Path,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        sql = sql_path.read_text(encoding="utf-8")
        # コメント行を除去
        lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
        query = "\n".join(lines).strip()
        query = query.replace(":period_start", "?").replace(":period_end", "?")
        row = self._db.fetchone(query, (period_start, period_end))
        if not row:
            return 0
        return int(row[0])
