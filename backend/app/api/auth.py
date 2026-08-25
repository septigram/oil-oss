"""認証 API。"""

from __future__ import annotations

import logging

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth.dependencies import get_current_user, get_optional_user
from app.auth.models import CurrentUser, LoginRequest, UserSummaryResponse
from app.auth.password import verify_password
from app.auth.rate_limit import is_rate_limited, record_failed_attempt
from app.auth.session_token import issue_session_token
from app.config import get_settings
from app.logging_config import log_event
from app.repository.session import SessionRepository
from app.repository.user import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_users = UserRepository()
_sessions = SessionRepository()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> UserSummaryResponse:
    settings = get_settings()
    if not settings.auth.enabled:
        user = CurrentUser(
            user_id="USR-DUMMY",
            employee_id=settings.operator.employee_id,
            display_name=settings.operator.display_name,
            login_name=body.login_name,
            roles=[],
        )
        return UserSummaryResponse(
            user_id=user.user_id,
            employee_id=user.employee_id,
            display_name=user.display_name,
            roles=["ADMIN"],
        )

    ip = _client_ip(request)
    if is_rate_limited(ip, body.login_name):
        log_event(
            logger,
            event="auth_login_failed",
            login_name=body.login_name,
            reason="rate_limited",
        )
        raise HTTPException(status_code=429, detail="ログイン試行回数が多すぎます")

    _sessions.purge_expired()
    user_row = _users.get_by_login_name(body.login_name)
    if not user_row or not user_row["is_active"]:
        record_failed_attempt(ip, body.login_name)
        log_event(
            logger,
            event="auth_login_failed",
            login_name=body.login_name,
            reason="invalid_credentials",
        )
        raise HTTPException(status_code=401, detail="ログイン ID またはパスワードが正しくありません")

    if not verify_password(body.password, user_row["password_hash"]):
        record_failed_attempt(ip, body.login_name)
        log_event(
            logger,
            event="auth_login_failed",
            login_name=body.login_name,
            reason="invalid_credentials",
        )
        raise HTTPException(status_code=401, detail="ログイン ID またはパスワードが正しくありません")

    session_id = _sessions.create(user_row["user_id"], settings.auth.session_ttl_hours)
    max_age = settings.auth.session_ttl_hours * 3600
    token = issue_session_token(session_id, max_age)
    cookie_path = f"{settings.context_path}/"
    response.set_cookie(
        key=settings.auth.cookie_name,
        value=token,
        httponly=True,
        secure=settings.auth.secure_cookie,
        samesite="lax",
        path=cookie_path,
        max_age=max_age,
    )

    display_name = _users.get_employee_name(user_row["employee_id"]) or body.login_name
    roles = [r.value for r in _users.list_roles(user_row["user_id"])]
    log_event(
        logger,
        event="auth_login",
        user_id=user_row["user_id"],
        employee_id=user_row["employee_id"],
        login_name=body.login_name,
    )
    return UserSummaryResponse(
        user_id=user_row["user_id"],
        employee_id=user_row["employee_id"],
        display_name=display_name,
        roles=roles,
    )


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    settings = get_settings()
    if settings.auth.enabled:
        from app.auth.session_token import parse_session_token

        token = request.cookies.get(settings.auth.cookie_name)
        if token:
            max_age = settings.auth.session_ttl_hours * 3600
            session_id = parse_session_token(token, max_age)
            if session_id:
                session = _sessions.get_valid(session_id)
                if session:
                    _sessions.delete(session_id)
                    log_event(logger, event="auth_logout", user_id=session["user_id"])
        response.delete_cookie(
            key=settings.auth.cookie_name,
            path=f"{settings.context_path}/",
        )
    return {"status": "ok"}


@router.get("/me")
async def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> UserSummaryResponse:
    return UserSummaryResponse(
        user_id=user.user_id,
        employee_id=user.employee_id,
        display_name=user.display_name,
        roles=[r.value for r in user.roles],
    )
