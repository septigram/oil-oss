"""log_buffer の単体テスト。"""

import logging
from unittest.mock import patch

from app.log_buffer import append_log_entry, get_logs_after, reset_for_tests
from app.logging_config import log_event


def setup_function() -> None:
    reset_for_tests()


def test_append_llm_event_increments_seq() -> None:
    append_log_entry({"event": "chat_request", "ts": "2026-06-25T10:00:00+09:00"})
    append_log_entry({"event": "ai_sql", "ts": "2026-06-25T10:00:01+09:00"})
    items, cursor = get_logs_after(0)
    assert len(items) == 2
    assert items[0]["seq"] == 1
    assert items[1]["seq"] == 2
    assert cursor == 2


def test_non_llm_event_is_ignored() -> None:
    append_log_entry({"event": "api_timing", "ts": "2026-06-25T10:00:00+09:00"})
    items, cursor = get_logs_after(0)
    assert items == []
    assert cursor == 0


def test_get_logs_after_filters() -> None:
    for i in range(3):
        append_log_entry({"event": "chat_timing", "ts": f"t{i}"})
    items, cursor = get_logs_after(1)
    assert len(items) == 2
    assert items[0]["seq"] == 2
    assert cursor == 3


def test_maxlen_truncates_old_entries() -> None:
    for i in range(1001):
        append_log_entry({"event": "ai_rag", "ts": f"t{i}", "i": i})
    items, cursor = get_logs_after(0)
    assert len(items) == 1000
    assert items[0]["i"] == 1
    assert items[-1]["i"] == 1000
    assert cursor == 1001


def test_log_event_appends_to_buffer() -> None:
    logger = logging.getLogger("app.test.log_buffer")
    with patch.object(logger, "info"):
        log_event(logger, event="chat_request", user_message="hello")
    items, _ = get_logs_after(0)
    assert len(items) == 1
    assert items[0]["event"] == "chat_request"
    assert items[0]["user_message"] == "hello"
