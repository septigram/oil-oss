"""ReferenceDateService の単体テスト。"""

from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.config import AppConfig, ReferenceDateConfig
from app.services.reference_date import ReferenceDateService

from tests.conftest import make_app_config


def test_reference_date_fixed(fixed_settings: AppConfig) -> None:
    svc = ReferenceDateService(fixed_settings)
    assert svc.get_reference_date() == date(2020, 5, 31)


def test_current_month(fixed_settings: AppConfig) -> None:
    svc = ReferenceDateService(fixed_settings)
    r = svc.current_month()
    assert r.start.date() == date(2020, 5, 1)
    assert r.end.date() == date(2020, 5, 31)


def test_previous_month(fixed_settings: AppConfig) -> None:
    svc = ReferenceDateService(fixed_settings)
    r = svc.previous_month()
    assert r.start.date() == date(2020, 4, 1)
    assert r.end.date() == date(2020, 4, 30)


def test_past_one_month(fixed_settings: AppConfig) -> None:
    svc = ReferenceDateService(fixed_settings)
    r = svc.past_one_month()
    assert r.start.date() == date(2020, 5, 1)
    assert r.end.date() == date(2020, 5, 31)


def test_last_week(fixed_settings: AppConfig) -> None:
    svc = ReferenceDateService(fixed_settings)
    r = svc.last_week()
    assert r.start.date() == date(2020, 5, 18)
    assert r.end.date() == date(2020, 5, 24)


def test_two_weeks_ago(fixed_settings: AppConfig) -> None:
    svc = ReferenceDateService(fixed_settings)
    r = svc.two_weeks_ago()
    assert r.start.date() == date(2020, 5, 11)
    assert r.end.date() == date(2020, 5, 17)


def test_past_two_months(fixed_settings: AppConfig) -> None:
    svc = ReferenceDateService(fixed_settings)
    r = svc.past_two_months()
    assert r.start.date() == date(2020, 4, 1)
    assert r.end.date() == date(2020, 5, 31)


def test_period_range_past_two_months(fixed_settings: AppConfig) -> None:
    svc = ReferenceDateService(fixed_settings)
    r = svc.period_range("past_two_months")
    assert r.start.date() == date(2020, 4, 1)
    assert r.end.date() == date(2020, 5, 31)


def test_reference_date_system_mode(fixed_settings: AppConfig) -> None:
    system_settings = make_app_config(reference_date_mode="system")
    svc = ReferenceDateService(system_settings)
    tz = ZoneInfo("Asia/Tokyo")
    fake_now = datetime(2026, 6, 24, 15, 30, 0, tzinfo=tz)
    with patch("app.services.reference_date.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        assert svc.get_reference_date() == date(2026, 6, 24)


def test_get_current_datetime_snapshot_fixed(fixed_settings: AppConfig) -> None:
    svc = ReferenceDateService(fixed_settings)
    tz = ZoneInfo("Asia/Tokyo")
    fake_now = datetime(2026, 7, 4, 9, 34, 4, tzinfo=tz)
    with patch("app.services.reference_date.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        snap = svc.get_current_datetime_snapshot()
    assert snap["now"] == fake_now.isoformat()
    assert snap["timezone"] == "Asia/Tokyo"
    assert snap["reference_date"] == "2020-05-31"
    assert snap["reference_date_mode"] == "fixed"


def test_get_current_datetime_snapshot_system() -> None:
    system_settings = make_app_config(reference_date_mode="system")
    svc = ReferenceDateService(system_settings)
    tz = ZoneInfo("Asia/Tokyo")
    fake_now = datetime(2026, 7, 4, 9, 34, 4, tzinfo=tz)
    with patch("app.services.reference_date.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        snap = svc.get_current_datetime_snapshot()
    assert snap["reference_date"] == "2026-07-04"
    assert snap["reference_date_mode"] == "system"
