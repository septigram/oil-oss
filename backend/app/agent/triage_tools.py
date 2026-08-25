"""トリアージ用エージェントツールの SSE ペイロード生成。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.agent.tool_logging import tool_output_to_text
from app.services.triage_service import TriageService

_SSE_KEY = "_sse_events"


def parse_tool_sse_events(output: Any) -> list[dict[str, Any]]:
    """ツール出力から SSE イベントを抽出する。"""
    text = tool_output_to_text(output)
    if not text:
        return []
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, dict):
        return []
    events = data.get(_SSE_KEY)
    if not isinstance(events, list):
        return []
    return [e for e in events if isinstance(e, dict) and e.get("type")]


def _wrap(message: str, events: list[dict[str, Any]]) -> str:
    return json.dumps({"message": message, _SSE_KEY: events}, ensure_ascii=False, default=str)


def make_start_triage_result(
    service: TriageService,
    incident_id: str,
    *,
    recovery_minutes: int | None = None,
    external_cause: bool | None = None,
) -> str:
    result = service.start_triage(
        incident_id,
        recovery_minutes=recovery_minutes,
        external_cause=external_cause,
    )
    if not result:
        return json.dumps({"error": "not found"})
    events: list[dict[str, Any]] = [
        {"type": "triage_started", "incident_id": incident_id},
    ]
    for prop in result.get("proposals") or []:
        events.append({"type": "proposal", **prop})
    summary = (
        f"トリアージを開始しました。推奨重要度は {result.get('suggested_severity')}。"
        f" 提案 {len(result.get('proposals') or [])} 件。"
    )
    return _wrap(summary, events)


def make_propose_changes_result(
    service: TriageService,
    incident_id: str,
    fields: list[str] | None = None,
    *,
    recovery_minutes: int | None = None,
    external_cause: bool | None = None,
) -> str:
    result = service.build_proposals(
        incident_id,
        focus_fields=fields,
        recovery_minutes=recovery_minutes,
        external_cause=external_cause,
    )
    if not result:
        return json.dumps({"error": "not found"})
    events = [{"type": "proposal", **p} for p in result.get("proposals") or []]
    summary = f"変更提案 {len(events)} 件（推奨重要度: {result.get('suggested_severity')}）。"
    return _wrap(summary, events)


def make_prompt_user_input_result(
    *,
    kind: str,
    label: str,
    options: list[dict[str, str]] | None = None,
    required: bool = True,
    widget_id: str | None = None,
) -> str:
    wid = widget_id or uuid.uuid4().hex[:12]
    event: dict[str, Any] = {
        "type": "widget",
        "widget_id": wid,
        "kind": kind,
        "label": label,
        "required": required,
    }
    if options:
        event["options"] = options
    return _wrap(f"ユーザー入力を促しました: {label}", [event])
