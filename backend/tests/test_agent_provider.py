"""LLM プロバイダ切替の単体テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agent.service import (
    AgentService,
    _extract_message_text,
    _is_internal_json_blob,
    _is_tool_only_message,
    _pick_user_facing_response,
    _streamable_chunk_text,
)
from app.config import AppConfig
from tests.conftest import make_app_config


def _settings(*, llm_provider: str = "openai", embedding_provider: str = "openai") -> AppConfig:
    return make_app_config(
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
    )


def test_create_llm_uses_ollama_when_configured() -> None:
    settings = _settings(llm_provider="ollama")
    service = AgentService(settings)
    with patch("app.agent.service.ChatOllama") as chat_ollama:
        chat_ollama.return_value = MagicMock()
        service._create_llm("ollama", "custom-model")
        chat_ollama.assert_called_once_with(
            model="custom-model",
            base_url="http://localhost:11434",
            streaming=True,
        )


def test_create_llm_uses_openai_when_configured() -> None:
    settings = _settings(llm_provider="openai")
    service = AgentService(settings)
    with (
        patch("app.agent.service.get_openai_api_key", return_value="test-key"),
        patch("app.agent.service.ChatOpenAI") as chat_openai,
    ):
        chat_openai.return_value = MagicMock()
        service._create_llm("openai", "gpt-4o")
        chat_openai.assert_called_once_with(
            model="gpt-4o",
            api_key="test-key",
            streaming=True,
            model_kwargs={"stream_options": {"include_usage": True}},
        )


def test_create_llm_openai_requires_api_key() -> None:
    settings = _settings(llm_provider="openai")
    service = AgentService(settings)
    with patch("app.agent.service.get_openai_api_key", return_value=None):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            service._create_llm()


def test_streamable_chunk_text_excludes_thinking() -> None:
    assert _streamable_chunk_text("hello") == "hello"
    assert _streamable_chunk_text([{"type": "text", "text": "a"}, "b"]) == "ab"
    assert _streamable_chunk_text([{"type": "thinking", "thinking": "考え中"}]) == ""
    assert (
        _streamable_chunk_text(
            [
                {"type": "thinking", "thinking": '{"occurred_at": "..."}'},
                {"type": "text", "text": "回答です"},
            ]
        )
        == "回答です"
    )
    assert _streamable_chunk_text(None) == ""


def test_extract_message_text_ignores_reasoning_kwargs() -> None:
    msg = MagicMock()
    msg.content = ""
    msg.additional_kwargs = {"reasoning": "内部推論"}
    assert _extract_message_text(msg) == ""


def test_is_tool_only_message() -> None:
    msg = MagicMock()
    msg.content = ""
    msg.tool_calls = [{"name": "search_incidents"}]
    assert _is_tool_only_message(msg) is True
    msg.content = "回答"
    assert _is_tool_only_message(msg) is False
    msg.content = [{"type": "thinking", "thinking": "JSON only"}]
    assert _is_tool_only_message(msg) is True


def test_is_internal_json_blob() -> None:
    assert _is_internal_json_blob('{"occurred_at": "2026-06-25T00:00:00+09:00"}') is True
    assert _is_internal_json_blob("インシデントの説明です。") is False
    assert _is_internal_json_blob("prefix {\"a\": 1}") is False


def test_pick_user_facing_response_skips_intermediate_json() -> None:
    json_blob = (
        '{\n "occurred_at": "2026-06-25T00:00:00+09:00",\n "confidence": "high"\n}'
    )
    summary = "インシデントのトリアージを開始しました。"
    assert _pick_user_facing_response([json_blob, json_blob, summary], set()) == summary
    assert _pick_user_facing_response([json_blob], set()) == ""


def test_system_prompt_includes_status_mapping() -> None:
    settings = _settings()
    service = AgentService(settings)
    prompt = service._system_prompt()
    assert "| OPEN | 未着手 |" in prompt
    assert "| CRITICAL | CRITICAL |" in prompt
    assert "search_incidents" in prompt
