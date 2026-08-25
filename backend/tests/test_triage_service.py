"""TriageService 単体テスト。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.domain.models import Severity
from app.services.triage_service import TriageContext, TriageService

TZ = timezone(timedelta(hours=9))


def _ctx(**overrides) -> TriageContext:
    base = {
        "incident_id": "INC-2020-00001",
        "type_id": "ITYP-001",
        "severity_default": Severity.MEDIUM.value,
        "occurred_at": datetime(2020, 5, 15, 10, 0, tzinfo=TZ),
        "detected_at": datetime(2020, 5, 15, 10, 30, tzinfo=TZ),
        "title": "テスト",
        "description": "在庫登録失敗",
        "location_name": "Mercury AWS AP",
        "affected_service_ids": ["SVC-001"],
        "customer_ids": [],
        "severity": Severity.LOW.value,
        "status": "OPEN",
        "recovery_minutes": None,
        "external_cause": False,
    }
    base.update(overrides)
    return TriageContext(**base)


def test_infer_external_cause_by_type():
    svc = TriageService()
    assert svc.infer_external_cause(type_id="ITYP-004", description="") is True
    assert svc.infer_external_cause(type_id="ITYP-001", description="社外の回線") is True
    assert svc.infer_external_cause(type_id="ITYP-001", description="内部設定ミス") is False


def test_suggest_severity_external_cause_raises_to_medium():
    svc = TriageService()
    ctx = _ctx(severity=Severity.LOW.value, external_cause=True)
    suggested, hits = svc.suggest_severity(ctx)
    assert suggested == Severity.MEDIUM.value
    assert "external_cause" in hits


def test_suggest_severity_customers_4plus_high():
    svc = TriageService()
    ctx = _ctx(
        customer_ids=["C1", "C2", "C3", "C4"],
        severity_default=Severity.LOW.value,
    )
    suggested, hits = svc.suggest_severity(ctx)
    assert suggested == Severity.HIGH.value
    assert "customers_4plus" in hits


def test_suggest_severity_recovery_120_critical():
    svc = TriageService()
    ctx = _ctx(recovery_minutes=125, severity_default=Severity.LOW.value)
    suggested, hits = svc.suggest_severity(ctx)
    assert suggested == Severity.CRITICAL.value
    assert "recovery_120min" in hits


def test_suggest_severity_recovery_30_high():
    svc = TriageService()
    ctx = _ctx(recovery_minutes=45, severity_default=Severity.LOW.value)
    suggested, _ = svc.suggest_severity(ctx)
    assert suggested == Severity.HIGH.value


def test_severity_proposal_when_user_too_low():
    svc = TriageService()
    ctx = _ctx(severity=Severity.LOW.value, external_cause=True)
    prop = svc._severity_proposal(ctx)
    assert prop is not None
    assert prop.proposed == Severity.MEDIUM.value


def test_severity_proposal_none_when_user_ok():
    svc = TriageService()
    ctx = _ctx(severity=Severity.HIGH.value, external_cause=True)
    prop = svc._severity_proposal(ctx)
    assert prop is None


def test_compute_recovery_minutes_from_responses():
    svc = TriageService()
    occurred = datetime(2020, 5, 15, 10, 0, tzinfo=TZ)
    ended = datetime(2020, 5, 15, 11, 0, tzinfo=TZ)
    minutes = svc.compute_recovery_minutes(
        occurred_at=occurred,
        status="RESOLVED",
        responses=[{"ended_at": ended}],
    )
    assert minutes == 60


def test_occurred_at_proposal_from_description():
    svc = TriageService()
    ctx = _ctx(
        occurred_at=datetime(2020, 5, 15, 10, 0, tzinfo=TZ),
        description="発生日時: 2020-04-01 09:00 に障害発生",
    )
    prop = svc._occurred_at_proposal(ctx)
    assert prop is not None
    assert "2020-04-01" in prop.proposed
    assert prop.confidence in ("high", "medium", "low")


def test_apply_auto_severity_upgrades():
    incidents = MagicMock()
    masters = MagicMock()
    masters.list_incident_types.return_value = [
        {
            "type_id": "ITYP-004",
            "type_name": "社外",
            "severity_default": Severity.MEDIUM.value,
            "avg_detection_minutes": 30,
        }
    ]
    incidents.get_detail.return_value = {
        "incident": {
            "incident_id": "INC-2020-00001",
            "type_id": "ITYP-004",
            "severity": Severity.LOW.value,
            "occurred_at": datetime(2020, 5, 15, 10, 0, tzinfo=TZ),
            "detected_at": datetime(2020, 5, 15, 10, 30, tzinfo=TZ),
            "title": "t",
            "description": "社外",
            "location_name": "loc",
            "affected_service_ids": [],
            "status": "OPEN",
        },
        "customers": [],
    }
    svc = TriageService(incidents=incidents, masters=masters)
    result = svc.apply_auto_severity(
        "INC-2020-00001",
        external_cause=True,
        operator_id="EMP-00001",
    )
    assert result is not None
    assert result["after"] == Severity.MEDIUM.value
    incidents.update_severity.assert_called_once()


def test_apply_auto_severity_no_change():
    incidents = MagicMock()
    masters = MagicMock()
    masters.list_incident_types.return_value = [
        {
            "type_id": "ITYP-001",
            "type_name": "内部",
            "severity_default": Severity.MEDIUM.value,
            "avg_detection_minutes": 30,
        }
    ]
    incidents.get_detail.return_value = {
        "incident": {
            "incident_id": "INC-2020-00001",
            "type_id": "ITYP-001",
            "severity": Severity.HIGH.value,
            "occurred_at": datetime(2020, 5, 15, 10, 0, tzinfo=TZ),
            "detected_at": datetime(2020, 5, 15, 10, 30, tzinfo=TZ),
            "title": "t",
            "description": "d",
            "location_name": "loc",
            "affected_service_ids": [],
            "status": "OPEN",
        },
        "customers": [],
    }
    svc = TriageService(incidents=incidents, masters=masters)
    result = svc.apply_auto_severity("INC-2020-00001", operator_id="EMP-00001")
    assert result is None
    incidents.update_severity.assert_not_called()


def test_detected_at_proposal_prefers_description_over_average():
    svc = TriageService()
    ctx = _ctx(
        occurred_at=datetime(2020, 4, 1, 9, 0, tzinfo=TZ),
        detected_at=datetime(2020, 5, 15, 10, 30, tzinfo=TZ),
        description="検知日時 2020/04/01 10:30 に検知",
    )
    prop = svc._detected_at_proposal(ctx)
    assert prop is not None
    assert "説明文" in prop.reason
    assert "10:30" in prop.proposed or "10:30:00" in prop.proposed


def test_detected_at_proposal_falls_back_to_average():
    masters = MagicMock()
    masters.list_incident_types.return_value = [
        {
            "type_id": "ITYP-001",
            "type_name": "内部",
            "severity_default": Severity.MEDIUM.value,
            "avg_detection_minutes": 30,
        }
    ]
    svc = TriageService(masters=masters)
    ctx = _ctx(
        occurred_at=datetime(2020, 5, 15, 10, 0, tzinfo=TZ),
        detected_at=datetime(2020, 5, 15, 12, 0, tzinfo=TZ),
        description="在庫登録失敗",
    )
    prop = svc._detected_at_proposal(ctx)
    assert prop is not None
    assert "平均検知時間" in prop.reason
