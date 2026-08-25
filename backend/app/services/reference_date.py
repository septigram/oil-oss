"""基準日・期間算出サービス。"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import AppConfig, get_settings


@dataclass(frozen=True)
class DateRange:
    start: datetime
    end: datetime


class ReferenceDateService:
    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or get_settings()
        self._tz = ZoneInfo(self._settings.timezone)

    def get_reference_date(self) -> date:
        mode = self._settings.reference_date.mode
        if mode == "system":
            return datetime.now(self._tz).date()
        return date.fromisoformat(self._settings.reference_date.fixed_date)

    def get_current_datetime_snapshot(self) -> dict[str, str]:
        now = datetime.now(self._tz)
        return {
            "now": now.isoformat(),
            "timezone": self._settings.timezone,
            "reference_date": self.get_reference_date().isoformat(),
            "reference_date_mode": self._settings.reference_date.mode,
        }

    def day_start(self, d: date) -> datetime:
        return datetime.combine(d, time.min, tzinfo=self._tz)

    def day_end(self, d: date) -> datetime:
        return datetime.combine(d, time(23, 59, 59, 999000), tzinfo=self._tz)

    def current_month(self) -> DateRange:
        ref = self.get_reference_date()
        start = self.day_start(ref.replace(day=1))
        end = self.day_end(ref)
        return DateRange(start, end)

    def previous_month(self) -> DateRange:
        ref = self.get_reference_date()
        first_this = ref.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        start = self.day_start(last_prev.replace(day=1))
        end = self.day_end(last_prev)
        return DateRange(start, end)

    def past_one_month(self) -> DateRange:
        ref = self.get_reference_date()
        one_month_ago = self._date_months_ago(ref, 1)
        start = self.day_start(one_month_ago + timedelta(days=1))
        end = self.day_end(ref)
        return DateRange(start, end)

    def past_two_months(self) -> DateRange:
        ref = self.get_reference_date()
        two_months_ago = self._date_months_ago(ref, 2)
        start = self.day_start(two_months_ago + timedelta(days=1))
        end = self.day_end(ref)
        return DateRange(start, end)

    def _date_months_ago(self, ref: date, months: int) -> date:
        month = ref.month - months
        year = ref.year
        while month <= 0:
            month += 12
            year -= 1
        max_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(ref.day, max_day))

    def week_containing(self, d: date) -> DateRange:
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        return DateRange(self.day_start(monday), self.day_end(sunday))

    def last_week(self) -> DateRange:
        ref = self.get_reference_date()
        this_monday = ref - timedelta(days=ref.weekday())
        last_monday = this_monday - timedelta(days=7)
        last_sunday = last_monday + timedelta(days=6)
        return DateRange(self.day_start(last_monday), self.day_end(last_sunday))

    def two_weeks_ago(self) -> DateRange:
        ref = self.get_reference_date()
        this_monday = ref - timedelta(days=ref.weekday())
        monday = this_monday - timedelta(days=14)
        sunday = monday + timedelta(days=6)
        return DateRange(self.day_start(monday), self.day_end(sunday))

    def period_range(self, period: str) -> DateRange:
        if period == "last_week":
            return self.last_week()
        if period == "two_weeks_ago":
            return self.two_weeks_ago()
        if period == "past_one_month":
            return self.past_one_month()
        if period == "past_two_months":
            return self.past_two_months()
        if period == "current_month":
            return self.current_month()
        if period == "previous_month":
            return self.previous_month()
        raise ValueError(f"unknown period: {period}")
