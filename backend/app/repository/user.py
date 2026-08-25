"""ユーザ・ロールリポジトリ。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.auth.models import Role
from app.auth.password import hash_password
from app.config import get_settings
from app.domain.id_gen import parse_user_sequence, format_user_id
from app.repository.tsurugi_conn import TsurugiConnection


class UserRepository:
    def __init__(self, db: TsurugiConnection | None = None) -> None:
        self._db = db or TsurugiConnection()
        self._tz = ZoneInfo(get_settings().timezone)

    def _now(self) -> datetime:
        return datetime.now(tz=self._tz)

    def _next_user_id(self) -> str:
        rows = self._db.fetchall("SELECT user_id FROM oil_users")
        max_seq = 0
        for row in rows:
            try:
                max_seq = max(max_seq, parse_user_sequence(row[0]))
            except ValueError:
                continue
        return format_user_id(max_seq + 1)

    def get_by_login_name(self, login_name: str) -> dict[str, Any] | None:
        row = self._db.fetchone(
            """
            SELECT user_id, employee_id, login_name, password_hash, is_active, row_version
            FROM oil_users WHERE login_name = ?
            """,
            (login_name,),
        )
        if not row:
            return None
        return {
            "user_id": row[0],
            "employee_id": row[1],
            "login_name": row[2],
            "password_hash": row[3],
            "is_active": int(row[4]) == 1,
            "row_version": int(row[5]),
        }

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        row = self._db.fetchone(
            """
            SELECT user_id, employee_id, login_name, password_hash, is_active, row_version,
                   created_at, updated_at
            FROM oil_users WHERE user_id = ?
            """,
            (user_id,),
        )
        if not row:
            return None
        return {
            "user_id": row[0],
            "employee_id": row[1],
            "login_name": row[2],
            "password_hash": row[3],
            "is_active": int(row[4]) == 1,
            "row_version": int(row[5]),
            "created_at": row[6],
            "updated_at": row[7],
        }

    def list_roles(self, user_id: str) -> list[Role]:
        rows = self._db.fetchall(
            "SELECT user_role FROM oil_user_roles WHERE user_id = ? ORDER BY user_role",
            (user_id,),
        )
        return [Role(r[0]) for r in rows]

    def get_employee_name(self, employee_id: str) -> str | None:
        row = self._db.fetchone(
            """
            SELECT employee_name FROM oil_personnel_history
            WHERE employee_id = ?
            ORDER BY effective_at DESC
            LIMIT 1
            """,
            (employee_id,),
        )
        return row[0] if row else None

    def list_users(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT u.user_id, u.employee_id, u.login_name, u.is_active, u.row_version
            FROM oil_users u ORDER BY u.user_id
            """
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            user_id = row[0]
            items.append(
                {
                    "user_id": user_id,
                    "employee_id": row[1],
                    "employee_name": self.get_employee_name(row[1]) or "",
                    "login_name": row[2],
                    "is_active": int(row[3]) == 1,
                    "row_version": int(row[4]),
                    "roles": [r.value for r in self.list_roles(user_id)],
                }
            )
        return items

    def create_user(
        self,
        *,
        employee_id: str,
        login_name: str,
        password: str,
        roles: list[Role],
    ) -> dict[str, Any]:
        user_id = self._next_user_id()
        now = self._now()
        self._db.execute(
            """
            INSERT INTO oil_users (
                user_id, employee_id, login_name, password_hash, is_active,
                row_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, 1, ?, ?)
            """,
            (user_id, employee_id, login_name, hash_password(password), now, now),
        )
        self.replace_roles(user_id, roles)
        user = self.get_by_id(user_id)
        assert user is not None
        return user

    def replace_roles(self, user_id: str, roles: list[Role]) -> None:
        self._db.execute("DELETE FROM oil_user_roles WHERE user_id = ?", (user_id,))
        for role in roles:
            self._db.execute(
                "INSERT INTO oil_user_roles (user_id, user_role) VALUES (?, ?)",
                (user_id, role.value),
            )

    def update_user(
        self,
        user_id: str,
        *,
        row_version: int,
        is_active: bool | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        current = self.get_by_id(user_id)
        if not current:
            raise ValueError("not_found")
        now = self._now()
        new_active = int(current["is_active"]) if is_active is None else int(is_active)
        new_hash = current["password_hash"] if password is None else hash_password(password)
        updated = self._db.execute(
            """
            UPDATE oil_users SET
                is_active = ?, password_hash = ?,
                row_version = row_version + 1, updated_at = ?
            WHERE user_id = ? AND row_version = ?
            """,
            (new_active, new_hash, now, user_id, row_version),
        )
        if updated == 0:
            from app.repository.optimistic import OptimisticLockError

            fresh = self.get_by_id(user_id)
            raise OptimisticLockError(fresh or {"user_id": user_id})
        fresh = self.get_by_id(user_id)
        assert fresh is not None
        return fresh

    def update_roles(
        self, user_id: str, *, row_version: int, roles: list[Role]
    ) -> dict[str, Any]:
        now = self._now()
        updated = self._db.execute(
            """
            UPDATE oil_users SET row_version = row_version + 1, updated_at = ?
            WHERE user_id = ? AND row_version = ?
            """,
            (now, user_id, row_version),
        )
        if updated == 0:
            from app.repository.optimistic import OptimisticLockError

            fresh = self.get_by_id(user_id)
            raise OptimisticLockError(fresh or {"user_id": user_id})
        self.replace_roles(user_id, roles)
        fresh = self.get_by_id(user_id)
        assert fresh is not None
        return fresh

    def count_users(self) -> int:
        row = self._db.fetchone("SELECT COUNT(*) FROM oil_users")
        return int(row[0]) if row else 0
