"""運用システム背景情報の組み立てサービス。"""

from __future__ import annotations

from typing import Any

from app.repository.master import MasterRepository

ALLOWED_SECTIONS: tuple[str, ...] = (
    "company",
    "departments",
    "employees",
    "services",
    "customers",
    "incident_types",
    "incident_type_locations",
    "external_events",
)

_SECTION_BUILDERS: dict[str, str] = {
    "company": "_build_company",
    "departments": "_build_departments",
    "employees": "_build_employees",
    "services": "_build_services",
    "customers": "_build_customers",
    "incident_types": "_build_incident_types",
    "incident_type_locations": "_build_incident_type_locations",
    "external_events": "_build_external_events",
}


class SystemContextService:
    def __init__(self, masters: MasterRepository | None = None) -> None:
        self._masters = masters or MasterRepository()

    def build_context(self, sections: list[str] | None = None) -> dict[str, Any]:
        selected = self._normalize_sections(sections)
        result: dict[str, Any] = {}
        for section in selected:
            builder_name = _SECTION_BUILDERS[section]
            builder = getattr(self, builder_name)
            result[section] = builder()
        return result

    def _normalize_sections(self, sections: list[str] | None) -> list[str]:
        if not sections:
            return list(ALLOWED_SECTIONS)
        normalized = [s.strip().lower() for s in sections if s and s.strip()]
        filtered = [s for s in normalized if s in ALLOWED_SECTIONS]
        if not filtered:
            return list(ALLOWED_SECTIONS)
        return filtered

    def _build_company(self) -> dict[str, Any] | None:
        return self._masters.get_company()

    def _build_departments(self) -> list[dict[str, Any]]:
        return self._masters.list_departments_for_context()

    def _build_employees(self) -> list[dict[str, Any]]:
        return self._masters.list_employees_for_context()

    def _build_services(self) -> list[dict[str, Any]]:
        return self._masters.list_services_for_context()

    def _build_customers(self) -> list[dict[str, Any]]:
        return self._masters.list_customers_for_context()

    def _build_incident_types(self) -> list[dict[str, Any]]:
        return self._masters.list_incident_types_for_context()

    def _build_incident_type_locations(self) -> list[dict[str, Any]]:
        return self._masters.list_all_incident_type_locations()

    def _build_external_events(self) -> list[dict[str, Any]]:
        return self._masters.list_external_events()
