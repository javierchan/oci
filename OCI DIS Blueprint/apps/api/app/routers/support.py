"""Session-isolated contextual App support endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.agent import AgentCreateRequest, SupportConversationResponse, SupportMessageCreateRequest
from app.services import agent_service, support_service
from app.services.authz import require_roles
from app.workers.agent_worker import execute_agent_run_task


router = APIRouter(prefix="/support", tags=["Contextual Support"])


@router.post(
    "/conversations/current",
    response_model=SupportConversationResponse,
    summary="Get or create the current isolated support conversation",
)
async def get_or_create_support_conversation(
    db: AsyncSession = Depends(get_db),
    session_id: str = Header(..., alias="X-Support-Session-Id"),
    actor_id: str = Header("web-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> SupportConversationResponse:
    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst", "Viewer"},
        error_code="SUPPORT_ROLE_REQUIRED",
    )
    async with db.begin():
        return await support_service.get_or_create_conversation(session_id, actor_id, db)


@router.get(
    "/conversations/{conversation_id}",
    response_model=SupportConversationResponse,
    summary="Read one isolated support conversation",
)
async def get_support_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    session_id: str = Header(..., alias="X-Support-Session-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> SupportConversationResponse:
    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst", "Viewer"},
        error_code="SUPPORT_ROLE_REQUIRED",
    )
    return await support_service.get_conversation(conversation_id, session_id, db)


@router.delete(
    "/conversations/{conversation_id}/messages",
    response_model=SupportConversationResponse,
    summary="Clear one isolated support conversation history",
)
async def clear_support_conversation_history(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    session_id: str = Header(..., alias="X-Support-Session-Id"),
    actor_id: str = Header("web-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> SupportConversationResponse:
    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst", "Viewer"},
        error_code="SUPPORT_ROLE_REQUIRED",
    )
    async with db.begin():
        return await support_service.clear_conversation_history(
            conversation_id, session_id, actor_id, db
        )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SupportConversationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit one contextual App support question",
)
async def create_support_message(
    conversation_id: str,
    body: SupportMessageCreateRequest,
    db: AsyncSession = Depends(get_db),
    session_id: str = Header(..., alias="X-Support-Session-Id"),
    actor_id: str = Header("web-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> SupportConversationResponse:
    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst", "Viewer"},
        error_code="SUPPORT_ROLE_REQUIRED",
    )
    async with db.begin():
        _, assistant_message, context = await support_service.prepare_support_turn(
            conversation_id, session_id, body, db
        )
        run = await agent_service.create_agent_run(
            AgentCreateRequest(
                agent_type="support_assistant",
                project_id=body.project_id,
                integration_id=body.integration_id,
                context=context,
                message=body.content,
                include_provider=True,
            ),
            actor_id,
            actor_role,
            db,
        )
        await support_service.link_support_run(assistant_message.id, run.id, db)
        conversation = await support_service.get_conversation(conversation_id, session_id, db)
    try:
        execute_agent_run_task.apply_async(args=[run.id], task_id=run.id, queue="agents")
    except Exception as exc:  # pragma: no cover - defensive dispatch path.
        async with db.begin():
            await agent_service.mark_agent_run_failed(
                run.id, {"detail": f"Unable to dispatch support agent: {exc}"}, db
            )
        raise HTTPException(
            status_code=503,
            detail={"detail": "Support agent could not be dispatched", "error_code": "SUPPORT_DISPATCH_FAILED"},
        ) from exc
    return conversation
