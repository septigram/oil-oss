"""Slack Bot（Socket Mode）。"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from app.agent.service import AgentService, is_slack_mutation_request
from app.config import get_settings
from app.logging_config import log_event
from app.metrics import record_metric
from app.slack.markdown import post_slack_markdown_reply

logger = logging.getLogger(__name__)

_handler: Any | None = None
_bot_task: asyncio.Task[Any] | None = None
_handler_lock = asyncio.Lock()

MUTATION_REPLY = "Slack からは参照のみ可能です。インシデントの登録・更新は Web UI をご利用ください。"


def _strip_mention(text: str) -> str:
    return re.sub(r"<@[^>]+>\s*", "", text or "").strip()


def start_slack_bot_if_configured() -> asyncio.Task[Any] | None:
    """Slack Bot をバックグラウンドタスクで起動する。"""
    global _bot_task
    settings = get_settings()
    if not settings.slack.bot_token or not settings.slack.app_token:
        log_event(logger, event="slack_bot_skipped", reason="tokens_not_configured")
        return None

    async def _run() -> None:
        global _handler
        try:
            from slack_bolt.async_app import AsyncApp
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
        except ImportError as exc:
            log_event(logger, event="slack_bot_start_failed", error=str(exc))
            return

        app = AsyncApp(token=settings.slack.bot_token)
        agent = AgentService(settings)

        @app.event("app_mention")
        async def handle_mention(event: dict[str, Any], say: Any, client: Any) -> None:
            start = time.perf_counter()
            text = _strip_mention(str(event.get("text", "")))
            thread_ts = event.get("thread_ts") or event.get("ts")
            channel = event.get("channel")
            try:
                await client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text="処理中...",
                )
            except Exception:
                pass

            if is_slack_mutation_request(text):
                reply = MUTATION_REPLY
            else:
                try:
                    reply = await agent.run_viewer_chat(text)
                except Exception as exc:
                    log_event(logger, event="slack_bot_error", error=str(exc))
                    reply = "エラーが発生しました。しばらくしてから再度お試しください。"

            await post_slack_markdown_reply(
                client,
                channel=channel,
                thread_ts=thread_ts,
                reply=reply,
            )
            duration = round(time.perf_counter() - start, 3)
            record_metric(
                {
                    "event": "slack_bot_request_duration_seconds",
                    "duration_seconds": duration,
                }
            )
            log_event(logger, event="slack_bot_request", duration_seconds=duration)

        handler = AsyncSocketModeHandler(app, settings.slack.app_token)
        async with _handler_lock:
            _handler = handler
        try:
            log_event(logger, event="slack_bot_started")
            await handler.start_async()
        except Exception as exc:
            log_event(logger, event="slack_bot_start_failed", error=str(exc))
        finally:
            async with _handler_lock:
                if _handler is handler:
                    _handler = None

    _bot_task = asyncio.create_task(_run())
    return _bot_task


async def stop_slack_bot(task: asyncio.Task[Any] | None) -> None:
    global _handler, _bot_task
    if _handler is not None:
        try:
            await _handler.close_async()
            log_event(logger, event="slack_bot_stopped")
        except Exception as exc:
            log_event(logger, event="slack_bot_stop_failed", error=str(exc))
        finally:
            async with _handler_lock:
                _handler = None
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _bot_task = None
