"""AiModelService の単体テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.ai_model_service import AiModelService, LlmModelItem

from tests.conftest import make_app_config


def test_default_llm_uses_config() -> None:
    service = AiModelService(make_app_config(llm_provider="ollama"))
    assert service.default_llm() == {"provider": "ollama", "model": "qwen3.6:27b"}


def test_resolve_llm_returns_default_when_omitted() -> None:
    service = AiModelService(make_app_config(llm_provider="ollama"))
    assert service.resolve_llm(None, None) == ("ollama", "qwen3.6:27b")


def test_resolve_llm_requires_both_fields() -> None:
    service = AiModelService(make_app_config(llm_provider="ollama"))
    with pytest.raises(ValueError, match="together"):
        service.resolve_llm("ollama", None)


def test_list_models_merges_sources_and_includes_default() -> None:
    service = AiModelService(make_app_config(llm_provider="ollama"))
    with (
        patch.object(service, "_fetch_ollama_models", return_value=([], "connection refused")),
        patch.object(
            service,
            "_fetch_openai_models",
            return_value=([LlmModelItem("openai", "gpt-4o-mini", "gpt-4o-mini")], None),
        ),
    ):
        payload = service.list_models(force_refresh=True)

    assert payload["default"] == {"provider": "ollama", "model": "qwen3.6:27b"}
    models = {(item["provider"], item["model"]) for item in payload["items"]}
    assert ("ollama", "qwen3.6:27b") in models
    assert ("openai", "gpt-4o-mini") in models
    assert payload["sources"][0]["status"] == "error"
    assert payload["sources"][1]["status"] == "ok"


def test_validate_llm_allows_default_when_provider_unreachable() -> None:
    service = AiModelService(make_app_config(llm_provider="ollama"))
    with (
        patch.object(service, "_fetch_ollama_models", return_value=([], "down")),
        patch.object(service, "_fetch_openai_models", return_value=([], "no key")),
    ):
        service.validate_llm("ollama", "qwen3.6:27b")


def test_validate_llm_rejects_unknown_model() -> None:
    service = AiModelService(make_app_config(llm_provider="ollama"))
    with (
        patch.object(service, "_fetch_ollama_models", return_value=([], None)),
        patch.object(service, "_fetch_openai_models", return_value=([], None)),
    ):
        with pytest.raises(ValueError, match="allowed"):
            service.validate_llm("openai", "unknown-model")


def test_fetch_ollama_models_skips_embedding_models() -> None:
    service = AiModelService(make_app_config(llm_provider="ollama"))
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "models": [
            {"name": "qwen3.6:27b"},
            {"name": "nomic-embed-text"},
            {"name": "mxbai-embed-large"},
        ]
    }
    with patch("app.services.ai_model_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = response
        items, error = service._fetch_ollama_models()

    assert error is None
    assert [item.model for item in items] == ["qwen3.6:27b"]


def test_get_context_limit_ollama_from_show() -> None:
    service = AiModelService(make_app_config(llm_provider="ollama"))
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "model_info": {
            "llama.context_length": 8192,
        }
    }
    with patch("app.services.ai_model_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = response
        limit = service.get_context_limit("ollama", "llama3.2")

    assert limit == 8192


def test_get_context_limit_openai_uses_retrieve() -> None:
    service = AiModelService(make_app_config())
    model = MagicMock()
    model.context_window = 128000
    with (
        patch("app.services.ai_model_service.get_openai_api_key", return_value="test-key"),
        patch("app.services.ai_model_service.OpenAI") as openai_cls,
    ):
        openai_cls.return_value.models.retrieve.return_value = model
        limit = service.get_context_limit("openai", "gpt-4o-mini")

    assert limit == 128000


def test_get_context_limit_openai_fallback() -> None:
    service = AiModelService(make_app_config())
    with (
        patch("app.services.ai_model_service.get_openai_api_key", return_value="test-key"),
        patch("app.services.ai_model_service.OpenAI") as openai_cls,
    ):
        openai_cls.return_value.models.retrieve.side_effect = RuntimeError("network")
        limit = service.get_context_limit("openai", "gpt-4o-mini")

    assert limit == 128_000
