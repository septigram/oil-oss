"""OpenTelemetry トレース設定。"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import SpanKind, Status, StatusCode

from app.config import get_observability_env, get_observability_version
from app.logging_config import SERVICE_NAME

_tracer_provider: TracerProvider | None = None
_instrumented = False


def _otlp_configured() -> bool:
    return bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))


def setup_tracing(*, app_version: str = "0.1.0") -> None:
    """OTLP 未設定時は NoOp（TracerProvider を設定しない）。"""
    global _tracer_provider, _instrumented
    if _instrumented:
        return
    _instrumented = True
    if not _otlp_configured():
        return
    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": get_observability_version(default=app_version),
            "deployment.environment": get_observability_env(),
        }
    )
    provider = TracerProvider(resource=resource)
    if os.getenv("OTEL_CONSOLE_EXPORTER") == "1":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _tracer_provider = provider


def shutdown_tracing() -> None:
    global _tracer_provider
    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        _tracer_provider = None


def instrument_app(app: Any) -> None:
    if not _otlp_configured():
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()


def get_tracer(name: str):
    return trace.get_tracer(name)


def get_trace_log_fields() -> dict[str, str]:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return {}
    return {
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
    }


@contextmanager
def trace_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> Generator[Any, None, None]:
    tracer = get_tracer("oil")
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
