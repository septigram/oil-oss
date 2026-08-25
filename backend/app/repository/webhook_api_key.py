"""Webhook API キーリポジトリ。"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.auth.password import hash_password, verify_password
from app.config import get_settings
from app.domain.id_gen import format_webhook_key_id, parse_webhook_key_sequence
from app.repository.tsurugi_conn import TsurugiConnection


class WebhookApiKeyRepository:
    def __init__(self, db: TsurugiConnection | None = None) -> None:
        self._db = db or TsurugiConnection()
        self._tz = ZoneInfo(get_settings().timezone)

    def _now(self) -> datetime:
        return datetime.now(tz=self._tz)

    def _next_key_id(self) -> str:
        rows = self._db.fetchall("SELECT key_id FROM oil_webhook_api_keys")
        max_seq = 0
        for row in rows:
            try:
                max_seq = max(max_seq, parse_webhook_key_sequence(row[0]))
            except ValueError:
                continue
        return format_webhook_key_id(max_seq + 1)

    @staticmethod
    def generate_plain_key() -> str:
        return f"oil_whk_{secrets.token_urlsafe(32)}"

    def list_keys(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT key_id, name, operator_employee_id, expires_at, is_active,
                   created_by_user_id, created_at, updated_at
            FROM oil_webhook_api_keys
            ORDER BY created_at DESC
            """
        )
        return [
            {
                "key_id": r[0],
                "name": r[1],
                "operator_employee_id": r[2],
                "expires_at": r[3],
                "is_active": int(r[4]) == 1,
                "created_by_user_id": r[5],
                "created_at": r[6],
                "updated_at": r[7],
            }
            for r in rows
        ]

    def get_by_id(self, key_id: str) -> dict[str, Any] | None:
        row = self._db.fetchone(
            """
            SELECT key_id, name, api_key_hash, operator_employee_id, expires_at, is_active,
                   created_by_user_id, created_at, updated_at
            FROM oil_webhook_api_keys WHERE key_id = ?
            """,
            (key_id,),
        )
        if not row:
            return None
        return {
            "key_id": row[0],
            "name": row[1],
            "api_key_hash": row[2],
            "operator_employee_id": row[3],
            "expires_at": row[4],
            "is_active": int(row[5]) == 1,
            "created_by_user_id": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }

    def create_key(
        self,
        *,
        name: str,
        operator_employee_id: str,
        created_by_user_id: str,
        expires_at: datetime | None = None,
    ) -> tuple[dict[str, Any], str]:
        plain = self.generate_plain_key()
        now = self._now()
        key_id = self._next_key_id()
        self._db.execute(
            """
            INSERT INTO oil_webhook_api_keys (
                key_id, name, api_key_hash, operator_employee_id, expires_at,
                is_active, created_by_user_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                key_id,
                name,
                hash_password(plain),
                operator_employee_id,
                expires_at,
                created_by_user_id,
                now,
                now,
            ),
        )
        item = self.get_by_id(key_id)
        assert item is not None
        return item, plain

    def update_key(
        self,
        key_id: str,
        *,
        name: str | None = None,
        operator_employee_id: str | None = None,
        expires_at: datetime | None = ...,  # type: ignore[assignment]
        is_active: bool | None = None,
    ) -> dict[str, Any] | None:
        current = self.get_by_id(key_id)
        if not current:
            return None
        new_name = name if name is not None else current["name"]
        new_operator = (
            operator_employee_id
            if operator_employee_id is not None
            else current["operator_employee_id"]
        )
        new_expires = current["expires_at"] if expires_at is ... else expires_at
        new_active = current["is_active"] if is_active is None else is_active
        now = self._now()
        self._db.execute(
            """
            UPDATE oil_webhook_api_keys
            SET name = ?, operator_employee_id = ?, expires_at = ?, is_active = ?, updated_at = ?
            WHERE key_id = ?
            """,
            (
                new_name,
                new_operator,
                new_expires,
                1 if new_active else 0,
                now,
                key_id,
            ),
        )
        return self.get_by_id(key_id)

    def deactivate(self, key_id: str) -> bool:
        updated = self.update_key(key_id, is_active=False)
        return updated is not None

    def verify_key(self, plain_key: str) -> dict[str, Any] | None:
        rows = self._db.fetchall(
            """
            SELECT key_id, name, api_key_hash, operator_employee_id, expires_at, is_active
            FROM oil_webhook_api_keys WHERE is_active = 1
            """
        )
        now = self._now()
        for row in rows:
            if not verify_password(plain_key, row[2]):
                continue
            expires_at = row[4]
            if expires_at is not None and expires_at <= now:
                continue
            return {
                "key_id": row[0],
                "name": row[1],
                "operator_employee_id": row[3],
            }
        return None
