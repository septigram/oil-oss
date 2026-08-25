"""Webhook API キー認証。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException

from app.logging_config import log_event
from app.repository.webhook_api_key import WebhookApiKeyRepository

logger = logging.getLogger(__name__)
_keys = WebhookApiKeyRepository()


@dataclass
class WebhookApiKeyContext:
    key_id: str
    name: str
    operator_employee_id: str


async def verify_webhook_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> WebhookApiKeyContext:
    if not x_api_key or not x_api_key.strip():
        log_event(logger, event="webhook_auth_failed", reason="missing_key")
        raise HTTPException(status_code=401, detail="API キーが必要です")
    ctx = _keys.verify_key(x_api_key.strip())
    if not ctx:
        log_event(logger, event="webhook_auth_failed", reason="invalid_or_expired")
        raise HTTPException(status_code=401, detail="API キーが無効です")
    return WebhookApiKeyContext(
        key_id=ctx["key_id"],
        name=ctx["name"],
        operator_employee_id=ctx["operator_employee_id"],
    )
