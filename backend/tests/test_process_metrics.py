"""プロセスメトリクスの単体テスト。"""

from __future__ import annotations

from app.observability.process_metrics import read_process_rss_bytes, refresh_process_metrics
from app.observability.prometheus_metrics import render_metrics


def test_read_process_rss_bytes_positive() -> None:
    rss = read_process_rss_bytes()
    assert rss is not None
    assert rss > 0


def test_render_metrics_includes_process_resident_memory_bytes() -> None:
    refresh_process_metrics()
    body = render_metrics().decode("utf-8")
    assert "process_resident_memory_bytes" in body
