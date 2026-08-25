"""LangGraph AI エージェント。"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date
from typing import Any, AsyncIterator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.agent.aggregate_tool import run_aggregate_incidents
from app.agent.chat_error import format_chat_error_for_client, log_chat_stream_error
from app.agent.context_usage import (
    ContextUsageTracker,
    build_context_usage_event,
    extract_token_usage,
)
from app.agent.triage_tools import (
    make_prompt_user_input_result,
    make_propose_changes_result,
    make_start_triage_result,
    parse_tool_sse_events,
)
from app.config import AppConfig, get_openai_api_key, get_settings
from app.auth.models import Role
from app.domain.models import format_domain_enums_for_prompt, normalize_severities, normalize_statuses
from app.agent.tool_logging import log_mcp_tool_call
from app.logging_config import log_event
from app.metrics import record_metric
from app.rag.index_service import RagIndexService
from app.repository.ai_sql_context import ai_sql_logging
from app.repository.incident import IncidentRepository, IncidentSearchParams
from app.services.ai_model_service import AiModelService
from app.services.notification_service import NotificationService
from app.services.reference_date import ReferenceDateService
from app.services.system_context_service import SystemContextService
from app.services.triage_service import TriageService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """あなたは Ops Incident Ledger のインシデント管理アシスタントです。
日本語で簡潔に回答してください。基準日は {reference_date}（{reference_date_mode}）です。

{domain_enums}

ツールの使い分け:
- 件数・グループ別件数（発生個所別・種別別・状態別など）: aggregate_incidents（group_by と period または occurred_from/to を指定）
- 事前定義の週次サマリ文（先週の件数など）: search_documents_rag で集計サマリ（doc_type=summary）を検索してもよい
- 特定日時・障害内容の質問: まず search_documents_rag、必要なら get_incident_detail で incident_id の詳細を取得
- 対応手順書（KEDB）の検索: search_documents_rag（doc_type=procedure）。手順書 ID は PRC-00001 形式
- 明細一覧・条件検索: search_incidents（日付は occurred_from / occurred_to に YYYY-MM-DD。status には必ず OPEN / IN_PROGRESS / RESOLVED のいずれかを指定。未着手は OPEN）
- キーワードはタイトル・説明の部分一致。cluster 名は中点を含める（例: 運用操作・権限障害）
- 現在日時・タイムゾーン・基準日: get_current_datetime
- 会社概要・サービス構成・顧客・種類定義など運用背景: get_system_context（必要なら sections で絞る）

トリアージ（context_incident_id があるとき）:
- ユーザーがトリアージを依頼した、または新規保存直後の初動確認: start_triage を呼ぶ
- フィールドの変更提案: propose_incident_changes（fields で対象を限定可）
- 不足情報の聞き取り: prompt_user_input（kind: text / radio / checkbox / datetime）
- 重要度は種類の severity_default、影響顧客数、社外原因、回復時間から複合判定する
- 変更提案は必ず start_triage または propose_incident_changes を呼び出すこと（テキストだけで「提案を作成した」と述べない）
- ツールが返す提案はチャット画面に承認カード（受け入れる/却下ボタン）として表示される。ユーザーはカードで承認する

RAG でヒットした incident_id があれば get_incident_detail で詳細を確認してから回答すること。
ツール結果を無視せず、必ずユーザーへの最終回答文を日本語で生成すること。"""

SLACK_VIEWER_PROMPT_SUFFIX = """

Slack からの問い合わせです。参照・検索のみ行い、インシデントや対応の登録・更新は一切行わないでください。
更新や登録を依頼された場合は「Slack からは参照のみ可能です」と回答してください。
日時や運用背景の質問には get_current_datetime / get_system_context を使ってください。"""

_MUTATION_KEYWORDS = (
    "更新して",
    "変更して",
    "登録して",
    "削除して",
    " HIGH に",
    " LOW に",
    " MEDIUM に",
    " CRITICAL に",
    "解決済みに",
    "対応中に",
)


def is_slack_mutation_request(message: str) -> bool:
    normalized = message.strip()
    if not normalized:
        return False
    lower = normalized.lower()
    for keyword in _MUTATION_KEYWORDS:
        if keyword.lower() in lower:
            return True
    if re.search(r"(INC-\d{4}-\d{5}).*(更新|変更|登録|削除)", normalized, re.I):
        return True
    return False


def _streamable_chunk_text(content: Any) -> str:
    """ユーザー向けテキスト。thinking / reasoning ブロックは含めない。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""


def _extract_message_text(message: Any) -> str:
    return _streamable_chunk_text(getattr(message, "content", ""))


def _has_tool_calls(message: Any) -> bool:
    tool_calls = getattr(message, "tool_calls", None)
    return bool(tool_calls)


def _is_tool_only_message(message: Any) -> bool:
    if not _has_tool_calls(message):
        return False
    return not _streamable_chunk_text(getattr(message, "content", "")).strip()


def _is_internal_json_blob(text: str) -> bool:
    """LLM が内部処理用に出力した JSON オブジェクトのみのテキスト。"""
    stripped = text.strip()
    if not stripped.startswith("{"):
        return False
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict)


def _pick_user_facing_response(candidates: list[str], prior: set[str]) -> str:
    """ReAct 中間ターンを除き、最後のユーザー向け応答を選ぶ。"""
    for text in reversed(candidates):
        if not text.strip() or text in prior:
            continue
        if _is_internal_json_blob(text):
            continue
        return text
    return ""


def _is_triage_request(message: str) -> bool:
    return "トリアージ" in message.strip()


class AgentService:
    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or get_settings()
        self._incidents = IncidentRepository()
        self._rag = RagIndexService(self._settings)
        self._ref = ReferenceDateService(self._settings)
        self._system_context = SystemContextService()
        self._triage = TriageService(self._incidents)
        self._model_service = AiModelService(self._settings)
        self._notifications = NotificationService(incidents=self._incidents)

    def _system_prompt(self, *, viewer_only: bool = False) -> str:
        ref_date = self._ref.get_reference_date().isoformat()
        mode = self._settings.reference_date.mode
        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            reference_date=ref_date,
            reference_date_mode=mode,
            domain_enums=format_domain_enums_for_prompt(),
        )
        if viewer_only:
            prompt += SLACK_VIEWER_PROMPT_SUFFIX
        return prompt

    def _parse_date_bound(self, value: str, *, end_of_day: bool = False):
        d = date.fromisoformat(value)
        if end_of_day:
            return self._ref.day_end(d)
        return self._ref.day_start(d)

    def _make_tools(
        self,
        context_incident_id: str | None,
        *,
        viewer_only: bool = False,
        allow_notification: bool = False,
    ):
        incidents = self._incidents
        rag = self._rag
        ref = self._ref
        system_context = self._system_context
        parse_from = self._parse_date_bound

        @tool
        def get_current_datetime() -> str:
            """アプリケーションの現在日時・タイムゾーン・基準日を取得する。相対期間の解釈や「今日」「現在時刻」の回答に使う。"""
            return json.dumps(ref.get_current_datetime_snapshot(), ensure_ascii=False)

        @tool
        def get_system_context(sections: list[str] | None = None) -> str:
            """運用システムの背景情報（企業・サービス・部署・顧客・従業員・インシデント種類・発生個所）を DB マスタから取得する。サービス概要や組織構成の質問に使う。"""
            payload = system_context.build_context(sections)
            return json.dumps(payload, ensure_ascii=False, default=str)

        @tool
        def search_incidents(
            status: list[str] | None = None,
            severity: list[str] | None = None,
            type_id: str | None = None,
            keyword: str | None = None,
            occurred_from: str | None = None,
            occurred_to: str | None = None,
        ) -> str:
            """インシデントを RDB から検索する。status / severity は models.STATUS_SPECS / SEVERITY_SPECS の DB値 を指定（画面表示の日本語は status のみ不可）。occurred_from/to は YYYY-MM-DD。"""
            params = IncidentSearchParams(
                keyword=keyword,
                statuses=normalize_statuses(status),
                severities=normalize_severities(severity),
                type_id=type_id,
                occurred_from=parse_from(occurred_from) if occurred_from else None,
                occurred_to=parse_from(occurred_to, end_of_day=True) if occurred_to else None,
                page=1,
                page_size=20,
            )
            items, total = incidents.search(params)
            return json.dumps({"total": total, "items": items}, ensure_ascii=False, default=str)

        @tool
        def search_documents_rag(query: str) -> str:
            """FAISS RAG で障害報告・調査・対応・集計サマリ・対応手順書（procedure）を検索する。"""
            results = rag.search(query, top_k=10)
            compact = [
                {
                    "doc_id": r.get("doc_id"),
                    "score": r.get("score"),
                    "text": r.get("text", ""),
                    "incident_id": (r.get("metadata") or {}).get("incident_id"),
                    "procedure_id": (r.get("metadata") or {}).get("procedure_id"),
                    "doc_type": (r.get("metadata") or {}).get("doc_type"),
                    "template_id": (r.get("metadata") or {}).get("template_id"),
                }
                for r in results
            ]
            return json.dumps(compact, ensure_ascii=False, default=str)

        @tool
        def get_incident_detail(incident_id: str) -> str:
            """指定インシデントの詳細を取得する。"""
            detail = incidents.get_detail(incident_id)
            if not detail:
                return json.dumps({"error": "not found"})
            return json.dumps(detail, ensure_ascii=False, default=str)

        @tool
        def aggregate_incidents(
            group_by: str,
            period: str | None = None,
            occurred_from: str | None = None,
            occurred_to: str | None = None,
            status: list[str] | None = None,
            severity: list[str] | None = None,
            type_id: str | None = None,
            keyword: str | None = None,
        ) -> str:
            """oil_incidents を GROUP BY して件数を集計する。group_by は許可列のみ。期間は period または occurred_from/to（YYYY-MM-DD）。status/severity は DB値。一覧の明細は search_incidents を使う。"""
            result = run_aggregate_incidents(
                incidents,
                ref,
                parse_from,
                group_by=group_by,
                period=period,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
                status=status,
                severity=severity,
                type_id=type_id,
                keyword=keyword,
                normalize_statuses=normalize_statuses,
                normalize_severities=normalize_severities,
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        tools = [
            get_current_datetime,
            get_system_context,
            search_incidents,
            search_documents_rag,
            get_incident_detail,
            aggregate_incidents,
        ]

        if allow_notification and not viewer_only:
            notifications = self._notifications

            @tool
            def send_incident_notification(
                incident_id: str,
                channel_id: str | None = None,
            ) -> str:
                """インシデント情報を Slack 通知チャネルへ送信する。channel_id 未指定時は種類に紐づく全チャネルへ送る。"""
                channel_ids = [channel_id] if channel_id else None
                sent = notifications.notify_incident(
                    incident_id,
                    channel_ids=channel_ids,
                )
                return json.dumps({"sent": sent, "incident_id": incident_id}, ensure_ascii=False)

            tools.append(send_incident_notification)

        if viewer_only:
            return tools

        @tool
        def prompt_user_input(
            kind: str,
            label: str,
            options: list[dict[str, str]] | None = None,
            required: bool = True,
        ) -> str:
            """ユーザーにチャット UI で入力を促す。kind は text / radio / checkbox / datetime。radio/checkbox では options に value/label の配列を渡す。"""
            normalized = kind.strip().lower()
            if normalized not in ("text", "radio", "checkbox", "datetime"):
                return json.dumps({"error": f"invalid kind: {kind}"})
            return make_prompt_user_input_result(
                kind=normalized,
                label=label,
                options=options,
                required=required,
            )

        tools.append(prompt_user_input)

        if context_incident_id:
            triage = self._triage
            ctx_id = context_incident_id

            @tool
            def get_context_incident() -> str:
                """チャットコンテキストのインシデント詳細を取得する。"""
                detail = incidents.get_detail(ctx_id)
                return json.dumps(detail or {"error": "not found"}, ensure_ascii=False, default=str)

            @tool
            def start_triage(
                recovery_minutes: int | None = None,
                external_cause: bool | None = None,
            ) -> str:
                """コンテキストのインシデントで AI トリアージを開始する。重要度・フィールドの変更提案を生成する。"""
                return make_start_triage_result(
                    triage,
                    ctx_id,
                    recovery_minutes=recovery_minutes,
                    external_cause=external_cause,
                )

            @tool
            def propose_incident_changes(
                fields: list[str] | None = None,
                recovery_minutes: int | None = None,
                external_cause: bool | None = None,
            ) -> str:
                """コンテキストのインシデントについてフィールド変更を提案する。fields は occurred_at / detected_at / type_id / location_name / affected_service_ids / customer_ids / severity。"""
                return make_propose_changes_result(
                    triage,
                    ctx_id,
                    fields,
                    recovery_minutes=recovery_minutes,
                    external_cause=external_cause,
                )

            tools.extend([get_context_incident, start_triage, propose_incident_changes])
        return tools

    def _create_llm(self, llm_provider: str | None = None, model: str | None = None) -> BaseChatModel:
        ai = self._settings.ai
        provider = llm_provider or ai.llm_provider
        if provider == "ollama":
            llm_model = model or ai.ollama_llm_model
            return ChatOllama(
                model=llm_model,
                base_url=ai.ollama_base_url,
                streaming=True,
            )
        llm_model = model or ai.llm_model
        api_key = get_openai_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return ChatOpenAI(
            model=llm_model,
            api_key=api_key,
            streaming=True,
            model_kwargs={"stream_options": {"include_usage": True}},
        )

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        context_incident_id: str | None = None,
        *,
        llm_provider: str | None = None,
        model: str | None = None,
        viewer_only: bool = False,
        user_roles: list[Role] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        start = time.perf_counter()
        llm_ms = 0.0
        tool_ms = 0.0
        allow_notification = bool(
            user_roles and any(r in (Role.ADMIN, Role.OPERATOR) for r in user_roles)
        )
        tools = self._make_tools(
            context_incident_id,
            viewer_only=viewer_only,
            allow_notification=allow_notification,
        )
        llm = self._create_llm(llm_provider, model)
        agent = create_react_agent(llm, tools)

        lc_messages = [SystemMessage(content=self._system_prompt(viewer_only=viewer_only))]
        prior_ai_texts: set[str] = set()
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                content = msg["content"].strip()
                if content:
                    prior_ai_texts.add(content)
                    lc_messages.append(AIMessage(content=content))

        baseline_message_count = len(lc_messages)
        candidate_responses: list[str] = []
        pending_stream_parts: list[str] = []
        tools_ran = False
        proposals_yielded = False
        usage_tracker = ContextUsageTracker()
        resolved_provider, resolved_model = self._model_service.resolve_llm(llm_provider, model)
        context_limit = self._model_service.get_context_limit(resolved_provider, resolved_model)
        user_turns = [m["content"] for m in messages if m["role"] == "user"]
        last_user_message = user_turns[-1] if user_turns else ""
        log_event(
            logger,
            event="chat_request",
            user_message=last_user_message[:300],
            turn=len(user_turns),
            history_messages=len(messages),
            context_incident_id=context_incident_id,
            llm_provider=llm_provider,
            model=model,
        )

        chat_failed = False
        final_response = ""
        try:
            with ai_sql_logging():
                async for event in agent.astream_events(
                    {"messages": lc_messages},
                    version="v2",
                    config={"recursion_limit": 25},
                ):
                    kind = event.get("event")
                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        text = _streamable_chunk_text(chunk.content)
                        if text:
                            pending_stream_parts.append(text)
                    elif kind == "on_chat_model_end":
                        output = event["data"].get("output")
                        if output is not None:
                            prompt_tokens, output_tokens = extract_token_usage(output)
                            if prompt_tokens is not None or output_tokens is not None:
                                usage_tracker.record(prompt_tokens, output_tokens)
                        if _has_tool_calls(output):
                            pending_stream_parts.clear()
                            continue
                        if pending_stream_parts:
                            combined = "".join(pending_stream_parts)
                            pending_stream_parts.clear()
                            if combined.strip():
                                candidate_responses.append(combined)
                        text = _extract_message_text(output)
                        if text and text not in prior_ai_texts:
                            if not candidate_responses or candidate_responses[-1] != text:
                                candidate_responses.append(text)
                            llm_ms = round((time.perf_counter() - start) * 1000, 2)
                    elif kind == "on_tool_end":
                        tools_ran = True
                        tool_ms = round((time.perf_counter() - start) * 1000, 2)
                        data = event.get("data") or {}
                        tool_output = data.get("output")
                        log_mcp_tool_call(
                            logger,
                            tool_name=str(event.get("name") or ""),
                            parameters=data.get("input"),
                            output=tool_output,
                        )
                        for sse_evt in parse_tool_sse_events(tool_output):
                            if sse_evt.get("type") == "proposal":
                                proposals_yielded = True
                            yield sse_evt
                    elif kind == "on_chain_end":
                        output = event["data"].get("output")
                        if not isinstance(output, dict) or "messages" not in output:
                            continue
                        new_messages = output["messages"][baseline_message_count:]
                        for msg in reversed(new_messages):
                            if not isinstance(msg, AIMessage) or _is_tool_only_message(msg):
                                continue
                            text = _extract_message_text(msg)
                            if text.strip() and text not in prior_ai_texts:
                                if not candidate_responses or candidate_responses[-1] != text:
                                    candidate_responses.append(text)
                                break

            final_response = _pick_user_facing_response(candidate_responses, prior_ai_texts)
            if final_response:
                yield {"type": "token", "content": final_response}
            elif tools_ran:
                yield {
                    "type": "error",
                    "message": "ツールは実行しましたが応答文を生成できませんでした。",
                }

            if (
                not viewer_only
                and context_incident_id
                and not proposals_yielded
                and _is_triage_request(last_user_message)
            ):
                triage_result = self._triage.build_proposals(context_incident_id)
                if triage_result:
                    yield {"type": "triage_started", "incident_id": context_incident_id}
                    for prop in triage_result.get("proposals") or []:
                        yield {"type": "proposal", **prop}

            if usage_tracker.llm_calls > 0:
                yield build_context_usage_event(usage_tracker, context_limit)

            yield {"type": "done"}
        except Exception as exc:
            chat_failed = True
            total_ms = round((time.perf_counter() - start) * 1000, 2)
            log_chat_stream_error(
                logger,
                exc,
                llm_provider=llm_provider,
                model=model,
                context_incident_id=context_incident_id,
                turn=len(user_turns),
                duration_ms=total_ms,
            )
            if usage_tracker.llm_calls > 0:
                yield build_context_usage_event(usage_tracker, context_limit)
            yield {
                "type": "error",
                "message": format_chat_error_for_client(
                    exc,
                    llm_provider=llm_provider,
                    model=model,
                ),
            }
        finally:
            total_ms = round((time.perf_counter() - start) * 1000, 2)
            entry: dict[str, Any] = {
                "event": "chat_timing",
                "duration_ms": total_ms,
                "llm_ms": llm_ms,
                "tool_ms": tool_ms,
                "turn": len(user_turns),
                "response_chars": len(final_response) if final_response else 0,
                "llm_provider": llm_provider,
                "model": model,
                "status": "error" if chat_failed else "ok",
            }
            log_event(logger, **entry)
            record_metric(entry)
            try:
                from app.observability.prometheus_metrics import observe_chat_turn

                observe_chat_turn(
                    provider=llm_provider or "unknown",
                    duration_seconds=total_ms / 1000.0,
                )
            except ImportError:
                pass

    async def run_viewer_chat(self, text: str) -> str:
        messages = [{"role": "user", "content": text}]
        final = ""
        async for event in self.stream_chat(messages, viewer_only=True):
            if event.get("type") == "token":
                final = event.get("content", "")
            elif event.get("type") == "error":
                return event.get("message", "エラーが発生しました。")
        return final or "回答を生成できませんでした。"
