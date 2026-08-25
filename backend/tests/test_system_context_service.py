"""SystemContextService の単体テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.system_context_service import SystemContextService


def test_build_context_all_sections() -> None:
    masters = MagicMock()
    masters.get_company.return_value = {
        "company_id": "COMP-001",
        "company_name": "株式会社ストッククラウド",
        "industry": "在庫管理SaaS",
    }
    masters.list_departments_for_context.return_value = []
    masters.list_employees_for_context.return_value = []
    masters.list_services_for_context.return_value = [
        {"service_id": "SVC-001", "service_name": "Mercury"}
    ]
    masters.list_customers_for_context.return_value = []
    masters.list_incident_types_for_context.return_value = []
    masters.list_all_incident_type_locations.return_value = []
    masters.list_external_events.return_value = []

    svc = SystemContextService(masters)
    result = svc.build_context(None)

    assert result["company"]["company_name"] == "株式会社ストッククラウド"
    assert result["services"][0]["service_name"] == "Mercury"
    assert result["external_events"] == []


def test_build_context_sections_filter() -> None:
    masters = MagicMock()
    masters.list_services_for_context.return_value = [
        {"service_id": "SVC-002", "service_name": "Venus"}
    ]

    svc = SystemContextService(masters)
    result = svc.build_context(["services"])

    assert set(result.keys()) == {"services"}
    assert result["services"][0]["service_name"] == "Venus"
    masters.get_company.assert_not_called()


def test_build_context_ignores_invalid_sections() -> None:
    masters = MagicMock()
    masters.get_company.return_value = {"company_name": "Test Co"}

    svc = SystemContextService(masters)
    result = svc.build_context(["invalid", "company"])

    assert set(result.keys()) == {"company"}


def test_build_context_empty_sections_returns_all() -> None:
    masters = MagicMock()
    masters.get_company.return_value = {"company_name": "Test Co"}
    masters.list_departments_for_context.return_value = []
    masters.list_employees_for_context.return_value = []
    masters.list_services_for_context.return_value = []
    masters.list_customers_for_context.return_value = []
    masters.list_incident_types_for_context.return_value = []
    masters.list_all_incident_type_locations.return_value = []
    masters.list_external_events.return_value = []

    svc = SystemContextService(masters)
    result = svc.build_context([])

    assert "company" in result
    assert "services" in result
    assert "external_events" in result
