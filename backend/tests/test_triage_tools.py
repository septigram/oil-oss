"""トリアージツール SSE ペイロードテスト。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.agent.triage_tools import (
    make_prompt_user_input_result,
    make_propose_changes_result,
    make_start_triage_result,
    parse_tool_sse_events,
)


def test_parse_tool_sse_events_proposal():
    payload = json.dumps(
        {
            "message": "ok",
            "_sse_events": [
                {"type": "proposal", "proposal_id": "p1", "field": "severity"},
            ],
        }
    )
    events = parse_tool_sse_events(payload)
    assert len(events) == 1
    assert events[0]["type"] == "proposal"


def test_parse_tool_sse_events_from_tool_message_object():
    payload = json.dumps(
        {
            "message": "ok",
            "_sse_events": [{"type": "proposal", "proposal_id": "p2", "field": "severity"}],
        }
    )

    class _ToolMessage:
        content = payload

    events = parse_tool_sse_events(_ToolMessage())
    assert len(events) == 1
    assert events[0]["proposal_id"] == "p2"


def test_make_prompt_user_input_result_widget():
    raw = make_prompt_user_input_result(
        kind="radio",
        label="重要度を選択",
        options=[{"value": "HIGH", "label": "HIGH"}],
    )
    data = json.loads(raw)
    events = data["_sse_events"]
    assert events[0]["type"] == "widget"
    assert events[0]["kind"] == "radio"
    assert events[0]["label"] == "重要度を選択"


def test_make_start_triage_result_events():
    mock_svc = MagicMock()
    mock_svc.start_triage.return_value = {
        "incident_id": "INC-2020-00001",
        "proposals": [
            {
                "proposal_id": "p1",
                "field": "severity",
                "current": "LOW",
                "proposed": "MEDIUM",
                "reason": "test",
                "confidence": "high",
            }
        ],
        "suggested_severity": "MEDIUM",
        "severity_rule_hits": ["external_cause"],
        "status": "started",
    }
    raw = make_start_triage_result(mock_svc, "INC-2020-00001")
    data = json.loads(raw)
    types = [e["type"] for e in data["_sse_events"]]
    assert "triage_started" in types
    assert "proposal" in types


def test_make_propose_changes_result():
    mock_svc = MagicMock()
    mock_svc.build_proposals.return_value = {
        "incident_id": "INC-2020-00001",
        "proposals": [],
        "suggested_severity": "LOW",
        "severity_rule_hits": [],
    }
    raw = make_propose_changes_result(mock_svc, "INC-2020-00001")
    data = json.loads(raw)
    assert "message" in data
    assert data["_sse_events"] == []
