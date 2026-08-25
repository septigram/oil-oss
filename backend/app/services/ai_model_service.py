"""チャット用 LLM モデル一覧の取得と検証。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from openai import OpenAI

from app.config import AppConfig, get_openai_api_key, get_settings

CACHE_TTL_SEC = 300
VALID_PROVIDERS = frozenset({"ollama", "openai"})


@dataclass(frozen=True)
class LlmModelItem:
    provider: str
    model: str
    label: str

    def as_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "model": self.model, "label": self.label}


class AiModelService:
    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or get_settings()
        self._cache_at: float | None = None
        self._cache_payload: dict[str, Any] | None = None
        self._context_limit_cache: dict[tuple[str, str], tuple[float, int | None]] = {}

    def default_llm(self) -> dict[str, str]:
        ai = self._settings.ai
        provider = ai.llm_provider
        model = ai.ollama_llm_model if provider == "ollama" else ai.llm_model
        return {"provider": provider, "model": model}

    def resolve_llm(self, llm_provider: str | None, model: str | None) -> tuple[str, str]:
        default = self.default_llm()
        if llm_provider is None and model is None:
            return default["provider"], default["model"]
        if llm_provider is None or model is None:
            raise ValueError("llm_provider and model must be specified together")
        if llm_provider not in VALID_PROVIDERS:
            raise ValueError(f"invalid llm_provider: {llm_provider}")
        return llm_provider, model

    def validate_llm(self, llm_provider: str, model: str) -> None:
        catalog = self.list_models()
        allowed = {(item["provider"], item["model"]) for item in catalog["items"]}
        default = catalog["default"]
        allowed.add((default["provider"], default["model"]))
        if (llm_provider, model) not in allowed:
            raise ValueError("model is not in the allowed list")

    def list_models(self, *, force_refresh: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if (
            not force_refresh
            and self._cache_payload is not None
            and self._cache_at is not None
            and now - self._cache_at < CACHE_TTL_SEC
        ):
            return self._cache_payload

        ollama_items, ollama_error = self._fetch_ollama_models()
        openai_items, openai_error = self._fetch_openai_models()

        items = ollama_items + openai_items
        default = self.default_llm()
        items = self._ensure_default_item(items, default)

        payload = {
            "default": default,
            "items": [item.as_dict() for item in items],
            "sources": [
                {
                    "provider": "ollama",
                    "status": "ok" if ollama_error is None else "error",
                    "error": ollama_error,
                },
                {
                    "provider": "openai",
                    "status": "ok" if openai_error is None else "error",
                    "error": openai_error,
                },
            ],
        }
        self._cache_at = now
        self._cache_payload = payload
        return payload

    def _ensure_default_item(
        self,
        items: list[LlmModelItem],
        default: dict[str, str],
    ) -> list[LlmModelItem]:
        key = (default["provider"], default["model"])
        if any((item.provider, item.model) == key for item in items):
            return items
        return [
            LlmModelItem(
                provider=default["provider"],
                model=default["model"],
                label=default["model"],
            ),
            *items,
        ]

    def _is_embedding_model(self, provider: str, model_id: str) -> bool:
        ai = self._settings.ai
        lowered = model_id.lower()
        if provider == "ollama":
            if model_id == ai.ollama_embedding_model:
                return True
            return "embed" in lowered
        if "embed" in lowered:
            return True
        return model_id == ai.embedding_model

    def _fetch_ollama_models(self) -> tuple[list[LlmModelItem], str | None]:
        base_url = self._settings.ai.ollama_base_url.rstrip("/")
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            return [], str(exc)

        items: list[LlmModelItem] = []
        for entry in data.get("models", []):
            name = str(entry.get("name", "")).strip()
            if not name or self._is_embedding_model("ollama", name):
                continue
            items.append(LlmModelItem(provider="ollama", model=name, label=name))
        items.sort(key=lambda item: item.model)
        return items, None

    def _fetch_openai_models(self) -> tuple[list[LlmModelItem], str | None]:
        api_key = get_openai_api_key()
        if not api_key:
            return [], "OPENAI_API_KEY is not set"
        try:
            client = OpenAI(api_key=api_key)
            items: list[LlmModelItem] = []
            for entry in client.models.list():
                model_id = str(entry.id)
                if self._is_embedding_model("openai", model_id):
                    continue
                if not self._is_openai_chat_model(model_id):
                    continue
                items.append(LlmModelItem(provider="openai", model=model_id, label=model_id))
            items.sort(key=lambda item: item.model)
            return items, None
        except Exception as exc:  # noqa: BLE001
            return [], str(exc)

    @staticmethod
    def _is_openai_chat_model(model_id: str) -> bool:
        prefixes = ("gpt-", "o1", "o3", "o4", "chatgpt")
        return any(model_id.startswith(prefix) for prefix in prefixes)

    def get_context_limit(self, llm_provider: str, model: str) -> int | None:
        key = (llm_provider, model)
        now = time.monotonic()
        cached = self._context_limit_cache.get(key)
        if cached is not None and now - cached[0] < CACHE_TTL_SEC:
            return cached[1]

        limit = self._fetch_context_limit(llm_provider, model)
        self._context_limit_cache[key] = (now, limit)
        return limit

    def _fetch_context_limit(self, llm_provider: str, model: str) -> int | None:
        if llm_provider == "ollama":
            return self._fetch_ollama_context_limit(model)
        if llm_provider == "openai":
            return self._fetch_openai_context_limit(model)
        return None

    def _fetch_ollama_context_limit(self, model: str) -> int | None:
        base_url = self._settings.ai.ollama_base_url.rstrip("/")
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(f"{base_url}/api/show", json={"name": model})
                response.raise_for_status()
                data = response.json()
        except Exception:  # noqa: BLE001
            return None

        model_info = data.get("model_info")
        if not isinstance(model_info, dict):
            return None
        for info_key, value in model_info.items():
            if str(info_key).endswith(".context_length"):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
        return None

    def _fetch_openai_context_limit(self, model_id: str) -> int | None:
        api_key = get_openai_api_key()
        if not api_key:
            return None
        try:
            client = OpenAI(api_key=api_key)
            model = client.models.retrieve(model_id)
            context_window = getattr(model, "context_window", None)
            if context_window is not None:
                return int(context_window)
        except Exception:  # noqa: BLE001
            pass
        return self._openai_context_limit_fallback(model_id)

    @staticmethod
    def _openai_context_limit_fallback(model_id: str) -> int | None:
        """models.retrieve 失敗時の既知モデル上限（概算）。"""
        known: dict[str, int] = {
            "gpt-4o": 128_000,
            "gpt-4o-mini": 128_000,
            "gpt-4-turbo": 128_000,
            "gpt-4": 128_000,
            "gpt-3.5-turbo": 16_385,
        }
        if model_id in known:
            return known[model_id]
        for prefix, limit in known.items():
            if model_id.startswith(prefix):
                return limit
        if model_id.startswith("o1") or model_id.startswith("o3") or model_id.startswith("o4"):
            return 200_000
        return None
