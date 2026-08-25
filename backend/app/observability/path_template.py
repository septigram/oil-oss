"""URL パスを Prometheus ラベル用テンプレートに正規化。"""

from __future__ import annotations

import re

_INC = r"/api/incidents/(INC-\d{4}-\d{5})"

# (pattern, replacement) — 先にマッチしたものを適用
_PATH_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(_INC + r"(?:/|$)"), "/api/incidents/{id}"),
    (
        re.compile(_INC + r"/procedures/from-incident"),
        "/api/incidents/{id}/procedures/from-incident",
    ),
    (re.compile(_INC + r"/procedures"), "/api/incidents/{id}/procedures"),
    (
        re.compile(_INC + r"/recommended-procedures"),
        "/api/incidents/{id}/recommended-procedures",
    ),
    (re.compile(_INC + r"/triage/proposals"), "/api/incidents/{id}/triage/proposals"),
    (re.compile(_INC + r"/responses"), "/api/incidents/{id}/responses"),
    (re.compile(r"/api/procedures/(PRC-\d{5})(?:/|$)"), "/api/procedures/{id}"),
    (re.compile(r"/api/procedures/(PRC-\d{5})/incidents"), "/api/procedures/{id}/incidents"),
    (re.compile(r"/api/masters/[^/]+"), "/api/masters/{type}"),
]


def normalize_path_template(path: str, *, context_path: str = "") -> str:
    """生パスを低カーディナリティのテンプレートに変換する。"""
    normalized = path
    if context_path and normalized.startswith(context_path):
        normalized = normalized[len(context_path) :] or "/"
    for pattern, replacement in _PATH_RULES:
        if pattern.search(normalized):
            normalized = pattern.sub(replacement, normalized, count=1)
            break
    if context_path:
        return f"{context_path}{normalized}"
    return normalized
