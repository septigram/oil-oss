"""構造化ログ。"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.config import get_observability_env, get_observability_version
from app.request_context import get_request_id

LOG_TIMEZONE = ZoneInfo("Asia/Tokyo")
SERVICE_NAME = "oil"


def _base_log_fields() -> dict[str, Any]:
    fields: dict[str, Any] = {
        "service": SERVICE_NAME,
        "env": get_observability_env(),
        "version": get_observability_version(),
    }
    request_id = get_request_id()
    if request_id:
        fields["request_id"] = request_id
    try:
        from app.observability.tracing import get_trace_log_fields

        fields.update(get_trace_log_fields())
    except ImportError:
        pass
    return fields


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=LOG_TIMEZONE).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            payload.update(record.extra_data)
        if record.exc_info and record.exc_info[1] is not None:
            exc_type, exc_value, _ = record.exc_info
            payload["exception_type"] = exc_type.__name__ if exc_type else None
            payload["exception_message"] = str(exc_value)
            payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(*, force: bool = False) -> None:
    """`app.*` ロガーを stderr に JSON 出力する。

    環境変数 ``OIL_LOG_FILE`` が設定されていれば、``log_event`` の JSON を UTF-8 ファイルにも追記する
    （Loki / promtail 向け。verbose の有無は問わない）。

    ``api_timing`` および Uvicorn HTTP アクセスログは通常時も出力するが、
    LogPanel がポーリングする ``/api/logs/recent`` 等は verbose 時のみ出す（``log_noise`` 参照）。

    uvicorn --reload の子プロセスでは stdout がコンソールに届かないことがあるため stderr を使う。
    """
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

    app_logger = logging.getLogger("app")
    if not force and any(isinstance(h.formatter, JsonFormatter) for h in app_logger.handlers):
        return
    if force:
        app_logger.handlers.clear()

    formatter = JsonFormatter()

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    app_logger.addHandler(stderr_handler)

    log_file = os.environ.get("OIL_LOG_FILE", "").strip()
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        app_logger.addHandler(file_handler)

    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    ts = datetime.now(LOG_TIMEZONE).isoformat(timespec="milliseconds")
    payload = {"event": event, "ts": ts, **_base_log_fields(), **fields}
    logger.info(event, extra={"extra_data": payload})
    from app.log_buffer import append_log_entry

    append_log_entry(payload)
