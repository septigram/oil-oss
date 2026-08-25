"""log_noise（ポーリング API ログ抑制）の単体テスト。"""

from __future__ import annotations

import logging

from app.log_noise import (
    PollingNoiseAccessFilter,
    is_noisy_polling_path,
    should_log_api_timing,
)
from app.runtime_flags import set_verbose


def test_is_noisy_polling_path() -> None:
    assert is_noisy_polling_path("/oil/api/logs/recent")
    assert is_noisy_polling_path("/oil/api/logs/recent?after=6")
    assert is_noisy_polling_path("/oil/api/metrics/recent")
    assert is_noisy_polling_path("/oil/health/ready")
    assert is_noisy_polling_path("/oil/metrics")
    assert not is_noisy_polling_path("/oil/api/incidents")
    assert not is_noisy_polling_path("/oil/health/live")


def test_should_log_api_timing_suppresses_polling_when_not_verbose() -> None:
    set_verbose(False)
    assert not should_log_api_timing("/oil/api/logs/recent")
    assert should_log_api_timing("/oil/api/incidents")


def test_should_log_api_timing_logs_polling_when_verbose() -> None:
    set_verbose(True)
    assert should_log_api_timing("/oil/api/logs/recent")
    assert should_log_api_timing("/oil/api/incidents")


def test_polling_noise_access_filter() -> None:
    filt = PollingNoiseAccessFilter()
    set_verbose(False)
    recent = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='127.0.0.1 - "GET /oil/api/logs/recent?after=6 HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    health = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='127.0.0.1 - "GET /oil/api/incidents HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    assert filt.filter(recent) is False
    assert filt.filter(health) is True
    ready = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='127.0.0.1 - "GET /oil/health/ready HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    metrics = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='127.0.0.1 - "GET /oil/metrics HTTP/1.1" 200',
        args=(),
        exc_info=None,
    )
    assert filt.filter(ready) is False
    assert filt.filter(metrics) is False
    set_verbose(True)
    assert filt.filter(recent) is True
