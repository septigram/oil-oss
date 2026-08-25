"""RAG 同期完了時の Prometheus 記録。"""

from __future__ import annotations


def record_rag_sync_complete(
    *, duration_ms: float, error: str | None = None, skipped: bool = False
) -> None:
    if skipped:
        result = "skipped"
    elif error:
        result = "error"
    else:
        result = "success"
    try:
        from app.observability.prometheus_metrics import observe_rag_sync

        observe_rag_sync(result=result, duration_seconds=duration_ms / 1000.0)
    except ImportError:
        pass
