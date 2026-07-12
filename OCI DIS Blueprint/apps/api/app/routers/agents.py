"""Governed agent catalog, execution, cancellation, and approval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.agent import (
    AgentApprovalDecisionRequest,
    AgentCreateRequest,
    AgentDefinitionResponse,
    AgentProviderStatusResponse,
    AgentRunListResponse,
    AgentRunResponse,
)
from app.services import agent_service
from app.services.authz import require_roles
from app.workers.agent_worker import execute_agent_run_task


router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("/provider-status", response_model=AgentProviderStatusResponse, summary="Inspect agent provider readiness")
async def get_agent_provider_status(
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> AgentProviderStatusResponse:
    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst", "Viewer"},
        error_code="AGENT_PROVIDER_STATUS_ROLE_REQUIRED",
    )
    return await agent_service.get_agent_provider_status(db)


@router.get("", response_model=list[AgentDefinitionResponse], summary="List governed agent definitions")
async def list_agents(
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> list[AgentDefinitionResponse]:
    return agent_service.list_agent_definitions(actor_role)


@router.post("/runs", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED, summary="Create an agent run")
async def create_agent_run(
    body: AgentCreateRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AgentRunResponse:
    async with db.begin():
        run = await agent_service.create_agent_run(body, actor_id, actor_role, db)
    try:
        execute_agent_run_task.apply_async(args=[run.id], task_id=run.id, queue="agents")
    except Exception as exc:  # pragma: no cover - defensive dispatch path.
        async with db.begin():
            await agent_service.mark_agent_run_failed(run.id, {"detail": f"Unable to dispatch agent: {exc}"}, db)
        raise HTTPException(status_code=503, detail={"detail": "Agent worker could not be dispatched", "error_code": "AGENT_DISPATCH_FAILED"}) from exc
    return run


@router.get("/runs", response_model=AgentRunListResponse, summary="List governed agent runs")
async def list_agent_runs(
    project_id: str | None = Query(None), limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AgentRunListResponse:
    return await agent_service.list_agent_runs(db, actor_role=actor_role, project_id=project_id, limit=limit)


@router.get("/runs/{run_id}", response_model=AgentRunResponse, summary="Inspect one agent run")
async def get_agent_run(
    run_id: str, db: AsyncSession = Depends(get_db),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AgentRunResponse:
    return await agent_service.get_agent_run(run_id, actor_role, db)


@router.post("/runs/{run_id}/cancel", response_model=AgentRunResponse, summary="Request agent cancellation")
async def cancel_agent_run(
    run_id: str, db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AgentRunResponse:
    async with db.begin():
        return await agent_service.request_agent_cancellation(run_id, actor_id, actor_role, db)


@router.post("/runs/{run_id}/approvals/{approval_id}", response_model=AgentRunResponse, summary="Decide an agent proposal")
async def decide_agent_approval(
    run_id: str, approval_id: str, body: AgentApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AgentRunResponse:
    async with db.begin():
        return await agent_service.decide_agent_approval(run_id, approval_id, body, actor_id, actor_role, db)
