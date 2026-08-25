"""AI チャット経由のツール実行（RDB / RAG）を識別するコンテキスト。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator

_ai_sql_logging: ContextVar[bool] = ContextVar("ai_sql_logging", default=False)


def is_ai_agent_logging_enabled() -> bool:
    return _ai_sql_logging.get()


def is_ai_sql_logging_enabled() -> bool:
    return is_ai_agent_logging_enabled()


@contextmanager
def ai_agent_logging() -> Generator[None, None, None]:
    token = _ai_sql_logging.set(True)
    try:
        yield
    finally:
        _ai_sql_logging.reset(token)


@contextmanager
def ai_sql_logging() -> Generator[None, None, None]:
    with ai_agent_logging():
        yield
