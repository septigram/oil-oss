"""AI 経由 RAG ログのテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.rag.index_service import RagIndexService, log_ai_rag
from app.repository.ai_sql_context import ai_agent_logging


@patch("app.rag.index_service.log_event")
def test_log_ai_rag_writes_structured_log(mock_log_event: MagicMock) -> None:
    log_ai_rag(
        "先週の件数",
        top_k=5,
        duration_ms=42.5,
        results=[
            {"doc_id": "DOC-SUM-LAST-WEEK-ALL", "score": 0.91},
            {"doc_id": "DOC-INC-00001", "score": 0.75},
        ],
    )
    mock_log_event.assert_called_once()
    kwargs = mock_log_event.call_args.kwargs
    assert kwargs["event"] == "ai_rag"
    assert kwargs["query"] == "先週の件数"
    assert kwargs["top_k"] == 5
    assert kwargs["duration_ms"] == 42.5
    assert kwargs["result_count"] == 2
    assert kwargs["doc_ids"] == ["DOC-SUM-LAST-WEEK-ALL", "DOC-INC-00001"]
    assert kwargs["scores"] == [0.91, 0.75]


@patch("app.rag.index_service.log_event")
def test_rag_search_logs_in_ai_context(mock_log_event: MagicMock) -> None:
    service = RagIndexService()
    mock_store = MagicMock()
    mock_store.exists.return_value = True
    mock_store.search.return_value = [{"doc_id": "DOC-SUM-LAST-WEEK-ALL", "score": 0.8}]
    service._store = mock_store
    with ai_agent_logging():
        results = service.search("先週の件数", top_k=3)
    assert len(results) == 1
    mock_log_event.assert_called_once()
    assert mock_log_event.call_args.kwargs["event"] == "ai_rag"
    assert mock_log_event.call_args.kwargs["result_count"] == 1


@patch("app.rag.index_service.log_event")
def test_rag_search_skips_log_outside_ai_context(mock_log_event: MagicMock) -> None:
    service = RagIndexService()
    mock_store = MagicMock()
    mock_store.exists.return_value = True
    mock_store.search.return_value = []
    service._store = mock_store
    service.search("test", top_k=5)
    mock_log_event.assert_not_called()
