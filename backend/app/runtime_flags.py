"""起動時フラグ（--verbose 等）。"""

from __future__ import annotations

import os
import sys

_verbose: bool | None = None


def _env_verbose() -> bool:
    return os.environ.get("OIL_VERBOSE", "").strip().lower() in ("1", "true", "yes")


def is_verbose() -> bool:
    global _verbose
    if _verbose is None:
        _verbose = _env_verbose() or "--verbose" in sys.argv
    return _verbose


def set_verbose(value: bool) -> None:
    global _verbose
    _verbose = value
    os.environ["OIL_VERBOSE"] = "1" if value else "0"
    _apply_access_log_level()


def init_runtime_flags() -> None:
    """モジュール import 時に verbose 状態を確定し、アクセスログレベルを設定する。"""
    is_verbose()
    _apply_access_log_level()


def _apply_access_log_level() -> None:
    from app.log_noise import configure_uvicorn_access_log

    configure_uvicorn_access_log()
