"""システム API。"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.domain.models import UiConfigResponse
from app.log_buffer import get_logs_after
from app.metrics import get_recent_metrics
from app.services.reference_date import ReferenceDateService

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/config/ui", response_model=UiConfigResponse)
def get_ui_config() -> UiConfigResponse:
    settings = get_settings()
    ref = ReferenceDateService(settings)
    return UiConfigResponse(
        operator_name=settings.operator.display_name,
        reference_date=ref.get_reference_date().isoformat(),
        reference_date_mode=settings.reference_date.mode,
        timezone=settings.timezone,
    )


@router.get("/metrics/recent")
def get_recent() -> dict:
    return {"items": get_recent_metrics()}


@router.get("/logs/recent")
def get_recent_logs(after: int = 0) -> dict:
    items, next_cursor = get_logs_after(after)
    return {"items": items, "next_cursor": next_cursor}
