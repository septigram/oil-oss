"""AI 経由 SQL ログのテスト。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.repository.ai_sql_context import ai_sql_logging, is_ai_sql_logging_enabled
from app.repository.tsurugi_conn import TsurugiConnection, log_ai_sql


def test_ai_sql_context_default_off() -> None:
    assert is_ai_sql_logging_enabled() is False


def test_ai_sql_context_enabled_inside_block() -> None:
    with ai_sql_logging():
        assert is_ai_sql_logging_enabled() is True
    assert is_ai_sql_logging_enabled() is False


@patch("app.repository.tsurugi_conn.log_event")
def test_log_ai_sql_writes_structured_log(mock_log_event: MagicMock) -> None:
    log_ai_sql(
        "SELECT * FROM t WHERE id = ?",
        (1,),
        duration_ms=12.34,
        row_count=3,
    )
    mock_log_event.assert_called_once()
    _, kwargs = mock_log_event.call_args
    assert kwargs["event"] == "ai_sql"
    assert kwargs["sql"] == "SELECT * FROM t WHERE id = ?"
    assert kwargs["params"] == [1]
    assert kwargs["duration_ms"] == 12.34
    assert kwargs["row_count"] == 3


@patch("app.repository.tsurugi_conn.log_event")
def test_tsurugi_fetchall_logs_when_ai_context(mock_log_event: MagicMock) -> None:
    conn = TsurugiConnection()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(1,), (2,)]
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_db_conn = MagicMock()
    mock_db_conn.cursor.return_value = mock_cursor
    mock_db_conn.__enter__ = MagicMock(return_value=mock_db_conn)
    mock_db_conn.__exit__ = MagicMock(return_value=False)

    with ai_sql_logging():
        with patch.object(conn, "connect", return_value=mock_db_conn):
            rows = conn.fetchall("SELECT 1", ())
    assert len(rows) == 2
    mock_log_event.assert_called_once()
    assert mock_log_event.call_args.kwargs["row_count"] == 2
    assert mock_log_event.call_args.kwargs["duration_ms"] >= 0


@patch("app.repository.tsurugi_conn.log_event")
def test_tsurugi_does_not_log_outside_ai_context(mock_log_event: MagicMock) -> None:
    conn = TsurugiConnection()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_db_conn = MagicMock()
    mock_db_conn.cursor.return_value = mock_cursor
    mock_db_conn.__enter__ = MagicMock(return_value=mock_db_conn)
    mock_db_conn.__exit__ = MagicMock(return_value=False)

    with patch.object(conn, "connect", return_value=mock_db_conn):
        conn.fetchone("SELECT 1", ())
    mock_log_event.assert_not_called()


@patch("app.repository.tsurugi_conn.log_event")
def test_log_ai_sql_serializes_params(mock_log_event: MagicMock) -> None:
    dt = datetime(2020, 5, 1, tzinfo=timezone.utc)
    log_ai_sql("SELECT ?", (dt,), duration_ms=1.0, row_count=1)
    assert mock_log_event.call_args.kwargs["params"] == ["2020-05-01T00:00:00+00:00"]
