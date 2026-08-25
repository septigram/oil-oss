"""チャット API。"""

from __future__ import annotations

import json

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.agent.service import AgentService
from app.auth.dependencies import require_any_authenticated
from app.auth.models import CurrentUser
from app.domain.models import AiModelsResponse, ChatPromptTemplatesResponse, ChatRequest
from app.services.ai_model_service import AiModelService
from app.services.chat_prompt_template import ChatPromptTemplateService

router = APIRouter(prefix="/api", tags=["chat"])
_agent = AgentService()
_model_service = AiModelService()
_prompt_templates = ChatPromptTemplateService()


@router.get("/ai/models", response_model=AiModelsResponse)
def list_ai_models(
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> AiModelsResponse:
    return AiModelsResponse.model_validate(_model_service.list_models())


@router.get("/chat/prompt-templates", response_model=ChatPromptTemplatesResponse)
def list_chat_prompt_templates(
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> ChatPromptTemplatesResponse:
    items = _prompt_templates.list_templates()
    return ChatPromptTemplatesResponse(items=items)


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> EventSourceResponse:
    try:
        llm_provider, model = _model_service.resolve_llm(body.llm_provider, body.model)
        _model_service.validate_llm(llm_provider, model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    messages = [m.model_dump() for m in body.messages]

    async def event_generator():
        async for event in _agent.stream_chat(
            messages,
            body.context_incident_id,
            llm_provider=llm_provider,
            model=model,
            user_roles=user.roles,
        ):
            yield {"data": json.dumps(event, ensure_ascii=False)}

    return EventSourceResponse(event_generator())
