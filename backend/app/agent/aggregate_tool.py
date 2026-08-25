"""aggregate_incidents ツールの期間解決とレスポンス整形。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from app.repository.incident import IncidentAggregateParams, IncidentRepository
from app.services.reference_date import ReferenceDateService


def resolve_aggregate_date_range(
    period: str | None,
    occurred_from: str | None,
    occurred_to: str | None,
    ref: ReferenceDateService,
    parse_date_bound: Callable[..., datetime],
) -> dict[str, Any] | tuple[datetime, datetime, str | None]:
    """期間を解決する。成功時は (start, end, period) を、失敗時は error dict を返す。"""
    if period:
        try:
            date_range = ref.period_range(period)
            return date_range.start, date_range.end, period
        except ValueError:
            return {"error": f"unknown period: {period}"}

    if occurred_from and occurred_to:
        start = parse_date_bound(occurred_from)
        end = parse_date_bound(occurred_to, end_of_day=True)
        return start, end, None

    if occurred_from or occurred_to:
        return {"error": "both occurred_from and occurred_to are required when period is omitted"}

    return {"error": "period or occurred_from/to is required"}


def run_aggregate_incidents(
    incidents: IncidentRepository,
    ref: ReferenceDateService,
    parse_date_bound: Callable[..., datetime],
    *,
    group_by: str,
    period: str | None = None,
    occurred_from: str | None = None,
    occurred_to: str | None = None,
    status: list[str] | None = None,
    severity: list[str] | None = None,
    type_id: str | None = None,
    keyword: str | None = None,
    normalize_statuses: Callable[[list[str] | None], list[str] | None],
    normalize_severities: Callable[[list[str] | None], list[str] | None],
) -> dict[str, Any]:
    resolved = resolve_aggregate_date_range(
        period,
        occurred_from,
        occurred_to,
        ref,
        parse_date_bound,
    )
    if isinstance(resolved, dict):
        return resolved

    start, end, resolved_period = resolved
    params = IncidentAggregateParams(
        group_by=group_by,
        occurred_from=start,
        occurred_to=end,
        statuses=normalize_statuses(status),
        severities=normalize_severities(severity),
        type_id=type_id,
        keyword=keyword,
    )
    result = incidents.aggregate(params)
    if "error" in result:
        return result

    return {
        **result,
        "period": resolved_period,
        "occurred_from": start.isoformat(),
        "occurred_to": end.isoformat(),
        "filters": {
            "status": normalize_statuses(status),
            "severity": normalize_severities(severity),
            "type_id": type_id,
            "keyword": keyword,
        },
    }
