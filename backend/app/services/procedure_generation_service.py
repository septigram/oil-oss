"""手順書 LLM バッチ生成サービス。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.config import AppConfig, get_openai_api_key, get_settings
from app.repository.procedure import ProcedureRepository

logger = logging.getLogger(__name__)

_SYSTEM = """あなたは IT インシデント対応手順書を作成するアシスタントです。
入力されたインシデント情報とたたき台をもとに、再利用可能な対応手順書を JSON で出力してください。

出力形式（JSON のみ、説明文不要）:
{
  "title": "100文字以内のタイトル",
  "problem_description": "Markdown形式の問題説明",
  "procedure_steps": "Markdown形式のステップバイステップ手順",
  "precautions": "Markdown形式の注意事項（任意）",
  "required_tools": "Markdown形式の必要機材（任意、null可）"
}
"""


class ProcedureGenerationService:
    def __init__(
        self,
        settings: AppConfig | None = None,
        procedures: ProcedureRepository | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._procedures = procedures or ProcedureRepository()

    def _llm(self):
        ai = self._settings.ai
        provider = ai.llm_provider or ai.provider
        if provider == "openai":
            return ChatOpenAI(
                model=ai.llm_model,
                api_key=get_openai_api_key(),
                temperature=0.2,
            )
        return ChatOllama(
            model=ai.ollama_llm_model,
            base_url=ai.ollama_base_url,
            temperature=0.2,
        )

    def _build_prompt(self, incident_id: str, draft: dict[str, Any]) -> str:
        return f"""インシデント ID: {incident_id}

## たたき台
タイトル: {draft['title']}
問題説明:
{draft['problem_description'][:3000]}

手順:
{draft['procedure_steps'][:3000]}
"""

    def _invoke_llm_parse(self, incident_id: str, draft: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(incident_id, draft)
        llm = self._llm()
        response = llm.invoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        text = response.content if isinstance(response.content, str) else str(response.content)
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError("LLM response did not contain JSON")
        return json.loads(match.group())

    def _merge_generated(
        self,
        incident_id: str,
        draft: dict[str, Any],
        generated: dict[str, Any],
        *,
        is_active: bool,
    ) -> dict[str, Any]:
        return {
            "title": str(generated.get("title", draft["title"]))[:100],
            "problem_description": str(
                generated.get("problem_description", draft["problem_description"])
            )[:16384],
            "type_id": draft["type_id"],
            "importance": draft["importance"],
            "procedure_steps": str(
                generated.get("procedure_steps", draft["procedure_steps"])
            )[:16384],
            "required_tools": generated.get("required_tools"),
            "precautions": generated.get("precautions") or draft.get("precautions"),
            "estimated_time": None,
            "source_incident_id": incident_id,
            "tags": None,
            "is_active": is_active,
        }

    def generate_preview_for_incident(self, incident_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """UI 用プレビュー。DB INSERT なし。LLM 失敗時はルールベースへフォールバック。"""
        draft = self._procedures.build_from_incident(incident_id)
        try:
            generated = self._invoke_llm_parse(incident_id, draft)
            preview = self._merge_generated(incident_id, draft, generated, is_active=True)
            return preview, {"source": "llm"}
        except Exception as exc:
            logger.warning("procedure preview LLM fallback: %s", exc)
            return draft, {"source": "rule_based", "fallback_reason": str(exc)}

    def generate_for_incident(self, incident_id: str) -> dict[str, Any]:
        draft = self._procedures.build_from_incident(incident_id)
        generated = self._invoke_llm_parse(incident_id, draft)
        return self._merge_generated(incident_id, draft, generated, is_active=False)
