"""集計サマリテンプレートの単体・結合テスト。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.config import get_settings
from app.repository.summary_query import SummaryQueryRepository
from app.services.reference_date import ReferenceDateService
from app.services.summary_template import SummaryTemplateService
from tests.conftest import tsurugi_available


def test_summary_query_binds_period_parameters(tmp_path: Path) -> None:
    sql_path = tmp_path / "count.sql"
    sql_path.write_text(
        "SELECT COUNT(*) AS cnt FROM t WHERE occurred_at >= :period_start AND occurred_at <= :period_end",
        encoding="utf-8",
    )
    db = MagicMock()
    db.fetchone.return_value = (7,)
    repo = SummaryQueryRepository(db)
    tz = ZoneInfo("Asia/Tokyo")
    start = datetime(2020, 5, 18, 0, 0, 0, tzinfo=tz)
    end = datetime(2020, 5, 24, 23, 59, 59, 999000, tzinfo=tz)
    count = repo.execute_sql_file(sql_path, start, end)
    assert count == 7
    sql, params = db.fetchone.call_args[0]
    assert "?" in sql
    assert ":period_start" not in sql
    assert params == (start, end)


def test_build_all_summaries_uses_query_counts() -> None:
    ref = ReferenceDateService()
    query_repo = MagicMock()
    query_repo.execute_sql_file.return_value = 42
    service = SummaryTemplateService(ref_date=ref, query_repo=query_repo)
    docs = service.build_all_summaries()
    assert len(docs) == 4
    for doc in docs:
        assert doc.metadata["count"] == 42
        assert "{count}" not in doc.text
        assert "42件" in doc.text


@pytest.mark.integration
def test_summary_counts_match_seed_data() -> None:
    if not tsurugi_available():
        pytest.skip("Tsurugi に接続できません")
    settings = get_settings()
    ref = ReferenceDateService(settings)
    query_repo = SummaryQueryRepository()
    service = SummaryTemplateService(settings)
    docs = service.build_all_summaries()
    assert len(docs) == 4
    by_id = {doc.template_id: doc for doc in docs}
    base_dir = settings.paths.rag_summary_dir
    for tmpl in service._load_templates():
        period = ref.period_range(tmpl["period"])
        expected = query_repo.execute_sql_file(
            base_dir / tmpl["sql_file"], period.start, period.end
        )
        doc = by_id[tmpl["template_id"]]
        assert doc.metadata["count"] == expected
        assert str(expected) in doc.text
