"""パステンプレート正規化の単体テスト。"""

from __future__ import annotations

from app.observability.path_template import normalize_path_template


def test_incident_id_normalized() -> None:
    path = "/oil/api/incidents/INC-2026-00001"
    assert normalize_path_template(path, context_path="/oil") == "/oil/api/incidents/{id}"


def test_procedure_id_normalized() -> None:
    path = "/oil/api/procedures/PRC-00042"
    assert normalize_path_template(path, context_path="/oil") == "/oil/api/procedures/{id}"


def test_list_path_unchanged() -> None:
    path = "/oil/api/incidents"
    assert normalize_path_template(path, context_path="/oil") == path
