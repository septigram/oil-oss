"""対応リポジトリ。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.id_gen import format_response_id, parse_response_sequence
from app.repository.optimistic import OptimisticLockError
from app.repository.schema_compat import has_column
from app.repository.tsurugi_conn import TsurugiConnection


class ResponseRepository:
    def __init__(self, db: TsurugiConnection | None = None) -> None:
        self._db = db or TsurugiConnection()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_row(self, incident_id: str, response_id: str) -> dict[str, Any] | None:
        if has_column("oil_incident_responses", "row_version"):
            row = self._db.fetchone(
                """
                SELECT response_id, summary, row_version, updated_at, updated_by_employee_id
                FROM oil_incident_responses
                WHERE incident_id = ? AND response_id = ?
                """,
                (incident_id, response_id),
            )
            if not row:
                return None
            return {
                "response_id": row[0],
                "summary": row[1],
                "row_version": int(row[2]),
                "updated_at": row[3],
                "updated_by_employee_id": row[4],
            }
        row = self._db.fetchone(
            """
            SELECT response_id, summary
            FROM oil_incident_responses
            WHERE incident_id = ? AND response_id = ?
            """,
            (incident_id, response_id),
        )
        if not row:
            return None
        return {"response_id": row[0], "summary": row[1], "row_version": 1}

    def _next_response_id(self) -> str:
        rows = self._db.fetchall("SELECT response_id FROM oil_incident_responses")
        max_seq = 0
        for row in rows:
            try:
                max_seq = max(max_seq, parse_response_sequence(row[0]))
            except ValueError:
                continue
        return format_response_id(max_seq + 1)

    def _next_sequence_no(self, incident_id: str) -> int:
        row = self._db.fetchone(
            "SELECT MAX(sequence_no) FROM oil_incident_responses WHERE incident_id = ?",
            (incident_id,),
        )
        if not row or row[0] is None:
            return 1
        return int(row[0]) + 1

    def create(
        self, incident_id: str, data: dict[str, Any], *, operator_id: str
    ) -> dict[str, Any]:
        response_id = self._next_response_id()
        sequence_no = self._next_sequence_no(incident_id)
        now = self._now()
        if has_column("oil_incident_responses", "row_version"):
            self._db.execute(
                """
                INSERT INTO oil_incident_responses (
                    response_id, incident_id, response_type, sequence_no, assignee_employee_id,
                    started_at, ended_at, summary, detail,
                    row_version, updated_at, updated_by_employee_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    response_id,
                    incident_id,
                    data["response_type"],
                    sequence_no,
                    operator_id,
                    data["started_at"],
                    data.get("ended_at"),
                    data["summary"],
                    data["detail"],
                    now,
                    operator_id,
                ),
            )
        else:
            self._db.execute(
                """
                INSERT INTO oil_incident_responses (
                    response_id, incident_id, response_type, sequence_no, assignee_employee_id,
                    started_at, ended_at, summary, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response_id,
                    incident_id,
                    data["response_type"],
                    sequence_no,
                    operator_id,
                    data["started_at"],
                    data.get("ended_at"),
                    data["summary"],
                    data["detail"],
                ),
            )
        return {
            "response_id": response_id,
            "sequence_no": sequence_no,
            "assignee_employee_id": operator_id,
            "row_version": 1,
        }

    def update(
        self,
        incident_id: str,
        response_id: str,
        data: dict[str, Any],
        *,
        row_version: int,
        operator_id: str,
    ) -> None:
        now = self._now()
        if has_column("oil_incident_responses", "row_version"):
            updated = self._db.execute(
                """
                UPDATE oil_incident_responses SET
                    response_type = ?, started_at = ?, ended_at = ?, summary = ?, detail = ?,
                    row_version = row_version + 1, updated_at = ?, updated_by_employee_id = ?
                WHERE incident_id = ? AND response_id = ? AND row_version = ?
                """,
                (
                    data["response_type"],
                    data["started_at"],
                    data.get("ended_at"),
                    data["summary"],
                    data["detail"],
                    now,
                    operator_id,
                    incident_id,
                    response_id,
                    row_version,
                ),
            )
            if updated == 0:
                current = self._get_row(incident_id, response_id)
                raise OptimisticLockError(current or {"response_id": response_id})
            return
        self._db.execute(
            """
            UPDATE oil_incident_responses SET
                response_type = ?, started_at = ?, ended_at = ?, summary = ?, detail = ?
            WHERE incident_id = ? AND response_id = ?
            """,
            (
                data["response_type"],
                data["started_at"],
                data.get("ended_at"),
                data["summary"],
                data["detail"],
                incident_id,
                response_id,
            ),
        )

    def exists(self, incident_id: str, response_id: str) -> bool:
        row = self._db.fetchone(
            "SELECT 1 FROM oil_incident_responses WHERE incident_id = ? AND response_id = ?",
            (incident_id, response_id),
        )
        return row is not None
