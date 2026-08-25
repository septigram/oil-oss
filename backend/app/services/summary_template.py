"""集計サマリテンプレートサービス。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config import AppConfig, get_settings
from app.repository.summary_query import SummaryQueryRepository
from app.services.reference_date import ReferenceDateService


@dataclass
class SummaryDocument:
    template_id: str
    doc_id: str
    text: str
    metadata: dict[str, Any]


class SummaryTemplateService:
    def __init__(
        self,
        settings: AppConfig | None = None,
        ref_date: ReferenceDateService | None = None,
        query_repo: SummaryQueryRepository | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._ref_date = ref_date or ReferenceDateService(self._settings)
        self._query_repo = query_repo or SummaryQueryRepository()
        self._templates_path = self._settings.paths.rag_summary_dir / "templates.yaml"

    def _load_templates(self) -> list[dict[str, Any]]:
        with self._templates_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return raw["templates"]

    def build_all_summaries(self, allow_db_fallback: bool = False) -> list[SummaryDocument]:
        base_dir = self._settings.paths.rag_summary_dir
        documents: list[SummaryDocument] = []
        for tmpl in self._load_templates():
            period = self._ref_date.period_range(tmpl["period"])
            sql_path = base_dir / tmpl["sql_file"]
            try:
                count = self._query_repo.execute_sql_file(sql_path, period.start, period.end)
            except Exception:
                if not allow_db_fallback:
                    raise
                count = 0
            text = tmpl["text_template"].format(count=count)
            documents.append(
                SummaryDocument(
                    template_id=tmpl["template_id"],
                    doc_id=tmpl["doc_id"],
                    text=text,
                    metadata={
                        "doc_id": tmpl["doc_id"],
                        "doc_type": "summary",
                        "template_id": tmpl["template_id"],
                        "source": "summary",
                        "count": count,
                    },
                )
            )
        return documents
