"""認証 FastAPI 依存。"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request

from app.auth.models import CurrentUser, Role
from app.config import get_settings
from app.logging_config import log_event
from app.repository.session import SessionRepository
from app.repository.user import UserRepository

logger = logging.getLogger(__name__)

_users = UserRepository()
_sessions = SessionRepository()


def _dummy_user() -> CurrentUser:
    op = get_settings().operator
    return CurrentUser(
        user_id="USR-DUMMY",
        employee_id=op.employee_id,
        display_name=op.display_name,
        login_name="operator",
        roles=[Role.ADMIN, Role.OPERATOR, Role.VIEWER],
    )


def _user_from_session(session_id: str) -> CurrentUser | None:
    session = _sessions.get_valid(session_id)
    if not session:
        return None
    user = _users.get_by_id(session["user_id"])
    if not user or not user["is_active"]:
        return None
    display_name = _users.get_employee_name(user["employee_id"]) or user["login_name"]
    roles = _users.list_roles(user["user_id"])
    if not roles:
        roles = [Role.VIEWER]
    return CurrentUser(
        user_id=user["user_id"],
        employee_id=user["employee_id"],
        display_name=display_name,
        login_name=user["login_name"],
        roles=roles,
    )


async def get_current_user(
    request: Request,
    session_cookie: Annotated[str | None, Cookie()] = None,
) -> CurrentUser:
    settings = get_settings()
    if not settings.auth.enabled:
        return _dummy_user()

    cookie_name = settings.auth.cookie_name
    token = request.cookies.get(cookie_name) or session_cookie
    if not token:
        raise HTTPException(status_code=401, detail="認証が必要です")

    from app.auth.session_token import parse_session_token

    max_age = settings.auth.session_ttl_hours * 3600
    session_id = parse_session_token(token, max_age)
    if not session_id:
        raise HTTPException(status_code=401, detail="セッションが無効です")

    user = _user_from_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="セッションが無効です")
    return user


async def get_optional_user(
    request: Request,
    session_cookie: Annotated[str | None, Cookie()] = None,
) -> CurrentUser | None:
    settings = get_settings()
    if not settings.auth.enabled:
        return _dummy_user()
    try:
        return await get_current_user(request, session_cookie)
    except HTTPException:
        return None


def require_roles(*roles: Role):
    async def _checker(
        request: Request,
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if user.has_any_role(*roles):
            return user
        log_event(
            logger,
            event="auth_denied",
            user_id=user.user_id,
            required_roles=[r.value for r in roles],
            path=str(request.url.path),
        )
        raise HTTPException(status_code=403, detail="権限がありません")

    return _checker


def require_operator_or_admin():
    return require_roles(Role.ADMIN, Role.OPERATOR)


def require_admin():
    return require_roles(Role.ADMIN)


def require_any_authenticated():
    return get_current_user
