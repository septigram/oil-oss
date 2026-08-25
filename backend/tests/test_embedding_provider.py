"""埋め込みプロバイダ切替の単体テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.rag.embedding import (
    OLLAMA_EMBED_MAX_ATTEMPTS,
    OllamaEmbeddingClient,
    OpenAIEmbeddingClient,
    _post_ollama_embedding,
    create_embedding_client,
)

from tests.conftest import make_app_config


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://localhost:11434/api/embeddings")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_create_embedding_client_openai() -> None:
    settings = make_app_config(embedding_provider="openai")
    with patch("app.rag.embedding.get_openai_api_key", return_value="test-key"):
        client = create_embedding_client(settings)
    assert isinstance(client, OpenAIEmbeddingClient)
    assert client.model_name == "text-embedding-3-small"


def test_create_embedding_client_ollama() -> None:
    settings = make_app_config(embedding_provider="ollama")
    client = create_embedding_client(settings)
    assert isinstance(client, OllamaEmbeddingClient)
    assert client.model_name == "nomic-embed-text"


def test_openai_embedding_requires_api_key() -> None:
    settings = make_app_config(embedding_provider="openai")
    with patch("app.rag.embedding.get_openai_api_key", return_value=None):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            create_embedding_client(settings)


def test_post_ollama_embedding_retries_on_500() -> None:
    client = MagicMock()
    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    client.post.side_effect = [
        _http_status_error(500),
        _http_status_error(500),
        ok,
    ]
    with patch("app.rag.embedding.time.sleep") as sleep:
        resp = _post_ollama_embedding(client, "http://x/api/embeddings", {"model": "m", "prompt": "t"})
    assert resp is ok
    assert client.post.call_count == 3
    assert sleep.call_count == 2
    sleep.assert_any_call(1.0)
    sleep.assert_any_call(2.0)


def test_post_ollama_embedding_exhausts_retries() -> None:
    client = MagicMock()
    client.post.side_effect = _http_status_error(500)
    with patch("app.rag.embedding.time.sleep"):
        with pytest.raises(httpx.HTTPStatusError):
            _post_ollama_embedding(client, "http://x/api/embeddings", {"model": "m", "prompt": "t"})
    assert client.post.call_count == OLLAMA_EMBED_MAX_ATTEMPTS


def test_post_ollama_embedding_does_not_retry_400() -> None:
    client = MagicMock()
    client.post.side_effect = _http_status_error(400)
    with patch("app.rag.embedding.time.sleep") as sleep:
        with pytest.raises(httpx.HTTPStatusError):
            _post_ollama_embedding(client, "http://x/api/embeddings", {"model": "m", "prompt": "t"})
    assert client.post.call_count == 1
    sleep.assert_not_called()


def test_ollama_embed_texts_retries_transient_failure() -> None:
    settings = make_app_config(embedding_provider="ollama")
    client = OllamaEmbeddingClient(settings)
    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    ok.json.return_value = {"embedding": [1.0, 0.0]}
    with patch("app.rag.embedding.httpx.Client") as client_cls:
        http = MagicMock()
        client_cls.return_value.__enter__.return_value = http
        http.post.side_effect = [_http_status_error(503), ok]
        with patch("app.rag.embedding.time.sleep"):
            vectors = client.embed_texts(["hello"])
    assert vectors.shape == (1, 2)
    assert http.post.call_count == 2
