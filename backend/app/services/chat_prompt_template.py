"""チャット定型質問テンプレートの読込。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.config import AppConfig, get_settings


class ChatPromptTemplateService:
    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or get_settings()
        self._path = self._settings.paths.chat_prompt_templates

    @property
    def templates_path(self) -> Path:
        return self._path

    def list_templates(self) -> list[dict[str, str]]:
        if not self._path.exists():
            return []
        with self._path.open(encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
        items: list[dict[str, str]] = []
        for entry in raw.get("templates") or []:
            if not isinstance(entry, dict):
                continue
            message = str(entry.get("message", "")).strip()
            if not message:
                continue
            template_id = str(entry.get("id", "")).strip() or f"tpl-{len(items)}"
            label = str(entry.get("label", "")).strip() or message
            items.append({"id": template_id, "label": label, "message": message})
        return items
