"""インシデント説明文からの日時抽出（ルール + LLM ハイブリッド）。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.config import AppConfig, get_openai_api_key, get_settings

logger = logging.getLogger(__name__)

DatetimeKind = Literal["occurred", "detected"]

_OCCURRED_KEYWORDS = ("発生", "障害開始", "障害発生", "発生日")
_DETECTED_KEYWORDS = ("検知", "検出", "アラート", "検知日")
_TEMPORAL_HINTS = _OCCURRED_KEYWORDS + _DETECTED_KEYWORDS + ("昨日", "今日", "午前", "午後", "時")

_ISO_PATTERN = re.compile(
    r"(?P<y>\d{4})[-/年](?P<m>\d{1,2})[-/月](?P<d>\d{1,2})日?"
    r"(?:\s*(?P<h>\d{1,2})[:時](?P<min>\d{1,2})(?:[:分](?P<sec>\d{1,2}))?)?",
)
_LABELED_PATTERN = re.compile(
    r"(?P<label>発生(?:日時)?|検知(?:日時)?|障害開始(?:日時)?|アラート(?:日時)?)"
    r"[\s:：は]*"
    r"(?P<y>\d{4})[-/年](?P<m>\d{1,2})[-/月](?P<d>\d{1,2})日?"
    r"(?:\s*(?P<h>\d{1,2})[:時](?P<min>\d{1,2})(?:[:分](?P<sec>\d{1,2}))?)?",
)

_LLM_SYSTEM = """あなたはインシデント説明文から発生日時・検知日時を抽出するアシスタントです。
JSON のみを出力してください。

出力形式:
{
  "occurred_at": "ISO8601（Asia/Tokyo、不明なら null）",
  "detected_at": "ISO8601（Asia/Tokyo、不明なら null）",
  "occurred_excerpt": "根拠抜粋または null",
  "detected_excerpt": "根拠抜粋または null",
  "confidence": "high|medium|low"
}
"""


@dataclass(frozen=True)
class ExtractedDatetime:
    kind: DatetimeKind
    value: datetime
    excerpt: str
    confidence: str


class DatetimeExtractionService:
    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or get_settings()
        self._tz = ZoneInfo(self._settings.timezone)

    def _llm(self):
        ai = self._settings.ai
        provider = ai.llm_provider or ai.provider
        if provider == "openai":
            return ChatOpenAI(
                model=ai.llm_model,
                api_key=get_openai_api_key(),
                temperature=0.0,
            )
        return ChatOllama(
            model=ai.ollama_llm_model,
            base_url=ai.ollama_base_url,
            temperature=0.0,
        )

    def _parse_parts(
        self,
        match: re.Match[str],
        *,
        reference_date: date,
        ambiguous: bool,
    ) -> datetime | None:
        y = int(match.group("y"))
        m = int(match.group("m"))
        d = int(match.group("d"))
        h = match.group("h")
        minute = match.group("min")
        sec = match.group("sec")
        hour = int(h) if h else (9 if ambiguous else 0)
        min_val = int(minute) if minute else 0
        sec_val = int(sec) if sec else 0
        try:
            return datetime(y, m, d, hour, min_val, sec_val, tzinfo=self._tz)
        except ValueError:
            return None

    def _classify_label(self, label: str) -> DatetimeKind:
        text = label.lower()
        if any(k in label for k in ("検知", "検出", "アラート")):
            return "detected"
        return "occurred"

    def _rule_extract(self, text: str, reference_date: date) -> list[ExtractedDatetime]:
        results: list[ExtractedDatetime] = []
        seen: set[tuple[DatetimeKind, str]] = set()

        for match in _LABELED_PATTERN.finditer(text):
            dt = self._parse_parts(match, reference_date=reference_date, ambiguous=False)
            if not dt:
                continue
            kind = self._classify_label(match.group("label"))
            key = (kind, dt.isoformat())
            if key in seen:
                continue
            seen.add(key)
            start = max(0, match.start() - 5)
            end = min(len(text), match.end() + 5)
            results.append(
                ExtractedDatetime(
                    kind=kind,
                    value=dt,
                    excerpt=text[start:end].strip(),
                    confidence="high",
                )
            )

        for match in _ISO_PATTERN.finditer(text):
            if _LABELED_PATTERN.search(text[max(0, match.start() - 20) : match.start()]):
                continue
            dt = self._parse_parts(match, reference_date=reference_date, ambiguous=False)
            if not dt:
                continue
            context = text[max(0, match.start() - 30) : match.end() + 10]
            kind: DatetimeKind = "detected" if any(k in context for k in _DETECTED_KEYWORDS) else "occurred"
            if not any(k in context for k in _OCCURRED_KEYWORDS + _DETECTED_KEYWORDS):
                continue
            key = (kind, dt.isoformat())
            if key in seen:
                continue
            seen.add(key)
            results.append(
                ExtractedDatetime(
                    kind=kind,
                    value=dt,
                    excerpt=context.strip(),
                    confidence="medium",
                )
            )

        if "昨日" in text:
            ref_dt = datetime.combine(reference_date, time(9, 0), tzinfo=self._tz) - timedelta(days=1)
            for kind, kw in (("occurred", "発生"), ("detected", "検知")):
                if kw in text:
                    key = (kind, ref_dt.isoformat())
                    if key not in seen:
                        seen.add(key)
                        results.append(
                            ExtractedDatetime(
                                kind=kind,
                                value=ref_dt,
                                excerpt="昨日",
                                confidence="low",
                            )
                        )

        if "午前中" in text or "午前" in text:
            ref_dt = datetime.combine(reference_date, time(9, 0), tzinfo=self._tz)
            if any(k in text for k in _OCCURRED_KEYWORDS):
                key = ("occurred", ref_dt.isoformat())
                if key not in seen:
                    seen.add(key)
                    results.append(
                        ExtractedDatetime(
                            kind="occurred",
                            value=ref_dt,
                            excerpt="午前中",
                            confidence="low",
                        )
                    )

        return results

    def _llm_extract(self, text: str, title: str, reference_date: date) -> list[ExtractedDatetime]:
        prompt = f"""基準日: {reference_date.isoformat()} (Asia/Tokyo)

タイトル: {title}

説明:
{text[:4000]}
"""
        try:
            llm = self._llm()
            response = llm.invoke(
                [SystemMessage(content=_LLM_SYSTEM), HumanMessage(content=prompt)]
            )
            raw = response.content if isinstance(response.content, str) else str(response.content)
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                return []
            data = json.loads(match.group())
        except Exception as exc:
            logger.warning("datetime LLM extraction failed: %s", exc)
            return []

        confidence = str(data.get("confidence") or "low")
        results: list[ExtractedDatetime] = []
        for kind, field, excerpt_field in (
            ("occurred", "occurred_at", "occurred_excerpt"),
            ("detected", "detected_at", "detected_excerpt"),
        ):
            raw_dt = data.get(field)
            if not raw_dt:
                continue
            try:
                parsed = datetime.fromisoformat(str(raw_dt))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=self._tz)
                else:
                    parsed = parsed.astimezone(self._tz)
            except ValueError:
                continue
            excerpt = str(data.get(excerpt_field) or raw_dt)
            results.append(
                ExtractedDatetime(
                    kind=kind,  # type: ignore[arg-type]
                    value=parsed,
                    excerpt=excerpt,
                    confidence=confidence,
                )
            )
        return results

    def extract_from_text(
        self,
        text: str,
        *,
        title: str = "",
        reference_date: date,
        now: datetime | None = None,
    ) -> list[ExtractedDatetime]:
        combined = f"{title}\n{text}".strip()
        if not combined:
            return []

        rule_results = self._rule_extract(combined, reference_date)
        if rule_results:
            return self._filter_valid(rule_results, now=now)

        if not any(hint in combined for hint in _TEMPORAL_HINTS):
            return []

        llm_results = self._llm_extract(combined, title, reference_date)
        return self._filter_valid(llm_results, now=now)

    def _filter_valid(
        self,
        items: list[ExtractedDatetime],
        *,
        now: datetime | None,
    ) -> list[ExtractedDatetime]:
        if now is None:
            now = datetime.now(self._tz)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=self._tz)
        else:
            now = now.astimezone(self._tz)

        valid: list[ExtractedDatetime] = []
        for item in items:
            if item.value > now + timedelta(minutes=5):
                continue
            valid.append(item)
        return valid

    @staticmethod
    def pick_best(items: list[ExtractedDatetime], kind: DatetimeKind) -> ExtractedDatetime | None:
        candidates = [i for i in items if i.kind == kind]
        if not candidates:
            return None
        rank = {"high": 3, "medium": 2, "low": 1}
        return max(candidates, key=lambda i: rank.get(i.confidence, 0))
