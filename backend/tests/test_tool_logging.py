"""MCP ツール呼び出しログの単体テスト。"""

from __future__ import annotations

import logging
from unittest.mock import patch

from app.agent.tool_logging import (
    log_mcp_tool_call,
    preview_tool_response,
    tool_output_to_text,
    tool_parameters_to_dict,
)
from app.log_buffer import get_logs_after, reset_for_tests


def setup_function() -> None:
    reset_for_tests()


def test_preview_tool_response_short_text() -> None:
    assert preview_tool_response("hello") == "hello"


def test_preview_tool_response_truncates_with_ellipsis() -> None:
    text = "a" * 101
    assert preview_tool_response(text) == ("a" * 100) + "…"


def test_tool_output_to_text_from_string() -> None:
    assert tool_output_to_text('{"total": 1}') == '{"total": 1}'


def test_tool_parameters_to_dict() -> None:
    assert tool_parameters_to_dict({"status": ["OPEN"]}) == {"status": ["OPEN"]}
    assert tool_parameters_to_dict(None) == {}


def test_log_mcp_tool_call_appends_to_buffer() -> None:
    logger = logging.getLogger("app.test.tool_logging")
    with patch.object(logger, "info"):
        log_mcp_tool_call(
            logger,
            tool_name="search_incidents",
            parameters={"status": ["OPEN"]},
            output='{"total": 2, "items": []}',
        )
    items, _ = get_logs_after(0)
    assert len(items) == 1
    entry = items[0]
    assert entry["event"] == "mcp_tool"
    assert entry["tool_name"] == "search_incidents"
    assert entry["parameters"] == {"status": ["OPEN"]}
    assert entry["response_chars"] == len('{"total": 2, "items": []}')
    assert entry["response_preview"] == '{"total": 2, "items": []}'
