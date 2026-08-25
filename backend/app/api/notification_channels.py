"""通知チャネル API（OPERATOR 以上）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth.dependencies import require_operator_or_admin
from app.auth.models import CurrentUser
from app.repository.notification_channel import NotificationChannelRepository
from app.repository.optimistic import OptimisticLockError

router = APIRouter(prefix="/api/notification-channels", tags=["notification-channels"])
_channels = NotificationChannelRepository()


class NotificationChannelBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    webhook_url: str = Field(min_length=1, max_length=512)
    type_ids: list[str] = Field(default_factory=list)
    is_active: bool = True
    row_version: int | None = None


@router.get("")
def list_channels(
    _user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    return {"items": _channels.list_channels()}


@router.post("", status_code=201)
def create_channel(
    body: NotificationChannelBody,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> dict:
    item = _channels.create(
        name=body.name,
        webhook_url=body.webhook_url,
        type_ids=body.type_ids,
        is_active=body.is_active,
        operator_id=user.employee_id,
    )
    return item


@router.put("/{channel_id}")
def update_channel(
    channel_id: str,
    body: NotificationChannelBody,
    user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
):
    if body.row_version is None:
        raise HTTPException(status_code=400, detail="row_version が必要です")
    try:
        updated = _channels.update(
            channel_id,
            row_version=body.row_version,
            name=body.name,
            webhook_url=body.webhook_url,
            type_ids=body.type_ids,
            is_active=body.is_active,
            operator_id=user.employee_id,
        )
    except OptimisticLockError as exc:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "conflict",
                "message": "他のユーザによって更新されました。最新の内容を読み込んでください。",
                "current": exc.current,
            },
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="チャネルが見つかりません") from None
    return updated


@router.delete("/{channel_id}", status_code=204)
def delete_channel(
    channel_id: str,
    _user: Annotated[CurrentUser, Depends(require_operator_or_admin())],
) -> None:
    if not _channels.delete(channel_id):
        raise HTTPException(status_code=404, detail="チャネルが見つかりません")
