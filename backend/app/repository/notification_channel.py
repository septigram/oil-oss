"""通知チャネルリポジトリ。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.domain.id_gen import format_channel_id, parse_channel_sequence
from app.repository.optimistic import OptimisticLockError
from app.repository.tsurugi_conn import TsurugiConnection


class NotificationChannelRepository:
    def __init__(self, db: TsurugiConnection | None = None) -> None:
        self._db = db or TsurugiConnection()
        self._tz = ZoneInfo(get_settings().timezone)

    def _now(self) -> datetime:
        return datetime.now(tz=self._tz)

    def _next_channel_id(self) -> str:
        rows = self._db.fetchall("SELECT channel_id FROM oil_notification_channels")
        max_seq = 0
        for row in rows:
            try:
                max_seq = max(max_seq, parse_channel_sequence(row[0]))
            except ValueError:
                continue
        return format_channel_id(max_seq + 1)

    def _type_ids_for(self, channel_id: str) -> list[str]:
        rows = self._db.fetchall(
            "SELECT type_id FROM oil_notification_channel_types WHERE channel_id = ? ORDER BY type_id",
            (channel_id,),
        )
        return [r[0] for r in rows]

    def _replace_types(self, channel_id: str, type_ids: list[str]) -> None:
        self._db.execute(
            "DELETE FROM oil_notification_channel_types WHERE channel_id = ?",
            (channel_id,),
        )
        for type_id in type_ids:
            self._db.execute(
                "INSERT INTO oil_notification_channel_types (channel_id, type_id) VALUES (?, ?)",
                (channel_id, type_id),
            )

    def list_channels(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT channel_id, name, webhook_url, is_active, row_version,
                   created_at, updated_at, updated_by_employee_id
            FROM oil_notification_channels
            ORDER BY name
            """
        )
        items = []
        for r in rows:
            items.append(
                {
                    "channel_id": r[0],
                    "name": r[1],
                    "webhook_url": r[2],
                    "is_active": int(r[3]) == 1,
                    "row_version": int(r[4]),
                    "created_at": r[5],
                    "updated_at": r[6],
                    "updated_by_employee_id": r[7],
                    "type_ids": self._type_ids_for(r[0]),
                }
            )
        return items

    def get_by_id(self, channel_id: str) -> dict[str, Any] | None:
        row = self._db.fetchone(
            """
            SELECT channel_id, name, webhook_url, is_active, row_version,
                   created_at, updated_at, updated_by_employee_id
            FROM oil_notification_channels WHERE channel_id = ?
            """,
            (channel_id,),
        )
        if not row:
            return None
        return {
            "channel_id": row[0],
            "name": row[1],
            "webhook_url": row[2],
            "is_active": int(row[3]) == 1,
            "row_version": int(row[4]),
            "created_at": row[5],
            "updated_at": row[6],
            "updated_by_employee_id": row[7],
            "type_ids": self._type_ids_for(channel_id),
        }

    def list_active_for_type(self, type_id: str) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT c.channel_id, c.name, c.webhook_url
            FROM oil_notification_channels c
            INNER JOIN oil_notification_channel_types t ON c.channel_id = t.channel_id
            WHERE t.type_id = ? AND c.is_active = 1
            ORDER BY c.name
            """,
            (type_id,),
        )
        return [{"channel_id": r[0], "name": r[1], "webhook_url": r[2]} for r in rows]

    def create(
        self,
        *,
        name: str,
        webhook_url: str,
        type_ids: list[str],
        is_active: bool,
        operator_id: str,
    ) -> dict[str, Any]:
        now = self._now()
        channel_id = self._next_channel_id()
        self._db.execute(
            """
            INSERT INTO oil_notification_channels (
                channel_id, name, webhook_url, is_active, row_version,
                created_at, updated_at, updated_by_employee_id
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                channel_id,
                name,
                webhook_url,
                1 if is_active else 0,
                now,
                now,
                operator_id,
            ),
        )
        self._replace_types(channel_id, type_ids)
        item = self.get_by_id(channel_id)
        assert item is not None
        return item

    def update(
        self,
        channel_id: str,
        *,
        row_version: int,
        name: str,
        webhook_url: str,
        type_ids: list[str],
        is_active: bool,
        operator_id: str,
    ) -> dict[str, Any]:
        current = self.get_by_id(channel_id)
        if not current:
            raise ValueError("channel not found")
        if current["row_version"] != row_version:
            raise OptimisticLockError(current=current)
        now = self._now()
        new_version = row_version + 1
        self._db.execute(
            """
            UPDATE oil_notification_channels
            SET name = ?, webhook_url = ?, is_active = ?, row_version = ?,
                updated_at = ?, updated_by_employee_id = ?
            WHERE channel_id = ? AND row_version = ?
            """,
            (
                name,
                webhook_url,
                1 if is_active else 0,
                new_version,
                now,
                operator_id,
                channel_id,
                row_version,
            ),
        )
        self._replace_types(channel_id, type_ids)
        updated = self.get_by_id(channel_id)
        assert updated is not None
        return updated

    def delete(self, channel_id: str) -> bool:
        if not self.get_by_id(channel_id):
            return False
        self._db.execute(
            "DELETE FROM oil_notification_channel_types WHERE channel_id = ?",
            (channel_id,),
        )
        self._db.execute(
            "DELETE FROM oil_notification_channels WHERE channel_id = ?",
            (channel_id,),
        )
        return True
