"""対応手順書リポジトリ。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.id_gen import format_procedure_id, parse_procedure_sequence
from app.repository.incident import IncidentRepository
from app.repository.master import MasterRepository
from app.repository.optimistic import OptimisticLockError
from app.repository.schema_compat import has_column
from app.repository.tsurugi_conn import TsurugiConnection

_SEVERITY_TO_IMPORTANCE = {
    "CRITICAL": "HIGH",
    "HIGH": "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW": "LOW",
}

MAX_LIST_PAGE_SIZE = 100


class ProcedureSearchParams:
    def __init__(
        self,
        *,
        keyword: str | None = None,
        procedure_id: str | None = None,
        type_id: str | None = None,
        tags: str | None = None,
        is_active: bool | None = True,
        procedure_ids: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "-updated_at",
        skip_pagination: bool = False,
    ) -> None:
        self.keyword = keyword
        self.procedure_id = procedure_id
        self.type_id = type_id
        self.tags = tags
        self.is_active = is_active
        self.procedure_ids = procedure_ids
        self.page = page
        self.page_size = page_size
        self.sort = sort
        self.skip_pagination = skip_pagination


def _success_rate(usage_count: int, success_count: int) -> float | None:
    if usage_count <= 0:
        return None
    return round(success_count / usage_count * 100, 1)


def _row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    usage = int(row[11])
    success = int(row[12])
    return {
        "procedure_id": row[0],
        "title": row[1],
        "problem_description": row[2],
        "type_id": row[3],
        "importance": row[4],
        "procedure_steps": row[5],
        "required_tools": row[6],
        "precautions": row[7],
        "estimated_time": row[8],
        "source_incident_id": row[9],
        "tags": row[10],
        "usage_count": usage,
        "success_count": success,
        "success_rate": _success_rate(usage, success),
        "is_active": bool(row[13]),
        "created_by_employee_id": row[14],
        "created_at": row[15],
        "updated_by_employee_id": row[16],
        "updated_at": row[17],
        "row_version": int(row[18]) if len(row) > 18 and row[18] is not None else 1,
    }


_PROCEDURE_COLUMNS = """
    procedure_id, title, problem_description, type_id, importance,
    procedure_steps, required_tools, precautions, estimated_time,
    source_incident_id, tags, usage_count, success_count, is_active,
    created_by_employee_id, created_at, updated_by_employee_id, updated_at
"""

_PROCEDURE_COLUMNS_WITH_VERSION = _PROCEDURE_COLUMNS + ", row_version"


def _procedure_select_columns() -> str:
    if has_column("oil_procedures", "row_version"):
        return _PROCEDURE_COLUMNS_WITH_VERSION
    return _PROCEDURE_COLUMNS


class ProcedureRepository:
    def __init__(
        self,
        db: TsurugiConnection | None = None,
        master: MasterRepository | None = None,
        incidents: IncidentRepository | None = None,
    ) -> None:
        self._db = db or TsurugiConnection()
        self._master = master or MasterRepository(self._db)
        self._incidents = incidents or IncidentRepository(self._db, self._master)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _next_procedure_id(self) -> str:
        rows = self._db.fetchall("SELECT procedure_id FROM oil_procedures")
        max_seq = 0
        for row in rows:
            try:
                max_seq = max(max_seq, parse_procedure_sequence(row[0]))
            except ValueError:
                continue
        return format_procedure_id(max_seq + 1)

    def _next_link_id(self) -> int:
        row = self._db.fetchone("SELECT MAX(id) FROM oil_incident_procedures")
        if not row or row[0] is None:
            return 1
        return int(row[0]) + 1

    def _build_where(self, params: ProcedureSearchParams) -> tuple[str, list[Any]]:
        clauses: list[str] = ["1=1"]
        values: list[Any] = []
        if params.keyword:
            kw = f"%{params.keyword}%"
            clauses.append(
                "(title LIKE ? OR problem_description LIKE ? OR procedure_steps LIKE ?)"
            )
            values.extend([kw, kw, kw])
        if params.procedure_id:
            clauses.append("procedure_id = ?")
            values.append(params.procedure_id)
        if params.type_id:
            clauses.append("type_id = ?")
            values.append(params.type_id)
        if params.tags:
            clauses.append("tags LIKE ?")
            values.append(f"%{params.tags}%")
        if params.is_active is not None:
            clauses.append("is_active = ?")
            values.append(1 if params.is_active else 0)
        if params.procedure_ids is not None:
            if not params.procedure_ids:
                clauses.append("1=0")
            else:
                placeholders = ",".join("?" for _ in params.procedure_ids)
                clauses.append(f"procedure_id IN ({placeholders})")
                values.extend(params.procedure_ids)
        return " AND ".join(clauses), values

    def _order_clause(self, sort: str) -> str:
        mapping = {
            "-usage_count": "ORDER BY usage_count DESC, updated_at DESC",
            "usage_count": "ORDER BY usage_count ASC, updated_at DESC",
            "-success_rate": "ORDER BY CASE WHEN usage_count > 0 THEN success_count * 1.0 / usage_count ELSE 0 END DESC, updated_at DESC",
            "success_rate": "ORDER BY CASE WHEN usage_count > 0 THEN success_count * 1.0 / usage_count ELSE 0 END ASC, updated_at DESC",
            "-updated_at": "ORDER BY updated_at DESC",
            "updated_at": "ORDER BY updated_at ASC",
        }
        return mapping.get(sort, "ORDER BY updated_at DESC")

    def search(self, params: ProcedureSearchParams) -> tuple[list[dict[str, Any]], int]:
        if params.procedure_ids is not None and not params.procedure_ids:
            return [], 0

        where, values = self._build_where(params)
        count_row = self._db.fetchone(
            f"SELECT COUNT(*) FROM oil_procedures WHERE {where}",
            tuple(values),
        )
        total = int(count_row[0]) if count_row else 0

        page_size = max(1, min(int(params.page_size), MAX_LIST_PAGE_SIZE))
        offset = (max(1, int(params.page)) - 1) * page_size
        limit_clause = ""
        if not params.skip_pagination:
            fetch_limit = offset + page_size
            limit_clause = f" LIMIT {fetch_limit}"

        rows = self._db.fetchall(
            f"""
            SELECT {_procedure_select_columns()}
            FROM oil_procedures
            WHERE {where}
            {self._order_clause(params.sort)}
            {limit_clause}
            """,
            tuple(values),
        )
        page_rows = rows if params.skip_pagination else rows[offset : offset + page_size]
        return [_row_to_dict(r) for r in page_rows], total

    def get_by_id(self, procedure_id: str) -> dict[str, Any] | None:
        row = self._db.fetchone(
            f"SELECT {_procedure_select_columns()} FROM oil_procedures WHERE procedure_id = ?",
            (procedure_id,),
        )
        if not row:
            return None
        data = _row_to_dict(row)
        data["type_name"] = self._master.get_type_name(data["type_id"]) or ""
        return data

    def exists(self, procedure_id: str) -> bool:
        row = self._db.fetchone(
            "SELECT 1 FROM oil_procedures WHERE procedure_id = ?",
            (procedure_id,),
        )
        return row is not None

    def create(self, data: dict[str, Any], *, operator_id: str) -> str:
        procedure_id = self._next_procedure_id()
        now = self._now()
        if has_column("oil_procedures", "row_version"):
            self._db.execute(
                """
                INSERT INTO oil_procedures (
                    procedure_id, title, problem_description, type_id, importance,
                    procedure_steps, required_tools, precautions, estimated_time,
                    source_incident_id, tags, usage_count, success_count, is_active,
                    created_by_employee_id, created_at, updated_by_employee_id, updated_at,
                    row_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, 1)
                """,
                (
                    procedure_id,
                    data["title"],
                    data["problem_description"],
                    data["type_id"],
                    data.get("importance"),
                    data["procedure_steps"],
                    data.get("required_tools"),
                    data.get("precautions"),
                    data.get("estimated_time"),
                    data.get("source_incident_id"),
                    data.get("tags"),
                    1 if data.get("is_active", True) else 0,
                    operator_id,
                    now,
                    operator_id,
                    now,
                ),
            )
        else:
            self._db.execute(
                """
                INSERT INTO oil_procedures (
                    procedure_id, title, problem_description, type_id, importance,
                    procedure_steps, required_tools, precautions, estimated_time,
                    source_incident_id, tags, usage_count, success_count, is_active,
                    created_by_employee_id, created_at, updated_by_employee_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?)
                """,
                (
                    procedure_id,
                    data["title"],
                    data["problem_description"],
                    data["type_id"],
                    data.get("importance"),
                    data["procedure_steps"],
                    data.get("required_tools"),
                    data.get("precautions"),
                    data.get("estimated_time"),
                    data.get("source_incident_id"),
                    data.get("tags"),
                    1 if data.get("is_active", True) else 0,
                    operator_id,
                    now,
                    operator_id,
                    now,
                ),
            )
        return procedure_id

    def update(
        self,
        procedure_id: str,
        data: dict[str, Any],
        *,
        row_version: int,
        operator_id: str,
    ) -> None:
        now = self._now()
        if has_column("oil_procedures", "row_version"):
            updated = self._db.execute(
                """
                UPDATE oil_procedures SET
                    title = ?, problem_description = ?, type_id = ?, importance = ?,
                    procedure_steps = ?, required_tools = ?, precautions = ?,
                    estimated_time = ?, source_incident_id = ?, tags = ?, is_active = ?,
                    updated_by_employee_id = ?, updated_at = ?,
                    row_version = row_version + 1
                WHERE procedure_id = ? AND row_version = ?
                """,
                (
                    data["title"],
                    data["problem_description"],
                    data["type_id"],
                    data.get("importance"),
                    data["procedure_steps"],
                    data.get("required_tools"),
                    data.get("precautions"),
                    data.get("estimated_time"),
                    data.get("source_incident_id"),
                    data.get("tags"),
                    1 if data.get("is_active", True) else 0,
                    operator_id,
                    now,
                    procedure_id,
                    row_version,
                ),
            )
            if updated == 0:
                current = self.get_by_id(procedure_id)
                raise OptimisticLockError(current or {"procedure_id": procedure_id})
            return
        self._db.execute(
            """
            UPDATE oil_procedures SET
                title = ?, problem_description = ?, type_id = ?, importance = ?,
                procedure_steps = ?, required_tools = ?, precautions = ?,
                estimated_time = ?, source_incident_id = ?, tags = ?, is_active = ?,
                updated_by_employee_id = ?, updated_at = ?
            WHERE procedure_id = ?
            """,
            (
                data["title"],
                data["problem_description"],
                data["type_id"],
                data.get("importance"),
                data["procedure_steps"],
                data.get("required_tools"),
                data.get("precautions"),
                data.get("estimated_time"),
                data.get("source_incident_id"),
                data.get("tags"),
                1 if data.get("is_active", True) else 0,
                operator_id,
                now,
                procedure_id,
            ),
        )

    def apply_to_incident(
        self,
        incident_id: str,
        procedure_id: str,
        notes: str | None = None,
        *,
        operator_id: str,
    ) -> dict[str, Any]:
        if not self.exists(procedure_id):
            raise ValueError("procedure not found")
        link_id = self._next_link_id()
        now = self._now()
        self._db.execute(
            """
            INSERT INTO oil_incident_procedures (
                id, incident_id, procedure_id, applied_at,
                applied_by_employee_id, was_successful, notes
            ) VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (link_id, incident_id, procedure_id, now, operator_id, notes),
        )
        self._db.execute(
            "UPDATE oil_procedures SET usage_count = usage_count + 1 WHERE procedure_id = ?",
            (procedure_id,),
        )
        return {"id": link_id, "procedure_id": procedure_id, "applied_at": now}

    def list_by_incident(self, incident_id: str) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT ip.id, ip.procedure_id, ip.applied_at, ip.applied_by_employee_id,
                   ip.was_successful, ip.notes,
                   p.title, p.usage_count, p.success_count
            FROM oil_incident_procedures ip
            JOIN oil_procedures p ON ip.procedure_id = p.procedure_id
            WHERE ip.incident_id = ?
            ORDER BY ip.applied_at DESC
            """,
            (incident_id,),
        )
        return [
            {
                "id": r[0],
                "procedure_id": r[1],
                "applied_at": r[2],
                "applied_by_employee_id": r[3],
                "was_successful": r[4],
                "notes": r[5],
                "title": r[6],
                "usage_count": int(r[7]),
                "success_count": int(r[8]),
            }
            for r in rows
        ]

    def list_incidents_by_procedure(self, procedure_id: str) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT ip.incident_id, ip.applied_at, ip.was_successful, ip.notes,
                   i.title, i.status, i.occurred_at
            FROM oil_incident_procedures ip
            JOIN oil_incidents i ON ip.incident_id = i.incident_id
            WHERE ip.procedure_id = ?
            ORDER BY ip.applied_at DESC
            """,
            (procedure_id,),
        )
        return [
            {
                "incident_id": r[0],
                "applied_at": r[1],
                "was_successful": r[2],
                "notes": r[3],
                "title": r[4],
                "status": r[5],
                "occurred_at": r[6],
            }
            for r in rows
        ]

    def update_was_successful(
        self,
        link_id: int,
        was_successful: bool,
        notes: str | None = None,
    ) -> None:
        row = self._db.fetchone(
            """
            SELECT procedure_id, was_successful
            FROM oil_incident_procedures WHERE id = ?
            """,
            (link_id,),
        )
        if not row:
            raise ValueError("link not found")
        procedure_id, prev = row[0], row[1]
        prev_bool = bool(prev) if prev is not None else False
        val = 1 if was_successful else 0
        self._db.execute(
            """
            UPDATE oil_incident_procedures
            SET was_successful = ?, notes = COALESCE(?, notes)
            WHERE id = ?
            """,
            (val, notes, link_id),
        )
        if was_successful and not prev_bool:
            self._db.execute(
                "UPDATE oil_procedures SET success_count = success_count + 1 WHERE procedure_id = ?",
                (procedure_id,),
            )
        elif not was_successful and prev_bool:
            self._db.execute(
                """
                UPDATE oil_procedures
                SET success_count = CASE WHEN success_count > 0 THEN success_count - 1 ELSE 0 END
                WHERE procedure_id = ?
                """,
                (procedure_id,),
            )

    def unlink_from_incident(self, incident_id: str, link_id: int) -> None:
        row = self._db.fetchone(
            """
            SELECT incident_id, procedure_id, was_successful
            FROM oil_incident_procedures WHERE id = ?
            """,
            (link_id,),
        )
        if not row or row[0] != incident_id:
            raise ValueError("link not found")
        procedure_id, was_successful = row[1], row[2]
        self._db.execute(
            "DELETE FROM oil_incident_procedures WHERE id = ?",
            (link_id,),
        )
        self._db.execute(
            """
            UPDATE oil_procedures
            SET usage_count = CASE WHEN usage_count > 0 THEN usage_count - 1 ELSE 0 END
            WHERE procedure_id = ?
            """,
            (procedure_id,),
        )
        if was_successful:
            self._db.execute(
                """
                UPDATE oil_procedures
                SET success_count = CASE WHEN success_count > 0 THEN success_count - 1 ELSE 0 END
                WHERE procedure_id = ?
                """,
                (procedure_id,),
            )

    def get_procedure_ids_for_incidents(self, incident_ids: list[str]) -> dict[str, list[str]]:
        if not incident_ids:
            return {}
        result: dict[str, list[str]] = {iid: [] for iid in incident_ids}
        for iid in incident_ids:
            rows = self._db.fetchall(
                "SELECT DISTINCT procedure_id FROM oil_incident_procedures WHERE incident_id = ?",
                (iid,),
            )
            result[iid] = [r[0] for r in rows]
        return result

    def has_source_incident(self, incident_id: str) -> bool:
        row = self._db.fetchone(
            "SELECT 1 FROM oil_procedures WHERE source_incident_id = ? LIMIT 1",
            (incident_id,),
        )
        return row is not None

    def build_from_incident(self, incident_id: str) -> dict[str, Any]:
        detail = self._incidents.get_detail(incident_id)
        if not detail:
            raise ValueError("incident not found")
        inc = detail["incident"]
        if inc["status"] != "RESOLVED":
            raise ValueError("incident must be RESOLVED")

        problem_parts = [inc["description"]]
        inv = detail.get("investigation")
        if inv:
            if inv.get("root_cause_summary"):
                problem_parts.append(inv["root_cause_summary"])
            if inv.get("investigation_detail"):
                problem_parts.append(inv["investigation_detail"])
        problem_description = "\n\n".join(problem_parts)

        step_lines: list[str] = []
        for resp in detail.get("responses") or []:
            seq = resp.get("sequence_no", 0)
            summary = resp.get("summary") or ""
            detail_text = resp.get("detail") or ""
            block = f"## ステップ {seq}: {summary}"
            if detail_text:
                block += f"\n{detail_text}"
            step_lines.append(block)
        procedure_steps = "\n\n".join(step_lines) if step_lines else "（対応履歴なし）"

        importance = _SEVERITY_TO_IMPORTANCE.get(inc.get("severity", "MEDIUM"), "MEDIUM")

        return {
            "title": inc["title"][:100],
            "problem_description": problem_description[:16384],
            "type_id": inc["type_id"],
            "importance": importance,
            "procedure_steps": procedure_steps[:16384],
            "required_tools": None,
            "precautions": "",
            "estimated_time": None,
            "source_incident_id": incident_id,
            "tags": None,
            "is_active": True,
        }

    def list_resolved_for_batch(
        self,
        *,
        min_responses: int = 1,
        min_content_chars: int = 200,
        skip_existing: bool = True,
        limit: int = 50,
        incident_id: str | None = None,
    ) -> list[str]:
        if incident_id:
            return [incident_id]
        rows = self._db.fetchall(
            """
            SELECT i.incident_id, i.title, i.description,
                   (SELECT COUNT(*) FROM oil_incident_responses r WHERE r.incident_id = i.incident_id) AS rc
            FROM oil_incidents i
            WHERE i.status = 'RESOLVED'
            ORDER BY i.occurred_at DESC
            """
        )
        candidates: list[str] = []
        for row in rows:
            iid, title, desc, rc = row[0], row[1], row[2], int(row[3])
            if rc < min_responses:
                continue
            inv_row = self._db.fetchone(
                "SELECT root_cause_summary, investigation_detail FROM oil_incident_investigations WHERE incident_id = ?",
                (iid,),
            )
            inv_text = ""
            if inv_row:
                inv_text = (inv_row[0] or "") + (inv_row[1] or "")
            if len(title) + len(desc) + len(inv_text) < min_content_chars:
                continue
            if skip_existing and self.has_source_incident(iid):
                continue
            candidates.append(iid)
            if len(candidates) >= limit:
                break
        return candidates

    def load_all_active(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            f"SELECT {_PROCEDURE_COLUMNS} FROM oil_procedures WHERE is_active = 1"
        )
        return [_row_to_dict(r) for r in rows]
