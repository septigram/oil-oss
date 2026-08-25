"""手順書 RAG 保存の単体テスト。"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_create_procedure_returns_id() -> None:
    client = TestClient(app)
    with patch("app.api.procedures._procedures") as mock_repo, patch(
        "app.api.procedures._sync_rag_after_procedure_save"
    ):
        mock_repo.create.return_value = "PRC-99999"
        body = {
            "title": "test proc",
            "problem_description": "problem",
            "type_id": "ITYP-001",
            "procedure_steps": "step1",
            "is_active": True,
        }
        resp = client.post("/oil/api/procedures", json=body)
        assert resp.status_code == 201
        assert resp.json()["procedure_id"] == "PRC-99999"
        mock_repo.create.assert_called_once()
