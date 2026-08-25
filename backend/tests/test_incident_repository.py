"""IncidentRepository 検索条件組み立ての単体テスト。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from app.repository.incident import (
    IncidentAggregateParams,
    IncidentRepository,
    IncidentSearchParams,
    _row_to_incident,
)

TZ = ZoneInfo("Asia/Tokyo")


def _capture_repo() -> tuple[IncidentRepository, MagicMock]:
    db = MagicMock()
    db.fetchone.return_value = (0,)
    db.fetchall.return_value = []
    return IncidentRepository(db=db), db


def test_build_where_includes_keyword_and_status() -> None:
    repo, db = _capture_repo()
    params = IncidentSearchParams(
        keyword="network",
        statuses=["OPEN", "IN_PROGRESS"],
        occurred_from=datetime(2020, 5, 1, tzinfo=TZ),
        occurred_to=datetime(2020, 5, 31, 23, 59, 59, tzinfo=TZ),
        type_id="ITYP-004",
        severities=["HIGH"],
    )
    repo.search(params)
    count_sql, values = db.fetchone.call_args[0]
    assert "i.title LIKE ?" in count_sql
    assert "i.status IN (?,?)" in count_sql
    assert "i.severity IN (?)" in count_sql
    assert "i.type_id = ?" in count_sql
    assert values[0] == "COMP-001"
    assert "%network%" in values


def test_search_uses_limit_literal_without_offset_sql() -> None:
    repo, db = _capture_repo()
    rows = [
        ("INC-1", datetime(2020, 5, 1, tzinfo=TZ), "t", "OPEN", "LOW"),
    ] * 25
    db.fetchone.return_value = (25,)
    db.fetchall.side_effect = [rows[:20], []]
    params = IncidentSearchParams(page=2, page_size=10)
    items, _total = repo.search(params)
    list_sql = db.fetchall.call_args_list[0][0][0]
    assert "OFFSET" not in list_sql.upper()
    assert "LIMIT 20" in list_sql
    assert len(items) == 10


def test_search_filters_by_incident_ids() -> None:
    repo, db = _capture_repo()
    db.fetchone.return_value = (1,)
    db.fetchall.side_effect = [
        [("INC-1", datetime(2020, 5, 1, tzinfo=TZ), "t", "OPEN", "LOW")],
        [],
    ]
    params = IncidentSearchParams(incident_ids=["INC-1"], skip_pagination=True)
    repo.search(params)
    count_sql, values = db.fetchone.call_args[0]
    assert "i.incident_id IN (?)" in count_sql
    assert "INC-1" in values


def test_aggregate_builds_group_by_sql() -> None:
    repo, db = _capture_repo()
    db.fetchall.return_value = [("東京DC", 5), ("大阪DC", 3)]
    params = IncidentAggregateParams(
        group_by="location_name",
        occurred_from=datetime(2020, 4, 1, tzinfo=TZ),
        occurred_to=datetime(2020, 5, 31, 23, 59, 59, tzinfo=TZ),
        statuses=["OPEN"],
        limit=100,
    )
    result = repo.aggregate(params)
    sql, values = db.fetchall.call_args[0]
    assert "GROUP BY i.location_name" in sql
    assert "ORDER BY COUNT(*) DESC" in sql
    assert "LIMIT 100" in sql
    assert "LIMIT ?" not in sql
    assert result["total_incidents"] == 8
    assert result["groups"][0]["key"] == "東京DC"
    assert result["groups"][0]["count"] == 5


def test_aggregate_rejects_invalid_group_by() -> None:
    repo, _db = _capture_repo()
    params = IncidentAggregateParams(
        group_by="title",
        occurred_from=datetime(2020, 4, 1, tzinfo=TZ),
        occurred_to=datetime(2020, 5, 31, 23, 59, 59, tzinfo=TZ),
    )
    result = repo.aggregate(params)
    assert result == {"error": "invalid group_by: title"}


def test_create_does_not_insert_investigation() -> None:
    repo, db = _capture_repo()
    db.fetchall.return_value = []
    occurred_at = datetime(2020, 5, 15, 10, 0, tzinfo=TZ)
    master = MagicMock()
    master.get_type_detection_minutes.return_value = 5
    repo._master = master
    incident_id = repo.create(
        {
            "type_id": "ITYP-001",
            "occurred_at": occurred_at,
            "title": "New incident",
            "description": "desc",
            "location_name": "loc",
            "affected_service_ids": ["SVC-001"],
            "detector_employee_id": "EMP-00001",
            "detector_department_id": "DEPT-OPS",
            "severity": "LOW",
            "status": "OPEN",
            "detection_source": "OPS_MONITORING",
        },
        operator_id="EMP-00001",
    )
    assert incident_id.startswith("INC-2020-")
    insert_sqls = [call[0][0] for call in db.execute.call_args_list]
    assert not any("oil_incident_investigations" in sql for sql in insert_sqls)
    assert any("oil_incidents" in sql for sql in insert_sqls)


def test_row_to_incident_includes_problem_management_no() -> None:
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
        "problem_management_no",
        "row_version",
        "updated_at",
        "updated_by_employee_id",
    ]
    occurred_at = datetime(2020, 5, 15, 10, 0, tzinfo=TZ)
    row = (
        "INC-2020-00001",
        "COMP-001",
        "ITYP-001",
        occurred_at,
        occurred_at,
        "title",
        "desc",
        "loc",
        "SVC-001",
        "EMP-00001",
        "DEPT-OPS",
        "LOW",
        "OPEN",
        "OPS_MONITORING",
        None,
        "PRB-99",
        1,
        occurred_at,
        "EMP-00001",
    )
    data = _row_to_incident(row, cols)
    assert data["problem_management_no"] == "PRB-99"
    assert data["affected_service_ids"] == ["SVC-001"]
