"""search_incidents ツールの単体テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.agent.service import AgentService


def test_search_incidents_passes_severity_filter() -> None:
    incidents = MagicMock()
    incidents.search.return_value = ([], 0)
    service = AgentService()
    service._incidents = incidents
    tools = service._make_tools(None)
    search_tool = next(t for t in tools if t.name == "search_incidents")
    search_tool.invoke({"severity": ["HIGH", "CRITICAL"]})
    params = incidents.search.call_args[0][0]
    assert params.severities == ["HIGH", "CRITICAL"]
