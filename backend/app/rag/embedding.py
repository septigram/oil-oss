"""埋め込みクライアント抽象化。"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import httpx
import numpy as np
from openai import OpenAI

from app.config import AppConfig, get_openai_api_key, get_settings

logger = logging.getLogger(__name__)

OLLAMA_EMBED_MAX_ATTEMPTS = 5
OLLAMA_EMBED_INITIAL_BACKOFF_SEC = 1.0
OLLAMA_EMBED_MAX_BACKOFF_SEC = 30.0
OLLAMA_EMBED_RETRYABLE_STATUS = frozenset({429, 500, 502, 503})


def _is_retryable_ollama_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in OLLAMA_EMBED_RETRYABLE_STATUS
    return isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout))


def _post_ollama_embedding(
    client: httpx.Client,
    url: str,
    payload: dict[str, str],
) -> httpx.Response:
    """Ollama /api/embeddings 呼び出し。一時障害時は指数バックオフでリトライする。"""
    backoff = OLLAMA_EMBED_INITIAL_BACKOFF_SEC
    last_exc: BaseException | None = None
    for attempt in range(1, OLLAMA_EMBED_MAX_ATTEMPTS + 1):
        try:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp
        except BaseException as exc:
            last_exc = exc
            if attempt >= OLLAMA_EMBED_MAX_ATTEMPTS or not _is_retryable_ollama_error(exc):
                raise
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "Ollama embedding request failed (attempt %s/%s, status=%s): %s; retry in %.1fs",
                attempt,
                OLLAMA_EMBED_MAX_ATTEMPTS,
                status,
                exc,
                backoff,
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, OLLAMA_EMBED_MAX_BACKOFF_SEC)
    assert last_exc is not None
    raise last_exc


class EmbeddingClient(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass


class OpenAIEmbeddingClient(EmbeddingClient):
    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or get_settings()
        api_key = get_openai_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self._client = OpenAI(api_key=api_key)
        self._model = self._settings.ai.embedding_model
        self._dim = 1536

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        sanitized = [t if t.strip() else "(empty)" for t in texts]
        vectors: list[list[float]] = []
        batch_size = 100
        for i in range(0, len(sanitized), batch_size):
            batch = sanitized[i : i + batch_size]
            response = self._client.embeddings.create(model=self._model, input=batch)
            vectors.extend(item.embedding for item in response.data)
        arr = np.array(vectors, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return arr / norms


class OllamaEmbeddingClient(EmbeddingClient):
    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or get_settings()
        self._base_url = self._settings.ai.ollama_base_url.rstrip("/")
        self._model = self._settings.ai.ollama_embedding_model
        self._dim = 768

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        sanitized = [t if t.strip() else "(empty)" for t in texts]
        vectors: list[list[float]] = []
        dim: int | None = None
        with httpx.Client(timeout=120.0) as client:
            url = f"{self._base_url}/api/embeddings"
            payload = {"model": self._model}
            for text in sanitized:
                resp = _post_ollama_embedding(
                    client,
                    url,
                    {**payload, "prompt": text},
                )
                emb = resp.json()["embedding"]
                if dim is None:
                    dim = len(emb)
                    self._dim = dim
                elif len(emb) != dim:
                    raise ValueError(
                        f"inconsistent embedding dimension: expected {dim}, got {len(emb)}"
                    )
                vectors.append(emb)
        arr = np.array(vectors, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return arr / norms


def create_embedding_client(settings: AppConfig | None = None) -> EmbeddingClient:
    cfg = settings or get_settings()
    if cfg.ai.provider == "ollama":
        return OllamaEmbeddingClient(cfg)
    return OpenAIEmbeddingClient(cfg)
