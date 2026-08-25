"""チャットエラー整形の単体テスト。"""

from __future__ import annotations

import logging
from unittest.mock import patch

from app.agent.chat_error import format_chat_error_for_client, log_chat_stream_error
from app.log_buffer import get_logs_after, reset_for_tests


def test_format_ollama_model_load_error() -> None:
    exc = RuntimeError(
        "llama-server process has terminated: exit status 1: error loading model: "
        "llamamodelloader: failed to load model from H:\\ollama\\models\\blobs\\sha256-abc"
    )
    msg = format_chat_error_for_client(exc, llm_provider="ollama", model="qwen3:8b")
    assert "Ollama でモデル「qwen3:8b」を読み込めませんでした" in msg
    assert "ollama pull qwen3:8b" in msg
    assert "詳細:" in msg


def test_format_generic_error_truncates_long_message() -> None:
    exc = RuntimeError("x" * 1000)
    msg = format_chat_error_for_client(exc, llm_provider="openai", model="gpt-4o-mini")
    assert msg.endswith("…")
    assert len(msg) < 1000


def test_log_chat_stream_error_writes_chat_error_event() -> None:
    reset_for_tests()
    logger = logging.getLogger("app.test.chat_error")
    exc = ValueError("test failure")
    with patch.object(logger, "info"), patch.object(logger, "error"):
        log_chat_stream_error(
            logger,
            exc,
            llm_provider="ollama",
            model="qwen3:8b",
            context_incident_id="INC-2026-00001",
            turn=2,
            duration_ms=123.4,
        )
    items, _ = get_logs_after(0)
    assert len(items) == 1
    entry = items[0]
    assert entry["event"] == "chat_error"
    assert entry["model"] == "qwen3:8b"
    assert entry["error_type"] == "ValueError"
    assert entry["error_message"] == "test failure"
    assert "traceback" in entry
