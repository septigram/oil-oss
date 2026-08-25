"""Webhook API キーの単体テスト。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth.api_key import verify_webhook_api_key
from app.auth.password import hash_password, verify_password
from app.repository.webhook_api_key import WebhookApiKeyRepository


def test_generate_plain_key_prefix() -> None:
    plain = WebhookApiKeyRepository.generate_plain_key()
    assert plain.startswith("oil_whk_")


def test_bcrypt_roundtrip() -> None:
    plain = WebhookApiKeyRepository.generate_plain_key()
    hashed = hash_password(plain)
    assert verify_password(plain, hashed)
    assert not verify_password("wrong", hashed)


@pytest.mark.asyncio
async def test_verify_webhook_api_key_missing() -> None:
    with pytest.raises(HTTPException) as exc:
        await verify_webhook_api_key(x_api_key=None)
    assert exc.value.status_code == 401
