"""aggregate_incidents ツールの単体テスト。"""

from __future__ import annotations

from datetime import date, datetime, time
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from app.agent.aggregate_tool import resolve_aggregate_date_range, run_aggregate_incidents
from app.config import AppConfig
from app.services.reference_date import ReferenceDateService

from tests.conftest import fixed_settings

TZ = ZoneInfo("Asia/Tokyo")


def _parse_date_bound(value: str, *, end_of_day: bool = False) -> datetime:
    d = date.fromisoformat(value)
    if end_of_day:
        return datetime.combine(d, time(23, 59, 59, 999000), tzinfo=TZ)
    return datetime.combine(d, time.min, tzinfo=TZ)


def test_resolve_period_past_two_months(fixed_settings: AppConfig) -> None:
    ref = ReferenceDateService(fixed_settings)
    resolved = resolve_aggregate_date_range("past_two_months", None, None, ref, _parse_date_bound)
    assert not isinstance(resolved, dict)
    start, end, period = resolved
    assert period == "past_two_months"
    assert start.date().isoformat() == "2020-04-01"
    assert end.date().isoformat() == "2020-05-31"


def test_resolve_requires_period_or_dates(fixed_settings: AppConfig) -> None:
    ref = ReferenceDateService(fixed_settings)
    result = resolve_aggregate_date_range(None, None, None, ref, _parse_date_bound)
    assert result == {"error": "period or occurred_from/to is required"}


def test_run_aggregate_incidents_wraps_repository_result(fixed_settings: AppConfig) -> None:
    ref = ReferenceDateService(fixed_settings)
    incidents = MagicMock()
    incidents.aggregate.return_value = {
        "group_by": "location_name",
        "total_incidents": 3,
        "groups": [{"key": "東京DC", "label": "東京DC", "count": 3}],
    }

    from app.domain.models import normalize_severities, normalize_statuses

    result = run_aggregate_incidents(
        incidents,
        ref,
        _parse_date_bound,
        group_by="location_name",
        period="past_two_months",
        normalize_statuses=normalize_statuses,
        normalize_severities=normalize_severities,
    )
    assert result["period"] == "past_two_months"
    assert result["total_incidents"] == 3
    assert result["filters"]["status"] is None
    incidents.aggregate.assert_called_once()
