"""ProcedureGenerationService プレビュー生成テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.procedure_generation_service import ProcedureGenerationService

_DRAFT = {
    "title": "障害対応",
    "problem_description": "説明",
    "type_id": "ITYP-001",
    "importance": "MEDIUM",
    "procedure_steps": "手順",
    "precautions": "",
    "is_active": True,
}


def test_generate_preview_uses_llm_result() -> None:
    procedures = MagicMock()
    procedures.build_from_incident.return_value = dict(_DRAFT)
    svc = ProcedureGenerationService(procedures=procedures)
    with patch.object(
        svc,
        "_invoke_llm_parse",
        return_value={
            "title": "AI タイトル",
            "problem_description": "AI 説明",
            "procedure_steps": "AI 手順",
        },
    ):
        preview, meta = svc.generate_preview_for_incident("INC-2020-00001")
    assert preview["title"] == "AI タイトル"
    assert preview["is_active"] is True
    assert meta == {"source": "llm"}


def test_generate_preview_falls_back_on_llm_failure() -> None:
    procedures = MagicMock()
    procedures.build_from_incident.return_value = dict(_DRAFT)
    svc = ProcedureGenerationService(procedures=procedures)
    with patch.object(svc, "_invoke_llm_parse", side_effect=ValueError("no json")):
        preview, meta = svc.generate_preview_for_incident("INC-2020-00001")
    assert preview["title"] == _DRAFT["title"]
    assert meta["source"] == "rule_based"
    assert "no json" in meta["fallback_reason"]


def test_generate_preview_propagates_build_error() -> None:
    procedures = MagicMock()
    procedures.build_from_incident.side_effect = ValueError("incident must be RESOLVED")
    svc = ProcedureGenerationService(procedures=procedures)
    with pytest.raises(ValueError, match="RESOLVED"):
        svc.generate_preview_for_incident("INC-2020-00001")
