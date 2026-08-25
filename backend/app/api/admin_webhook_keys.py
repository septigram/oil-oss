"""Webhook API キー管理 API（ADMIN）。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import require_admin
from app.auth.models import CurrentUser
from app.repository.webhook_api_key import WebhookApiKeyRepository

router = APIRouter(prefix="/api/admin/webhook-api-keys", tags=["admin-webhook-keys"])
_keys = WebhookApiKeyRepository()


class WebhookApiKeyCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    operator_employee_id: str = Field(min_length=1, max_length=16)
    expires_at: datetime | None = None


class WebhookApiKeyUpdateBody(BaseModel):
    name: str | None = None
    operator_employee_id: str | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None


@router.get("")
def list_webhook_api_keys(
    _user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    items = _keys.list_keys()
    return {"items": items}


@router.post("", status_code=201)
def create_webhook_api_key(
    body: WebhookApiKeyCreateBody,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    item, plain = _keys.create_key(
        name=body.name,
        operator_employee_id=body.operator_employee_id,
        created_by_user_id=user.user_id,
        expires_at=body.expires_at,
    )
    return {
        "key_id": item["key_id"],
        "name": item["name"],
        "operator_employee_id": item["operator_employee_id"],
        "expires_at": item["expires_at"],
        "is_active": item["is_active"],
        "api_key": plain,
    }


@router.put("/{key_id}")
def update_webhook_api_key(
    key_id: str,
    body: WebhookApiKeyUpdateBody,
    _user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    updated = _keys.update_key(
        key_id,
        name=body.name,
        operator_employee_id=body.operator_employee_id,
        expires_at=body.expires_at,
        is_active=body.is_active,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="API キーが見つかりません")
    return {
        "key_id": updated["key_id"],
        "name": updated["name"],
        "operator_employee_id": updated["operator_employee_id"],
        "expires_at": updated["expires_at"],
        "is_active": updated["is_active"],
    }


@router.delete("/{key_id}", status_code=204)
def delete_webhook_api_key(
    key_id: str,
    _user: Annotated[CurrentUser, Depends(require_admin())],
) -> None:
    if not _keys.deactivate(key_id):
        raise HTTPException(status_code=404, detail="API キーが見つかりません")
