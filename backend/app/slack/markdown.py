"""Slack 向けメッセージ整形（Markdown ブロック優先）。"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.logging_config import log_event

logger = logging.getLogger(__name__)

# Slack markdown ブロックの累積上限
SLACK_MARKDOWN_BLOCK_MAX = 12_000
# blocks 併用時の text フォールバック（通知プレビュー用）
SLACK_FALLBACK_TEXT_MAX = 3_000


def markdown_to_slack(text: str) -> str:
    """従来 mrkdwn 用の簡易変換（フォールバック経路のみ）。"""
    converted = text
    converted = re.sub(r"\*\*(.+?)\*\*", r"*\1*", converted)
    converted = re.sub(r"__(.+?)__", r"*\1*", converted)
    converted = re.sub(r"`([^`]+)`", r"`\1`", converted)
    converted = re.sub(r"\[(.+?)\]\((.+?)\)", r"<\2|\1>", converted)
    return converted


def slack_fallback_text(text: str, *, max_len: int = SLACK_FALLBACK_TEXT_MAX) -> str:
    """ブロック併用時の通知・プレビュー用プレーンテキスト。"""
    stripped = text.strip()
    if len(stripped) <= max_len:
        return stripped
    return stripped[: max_len - 3] + "..."


def build_markdown_block_message(text: str) -> dict[str, Any]:
    """LLM 出力を Slack markdown ブロック用ペイロードにする。"""
    body = text.strip()
    if len(body) > SLACK_MARKDOWN_BLOCK_MAX:
        body = body[: SLACK_MARKDOWN_BLOCK_MAX - 3] + "..."
    return {
        "blocks": [{"type": "markdown", "text": body}],
        "text": slack_fallback_text(body),
    }


async def post_slack_markdown_reply(
    client: Any,
    *,
    channel: str,
    thread_ts: str | None,
    reply: str,
) -> None:
    """Markdown ブロックで返信し、失敗時は mrkdwn テキストにフォールバックする。"""
    payload = build_markdown_block_message(reply)
    try:
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            blocks=payload["blocks"],
            text=payload["text"],
        )
        return
    except Exception as exc:
        log_event(
            logger,
            event="slack_markdown_block_failed",
            error=str(exc),
        )

    try:
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=markdown_to_slack(reply),
        )
    except Exception as exc:
        log_event(logger, event="slack_reply_failed", error=str(exc))
        raise
