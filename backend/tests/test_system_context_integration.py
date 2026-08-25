"""SystemContextService の DB 統合テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.system_context_service import SystemContextService
from tests.conftest import tsurugi_available

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MASTER_JSON = PROJECT_ROOT / "data" / "20260624T221136" / "master.json"


@pytest.mark.skipif(not tsurugi_available(), reason="Tsurugi not available")
def test_system_context_matches_master_json() -> None:
    expected = json.loads(MASTER_JSON.read_text(encoding="utf-8"))
    svc = SystemContextService()
    result = svc.build_context(None)

    assert result["company"]["company_name"] == expected["company"]["company_name"]
    assert result["company"]["industry"] == expected["company"]["industry"]

    service_names = {s["service_name"] for s in result["services"]}
    assert service_names == {s["service_name"] for s in expected["services"]}

    type_names = {t["type_name"] for t in result["incident_types"]}
    assert type_names == {t["type_name"] for t in expected["incident_types"]}

    assert result["external_events"] == expected["external_events"]
