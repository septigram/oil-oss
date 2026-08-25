"""OpenTelemetry の単体テスト。"""

from __future__ import annotations

import os
from unittest.mock import patch

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.observability.tracing import get_trace_log_fields, setup_tracing, trace_span


def test_setup_tracing_noop_without_otlp() -> None:
    env = {k: v for k, v in os.environ.items() if k != "OTEL_EXPORTER_OTLP_ENDPOINT"}
    with patch.dict(os.environ, env, clear=True):
        setup_tracing(app_version="test")
        provider = trace.get_tracer_provider()
        assert not isinstance(provider, TracerProvider)


def test_trace_span_creates_span() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    with trace_span("test.operation", attributes={"key": "value"}):
        fields = get_trace_log_fields()
        assert "trace_id" in fields
        assert "span_id" in fields
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test.operation"
