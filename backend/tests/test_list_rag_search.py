"""ListRagSearchService の単体テスト。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from app.repository.incident import IncidentRepository
from app.repository.procedure import ProcedureRepository
from app.services.list_rag_search_service import ListRagSearchService

TZ = ZoneInfo("Asia/Tokyo")


def test_search_incidents_attaches_score_and_paginates() -> None:
    rag = MagicMock()
    rag.search_incidents.return_value = [
        {
            "score": 0.85,
            "metadata": {"incident_id": "INC-2020-00001"},
        },
        {
            "score": 0.75,
            "metadata": {"incident_id": "INC-2020-00002"},
        },
    ]

    incidents = MagicMock(spec=IncidentRepository)
    incidents.search.return_value = (
        [
            {
                "incident_id": "INC-2020-00001",
                "occurred_at": datetime(2020, 5, 1, tzinfo=TZ),
                "title": "a",
                "status": "OPEN",
                "severity": "LOW",
                "response_count": 0,
            },
            {
                "incident_id": "INC-2020-00002",
                "occurred_at": datetime(2020, 5, 2, tzinfo=TZ),
                "title": "b",
                "status": "OPEN",
                "severity": "LOW",
                "response_count": 1,
            },
        ],
        2,
    )

    service = ListRagSearchService(incidents=incidents, rag=rag)
    items, total = service.search_incidents("network outage", page=1, page_size=1)

    assert total == 2
    assert len(items) == 1
    assert items[0]["incident_id"] == "INC-2020-00001"
    assert items[0]["score"] == 85.0
    rag.search_incidents.assert_called_once_with("network outage", top_k=50)


def test_search_incidents_returns_empty_when_below_threshold() -> None:
    rag = MagicMock()
    rag.search_incidents.return_value = [
        {"score": 0.5, "metadata": {"incident_id": "INC-2020-00001"}},
    ]
    incidents = MagicMock(spec=IncidentRepository)

    service = ListRagSearchService(incidents=incidents, rag=rag)
    items, total = service.search_incidents("test")

    assert items == []
    assert total == 0
    incidents.search.assert_not_called()


def test_search_procedures_collects_procedure_ids() -> None:
    rag = MagicMock()
    rag.search_procedures.return_value = [
        {"score": 0.9, "metadata": {"procedure_id": "PRC-00001"}},
    ]
    procedures = MagicMock(spec=ProcedureRepository)
    procedures.search.return_value = (
        [
            {
                "procedure_id": "PRC-00001",
                "title": "proc",
                "type_id": "ITYP-001",
                "usage_count": 1,
                "success_count": 1,
                "success_rate": 100.0,
                "is_active": True,
                "updated_at": datetime(2020, 5, 1, tzinfo=TZ),
            }
        ],
        1,
    )

    service = ListRagSearchService(procedures=procedures, rag=rag)
    items, total = service.search_procedures("restart service")

    assert total == 1
    assert items[0]["score"] == 90.0
    search_params = procedures.search.call_args[0][0]
    assert search_params.procedure_ids == ["PRC-00001"]
    assert search_params.skip_pagination is True
