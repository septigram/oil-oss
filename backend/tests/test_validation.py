"""Pydantic バリデーションの単体テスト。"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.domain.models import IncidentCreateRequest, IncidentStatus, ResponseCreateRequest, Severity


def test_incident_requires_non_empty_title() -> None:
    with pytest.raises(ValidationError):
        IncidentCreateRequest.model_validate(
            {
                "incident": {
                    "type_id": "ITYP-001",
                    "occurred_at": "2020-05-15T10:00:00+09:00",
                    "title": "",
                    "description": "desc",
                    "location_name": "loc",
                    "detector_employee_id": "EMP-00001",
                    "detector_department_id": "DEPT-OPS",
                    "severity": "LOW",
                    "status": "OPEN",
                    "detection_source": "OPS_MONITORING",
                }
            }
        )


def test_incident_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        IncidentCreateRequest.model_validate(
            {
                "incident": {
                    "type_id": "ITYP-001",
                    "occurred_at": "2020-05-15T10:00:00+09:00",
                    "title": "title",
                    "description": "desc",
                    "location_name": "loc",
                    "detector_employee_id": "EMP-00001",
                    "detector_department_id": "DEPT-OPS",
                    "severity": "LOW",
                    "status": "UNKNOWN",
                    "detection_source": "OPS_MONITORING",
                }
            }
        )


def test_response_requires_summary() -> None:
    with pytest.raises(ValidationError):
        ResponseCreateRequest.model_validate(
            {
                "response_type": "SECONDARY",
                "summary": "",
                "detail": "detail",
                "started_at": datetime(2020, 5, 15, 11, 0, tzinfo=datetime.now().astimezone().tzinfo),
            }
        )


def test_valid_enums_accepted() -> None:
    req = IncidentCreateRequest.model_validate(
        {
            "incident": {
                "type_id": "ITYP-001",
                "occurred_at": "2020-05-15T10:00:00+09:00",
                "title": "title",
                "description": "desc",
                "location_name": "loc",
                "detector_employee_id": "EMP-00001",
                "detector_department_id": "DEPT-OPS",
                "severity": Severity.LOW.value,
                "status": IncidentStatus.OPEN.value,
                "detection_source": "OPS_MONITORING",
                "problem_management_no": "PRB-2020-001",
            }
        }
    )
    assert req.incident.problem_management_no == "PRB-2020-001"


def test_problem_management_no_max_length() -> None:
    with pytest.raises(ValidationError):
        IncidentCreateRequest.model_validate(
            {
                "incident": {
                    "type_id": "ITYP-001",
                    "occurred_at": "2020-05-15T10:00:00+09:00",
                    "title": "title",
                    "description": "desc",
                    "location_name": "loc",
                    "detector_employee_id": "EMP-00001",
                    "detector_department_id": "DEPT-OPS",
                    "severity": Severity.LOW.value,
                    "status": IncidentStatus.OPEN.value,
                    "detection_source": "OPS_MONITORING",
                    "problem_management_no": "x" * 129,
                }
            }
        )
