"""ドメインモデル・列挙型。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DetectionSource(StrEnum):
    OPS_MONITORING = "OPS_MONITORING"
    SALES_INQUIRY = "SALES_INQUIRY"


class ResponseType(StrEnum):
    INITIAL = "INITIAL"
    SECONDARY = "SECONDARY"
    TERTIARY = "TERTIARY"
    PERMANENT = "PERMANENT"


# (DB値, 画面表示) — UI・API・DB で共有する唯一の対応表（status は日本語、severity は英字）
STATUS_SPECS: tuple[tuple[str, str], ...] = (
    (IncidentStatus.OPEN.value, "未着手"),
    (IncidentStatus.IN_PROGRESS.value, "対応中"),
    (IncidentStatus.RESOLVED.value, "解決済み"),
)

SEVERITY_SPECS: tuple[tuple[str, str], ...] = (
    (Severity.CRITICAL.value, Severity.CRITICAL.value),
    (Severity.HIGH.value, Severity.HIGH.value),
    (Severity.MEDIUM.value, Severity.MEDIUM.value),
    (Severity.LOW.value, Severity.LOW.value),
)

# 単一 DB値 ではない検索用複合条件（user-requirements の未完了・未解決）
STATUS_COMPOSITE_FILTERS: dict[str, tuple[str, ...]] = {
    "未完了": (IncidentStatus.OPEN.value, IncidentStatus.IN_PROGRESS.value),
    "未解決": (IncidentStatus.OPEN.value, IncidentStatus.IN_PROGRESS.value),
}

STATUS_LABELS = {IncidentStatus(db): display for db, display in STATUS_SPECS}


def status_display_label(db_value: str) -> str:
    """DB値（OPEN 等）を画面表示（未着手 等）に変換する。"""
    return dict(STATUS_SPECS).get(db_value, db_value)


def _db_values(specs: tuple[tuple[str, str], ...]) -> frozenset[str]:
    return frozenset(db for db, _ in specs)


def _display_to_db(specs: tuple[tuple[str, str], ...]) -> dict[str, str]:
    return {display: db for db, display in specs}


def _normalize_column_tokens(
    tokens: list[str] | None,
    specs: tuple[tuple[str, str], ...],
    *,
    composites: dict[str, tuple[str, ...]] | None = None,
) -> list[str] | None:
    """対応表に基づき DB値 に正規化する。対応表にない入力は無視する。"""
    if not tokens:
        return None
    valid_db = _db_values(specs)
    display_to_db = _display_to_db(specs)
    normalized: list[str] = []
    for raw in tokens:
        token = raw.strip()
        if not token:
            continue
        if composites and token in composites:
            normalized.extend(composites[token])
            continue
        upper = token.upper()
        if upper in valid_db:
            normalized.append(upper)
            continue
        if token in display_to_db:
            normalized.append(display_to_db[token])
            continue
    if not normalized:
        return None
    return list(dict.fromkeys(normalized))


def normalize_statuses(statuses: list[str] | None) -> list[str] | None:
    return _normalize_column_tokens(
        statuses,
        STATUS_SPECS,
        composites=STATUS_COMPOSITE_FILTERS,
    )


def normalize_severities(severities: list[str] | None) -> list[str] | None:
    return _normalize_column_tokens(severities, SEVERITY_SPECS)


def format_domain_enums_for_prompt() -> str:
    """エージェントシステムプロンプト用の列値対応表（STATUS_SPECS / SEVERITY_SPECS から生成）。"""
    lines = [
        "oil_incidents の列値対応（search_incidents 引数および SQL の WHERE には必ず「DB値」を使用）:",
        "",
        "## status（状態）",
        "",
        "| DB値 | 画面表示 |",
        "|------|----------|",
    ]
    for db, display in STATUS_SPECS:
        lines.append(f"| {db} | {display} |")
    lines.extend(
        [
            "",
            f"有効な DB値: {', '.join(db for db, _ in STATUS_SPECS)} のみ。",
            "画面表示の文字列（未着手・対応中・解決済み）を DB値 の代わりに使ってはならない。",
            "上記以外（unassigned / pending 等）は無効。",
            "",
            "検索上の複合条件（単一 DB値 ではない。status 引数に列挙で複数指定）:",
            "",
            "| ユーザー表現 | 指定する DB値 |",
            "|--------------|---------------|",
        ]
    )
    for label, values in STATUS_COMPOSITE_FILTERS.items():
        lines.append(f"| {label} | {', '.join(values)} |")
    lines.extend(
        [
            "",
            "## severity（重要度）",
            "",
            "| DB値 | 画面表示 |",
            "|------|----------|",
        ]
    )
    for db, display in SEVERITY_SPECS:
        lines.append(f"| {db} | {display} |")
    lines.append("")
    lines.append(
        f"有効な DB値: {', '.join(db for db, _ in SEVERITY_SPECS)} のみ。"
        " 本システムでは画面表示と DB値 は同一の英字コード。"
    )
    return "\n".join(lines)


class IncidentListItem(BaseModel):
    incident_id: str
    occurred_at: datetime
    title: str
    status: str
    status_label: str
    severity: str
    response_count: int


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class IncidentBase(BaseModel):
    type_id: str
    occurred_at: datetime
    title: str = Field(min_length=1, max_length=512)
    description: str = Field(min_length=1, max_length=4096)
    location_name: str = Field(min_length=1, max_length=256)
    affected_service_ids: list[str] = Field(default_factory=list)
    detector_employee_id: str
    detector_department_id: str
    severity: Severity
    status: IncidentStatus
    detection_source: DetectionSource
    related_event_id: str | None = None
    problem_management_no: str | None = Field(default=None, max_length=128)


class IncidentCreateRequest(BaseModel):
    incident: IncidentBase
    customer_ids: list[str] = Field(default_factory=list)
    detected_at: datetime | None = None


class IncidentUpdateRequest(BaseModel):
    incident: IncidentBase
    customer_ids: list[str] = Field(default_factory=list)
    detected_at: datetime | None = None
    row_version: int


class TriageProposalsResponse(BaseModel):
    incident_id: str
    proposals: list[dict[str, Any]]
    suggested_severity: str
    severity_rule_hits: list[str]


class ResponseCreateRequest(BaseModel):
    response_type: ResponseType
    summary: str = Field(min_length=1, max_length=2048)
    detail: str = Field(min_length=1, max_length=8192)
    started_at: datetime
    ended_at: datetime | None = None


class ResponseUpdateRequest(BaseModel):
    response_type: ResponseType
    summary: str = Field(min_length=1, max_length=2048)
    detail: str = Field(min_length=1, max_length=8192)
    started_at: datetime
    ended_at: datetime | None = None
    row_version: int


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context_incident_id: str | None = None
    llm_provider: str | None = None
    model: str | None = None


class LlmModelOption(BaseModel):
    provider: str
    model: str
    label: str


class LlmDefaultOption(BaseModel):
    provider: str
    model: str


class LlmSourceStatus(BaseModel):
    provider: str
    status: str
    error: str | None = None


class AiModelsResponse(BaseModel):
    default: LlmDefaultOption
    items: list[LlmModelOption]
    sources: list[LlmSourceStatus]


class ChatPromptTemplateItem(BaseModel):
    id: str
    label: str
    message: str


class ChatPromptTemplatesResponse(BaseModel):
    items: list[ChatPromptTemplateItem]


class UiConfigResponse(BaseModel):
    operator_name: str
    reference_date: str
    reference_date_mode: str
    timezone: str


class ProcedureImportance(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ProcedureBase(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    problem_description: str = Field(min_length=1, max_length=16384)
    type_id: str
    importance: ProcedureImportance | None = None
    procedure_steps: str = Field(min_length=1, max_length=16384)
    required_tools: str | None = Field(default=None, max_length=4096)
    precautions: str | None = Field(default=None, max_length=4096)
    estimated_time: str | None = Field(default=None, max_length=50)
    source_incident_id: str | None = None
    tags: str | None = Field(default=None, max_length=512)
    is_active: bool = True


class ProcedureCreateRequest(ProcedureBase):
    pass


class ProcedureUpdateRequest(ProcedureBase):
    row_version: int


class ProcedureApplyRequest(BaseModel):
    procedure_id: str
    notes: str | None = Field(default=None, max_length=4096)


class ProcedureSuccessUpdateRequest(BaseModel):
    was_successful: bool
    notes: str | None = Field(default=None, max_length=4096)
