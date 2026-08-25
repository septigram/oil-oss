"""ユーザ管理 API（ADMIN）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.auth.dependencies import require_admin
from app.auth.models import (
    CurrentUser,
    Role,
    UserCreateRequest,
    UserListItem,
    UserRolesUpdateRequest,
    UserUpdateRequest,
)
from app.repository.optimistic import OptimisticLockError
from app.repository.user import UserRepository

router = APIRouter(prefix="/api/admin/users", tags=["admin"])
_users = UserRepository()


@router.get("")
def list_users(_user: Annotated[CurrentUser, Depends(require_admin())]) -> dict:
    items = [
        UserListItem(
            user_id=u["user_id"],
            employee_id=u["employee_id"],
            employee_name=u["employee_name"],
            login_name=u["login_name"],
            is_active=u["is_active"],
            roles=u["roles"],
            row_version=u["row_version"],
        )
        for u in _users.list_users()
    ]
    return {"items": [i.model_dump() for i in items]}


@router.post("", status_code=201)
def create_user(
    body: UserCreateRequest,
    _user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    if _users.get_by_login_name(body.login_name):
        raise HTTPException(status_code=400, detail="login_name は既に使用されています")
    user = _users.create_user(
        employee_id=body.employee_id,
        login_name=body.login_name,
        password=body.password,
        roles=body.roles or [Role.OPERATOR],
    )
    return {
        "user_id": user["user_id"],
        "row_version": user["row_version"],
        "roles": [r.value for r in _users.list_roles(user["user_id"])],
    }


@router.put("/{user_id}")
def update_user(
    user_id: str,
    body: UserUpdateRequest,
    _user: Annotated[CurrentUser, Depends(require_admin())],
):
    try:
        updated = _users.update_user(
            user_id,
            row_version=body.row_version,
            is_active=body.is_active,
            password=body.password,
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
        raise HTTPException(status_code=404, detail="ユーザが見つかりません") from None
    return {"user_id": updated["user_id"], "row_version": updated["row_version"]}


@router.put("/{user_id}/roles")
def update_user_roles(
    user_id: str,
    body: UserRolesUpdateRequest,
    _user: Annotated[CurrentUser, Depends(require_admin())],
):
    if not body.roles:
        raise HTTPException(status_code=400, detail="ロールを 1 つ以上指定してください")
    try:
        updated = _users.update_roles(user_id, row_version=body.row_version, roles=body.roles)
    except OptimisticLockError as exc:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "conflict",
                "message": "他のユーザによって更新されました。最新の内容を読み込んでください。",
                "current": exc.current,
            },
        )
    return {
        "user_id": updated["user_id"],
        "row_version": updated["row_version"],
        "roles": [r.value for r in _users.list_roles(user_id)],
    }
