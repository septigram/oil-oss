"""Tsurugi 接続ラッパー。"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generator, Mapping, Sequence

import tsurugi_dbapi as tsurugi

from app.config import AppConfig, get_settings
from app.logging_config import log_event
from app.repository.ai_sql_context import is_ai_sql_logging_enabled

logger = logging.getLogger(__name__)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return value


def _normalize_params(params: Sequence[Any] | Mapping[str, Any] | None) -> Sequence[Any] | Mapping[str, Any] | None:
    if params is None:
        return None
    if isinstance(params, Mapping):
        return {k: _normalize_value(v) for k, v in params.items()}
    return tuple(_normalize_value(v) for v in params)


def _inline_null_params(sql: str, params: Sequence[Any]) -> tuple[str, tuple[Any, ...]]:
    """Tsurugi は NULL パラメータをバインドできないため、リテラル NULL に展開する。"""
    if not params:
        return sql, ()
    out: list[str] = []
    bound: list[Any] = []
    i = 0
    pi = 0
    while i < len(sql):
        if sql[i] == "?" and pi < len(params):
            value = _normalize_value(params[pi])
            pi += 1
            if value is None:
                out.append("NULL")
            else:
                out.append("?")
                bound.append(value)
            i += 1
            continue
        out.append(sql[i])
        i += 1
    return "".join(out), tuple(bound)


def _prepare_positional(sql: str, params: Sequence[Any] | Mapping[str, Any] | None) -> tuple[str, Sequence[Any]]:
    if params is None:
        return sql, ()
    if isinstance(params, Mapping):
        normalized = _normalize_params(params)
        assert isinstance(normalized, Mapping)
        return sql, normalized
    normalized = _normalize_params(params)
    assert isinstance(normalized, tuple)
    return _inline_null_params(sql, normalized)


def _format_sql(sql: str) -> str:
    return " ".join(sql.split())


def _serialize_params(params: Sequence[Any] | Mapping[str, Any] | None) -> list[Any]:
    if not params:
        return []
    values = params.values() if isinstance(params, Mapping) else params
    serialized: list[Any] = []
    for value in values:
        if isinstance(value, datetime):
            serialized.append(value.isoformat())
        elif isinstance(value, Enum):
            serialized.append(value.value)
        else:
            serialized.append(value)
    return serialized


def log_ai_sql(
    sql: str,
    params: Sequence[Any] | Mapping[str, Any] | None,
    *,
    duration_ms: float,
    row_count: int,
) -> None:
    log_event(
        logger,
        event="ai_sql",
        sql=_format_sql(sql),
        params=_serialize_params(params),
        duration_ms=round(duration_ms, 2),
        row_count=row_count,
    )


def _maybe_log_ai_sql(
    sql: str,
    params: Sequence[Any] | Mapping[str, Any] | None,
    *,
    duration_ms: float,
    row_count: int,
) -> None:
    if is_ai_sql_logging_enabled():
        log_ai_sql(sql, params, duration_ms=duration_ms, row_count=row_count)


class TsurugiConnection:
    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or get_settings()

    @contextmanager
    def connect(self) -> Generator[Any, None, None]:
        cfg = self._settings.tsurugi
        with tsurugi.connect(
            endpoint=cfg.endpoint,
            user=cfg.user,
            password=cfg.password,
            default_timeout=60,
        ) as connection:
            yield connection

    def execute(self, sql: str, params: Sequence[Any] | dict[str, Any] | None = None) -> int:
        sql, bound = _prepare_positional(sql, params)
        start = time.perf_counter()
        with self._trace_query("execute"):
            with self.connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, bound or ())
                    rowcount = cursor.rowcount
                conn.commit()
        duration = (time.perf_counter() - start) * 1000
        self._observe_query("execute", duration / 1000.0)
        _maybe_log_ai_sql(sql, bound, duration_ms=duration, row_count=rowcount)
        return rowcount

    def fetchone(self, sql: str, params: Sequence[Any] | dict[str, Any] | None = None) -> Any:
        sql, bound = _prepare_positional(sql, params)
        start = time.perf_counter()
        with self._trace_query("fetchone"):
            with self.connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, bound or ())
                    row = cursor.fetchone()
                conn.commit()
        duration = (time.perf_counter() - start) * 1000
        self._observe_query("fetchone", duration / 1000.0)
        _maybe_log_ai_sql(
            sql,
            bound,
            duration_ms=duration,
            row_count=0 if row is None else 1,
        )
        return row

    def fetchall(self, sql: str, params: Sequence[Any] | dict[str, Any] | None = None) -> list[Any]:
        sql, bound = _prepare_positional(sql, params)
        start = time.perf_counter()
        with self._trace_query("fetchall"):
            with self.connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, bound or ())
                    rows = cursor.fetchall()
                conn.commit()
        duration = (time.perf_counter() - start) * 1000
        self._observe_query("fetchall", duration / 1000.0)
        _maybe_log_ai_sql(
            sql,
            bound,
            duration_ms=duration,
            row_count=len(rows),
        )
        return rows

    @staticmethod
    def _observe_query(operation: str, duration_seconds: float) -> None:
        try:
            from app.observability.prometheus_metrics import observe_tsurugi_query

            observe_tsurugi_query(operation=operation, duration_seconds=duration_seconds)
        except ImportError:
            pass

    @staticmethod
    @contextmanager
    def _trace_query(operation: str):
        try:
            from app.observability.tracing import trace_span

            with trace_span("tsurugi.query", attributes={"db.operation": operation}):
                yield
        except ImportError:
            yield
