"""Slack メッセージ整形の単体テスト。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.slack.markdown import (
    build_markdown_block_message,
    markdown_to_slack,
    post_slack_markdown_reply,
    slack_fallback_text,
)


def test_bold_conversion_fallback() -> None:
    assert markdown_to_slack("**bold**") == "*bold*"


def test_link_conversion_fallback() -> None:
    assert markdown_to_slack("[label](https://example.com)") == "<https://example.com|label>"


def test_build_markdown_block_message() -> None:
    table = "| a | b |\n| --- | --- |\n| 1 | 2 |"
    payload = build_markdown_block_message(f"**見出し**\n{table}")
    assert payload["blocks"] == [{"type": "markdown", "text": f"**見出し**\n{table}"}]
    assert "**見出し**" in payload["text"]


def test_slack_fallback_text_truncates() -> None:
    long = "x" * 4000
    assert len(slack_fallback_text(long)) == 3000


@pytest.mark.asyncio
async def test_post_slack_markdown_reply_uses_blocks() -> None:
    client = AsyncMock()
    await post_slack_markdown_reply(
        client,
        channel="C1",
        thread_ts="123.456",
        reply="| h |\n| --- |\n| v |",
    )
    client.chat_postMessage.assert_awaited_once()
    kwargs = client.chat_postMessage.await_args.kwargs
    assert kwargs["blocks"][0]["type"] == "markdown"
    assert "| h |" in kwargs["blocks"][0]["text"]


@pytest.mark.asyncio
async def test_post_slack_markdown_reply_fallback_on_block_error() -> None:
    client = AsyncMock()
    client.chat_postMessage.side_effect = [
        RuntimeError("invalid_blocks"),
        MagicMock(),
    ]
    await post_slack_markdown_reply(
        client,
        channel="C1",
        thread_ts=None,
        reply="**bold** text",
    )
    assert client.chat_postMessage.await_count == 2
    fallback_kwargs = client.chat_postMessage.await_args_list[1].kwargs
    assert fallback_kwargs["text"] == "*bold* text"
    assert "blocks" not in fallback_kwargs
