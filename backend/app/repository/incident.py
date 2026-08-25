"""インシデントリポジトリ。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.domain.id_gen import format_incident_id, parse_incident_sequence
from app.domain.models import IncidentStatus, status_display_label
from app.repository.master import MasterRepository
from app.repository.optimistic import OptimisticLockError
from app.repository.schema_compat import has_column
from app.repository.tsurugi_conn import TsurugiConnection

COMPANY_ID = "COMP-001"
MAX_AGGREGATE_LIMIT = 1000
MAX_LIST_PAGE_SIZE = 100


def _problem_management_no_value(data: dict[str, Any]) -> str | None:
    if not has_column("oil_incidents", "problem_management_no"):
        return None
    raw = data.get("problem_management_no")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _incident_select_columns() -> list[str]:
    cols = [
        "incident_id",
        "company_id",
        "type_id",
        "occurred_at",
        "detected_at",
        "title",
        "description",
        "location_name",
        "affected_service_ids",
        "detector_employee_id",
        "detector_department_id",
        "severity",
        "status",
        "detection_source",
        "related_event_id",
    ]
    if has_column("oil_incidents", "problem_management_no"):
        cols.append("problem_management_no")
    if has_column("oil_incidents", "row_version"):
        cols.extend(["row_version", "updated_at", "updated_by_employee_id"])
    return cols


def _row_to_incident(row: tuple[Any, ...], cols: list[str]) -> dict[str, Any]:
    data = dict(zip(cols, row, strict=True))
    service_ids = [s for s in str(data["affected_service_ids"]).split(";") if s]
    result: dict[str, Any] = {
        "incident_id": data["incident_id"],
        "company_id": data["company_id"],
        "type_id": data["type_id"],
        "occurred_at": data["occurred_at"],
        "detected_at": data["detected_at"],
        "title": data["title"],
        "description": data["description"],
        "location_name": data["location_name"],
        "affected_service_ids": service_ids,
        "detector_employee_id": data["detector_employee_id"],
        "detector_department_id": data["detector_department_id"],
        "severity": data["severity"],
        "status": data["status"],
        "detection_source": data["detection_source"],
        "related_event_id": data["related_event_id"],
        "problem_management_no": data.get("problem_management_no"),
        "row_version": int(data.get("row_version", 1)),
        "updated_at": data.get("updated_at"),
        "updated_by_employee_id": data.get("updated_by_employee_id"),
    }
    return result

AGGREGATE_GROUP_BY_COLUMNS = frozenset({
    "location_name",
    "type_id",
    "severity",
    "status",
    "detection_source",
    "detector_department_id",
})


@dataclass
class IncidentAggregateParams:
    group_by: str
    occurred_from: datetime
    occurred_to: datetime
    statuses: list[str] | None = None
    severities: list[str] | None = None
    type_id: str | None = None
    keyword: str | None = None
    limit: int = 100


class IncidentSearchParams:
    def __init__(
        self,
        *,
        keyword: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        statuses: list[str] | None = None,
        severities: list[str] | None = None,
        type_id: str | None = None,
        incident_ids: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "-occurred_at",
        skip_pagination: bool = False,
    ) -> None:
        self.keyword = keyword
        self.occurred_from = occurred_from
        self.occurred_to = occurred_to
        self.statuses = statuses
        self.severities = severities
        self.type_id = type_id
        self.incident_ids = incident_ids
        self.page = page
        self.page_size = page_size
        self.sort = sort
        self.skip_pagination = skip_pagination


class IncidentRepository:
    def __init__(
        self,
        db: TsurugiConnection | None = None,
        master: MasterRepository | None = None,
    ) -> None:
        self._db = db or TsurugiConnection()
        self._master = master or MasterRepository(self._db)

    def _build_where(self, params: IncidentSearchParams) -> tuple[str, list[Any]]:
        clauses = ["i.company_id = ?"]
        values: list[Any] = [COMPANY_ID]
        if params.keyword:
            kw = f"%{params.keyword}%"
            clauses.append("(i.title LIKE ? OR i.description LIKE ?)")
            values.extend([kw, kw])
        if params.occurred_from:
            clauses.append("i.occurred_at >= ?")
            values.append(params.occurred_from)
        if params.occurred_to:
            clauses.append("i.occurred_at <= ?")
            values.append(params.occurred_to)
        if params.statuses:
            placeholders = ",".join("?" for _ in params.statuses)
            clauses.append(f"i.status IN ({placeholders})")
            values.extend(params.statuses)
        if params.severities:
            placeholders = ",".join("?" for _ in params.severities)
            clauses.append(f"i.severity IN ({placeholders})")
            values.extend(params.severities)
        if params.type_id:
            clauses.append("i.type_id = ?")
            values.append(params.type_id)
        if params.incident_ids is not None:
            if not params.incident_ids:
                clauses.append("1=0")
            else:
                placeholders = ",".join("?" for _ in params.incident_ids)
                clauses.append(f"i.incident_id IN ({placeholders})")
                values.extend(params.incident_ids)
        return " AND ".join(clauses), values

    def _order_clause(self, sort: str) -> str:
        if sort == "-occurred_at":
            return "ORDER BY i.occurred_at DESC"
        if sort == "occurred_at":
            return "ORDER BY i.occurred_at ASC"
        return "ORDER BY i.occurred_at DESC"

    def _response_counts(self) -> dict[str, int]:
        rows = self._db.fetchall(
            "SELECT incident_id, COUNT(*) FROM oil_incident_responses GROUP BY incident_id"
        )
        return {r[0]: int(r[1]) for r in rows}

    def search(self, params: IncidentSearchParams) -> tuple[list[dict[str, Any]], int]:
        if params.incident_ids is not None and not params.incident_ids:
            return [], 0

        where, values = self._build_where(params)
        count_sql = f"SELECT COUNT(*) FROM oil_incidents i WHERE {where}"
        total_row = self._db.fetchone(count_sql, tuple(values))
        total = int(total_row[0]) if total_row else 0

        page_size = max(1, min(int(params.page_size), MAX_LIST_PAGE_SIZE))
        offset = (max(1, int(params.page)) - 1) * page_size
        limit_clause = ""
        if not params.skip_pagination:
            fetch_limit = offset + page_size
            limit_clause = f" LIMIT {fetch_limit}"

        list_sql = f"""
            SELECT i.incident_id, i.occurred_at, i.title, i.status, i.severity
            FROM oil_incidents i
            WHERE {where}
            {self._order_clause(params.sort)}
            {limit_clause}
        """
        all_rows = self._db.fetchall(list_sql, tuple(values))
        rows = all_rows if params.skip_pagination else all_rows[offset : offset + page_size]
        response_counts = self._response_counts()
        items = []
        for r in rows:
            status = r[3]
            incident_id = r[0]
            items.append(
                {
                    "incident_id": incident_id,
                    "occurred_at": r[1],
                    "title": r[2],
                    "status": status,
                    "status_label": status_display_label(status),
                    "severity": r[4],
                    "response_count": response_counts.get(incident_id, 0),
                }
            )
        return items, total

    def aggregate(self, params: IncidentAggregateParams) -> dict[str, Any]:
        if params.group_by not in AGGREGATE_GROUP_BY_COLUMNS:
            return {"error": f"invalid group_by: {params.group_by}"}

        search_params = IncidentSearchParams(
            keyword=params.keyword,
            occurred_from=params.occurred_from,
            occurred_to=params.occurred_to,
            statuses=params.statuses,
            severities=params.severities,
            type_id=params.type_id,
        )
        where, values = self._build_where(search_params)
        col = params.group_by
        limit = max(1, min(int(params.limit), MAX_AGGREGATE_LIMIT))
        sql = f"""
            SELECT i.{col}, COUNT(*) AS cnt
            FROM oil_incidents i
            WHERE {where}
            GROUP BY i.{col}
            ORDER BY COUNT(*) DESC
            LIMIT {limit}
        """
        rows = self._db.fetchall(sql, tuple(values))

        groups: list[dict[str, Any]] = []
        total = 0
        for row in rows:
            key = row[0]
            count = int(row[1])
            total += count
            groups.append({
                "key": key,
                "label": self._aggregate_label(params.group_by, key),
                "count": count,
            })

        return {
            "group_by": params.group_by,
            "total_incidents": total,
            "groups": groups,
        }

    def _aggregate_label(self, group_by: str, key: Any) -> str:
        if key is None:
            return ""
        text = str(key)
        if group_by == "type_id":
            return self._master.get_type_name(text) or text
        if group_by == "status":
            return status_display_label(text)
        return text

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _conflict_payload(self, incident_id: str) -> dict[str, Any]:
        row = self.get_by_id(incident_id)
        if not row:
            return {"incident_id": incident_id}
        return {
            "incident_id": row["incident_id"],
            "row_version": row.get("row_version", 1),
            "title": row["title"],
            "updated_at": row.get("updated_at"),
            "updated_by_employee_id": row.get("updated_by_employee_id"),
        }

    def get_by_id(self, incident_id: str) -> dict[str, Any] | None:
        cols = _incident_select_columns()
        row = self._db.fetchone(
            f"SELECT {', '.join(cols)} FROM oil_incidents WHERE incident_id = ?",
            (incident_id,),
        )
        if not row:
            return None
        return _row_to_incident(row, cols)

    def get_detail(self, incident_id: str) -> dict[str, Any] | None:
        incident = self.get_by_id(incident_id)
        if not incident:
            return None
        incident["status_label"] = status_display_label(incident["status"])
        type_name = self._master.get_type_name(incident["type_id"]) or ""
        detector_name = self._master.get_employee_name(incident["detector_employee_id"]) or ""
        service_names = self._master.get_service_names(incident["affected_service_ids"])

        inv_row = self._db.fetchone(
            """
            SELECT investigation_id, root_cause_summary, investigation_detail, completed_at
            FROM oil_incident_investigations WHERE incident_id = ?
            """,
            (incident_id,),
        )
        investigation = None
        if inv_row:
            investigation = {
                "investigation_id": inv_row[0],
                "root_cause_summary": inv_row[1],
                "investigation_detail": inv_row[2],
                "completed_at": inv_row[3],
            }

        if has_column("oil_incident_responses", "row_version"):
            resp_rows = self._db.fetchall(
                """
                SELECT response_id, response_type, sequence_no, assignee_employee_id,
                       started_at, ended_at, summary, detail, row_version
                FROM oil_incident_responses
                WHERE incident_id = ?
                ORDER BY sequence_no
                """,
                (incident_id,),
            )
            responses = [
                {
                    "response_id": r[0],
                    "response_type": r[1],
                    "sequence_no": r[2],
                    "assignee_employee_id": r[3],
                    "assignee_name": self._master.get_employee_name(r[3]) or "",
                    "started_at": r[4],
                    "ended_at": r[5],
                    "summary": r[6],
                    "detail": r[7],
                    "row_version": int(r[8]),
                }
                for r in resp_rows
            ]
        else:
            resp_rows = self._db.fetchall(
                """
                SELECT response_id, response_type, sequence_no, assignee_employee_id,
                       started_at, ended_at, summary, detail
                FROM oil_incident_responses
                WHERE incident_id = ?
                ORDER BY sequence_no
                """,
                (incident_id,),
            )
            responses = [
                {
                    "response_id": r[0],
                    "response_type": r[1],
                    "sequence_no": r[2],
                    "assignee_employee_id": r[3],
                    "assignee_name": self._master.get_employee_name(r[3]) or "",
                    "started_at": r[4],
                    "ended_at": r[5],
                    "summary": r[6],
                    "detail": r[7],
                    "row_version": 1,
                }
                for r in resp_rows
            ]

        cust_rows = self._db.fetchall(
            """
            SELECT c.customer_id, c.customer_name
            FROM oil_incident_customers ic
            JOIN oil_customers c ON ic.customer_id = c.customer_id
            WHERE ic.incident_id = ?
            ORDER BY c.customer_id
            """,
            (incident_id,),
        )
        customers = [{"customer_id": r[0], "customer_name": r[1]} for r in cust_rows]

        return {
            "incident": incident,
            "type_name": type_name,
            "detector_name": detector_name,
            "service_names": service_names,
            "customers": customers,
            "investigation": investigation,
            "responses": responses,
        }

    def _next_incident_id(self, year: int) -> str:
        prefix = f"INC-{year}-"
        rows = self._db.fetchall(
            "SELECT incident_id FROM oil_incidents WHERE incident_id LIKE ?",
            (f"{prefix}%",),
        )
        max_seq = 0
        for row in rows:
            try:
                max_seq = max(max_seq, parse_incident_sequence(row[0]))
            except ValueError:
                continue
        return format_incident_id(year, max_seq + 1)

    def create(self, data: dict[str, Any], *, operator_id: str) -> str:
        occurred_at: datetime = data["occurred_at"]
        year = occurred_at.year
        incident_id = self._next_incident_id(year)
        detection_minutes = self._master.get_type_detection_minutes(data["type_id"])
        detected_at = data.get("detected_at")
        if detected_at is None:
            detected_at = occurred_at + timedelta(minutes=detection_minutes)
        affected = ";".join(data.get("affected_service_ids", []))
        pmno = _problem_management_no_value(data)
        now = self._now()
        if has_column("oil_incidents", "row_version"):
            if has_column("oil_incidents", "problem_management_no"):
                self._db.execute(
                    """
                    INSERT INTO oil_incidents (
                        incident_id, company_id, type_id, occurred_at, detected_at, title, description,
                        location_name, affected_service_ids, detector_employee_id, detector_department_id,
                        severity, status, detection_source, related_event_id, problem_management_no,
                        row_version, updated_at, updated_by_employee_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        incident_id,
                        COMPANY_ID,
                        data["type_id"],
                        occurred_at,
                        detected_at,
                        data["title"],
                        data["description"],
                        data["location_name"],
                        affected,
                        data["detector_employee_id"],
                        data["detector_department_id"],
                        data["severity"],
                        data["status"],
                        data["detection_source"],
                        data.get("related_event_id"),
                        pmno,
                        now,
                        operator_id,
                    ),
                )
            else:
                self._db.execute(
                    """
                    INSERT INTO oil_incidents (
                        incident_id, company_id, type_id, occurred_at, detected_at, title, description,
                        location_name, affected_service_ids, detector_employee_id, detector_department_id,
                        severity, status, detection_source, related_event_id,
                        row_version, updated_at, updated_by_employee_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        incident_id,
                        COMPANY_ID,
                        data["type_id"],
                        occurred_at,
                        detected_at,
                        data["title"],
                        data["description"],
                        data["location_name"],
                        affected,
                        data["detector_employee_id"],
                        data["detector_department_id"],
                        data["severity"],
                        data["status"],
                        data["detection_source"],
                        data.get("related_event_id"),
                        now,
                        operator_id,
                    ),
                )
        elif has_column("oil_incidents", "problem_management_no"):
            self._db.execute(
                """
                INSERT INTO oil_incidents (
                    incident_id, company_id, type_id, occurred_at, detected_at, title, description,
                    location_name, affected_service_ids, detector_employee_id, detector_department_id,
                    severity, status, detection_source, related_event_id, problem_management_no
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    COMPANY_ID,
                    data["type_id"],
                    occurred_at,
                    detected_at,
                    data["title"],
                    data["description"],
                    data["location_name"],
                    affected,
                    data["detector_employee_id"],
                    data["detector_department_id"],
                    data["severity"],
                    data["status"],
                    data["detection_source"],
                    data.get("related_event_id"),
                    pmno,
                ),
            )
        else:
            self._db.execute(
                """
                INSERT INTO oil_incidents (
                    incident_id, company_id, type_id, occurred_at, detected_at, title, description,
                    location_name, affected_service_ids, detector_employee_id, detector_department_id,
                    severity, status, detection_source, related_event_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    COMPANY_ID,
                    data["type_id"],
                    occurred_at,
                    detected_at,
                    data["title"],
                    data["description"],
                    data["location_name"],
                    affected,
                    data["detector_employee_id"],
                    data["detector_department_id"],
                    data["severity"],
                    data["status"],
                    data["detection_source"],
                    data.get("related_event_id"),
                ),
            )
        return incident_id

    def update(
        self,
        incident_id: str,
        data: dict[str, Any],
        *,
        row_version: int,
        operator_id: str,
    ) -> None:
        occurred_at: datetime = data["occurred_at"]
        detection_minutes = self._master.get_type_detection_minutes(data["type_id"])
        detected_at = data.get("detected_at")
        if detected_at is None:
            detected_at = occurred_at + timedelta(minutes=detection_minutes)
        affected = ";".join(data.get("affected_service_ids", []))
        pmno = _problem_management_no_value(data)
        now = self._now()
        if has_column("oil_incidents", "row_version"):
            if has_column("oil_incidents", "problem_management_no"):
                updated = self._db.execute(
                    """
                    UPDATE oil_incidents SET
                        type_id = ?, occurred_at = ?, detected_at = ?, title = ?, description = ?,
                        location_name = ?, affected_service_ids = ?, detector_employee_id = ?,
                        detector_department_id = ?, severity = ?, status = ?, detection_source = ?,
                        related_event_id = ?, problem_management_no = ?,
                        row_version = row_version + 1, updated_at = ?, updated_by_employee_id = ?
                    WHERE incident_id = ? AND row_version = ?
                    """,
                    (
                        data["type_id"],
                        occurred_at,
                        detected_at,
                        data["title"],
                        data["description"],
                        data["location_name"],
                        affected,
                        data["detector_employee_id"],
                        data["detector_department_id"],
                        data["severity"],
                        data["status"],
                        data["detection_source"],
                        data.get("related_event_id"),
                        pmno,
                        now,
                        operator_id,
                        incident_id,
                        row_version,
                    ),
                )
            else:
                updated = self._db.execute(
                    """
                    UPDATE oil_incidents SET
                        type_id = ?, occurred_at = ?, detected_at = ?, title = ?, description = ?,
                        location_name = ?, affected_service_ids = ?, detector_employee_id = ?,
                        detector_department_id = ?, severity = ?, status = ?, detection_source = ?,
                        related_event_id = ?,
                        row_version = row_version + 1, updated_at = ?, updated_by_employee_id = ?
                    WHERE incident_id = ? AND row_version = ?
                    """,
                    (
                        data["type_id"],
                        occurred_at,
                        detected_at,
                        data["title"],
                        data["description"],
                        data["location_name"],
                        affected,
                        data["detector_employee_id"],
                        data["detector_department_id"],
                        data["severity"],
                        data["status"],
                        data["detection_source"],
                        data.get("related_event_id"),
                        now,
                        operator_id,
                        incident_id,
                        row_version,
                    ),
                )
            if updated == 0:
                raise OptimisticLockError(self._conflict_payload(incident_id))
            return
        if has_column("oil_incidents", "problem_management_no"):
            self._db.execute(
                """
                UPDATE oil_incidents SET
                    type_id = ?, occurred_at = ?, detected_at = ?, title = ?, description = ?,
                    location_name = ?, affected_service_ids = ?, detector_employee_id = ?,
                    detector_department_id = ?, severity = ?, status = ?, detection_source = ?,
                    related_event_id = ?, problem_management_no = ?
                WHERE incident_id = ?
                """,
                (
                    data["type_id"],
                    occurred_at,
                    detected_at,
                    data["title"],
                    data["description"],
                    data["location_name"],
                    affected,
                    data["detector_employee_id"],
                    data["detector_department_id"],
                    data["severity"],
                    data["status"],
                    data["detection_source"],
                    data.get("related_event_id"),
                    pmno,
                    incident_id,
                ),
            )
            return
        self._db.execute(
            """
            UPDATE oil_incidents SET
                type_id = ?, occurred_at = ?, detected_at = ?, title = ?, description = ?,
                location_name = ?, affected_service_ids = ?, detector_employee_id = ?,
                detector_department_id = ?, severity = ?, status = ?, detection_source = ?,
                related_event_id = ?
            WHERE incident_id = ?
            """,
            (
                data["type_id"],
                occurred_at,
                detected_at,
                data["title"],
                data["description"],
                data["location_name"],
                affected,
                data["detector_employee_id"],
                data["detector_department_id"],
                data["severity"],
                data["status"],
                data["detection_source"],
                data.get("related_event_id"),
                incident_id,
            ),
        )

    def list_unresolved(self, limit: int = 50) -> list[dict[str, Any]]:
        params = IncidentSearchParams(
            statuses=[IncidentStatus.OPEN, IncidentStatus.IN_PROGRESS],
            page=1,
            page_size=limit,
        )
        items, _ = self.search(params)
        return items

    def update_severity(
        self,
        incident_id: str,
        severity: str,
        *,
        operator_id: str,
    ) -> None:
        now = self._now()
        if has_column("oil_incidents", "row_version"):
            self._db.execute(
                """
                UPDATE oil_incidents
                SET severity = ?, row_version = row_version + 1,
                    updated_at = ?, updated_by_employee_id = ?
                WHERE incident_id = ?
                """,
                (severity, now, operator_id, incident_id),
            )
        else:
            self._db.execute(
                "UPDATE oil_incidents SET severity = ? WHERE incident_id = ?",
                (severity, incident_id),
            )

