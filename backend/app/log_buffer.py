"""LLM 関連構造化ログのリングバッファ。"""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any

_MAX_ENTRIES = 1000
_LLM_EVENTS = frozenset({
    "chat_request",
    "chat_timing",
    "chat_error",
    "ai_sql",
    "ai_rag",
    "mcp_tool",
    "rag_sync_start",
    "rag_sync_complete",
})

_buffer: deque[dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)
_lock = Lock()
_seq = 0


def is_llm_event(event: str) -> bool:
    return event in _LLM_EVENTS


def append_log_entry(entry: dict[str, Any]) -> None:
    """LLM 関連イベントをバッファに追記する。"""
    global _seq
    event = entry.get("event", "")
    if not is_llm_event(event):
        return
    with _lock:
        _seq += 1
        _buffer.append({"seq": _seq, **entry})


def get_logs_after(after: int = 0) -> tuple[list[dict[str, Any]], int]:
    """指定 seq より大きいエントリと next_cursor を返す。"""
    with _lock:
        items = [e for e in _buffer if e["seq"] > after]
        next_cursor = _seq
    return items, next_cursor


def reset_for_tests() -> None:
    """テスト用にバッファをクリアする。"""
    global _seq
    with _lock:
        _buffer.clear()
        _seq = 0
