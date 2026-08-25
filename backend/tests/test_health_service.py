"""HealthService の単体テスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.health_service import HealthCheck, HealthService


def test_readiness_all_ok() -> None:
    db = MagicMock()
    db.fetchone.return_value = (1,)
    faiss = MagicMock()
    faiss.exists.return_value = True
    faiss.is_loaded.return_value = True
    svc = HealthService(db=db, faiss=faiss)
    result = svc.check_readiness()
    assert result.ready
    assert result.status == "ready"


def test_readiness_tsurugi_fails() -> None:
    db = MagicMock()
    db.fetchone.side_effect = ConnectionError("connection refused")
    faiss = MagicMock()
    faiss.exists.return_value = True
    faiss.is_loaded.return_value = True
    svc = HealthService(db=db, faiss=faiss)
    result = svc.check_readiness()
    assert not result.ready
    assert result.status == "not_ready"
    tsurugi = next(c for c in result.checks if c.name == "tsurugi")
    assert not tsurugi.ok


def test_degraded_llm_ok() -> None:
    svc = HealthService()
    with patch.object(svc, "_check_llm", return_value=HealthCheck(name="llm", ok=True, detail="ok")):
        result = svc.check_degraded()
    assert result.status == "ok"
