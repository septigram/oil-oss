"""Prometheus メトリクス API。"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.observability.prometheus_metrics import render_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def prometheus_metrics() -> Response:
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")
