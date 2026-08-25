"""context_usage ヘルパーの単体テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.agent.context_usage import (
    ContextUsageTracker,
    build_context_usage_event,
    extract_token_usage,
)


def test_extract_token_usage_from_usage_metadata_dict() -> None:
    msg = MagicMock()
    msg.usage_metadata = {"input_tokens": 120, "output_tokens": 34}
    msg.response_metadata = {}
    assert extract_token_usage(msg) == (120, 34)


def test_extract_token_usage_from_ollama_response_metadata() -> None:
    msg = MagicMock()
    msg.usage_metadata = None
    msg.response_metadata = {
        "prompt_eval_count": 512,
        "eval_count": 64,
    }
    assert extract_token_usage(msg) == (512, 64)


def test_extract_token_usage_from_openai_token_usage() -> None:
    msg = MagicMock()
    msg.usage_metadata = None
    msg.response_metadata = {
        "token_usage": {"prompt_tokens": 900, "completion_tokens": 45},
    }
    assert extract_token_usage(msg) == (900, 45)


def test_context_usage_tracker_records_peak() -> None:
    tracker = ContextUsageTracker()
    tracker.record(100, 10)
    tracker.record(250, 20)
    tracker.record(180, 15)
    assert tracker.llm_calls == 3
    assert tracker.peak_prompt_tokens == 250
    assert tracker.last_prompt_tokens == 180
    assert tracker.total_output_tokens == 45


def test_build_context_usage_event_computes_remaining() -> None:
    tracker = ContextUsageTracker()
    tracker.record(7000, 120)
    event = build_context_usage_event(tracker, 8192)
    assert event["type"] == "usage"
    assert event["prompt_tokens_peak"] == 7000
    assert event["remaining_estimate"] == 1192
    assert event["usage_ratio"] == round(7000 / 8192, 4)
    assert event["llm_calls"] == 1


def test_build_context_usage_event_without_context_limit() -> None:
    tracker = ContextUsageTracker()
    tracker.record(500, 20)
    event = build_context_usage_event(tracker, None)
    assert event["context_limit"] is None
    assert event["remaining_estimate"] is None
    assert event["usage_ratio"] is None
