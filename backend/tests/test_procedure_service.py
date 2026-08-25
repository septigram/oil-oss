"""ProcedureService 単体テスト。"""

from unittest.mock import MagicMock

from app.services.procedure_service import ProcedureService, _strip_markdown


def test_strip_markdown() -> None:
    assert _strip_markdown("# Title\n**bold**") == "Title bold"


def test_rerank_prefers_high_success_from_similar_incidents() -> None:
    procedures = MagicMock()
    procedures.get_by_id.side_effect = lambda pid: {
        "PRC-00001": {
            "procedure_id": "PRC-00001",
            "title": "A",
            "is_active": True,
            "success_rate": 90.0,
            "usage_count": 10,
            "type_id": "ITYP-001",
        },
        "PRC-00002": {
            "procedure_id": "PRC-00002",
            "title": "B",
            "is_active": True,
            "success_rate": 50.0,
            "usage_count": 4,
            "type_id": "ITYP-001",
        },
    }.get(pid)

    svc = ProcedureService(procedures=procedures, incidents=MagicMock(), rag=MagicMock())
    vector_hits = [
        {
            "procedure_id": "PRC-00002",
            "title": "B",
            "score": 0.75,
            "success_rate": 50.0,
            "usage_count": 4,
            "type_id": "ITYP-001",
        }
    ]
    similar = [{"applied_procedure_ids": ["PRC-00001"]}]
    ranked = svc._rerank_procedures(vector_hits, similar)
    assert ranked[0]["procedure_id"] == "PRC-00001"
