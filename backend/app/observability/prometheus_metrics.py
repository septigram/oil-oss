"""Prometheus メトリクス定義。"""

from __future__ import annotations

from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest

from app.config import get_settings
from app.observability.path_template import normalize_path_template
from app.observability.process_metrics import refresh_process_metrics

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path_template", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path_template", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

TSURUGI_QUERY_DURATION = Histogram(
    "tsurugi_query_duration_seconds",
    "Tsurugi query duration in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

RAG_SEARCH_DURATION = Histogram(
    "rag_search_duration_seconds",
    "FAISS RAG search duration in seconds",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

RAG_SYNC_DURATION = Histogram(
    "rag_sync_duration_seconds",
    "RAG background sync duration in seconds",
    ["result"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

LLM_REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

CHAT_TURN_DURATION = Histogram(
    "chat_turn_duration_seconds",
    "Chat turn duration in seconds",
    ["provider"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

FAISS_INDEX_LOADED = Gauge(
    "faiss_index_loaded",
    "Whether FAISS index is loaded in this process (1=yes, 0=no)",
)


def observe_http_request(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    context_path = get_settings().context_path
    path_template = normalize_path_template(path, context_path=context_path)
    status = str(status_code)
    HTTP_REQUESTS_TOTAL.labels(method=method, path_template=path_template, status=status).inc()
    HTTP_REQUEST_DURATION.labels(method=method, path_template=path_template, status=status).observe(
        duration_seconds
    )


def observe_tsurugi_query(*, operation: str, duration_seconds: float) -> None:
    TSURUGI_QUERY_DURATION.labels(operation=operation).observe(duration_seconds)


def observe_rag_search(*, duration_seconds: float) -> None:
    RAG_SEARCH_DURATION.observe(duration_seconds)


def observe_rag_sync(*, result: str, duration_seconds: float) -> None:
    RAG_SYNC_DURATION.labels(result=result).observe(duration_seconds)


def observe_llm_request(*, provider: str, model: str, duration_seconds: float) -> None:
    LLM_REQUEST_DURATION.labels(provider=provider, model=model).observe(duration_seconds)


def observe_chat_turn(*, provider: str, duration_seconds: float) -> None:
    CHAT_TURN_DURATION.labels(provider=provider).observe(duration_seconds)


def set_faiss_index_loaded(loaded: bool) -> None:
    FAISS_INDEX_LOADED.set(1 if loaded else 0)


def render_metrics() -> bytes:
    refresh_process_metrics()
    return generate_latest(REGISTRY)
