"""チャットエラーの整形と構造化ログ。"""

from __future__ import annotations

import logging
import traceback
from typing import Any

from app.logging_config import log_event

_MAX_CLIENT_DETAIL = 500
_MAX_LOG_MESSAGE = 4000
_MAX_TRACEBACK = 8000


def format_chat_error_for_client(
    exc: BaseException,
    *,
    llm_provider: str | None,
    model: str | None,
) -> str:
    """ユーザー向けチャットエラーメッセージ。"""
    raw = str(exc).strip() or "チャット処理中にエラーが発生しました。"
    lowered = raw.lower()

    if llm_provider == "ollama" and (
        "failed to load model" in lowered
        or "llamamodelloader" in lowered
        or "exit status" in lowered
        or "status code: 500" in lowered
    ):
        model_hint = model or "選択したモデル"
        detail = raw if len(raw) <= _MAX_CLIENT_DETAIL else f"{raw[:_MAX_CLIENT_DETAIL]}…"
        return (
            f"Ollama でモデル「{model_hint}」を読み込めませんでした。"
            "モデルファイルの破損・未ダウンロード・メモリ不足の可能性があります。"
            f"`ollama pull {model_hint}` で再取得するか、別のモデルを選択してください。"
            f"\n\n詳細: {detail}"
        )

    if llm_provider == "openai" and ("api" in lowered or "openai" in lowered):
        detail = raw if len(raw) <= _MAX_CLIENT_DETAIL else f"{raw[:_MAX_CLIENT_DETAIL]}…"
        return f"OpenAI API エラー: {detail}"

    if len(raw) > 800:
        return f"{raw[:800]}…"
    return raw


def log_chat_stream_error(
    logger: logging.Logger,
    exc: BaseException,
    *,
    llm_provider: str | None,
    model: str | None,
    context_incident_id: str | None,
    turn: int,
    duration_ms: float,
) -> None:
    """チャット失敗を構造化ログ・LLM ログバッファ・stderr に記録する。"""
    tb = traceback.format_exc()
    if len(tb) > _MAX_TRACEBACK:
        tb = tb[-_MAX_TRACEBACK:]

    error_message = str(exc)
    if len(error_message) > _MAX_LOG_MESSAGE:
        error_message = f"{error_message[:_MAX_LOG_MESSAGE]}…"

    fields: dict[str, Any] = {
        "llm_provider": llm_provider,
        "model": model,
        "context_incident_id": context_incident_id,
        "turn": turn,
        "duration_ms": round(duration_ms, 2),
        "error_type": type(exc).__name__,
        "error_message": error_message,
        "traceback": tb,
    }

    log_event(logger, event="chat_error", **fields)

    logger.error(
        "chat stream failed (%s): %s",
        type(exc).__name__,
        error_message,
        extra={"extra_data": {"event": "chat_stream_failed", **fields}},
        exc_info=True,
    )
