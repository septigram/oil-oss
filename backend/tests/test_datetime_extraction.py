"""DatetimeExtractionService 単体テスト。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.services.datetime_extraction import DatetimeExtractionService

TZ = timezone(timedelta(hours=9))
REF = date(2020, 5, 15)
NOW = datetime(2020, 5, 31, 23, 59, 59, tzinfo=TZ)


def test_rule_extract_occurred_labeled() -> None:
    svc = DatetimeExtractionService()
    text = "発生日時: 2020-04-01 10:30 に障害が発生しました。"
    items = svc.extract_from_text(text, reference_date=REF, now=NOW)
    occurred = DatetimeExtractionService.pick_best(items, "occurred")
    assert occurred is not None
    assert occurred.value == datetime(2020, 4, 1, 10, 30, tzinfo=TZ)
    assert occurred.confidence == "high"


def test_rule_extract_detected_labeled() -> None:
    svc = DatetimeExtractionService()
    text = "検知日時 2020/04/01 11:00 にアラートが上がった。"
    items = svc.extract_from_text(text, reference_date=REF, now=NOW)
    detected = DatetimeExtractionService.pick_best(items, "detected")
    assert detected is not None
    assert detected.value.hour == 11


def test_ambiguous_yesterday_low_confidence() -> None:
    svc = DatetimeExtractionService()
    text = "昨日の午前中に発生した障害です。"
    items = svc.extract_from_text(text, reference_date=REF, now=NOW)
    occurred = DatetimeExtractionService.pick_best(items, "occurred")
    assert occurred is not None
    assert occurred.confidence == "low"


def test_rejects_future_datetime() -> None:
    svc = DatetimeExtractionService()
    text = "発生日時: 2099-01-01 10:00"
    items = svc.extract_from_text(text, reference_date=REF, now=NOW)
    assert items == []
