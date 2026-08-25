"""ログポーリング API のノイズ抑制（LogPanel 等の高頻度リクエスト）。"""

from __future__ import annotations

import logging

from app.runtime_flags import is_verbose

# 高頻度ポーリング・監視スクレイプでログを埋めないパス（部分一致）
_NOISY_PATH_MARKERS = (
    "/api/logs/recent",
    "/api/metrics/recent",
    "/health/ready",  # Prometheus blackbox プローブ
    "/metrics",  # Prometheus scrape（{context_path}/metrics）
)


def is_noisy_polling_path(path: str) -> bool:
    """高頻度ポーリングでログを埋めないよう抑制対象とするパスか。"""
    return any(marker in path for marker in _NOISY_PATH_MARKERS)


def should_log_api_timing(path: str) -> bool:
    """``api_timing`` を stderr / OIL_LOG_FILE に出すか。

    verbose 時はすべて出力。通常時はポーリング API のみ抑制する。
    """
    if is_verbose():
        return True
    return not is_noisy_polling_path(path)


class PollingNoiseAccessFilter(logging.Filter):
    """Uvicorn アクセスログからポーリング API を除外する（verbose 時は通す）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if is_verbose():
            return True
        return not is_noisy_polling_path(record.getMessage())


def configure_uvicorn_access_log() -> None:
    """uvicorn.access を有効化し、ポーリング API 用フィルタを付与する。"""
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.disabled = False
    access_logger.setLevel(logging.INFO)
    if not any(isinstance(f, PollingNoiseAccessFilter) for f in access_logger.filters):
        access_logger.addFilter(PollingNoiseAccessFilter())
