"""セッションリポジトリ。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.auth.session_token import new_session_id
from app.config import get_settings
from app.repository.tsurugi_conn import TsurugiConnection


class SessionRepository:
    def __init__(self, db: TsurugiConnection | None = None) -> None:
        self._db = db or TsurugiConnection()
        self._tz = ZoneInfo(get_settings().timezone)

    def _now(self) -> datetime:
        return datetime.now(tz=self._tz)

    def create(self, user_id: str, ttl_hours: int) -> str:
        session_id = new_session_id()
        now = self._now()
        expires_at = now + timedelta(hours=ttl_hours)
        self._db.execute(
            """
            INSERT INTO oil_sessions (session_id, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, user_id, expires_at, now),
        )
        return session_id

    def delete(self, session_id: str) -> None:
        self._db.execute("DELETE FROM oil_sessions WHERE session_id = ?", (session_id,))

    def get_valid(self, session_id: str) -> dict[str, Any] | None:
        row = self._db.fetchone(
            """
            SELECT session_id, user_id, expires_at
            FROM oil_sessions WHERE session_id = ?
            """,
            (session_id,),
        )
        if not row:
            return None
        expires_at: datetime = row[2]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=self._tz)
        if expires_at <= self._now():
            self.delete(session_id)
            return None
        return {"session_id": row[0], "user_id": row[1], "expires_at": expires_at}

    def purge_expired(self) -> int:
        now = self._now()
        return self._db.execute(
            "DELETE FROM oil_sessions WHERE expires_at <= ?",
            (now,),
        )
