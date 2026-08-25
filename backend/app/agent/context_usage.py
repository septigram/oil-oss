"""チャットターンの LLM トークン使用量とコンテキスト残量推定。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextUsageTracker:
    llm_calls: int = 0
    last_prompt_tokens: int | None = None
    peak_prompt_tokens: int | None = None
    last_output_tokens: int | None = None
    total_output_tokens: int = field(default=0)

    def record(self, prompt_tokens: int | None, output_tokens: int | None) -> None:
        self.llm_calls += 1
        if prompt_tokens is not None:
            self.last_prompt_tokens = prompt_tokens
            if self.peak_prompt_tokens is None or prompt_tokens > self.peak_prompt_tokens:
                self.peak_prompt_tokens = prompt_tokens
        if output_tokens is not None:
            self.last_output_tokens = output_tokens
            self.total_output_tokens += output_tokens


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_token_usage(message: Any) -> tuple[int | None, int | None]:
    """AIMessage から (prompt_tokens, output_tokens) を取り出す。"""
    usage = getattr(message, "usage_metadata", None)
    if usage is not None:
        if isinstance(usage, dict):
            prompt = _coerce_int(usage.get("input_tokens"))
            output = _coerce_int(usage.get("output_tokens"))
            if prompt is not None or output is not None:
                return prompt, output
        else:
            prompt = _coerce_int(getattr(usage, "input_tokens", None))
            output = _coerce_int(getattr(usage, "output_tokens", None))
            if prompt is not None or output is not None:
                return prompt, output

    meta = getattr(message, "response_metadata", None) or {}
    if isinstance(meta, dict):
        prompt = _coerce_int(meta.get("prompt_eval_count"))
        output = _coerce_int(meta.get("eval_count"))
        if prompt is not None or output is not None:
            return prompt, output

        token_usage = meta.get("token_usage")
        if isinstance(token_usage, dict):
            prompt = _coerce_int(token_usage.get("prompt_tokens"))
            output = _coerce_int(token_usage.get("completion_tokens"))
            if prompt is not None or output is not None:
                return prompt, output

    return None, None


def build_context_usage_event(
    tracker: ContextUsageTracker,
    context_limit: int | None,
) -> dict[str, Any]:
    peak = tracker.peak_prompt_tokens
    remaining: int | None = None
    ratio: float | None = None
    if context_limit is not None and peak is not None:
        remaining = max(0, context_limit - peak)
        ratio = round(peak / context_limit, 4)

    return {
        "type": "usage",
        "prompt_tokens": tracker.last_prompt_tokens,
        "prompt_tokens_peak": tracker.peak_prompt_tokens,
        "output_tokens": tracker.last_output_tokens,
        "output_tokens_total": tracker.total_output_tokens if tracker.llm_calls else None,
        "context_limit": context_limit,
        "remaining_estimate": remaining,
        "usage_ratio": ratio,
        "llm_calls": tracker.llm_calls,
    }
