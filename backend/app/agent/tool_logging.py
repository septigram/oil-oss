"""エージェントツール（MCP 相当）呼び出しのログ整形。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.logging_config import log_event

_PREVIEW_MAX_CHARS = 100


def tool_output_to_text(output: Any) -> str:
    """ツール戻り値をログ用の単一文字列に変換する。"""
    if output is None:
        return ""
    content = getattr(output, "content", None)
    if content is not None:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            text = "".join(parts)
            if text:
                return text
    if isinstance(output, str):
        return output
    if isinstance(output, (dict, list)):
        return json.dumps(output, ensure_ascii=False, default=str)
    return str(output)


def tool_parameters_to_dict(parameters: Any) -> dict[str, Any]:
    if parameters is None:
        return {}
    if isinstance(parameters, dict):
        return parameters
    return {"value": parameters}


def preview_tool_response(text: str, max_chars: int = _PREVIEW_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}…"


def log_mcp_tool_call(
    logger: logging.Logger,
    *,
    tool_name: str,
    parameters: Any,
    output: Any,
) -> None:
    """MCP ツール呼び出しを構造化ログおよび LLM ログバッファに記録する。"""
    params = tool_parameters_to_dict(parameters)
    response_text = tool_output_to_text(output)
    log_event(
        logger,
        event="mcp_tool",
        tool_name=tool_name,
        parameters=params,
        response_preview=preview_tool_response(response_text),
        response_chars=len(response_text),
    )
