"""ヘルスチェック API。"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.services.health_service import HealthService

router = APIRouter(tags=["health"])
_service = HealthService()


@router.get("/health")
def health_legacy() -> dict[str, str]:
    """後方互換 Liveness。"""
    return {"status": "ok"}


@router.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready(response: Response) -> dict:
    result = _service.check_readiness()
    if not result.ready:
        response.status_code = 503
    return result.to_dict()


@router.get("/health/degraded")
def health_degraded() -> dict:
    return _service.check_degraded().to_dict()
