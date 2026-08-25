"""マスタデータリポジトリ。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.domain.id_gen import (
    format_customer_id,
    format_employee_id,
    format_personnel_history_id,
    format_service_id,
    format_type_id,
    parse_customer_sequence,
    parse_employee_sequence,
    parse_personnel_history_sequence,
    parse_service_sequence,
    parse_type_sequence,
)
from app.repository.optimistic import OptimisticLockError
from app.repository.schema_compat import has_column
from app.repository.tsurugi_conn import TsurugiConnection

COMPANY_ID = "COMP-001"


def _decimal_sql_literal(value: float | int, *, precision: int = 10, scale: int = 4) -> str:
    """Tsurugi は DECIMAL 列への float バインドが型解析エラーになるため、検証済みリテラルを SQL に埋め込む。"""
    d = Decimal(str(value)).quantize(Decimal(10) ** -scale, rounding=ROUND_HALF_UP)
    max_d = Decimal(10 ** (precision - scale)) - Decimal(10) ** -scale
    if d < 0 or d > max_d:
        raise ValueError(f"value out of range for DECIMAL({precision},{scale})")
    return format(d, "f")


class MasterRepository:
    def __init__(self, db: TsurugiConnection | None = None) -> None:
        self._db = db or TsurugiConnection()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _version_defaults(self) -> dict[str, Any]:
        return {
            "row_version": 1,
            "updated_at": self._now(),
            "updated_by_employee_id": None,
        }

    def list_incident_types(self) -> list[dict[str, Any]]:
        if has_column("oil_incident_types", "row_version"):
            rows = self._db.fetchall(
                """
                SELECT type_id, type_name, avg_detection_minutes, severity_default, detection_source,
                       description, row_version, updated_at, updated_by_employee_id
                FROM oil_incident_types ORDER BY type_id
                """
            )
            return [
                {
                    "type_id": r[0],
                    "type_name": r[1],
                    "avg_detection_minutes": r[2],
                    "severity_default": r[3],
                    "detection_source": r[4],
                    "description": r[5],
                    "row_version": int(r[6]),
                    "updated_at": r[7],
                    "updated_by_employee_id": r[8],
                }
                for r in rows
            ]
        rows = self._db.fetchall(
            """
            SELECT type_id, type_name, avg_detection_minutes, severity_default, detection_source, description
            FROM oil_incident_types ORDER BY type_id
            """
        )
        defaults = self._version_defaults()
        return [
            {
                "type_id": r[0],
                "type_name": r[1],
                "avg_detection_minutes": r[2],
                "severity_default": r[3],
                "detection_source": r[4],
                "description": r[5],
                **defaults,
            }
            for r in rows
        ]

    def get_incident_type(self, type_id: str) -> dict[str, Any] | None:
        items = [i for i in self.list_incident_types() if i["type_id"] == type_id]
        return items[0] if items else None

    def create_incident_type(self, data: dict[str, Any], *, operator_id: str) -> dict[str, Any]:
        if not has_column("oil_incident_types", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        rows = self._db.fetchall("SELECT type_id FROM oil_incident_types")
        max_seq = max((parse_type_sequence(r[0]) for r in rows), default=0)
        type_id = format_type_id(max_seq + 1)
        now = self._now()
        frequency_weight = _decimal_sql_literal(data.get("frequency_weight", 1.0))
        self._db.execute(
            f"""
            INSERT INTO oil_incident_types (
                type_id, company_id, type_name, frequency_weight, avg_detection_minutes,
                severity_default, detection_source, description,
                row_version, updated_at, updated_by_employee_id
            ) VALUES (?, ?, ?, {frequency_weight}, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                type_id,
                COMPANY_ID,
                data["type_name"],
                data["avg_detection_minutes"],
                data["severity_default"],
                data["detection_source"],
                data.get("description", ""),
                now,
                operator_id,
            ),
        )
        result = self.get_incident_type(type_id)
        assert result is not None
        return result

    def update_incident_type(
        self, type_id: str, data: dict[str, Any], *, row_version: int, operator_id: str
    ) -> dict[str, Any]:
        if not has_column("oil_incident_types", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        now = self._now()
        updated = self._db.execute(
            """
            UPDATE oil_incident_types SET
                type_name = ?, avg_detection_minutes = ?, severity_default = ?,
                detection_source = ?, description = ?,
                row_version = row_version + 1, updated_at = ?, updated_by_employee_id = ?
            WHERE type_id = ? AND row_version = ?
            """,
            (
                data["type_name"],
                data["avg_detection_minutes"],
                data["severity_default"],
                data["detection_source"],
                data.get("description", ""),
                now,
                operator_id,
                type_id,
                row_version,
            ),
        )
        if updated == 0:
            current = self.get_incident_type(type_id)
            raise OptimisticLockError(current or {"type_id": type_id})
        result = self.get_incident_type(type_id)
        assert result is not None
        return result

    def list_services(self) -> list[dict[str, Any]]:
        if has_column("oil_services", "row_version"):
            rows = self._db.fetchall(
                """
                SELECT service_id, service_name, description, row_version, updated_at, updated_by_employee_id
                FROM oil_services ORDER BY service_id
                """
            )
            return [
                {
                    "service_id": r[0],
                    "service_name": r[1],
                    "description": r[2],
                    "row_version": int(r[3]),
                    "updated_at": r[4],
                    "updated_by_employee_id": r[5],
                }
                for r in rows
            ]
        rows = self._db.fetchall(
            "SELECT service_id, service_name, description FROM oil_services ORDER BY service_id"
        )
        defaults = self._version_defaults()
        return [
            {"service_id": r[0], "service_name": r[1], "description": r[2], **defaults} for r in rows
        ]

    def get_service(self, service_id: str) -> dict[str, Any] | None:
        return next((s for s in self.list_services() if s["service_id"] == service_id), None)

    def create_service(self, data: dict[str, Any], *, operator_id: str) -> dict[str, Any]:
        if not has_column("oil_services", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        rows = self._db.fetchall("SELECT service_id FROM oil_services")
        max_seq = max((parse_service_sequence(r[0]) for r in rows), default=0)
        service_id = format_service_id(max_seq + 1)
        now = self._now()
        self._db.execute(
            """
            INSERT INTO oil_services (
                service_id, company_id, service_name, description, launch_at,
                owner_department_id, status, cloud_platform, incident_rate_multiplier,
                row_version, updated_at, updated_by_employee_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                service_id,
                COMPANY_ID,
                data["service_name"],
                data.get("description", ""),
                data.get("launch_at", now),
                data.get("owner_department_id", "DEPT-OPS"),
                data.get("status", "ACTIVE"),
                data.get("cloud_platform"),
                data.get("incident_rate_multiplier", 1.0),
                now,
                operator_id,
            ),
        )
        result = self.get_service(service_id)
        assert result is not None
        return result

    def update_service(
        self, service_id: str, data: dict[str, Any], *, row_version: int, operator_id: str
    ) -> dict[str, Any]:
        if not has_column("oil_services", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        now = self._now()
        updated = self._db.execute(
            """
            UPDATE oil_services SET service_name = ?, description = ?,
                row_version = row_version + 1, updated_at = ?, updated_by_employee_id = ?
            WHERE service_id = ? AND row_version = ?
            """,
            (data["service_name"], data.get("description", ""), now, operator_id, service_id, row_version),
        )
        if updated == 0:
            current = self.get_service(service_id)
            raise OptimisticLockError(current or {"service_id": service_id})
        result = self.get_service(service_id)
        assert result is not None
        return result

    def list_customers(self) -> list[dict[str, Any]]:
        if has_column("oil_customers", "row_version"):
            rows = self._db.fetchall(
                """
                SELECT customer_id, customer_name, industry_segment, service_id,
                       row_version, updated_at, updated_by_employee_id
                FROM oil_customers ORDER BY customer_id
                """
            )
            return [
                {
                    "customer_id": r[0],
                    "customer_name": r[1],
                    "industry_segment": r[2],
                    "service_id": r[3],
                    "row_version": int(r[4]),
                    "updated_at": r[5],
                    "updated_by_employee_id": r[6],
                }
                for r in rows
            ]
        rows = self._db.fetchall(
            "SELECT customer_id, customer_name, industry_segment, service_id FROM oil_customers ORDER BY customer_id"
        )
        defaults = self._version_defaults()
        return [
            {
                "customer_id": r[0],
                "customer_name": r[1],
                "industry_segment": r[2],
                "service_id": r[3],
                **defaults,
            }
            for r in rows
        ]

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        return next((c for c in self.list_customers() if c["customer_id"] == customer_id), None)

    def create_customer(self, data: dict[str, Any], *, operator_id: str) -> dict[str, Any]:
        if not has_column("oil_customers", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        rows = self._db.fetchall("SELECT customer_id FROM oil_customers")
        max_seq = max((parse_customer_sequence(r[0]) for r in rows), default=0)
        customer_id = format_customer_id(max_seq + 1)
        now = self._now()
        self._db.execute(
            """
            INSERT INTO oil_customers (
                customer_id, company_id, customer_name, industry_segment, service_id,
                contract_start_at, row_version, updated_at, updated_by_employee_id
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                customer_id,
                COMPANY_ID,
                data["customer_name"],
                data.get("industry_segment", "ENTERPRISE"),
                data.get("service_id", "SVC-001"),
                data.get("contract_start_at", date(2020, 4, 1)),
                now,
                operator_id,
            ),
        )
        result = self.get_customer(customer_id)
        assert result is not None
        return result

    def update_customer(
        self, customer_id: str, data: dict[str, Any], *, row_version: int, operator_id: str
    ) -> dict[str, Any]:
        if not has_column("oil_customers", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        now = self._now()
        updated = self._db.execute(
            """
            UPDATE oil_customers SET customer_name = ?, industry_segment = ?, service_id = ?,
                row_version = row_version + 1, updated_at = ?, updated_by_employee_id = ?
            WHERE customer_id = ? AND row_version = ?
            """,
            (
                data["customer_name"],
                data.get("industry_segment", "ENTERPRISE"),
                data.get("service_id", "SVC-001"),
                now,
                operator_id,
                customer_id,
                row_version,
            ),
        )
        if updated == 0:
            current = self.get_customer(customer_id)
            raise OptimisticLockError(current or {"customer_id": customer_id})
        result = self.get_customer(customer_id)
        assert result is not None
        return result

    def list_employees(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT ph.employee_id, ph.employee_name, ph.department_id
            FROM oil_personnel_history ph
            INNER JOIN (
                SELECT employee_id, MAX(effective_at) AS max_effective
                FROM oil_personnel_history
                GROUP BY employee_id
            ) latest ON ph.employee_id = latest.employee_id AND ph.effective_at = latest.max_effective
            ORDER BY ph.employee_id
            """
        )
        return [{"employee_id": r[0], "employee_name": r[1], "department_id": r[2]} for r in rows]

    def get_employee(self, employee_id: str) -> dict[str, Any] | None:
        row = self._db.fetchone(
            """
            SELECT ph.employee_id, ph.employee_name, ph.department_id, ph.role_title
            FROM oil_personnel_history ph
            WHERE ph.employee_id = ?
            ORDER BY ph.effective_at DESC
            """,
            (employee_id,),
        )
        if not row:
            return None
        item = {
            "employee_id": row[0],
            "employee_name": row[1],
            "department_id": row[2],
            "role_title": row[3],
            **self._version_defaults(),
        }
        if has_column("oil_personnel_history", "row_version"):
            vrow = self._db.fetchone(
                """
                SELECT row_version, updated_at, updated_by_employee_id
                FROM oil_personnel_history
                WHERE employee_id = ?
                ORDER BY effective_at DESC
                """,
                (employee_id,),
            )
            if vrow:
                item["row_version"] = int(vrow[0])
                item["updated_at"] = vrow[1]
                item["updated_by_employee_id"] = vrow[2]
        return item

    def create_employee_history(self, data: dict[str, Any], *, operator_id: str) -> dict[str, Any]:
        if not has_column("oil_personnel_history", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        employee_id = data.get("employee_id")
        if not employee_id:
            rows = self._db.fetchall("SELECT employee_id FROM oil_personnel_history")
            max_seq = max((parse_employee_sequence(r[0]) for r in rows), default=0)
            employee_id = format_employee_id(max_seq + 1)
        hist_rows = self._db.fetchall("SELECT history_id FROM oil_personnel_history")
        max_hist = max((parse_personnel_history_sequence(r[0]) for r in hist_rows), default=0)
        history_id = format_personnel_history_id(max_hist + 1)
        now = self._now()
        self._db.execute(
            """
            INSERT INTO oil_personnel_history (
                history_id, employee_id, employee_name, department_id, role_title,
                change_type, effective_at, row_version, updated_at, updated_by_employee_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                history_id,
                employee_id,
                data["employee_name"],
                data["department_id"],
                data.get("role_title", ""),
                data.get("change_type", "HIRE"),
                data.get("effective_at", date.today()),
                now,
                operator_id,
            ),
        )
        result = self.get_employee(employee_id)
        assert result is not None
        return result

    def update_employee_current(
        self, employee_id: str, data: dict[str, Any], *, row_version: int, operator_id: str
    ) -> dict[str, Any]:
        current = self.get_employee(employee_id)
        if not current:
            raise ValueError("not_found")
        if current["row_version"] != row_version:
            raise OptimisticLockError(current)
        return self.create_employee_history(
            {
                "employee_id": employee_id,
                "employee_name": data.get("employee_name", current["employee_name"]),
                "department_id": data["department_id"],
                "role_title": data.get("role_title", current.get("role_title", "")),
                "change_type": data.get("change_type", "TRANSFER"),
                "effective_at": data.get("effective_at", date.today()),
            },
            operator_id=operator_id,
        )

    def list_departments(self) -> list[dict[str, Any]]:
        if has_column("oil_departments", "row_version"):
            rows = self._db.fetchall(
                """
                SELECT department_id, department_name, row_version, updated_at, updated_by_employee_id
                FROM oil_departments ORDER BY department_id
                """
            )
            return [
                {
                    "department_id": r[0],
                    "department_name": r[1],
                    "row_version": int(r[2]),
                    "updated_at": r[3],
                    "updated_by_employee_id": r[4],
                }
                for r in rows
            ]
        rows = self._db.fetchall(
            "SELECT department_id, department_name FROM oil_departments ORDER BY department_id"
        )
        defaults = self._version_defaults()
        return [{"department_id": r[0], "department_name": r[1], **defaults} for r in rows]

    def get_department(self, department_id: str) -> dict[str, Any] | None:
        return next((d for d in self.list_departments() if d["department_id"] == department_id), None)

    def create_department(self, data: dict[str, Any], *, operator_id: str) -> dict[str, Any]:
        if not has_column("oil_departments", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        department_id = data["department_id"]
        now = self._now()
        self._db.execute(
            """
            INSERT INTO oil_departments (
                department_id, company_id, department_name, parent_department_id,
                valid_from, valid_to, row_version, updated_at, updated_by_employee_id
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                department_id,
                COMPANY_ID,
                data["department_name"],
                data.get("parent_department_id"),
                data.get("valid_from", date(2020, 4, 1)),
                data.get("valid_to"),
                now,
                operator_id,
            ),
        )
        result = self.get_department(department_id)
        assert result is not None
        return result

    def update_department(
        self, department_id: str, data: dict[str, Any], *, row_version: int, operator_id: str
    ) -> dict[str, Any]:
        if not has_column("oil_departments", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        now = self._now()
        updated = self._db.execute(
            """
            UPDATE oil_departments SET department_name = ?,
                row_version = row_version + 1, updated_at = ?, updated_by_employee_id = ?
            WHERE department_id = ? AND row_version = ?
            """,
            (data["department_name"], now, operator_id, department_id, row_version),
        )
        if updated == 0:
            current = self.get_department(department_id)
            raise OptimisticLockError(current or {"department_id": department_id})
        result = self.get_department(department_id)
        assert result is not None
        return result

    def list_incident_type_locations(self, type_id: str) -> list[dict[str, Any]]:
        if has_column("oil_incident_type_locations", "row_version"):
            rows = self._db.fetchall(
                """
                SELECT type_id, location_name, row_version, updated_at, updated_by_employee_id
                FROM oil_incident_type_locations
                WHERE type_id = ?
                ORDER BY location_name
                """,
                (type_id,),
            )
            return [
                {
                    "type_id": r[0],
                    "location_name": r[1],
                    "row_version": int(r[2]),
                    "updated_at": r[3],
                    "updated_by_employee_id": r[4],
                }
                for r in rows
            ]
        rows = self._db.fetchall(
            """
            SELECT type_id, location_name
            FROM oil_incident_type_locations
            WHERE type_id = ?
            ORDER BY location_name
            """,
            (type_id,),
        )
        defaults = self._version_defaults()
        return [{"type_id": r[0], "location_name": r[1], **defaults} for r in rows]

    def create_incident_type_location(
        self, type_id: str, location_name: str, *, operator_id: str
    ) -> dict[str, Any]:
        if not has_column("oil_incident_type_locations", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        now = self._now()
        self._db.execute(
            """
            INSERT INTO oil_incident_type_locations (
                type_id, location_name, row_version, updated_at, updated_by_employee_id
            ) VALUES (?, ?, 1, ?, ?)
            """,
            (type_id, location_name, now, operator_id),
        )
        return {
            "type_id": type_id,
            "location_name": location_name,
            "row_version": 1,
            "updated_at": now,
            "updated_by_employee_id": operator_id,
        }

    def update_incident_type_location(
        self,
        type_id: str,
        location_name: str,
        new_name: str,
        *,
        row_version: int,
        operator_id: str,
    ) -> dict[str, Any]:
        if not has_column("oil_incident_type_locations", "row_version"):
            raise RuntimeError("RFC005 migration required for master write")
        now = self._now()
        updated = self._db.execute(
            """
            UPDATE oil_incident_type_locations SET location_name = ?,
                row_version = row_version + 1, updated_at = ?, updated_by_employee_id = ?
            WHERE type_id = ? AND location_name = ? AND row_version = ?
            """,
            (new_name, now, operator_id, type_id, location_name, row_version),
        )
        if updated == 0:
            raise OptimisticLockError({"type_id": type_id, "location_name": location_name})
        return {
            "type_id": type_id,
            "location_name": new_name,
            "row_version": row_version + 1,
            "updated_at": now,
            "updated_by_employee_id": operator_id,
        }

    def get_company(self) -> dict[str, Any] | None:
        row = self._db.fetchone(
            "SELECT company_id, company_name, industry FROM oil_company WHERE company_id = ?",
            (COMPANY_ID,),
        )
        if not row:
            return None
        return {"company_id": row[0], "company_name": row[1], "industry": row[2]}

    def list_services_for_context(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT service_id, service_name, description, launch_at,
                   owner_department_id, status, cloud_platform
            FROM oil_services ORDER BY service_id
            """
        )
        return [
            {
                "service_id": r[0],
                "service_name": r[1],
                "description": r[2],
                "launch_at": r[3],
                "owner_department_id": r[4],
                "status": r[5],
                "cloud_platform": r[6],
            }
            for r in rows
        ]

    def list_departments_for_context(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT department_id, department_name, parent_department_id
            FROM oil_departments ORDER BY department_id
            """
        )
        return [
            {
                "department_id": r[0],
                "department_name": r[1],
                "parent_department_id": r[2],
            }
            for r in rows
        ]

    def list_employees_for_context(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT ph.employee_id, ph.employee_name, ph.department_id, ph.role_title
            FROM oil_personnel_history ph
            INNER JOIN (
                SELECT employee_id, MAX(effective_at) AS max_effective
                FROM oil_personnel_history
                GROUP BY employee_id
            ) latest ON ph.employee_id = latest.employee_id AND ph.effective_at = latest.max_effective
            ORDER BY ph.employee_id
            """
        )
        return [
            {
                "employee_id": r[0],
                "employee_name": r[1],
                "department_id": r[2],
                "role_title": r[3],
            }
            for r in rows
        ]

    def list_customers_for_context(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT customer_id, customer_name, industry_segment, service_id, contract_start_at
            FROM oil_customers ORDER BY customer_id
            """
        )
        return [
            {
                "customer_id": r[0],
                "customer_name": r[1],
                "industry_segment": r[2],
                "service_id": r[3],
                "contract_start_at": r[4],
            }
            for r in rows
        ]

    def list_incident_types_for_context(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT type_id, type_name, severity_default, detection_source,
                   description, avg_detection_minutes
            FROM oil_incident_types ORDER BY type_id
            """
        )
        return [
            {
                "type_id": r[0],
                "type_name": r[1],
                "severity_default": r[2],
                "detection_source": r[3],
                "description": r[4],
                "avg_detection_minutes": r[5],
            }
            for r in rows
        ]

    def list_all_incident_type_locations(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT type_id, location_name
            FROM oil_incident_type_locations
            ORDER BY type_id, location_name
            """
        )
        return [{"type_id": r[0], "location_name": r[1]} for r in rows]

    def list_external_events(self) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            """
            SELECT event_id, event_name, event_type, start_at, end_at,
                   description, related_service_ids
            FROM oil_external_events ORDER BY event_id
            """
        )
        return [
            {
                "event_id": r[0],
                "event_name": r[1],
                "event_type": r[2],
                "start_at": r[3],
                "end_at": r[4],
                "description": r[5],
                "related_service_ids": r[6],
            }
            for r in rows
        ]

    def get_type_detection_minutes(self, type_id: str) -> int:
        row = self._db.fetchone(
            "SELECT avg_detection_minutes FROM oil_incident_types WHERE type_id = ?",
            (type_id,),
        )
        if not row:
            raise ValueError(f"type not found: {type_id}")
        return int(row[0])

    def get_employee_name(self, employee_id: str) -> str | None:
        row = self._db.fetchone(
            """
            SELECT employee_name FROM oil_personnel_history
            WHERE employee_id = ?
            ORDER BY effective_at DESC
            """,
            (employee_id,),
        )
        return row[0] if row else None

    def get_type_name(self, type_id: str) -> str | None:
        row = self._db.fetchone(
            "SELECT type_name FROM oil_incident_types WHERE type_id = ?",
            (type_id,),
        )
        return row[0] if row else None

    def get_service_names(self, service_ids: list[str]) -> list[str]:
        if not service_ids:
            return []
        placeholders = ",".join("?" for _ in service_ids)
        rows = self._db.fetchall(
            f"SELECT service_name FROM oil_services WHERE service_id IN ({placeholders}) ORDER BY service_id",
            tuple(service_ids),
        )
        return [r[0] for r in rows]
