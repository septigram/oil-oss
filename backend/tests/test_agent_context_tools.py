"""get_current_datetime / get_system_context ツールの単体テスト。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.agent.service import AgentService


def _tool_names(tools: list) -> set[str]:
    return {t.name for t in tools}


def test_context_tools_registered_for_normal_chat() -> None:
    service = AgentService()
    tools = service._make_tools(None)
    names = _tool_names(tools)
    assert "get_current_datetime" in names
    assert "get_system_context" in names


def test_context_tools_registered_for_viewer_only() -> None:
    service = AgentService()
    tools = service._make_tools(None, viewer_only=True)
    names = _tool_names(tools)
    assert "get_current_datetime" in names
    assert "get_system_context" in names
    assert "prompt_user_input" not in names


def test_get_current_datetime_invoke() -> None:
    service = AgentService()
    service._ref = MagicMock()
    service._ref.get_current_datetime_snapshot.return_value = {
        "now": "2026-07-04T09:00:00+09:00",
        "timezone": "Asia/Tokyo",
        "reference_date": "2020-05-31",
        "reference_date_mode": "fixed",
    }
    tools = service._make_tools(None)
    tool = next(t for t in tools if t.name == "get_current_datetime")
    result = json.loads(tool.invoke({}))
    assert result["timezone"] == "Asia/Tokyo"
    assert result["reference_date"] == "2020-05-31"
    assert result["reference_date_mode"] == "fixed"


def test_get_system_context_invoke_all_sections() -> None:
    service = AgentService()
    service._system_context = MagicMock()
    service._system_context.build_context.return_value = {
        "company": {"company_name": "株式会社ストッククラウド"},
        "services": [{"service_name": "Mercury"}],
    }
    tools = service._make_tools(None)
    tool = next(t for t in tools if t.name == "get_system_context")
    result = json.loads(tool.invoke({}))
    assert result["company"]["company_name"] == "株式会社ストッククラウド"
    service._system_context.build_context.assert_called_once_with(None)


def test_get_system_context_invoke_with_sections() -> None:
    service = AgentService()
    service._system_context = MagicMock()
    service._system_context.build_context.return_value = {
        "services": [{"service_name": "Venus"}],
    }
    tools = service._make_tools(None)
    tool = next(t for t in tools if t.name == "get_system_context")
    result = json.loads(tool.invoke({"sections": ["services"]}))
    assert result["services"][0]["service_name"] == "Venus"
    service._system_context.build_context.assert_called_once_with(["services"])
