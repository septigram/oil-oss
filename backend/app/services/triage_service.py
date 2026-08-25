"""インシデント AI トリアージ（ルールベース提案）。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.domain.models import Severity
from app.repository.incident import IncidentRepository
from app.repository.master import MasterRepository
from app.services.datetime_extraction import DatetimeExtractionService, ExtractedDatetime
from app.services.reference_date import ReferenceDateService

EXTERNAL_CAUSE_TYPE_IDS = frozenset({"ITYP-004"})
EXTERNAL_CAUSE_KEYWORDS = ("顧客", "社外", "外部", "顧客側")
SEVERITY_RANK = {
    Severity.LOW.value: 0,
    Severity.MEDIUM.value: 1,
    Severity.HIGH.value: 2,
    Severity.CRITICAL.value: 3,
}

TRIAGE_FIELDS = (
    "occurred_at",
    "detected_at",
    "type_id",
    "location_name",
    "affected_service_ids",
    "customer_ids",
    "severity",
)


@dataclass
class TriageContext:
    incident_id: str
    type_id: str
    severity_default: str
    occurred_at: datetime
    detected_at: datetime
    title: str
    description: str
    location_name: str
    affected_service_ids: list[str]
    customer_ids: list[str]
    severity: str
    status: str
    recovery_minutes: int | None = None
    external_cause: bool = False
    severity_rule_hits: list[str] = field(default_factory=list)


@dataclass
class FieldProposal:
    field: str
    current: Any
    proposed: Any
    reason: str
    confidence: str = "high"
    proposal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "field": self.field,
            "current": self.current,
            "proposed": self.proposed,
            "reason": self.reason,
            "confidence": self.confidence,
        }


class TriageService:
    def __init__(
        self,
        incidents: IncidentRepository | None = None,
        masters: MasterRepository | None = None,
        datetime_extractor: DatetimeExtractionService | None = None,
        reference_dates: ReferenceDateService | None = None,
    ) -> None:
        self._incidents = incidents or IncidentRepository()
        self._masters = masters or MasterRepository()
        self._datetime_extractor = datetime_extractor or DatetimeExtractionService()
        self._reference_dates = reference_dates or ReferenceDateService()

    def _type_meta(self, type_id: str) -> dict[str, Any]:
        for row in self._masters.list_incident_types():
            if row["type_id"] == type_id:
                return row
        return {
            "type_id": type_id,
            "type_name": "",
            "avg_detection_minutes": 30,
            "severity_default": Severity.MEDIUM.value,
            "detection_source": "OPS_MONITORING",
        }

    def infer_external_cause(
        self,
        *,
        type_id: str,
        description: str,
        override: bool | None = None,
    ) -> bool:
        if override is not None:
            return override
        if type_id in EXTERNAL_CAUSE_TYPE_IDS:
            return True
        text = description or ""
        return any(kw in text for kw in EXTERNAL_CAUSE_KEYWORDS)

    def compute_recovery_minutes(
        self,
        *,
        occurred_at: datetime,
        status: str,
        responses: list[dict[str, Any]],
        override: int | None = None,
    ) -> int | None:
        if override is not None:
            return override
        if status != "RESOLVED":
            return None
        ended: list[datetime] = []
        for resp in responses:
            end = resp.get("ended_at")
            if end is not None:
                ended.append(end)
        if not ended:
            return None
        latest = max(ended)
        delta = latest - occurred_at
        return max(0, int(delta.total_seconds() // 60))

    def build_context(
        self,
        incident_id: str,
        *,
        recovery_minutes: int | None = None,
        external_cause: bool | None = None,
    ) -> TriageContext | None:
        detail = self._incidents.get_detail(incident_id)
        if not detail:
            return None
        inc = detail["incident"]
        customers = detail.get("customers") or []
        customer_ids = [c["customer_id"] for c in customers]
        type_meta = self._type_meta(inc["type_id"])
        ext = self.infer_external_cause(
            type_id=inc["type_id"],
            description=inc.get("description") or "",
            override=external_cause,
        )
        recovery = self.compute_recovery_minutes(
            occurred_at=inc["occurred_at"],
            status=inc["status"],
            responses=detail.get("responses") or [],
            override=recovery_minutes,
        )
        return TriageContext(
            incident_id=incident_id,
            type_id=inc["type_id"],
            severity_default=type_meta.get("severity_default", Severity.MEDIUM.value),
            occurred_at=inc["occurred_at"],
            detected_at=inc["detected_at"],
            title=inc.get("title") or "",
            description=inc.get("description") or "",
            location_name=inc.get("location_name") or "",
            affected_service_ids=list(inc.get("affected_service_ids") or []),
            customer_ids=customer_ids,
            severity=inc.get("severity") or Severity.MEDIUM.value,
            status=inc.get("status") or "OPEN",
            recovery_minutes=recovery,
            external_cause=ext,
        )

    def suggest_severity(self, ctx: TriageContext) -> tuple[str, list[str]]:
        hits: list[str] = []
        level = Severity.LOW.value

        if ctx.severity_default == Severity.CRITICAL.value or (
            ctx.recovery_minutes is not None and ctx.recovery_minutes >= 120
        ):
            level = Severity.CRITICAL.value
            if ctx.severity_default == Severity.CRITICAL.value:
                hits.append("severity_default_critical")
            if ctx.recovery_minutes is not None and ctx.recovery_minutes >= 120:
                hits.append("recovery_120min")

        if ctx.severity_default == Severity.HIGH.value or len(ctx.customer_ids) >= 4 or (
            ctx.recovery_minutes is not None and ctx.recovery_minutes >= 30
        ):
            if SEVERITY_RANK.get(level, 0) < SEVERITY_RANK[Severity.HIGH.value]:
                level = Severity.HIGH.value
            if ctx.severity_default == Severity.HIGH.value:
                hits.append("severity_default_high")
            if len(ctx.customer_ids) >= 4:
                hits.append("customers_4plus")
            if ctx.recovery_minutes is not None and ctx.recovery_minutes >= 30:
                hits.append("recovery_30min")

        if ctx.severity_default == Severity.MEDIUM.value or len(ctx.customer_ids) >= 1 or ctx.external_cause:
            if SEVERITY_RANK.get(level, 0) < SEVERITY_RANK[Severity.MEDIUM.value]:
                level = Severity.MEDIUM.value
            if ctx.severity_default == Severity.MEDIUM.value:
                hits.append("severity_default_medium")
            if len(ctx.customer_ids) >= 1:
                hits.append("customers_1plus")
            if ctx.external_cause:
                hits.append("external_cause")

        ctx.severity_rule_hits = hits
        return level, hits

    def _severity_proposal(self, ctx: TriageContext) -> FieldProposal | None:
        suggested, hits = self.suggest_severity(ctx)
        current = ctx.severity
        if SEVERITY_RANK.get(current, 0) >= SEVERITY_RANK.get(suggested, 0):
            return None
        reason_parts = [f"ルール上の推奨重要度は {suggested}"]
        if "external_cause" in hits:
            reason_parts.append("社外原因のため MEDIUM 以上が必要")
        if "customers_4plus" in hits:
            reason_parts.append("影響顧客が 4 社以上")
        if "recovery_120min" in hits:
            reason_parts.append("回復まで 2 時間以上")
        elif "recovery_30min" in hits:
            reason_parts.append("回復まで 30 分以上")
        return FieldProposal(
            field="severity",
            current=current,
            proposed=suggested,
            reason="。".join(reason_parts),
        )

    def _extract_datetimes(self, ctx: TriageContext) -> list[ExtractedDatetime]:
        ref = self._reference_dates.get_reference_date()
        now = self._reference_dates.day_end(ref)
        return self._datetime_extractor.extract_from_text(
            ctx.description,
            title=ctx.title,
            reference_date=ref,
            now=now,
        )

    def _occurred_at_proposal(self, ctx: TriageContext) -> FieldProposal | None:
        extracted = self._extract_datetimes(ctx)
        best = DatetimeExtractionService.pick_best(extracted, "occurred")
        if not best:
            return None
        if abs((best.value - ctx.occurred_at).total_seconds()) < 60:
            return None
        detected_best = DatetimeExtractionService.pick_best(extracted, "detected")
        if detected_best and best.value > detected_best.value:
            return None
        return FieldProposal(
            field="occurred_at",
            current=ctx.occurred_at.isoformat(),
            proposed=best.value.isoformat(),
            reason=f"説明文の記述に基づく発生日時（抜粋: 「{best.excerpt}」）",
            confidence=best.confidence,
        )

    def _detected_at_proposal(self, ctx: TriageContext) -> FieldProposal | None:
        extracted = self._extract_datetimes(ctx)
        best = DatetimeExtractionService.pick_best(extracted, "detected")
        if best:
            if best.value < ctx.occurred_at:
                return None
            if abs((best.value - ctx.detected_at).total_seconds()) < 60:
                return None
            return FieldProposal(
                field="detected_at",
                current=ctx.detected_at.isoformat(),
                proposed=best.value.isoformat(),
                reason=f"説明文の記述に基づく検知日時（抜粋: 「{best.excerpt}」）",
                confidence=best.confidence,
            )

        type_meta = self._type_meta(ctx.type_id)
        minutes = int(type_meta.get("avg_detection_minutes", 30))
        proposed = ctx.occurred_at + timedelta(minutes=minutes)
        if abs((proposed - ctx.detected_at).total_seconds()) < 60:
            return None
        return FieldProposal(
            field="detected_at",
            current=ctx.detected_at.isoformat(),
            proposed=proposed.isoformat(),
            reason=f"種類の平均検知時間（{minutes} 分）に基づく推奨検知日時",
            confidence="medium",
        )

    def _location_proposal(self, ctx: TriageContext) -> FieldProposal | None:
        locations = self._masters.list_incident_type_locations(ctx.type_id)
        if not locations:
            return None
        names = [loc["location_name"] for loc in locations]
        if ctx.location_name in names:
            return None
        desc = ctx.description.lower()
        for loc in locations:
            name = loc["location_name"]
            if name.lower() in desc or name.split()[0].lower() in desc:
                return FieldProposal(
                    field="location_name",
                    current=ctx.location_name,
                    proposed=name,
                    reason=f"説明文と種類に紐づく発生個所候補「{name}」",
                    confidence="medium",
                )
        if len(names) == 1 and not ctx.location_name.strip():
            return FieldProposal(
                field="location_name",
                current=ctx.location_name,
                proposed=names[0],
                reason="種類に紐づく唯一の発生個所候補",
                confidence="low",
            )
        return None

    def _type_proposal(self, ctx: TriageContext) -> FieldProposal | None:
        text = f"{ctx.title} {ctx.description}".lower()
        best_id: str | None = None
        best_score = 0
        for row in self._masters.list_incident_types():
            type_name = (row.get("type_name") or "").lower()
            score = 0
            for token in re.split(r"[\s・、]+", type_name):
                if len(token) >= 2 and token in text:
                    score += 2
            if type_name and type_name in text:
                score += 3
            if score > best_score:
                best_score = score
                best_id = row["type_id"]
        if best_id and best_id != ctx.type_id and best_score >= 2:
            meta = self._type_meta(best_id)
            return FieldProposal(
                field="type_id",
                current=ctx.type_id,
                proposed=best_id,
                reason=f"説明文に近い種類候補「{meta.get('type_name', best_id)}」",
                confidence="medium",
            )
        return None

    def build_proposals(
        self,
        incident_id: str,
        *,
        focus_fields: list[str] | None = None,
        recovery_minutes: int | None = None,
        external_cause: bool | None = None,
    ) -> dict[str, Any] | None:
        ctx = self.build_context(
            incident_id,
            recovery_minutes=recovery_minutes,
            external_cause=external_cause,
        )
        if not ctx:
            return None

        fields = focus_fields or list(TRIAGE_FIELDS)
        proposals: list[FieldProposal] = []

        if "severity" in fields:
            p = self._severity_proposal(ctx)
            if p:
                proposals.append(p)
        if "occurred_at" in fields:
            p = self._occurred_at_proposal(ctx)
            if p:
                proposals.append(p)
        if "detected_at" in fields:
            p = self._detected_at_proposal(ctx)
            if p:
                proposals.append(p)
        if "location_name" in fields:
            p = self._location_proposal(ctx)
            if p:
                proposals.append(p)
        if "type_id" in fields:
            p = self._type_proposal(ctx)
            if p:
                proposals.append(p)

        suggested, hits = self.suggest_severity(ctx)
        return {
            "incident_id": incident_id,
            "proposals": [p.to_dict() for p in proposals],
            "suggested_severity": suggested,
            "severity_rule_hits": hits,
        }

    def start_triage(
        self,
        incident_id: str,
        *,
        recovery_minutes: int | None = None,
        external_cause: bool | None = None,
    ) -> dict[str, Any] | None:
        result = self.build_proposals(
            incident_id,
            recovery_minutes=recovery_minutes,
            external_cause=external_cause,
        )
        if not result:
            return None
        result["status"] = "started"
        return result

    def apply_auto_severity(
        self,
        incident_id: str,
        *,
        recovery_minutes: int | None = None,
        external_cause: bool | None = None,
        operator_id: str,
    ) -> dict[str, Any] | None:
        ctx = self.build_context(
            incident_id,
            recovery_minutes=recovery_minutes,
            external_cause=external_cause,
        )
        if not ctx:
            return None
        proposal = self._severity_proposal(ctx)
        if not proposal:
            return None
        before = proposal.current
        after = proposal.proposed
        self._incidents.update_severity(incident_id, after, operator_id=operator_id)
        _, hits = self.suggest_severity(ctx)
        return {
            "incident_id": incident_id,
            "before": before,
            "after": after,
            "rule_hits": hits,
        }
