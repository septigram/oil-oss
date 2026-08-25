"""セッション Cookie 署名。"""

from __future__ import annotations

import logging
import os
import uuid
from functools import lru_cache

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

logger = logging.getLogger(__name__)

SALT = "oil-session"


@lru_cache
def _serializer() -> URLSafeTimedSerializer | None:
    secret = os.getenv("OIL_SESSION_SECRET")
    if not secret:
        logger.warning("OIL_SESSION_SECRET is not set; session cookies cannot be signed securely")
        return None
    return URLSafeTimedSerializer(secret, salt=SALT)


def issue_session_token(session_id: str, max_age_seconds: int) -> str:
    ser = _serializer()
    if ser is None:
        return session_id
    return ser.dumps({"sid": session_id})


def parse_session_token(token: str, max_age_seconds: int) -> str | None:
    ser = _serializer()
    if ser is None:
        return token if _looks_like_uuid(token) else None
    try:
        data = ser.loads(token, max_age=max_age_seconds)
        sid = data.get("sid")
        return sid if isinstance(sid, str) else None
    except (BadSignature, SignatureExpired):
        return None


def new_session_id() -> str:
    return str(uuid.uuid4())


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
