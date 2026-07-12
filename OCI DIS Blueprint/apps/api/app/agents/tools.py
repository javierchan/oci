"""Typed deterministic application tools available to governed agents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.agent import AgentType
from app.schemas.ai_review import AiReviewGraphContext
from app.schemas.service_products import ServiceVerificationRunRequest


ToolExecutor = Callable[[dict[str, object]], Awaitable[dict[str, object]]]
ReviewScope = Literal["project", "integration"]

EMPTY_PARAMETERS: dict[str, object] = {
    "type": "object", "properties": {}, "required": [], "additionalProperties": False,
}


def _graph_context(value: object) -> AiReviewGraphContext | None:
    return AiReviewGraphContext.model_validate(value) if isinstance(value, dict) else None


def build_tool_executor(
    *,
    agent_type: AgentType,
    project_id: str | None,
    integration_id: str | None,
    context: dict[str, object],
    actor_id: str,
    db: AsyncSession,
) -> tuple[str, str, dict[str, object], ToolExecutor]:
    """Build the one allowlisted deterministic tool for an agent definition."""

    async def architecture(_: dict[str, object]) -> dict[str, object]:
        from app.services.ai_review_service import build_review_result

        if project_id is None:
            raise HTTPException(status_code=422, detail="project_id is required")
        scope: ReviewScope = "integration" if integration_id else "project"
        result = await build_review_result(
            project_id=project_id, scope=scope, integration_id=integration_id,
            include_llm=False, graph_context=_graph_context(context.get("graph_context")),
            reviewer_personas=["architect", "security", "operations", "executive"], db=db,
        )
        return cast(dict[str, object], result.model_dump(mode="json"))

    async def verification(_: dict[str, object]) -> dict[str, object]:
        from app.services.service_product_service import execute_verification_job, run_verification_job

        existing_job_id = context.get("verification_job_id")
        if isinstance(existing_job_id, str) and existing_job_id:
            result = await run_verification_job(existing_job_id, db)
            return cast(dict[str, object], result.model_dump(mode="json"))
        request = ServiceVerificationRunRequest.model_validate(context.get("request", {}))
        result = await execute_verification_job(request, actor_id, db)
        return cast(dict[str, object], result.model_dump(mode="json"))

    async def import_quality(_: dict[str, object]) -> dict[str, object]:
        from app.services.import_service import get_import_quality_assistant

        batch_id = context.get("batch_id")
        if project_id is None or not isinstance(batch_id, str) or not batch_id:
            raise HTTPException(status_code=422, detail="project_id and context.batch_id are required")
        result = await get_import_quality_assistant(project_id, batch_id, db)
        return cast(dict[str, object], result.model_dump(mode="json"))

    async def bom(_: dict[str, object]) -> dict[str, object]:
        from app.services.bom_service import build_scenario_assistant

        if project_id is None:
            raise HTTPException(status_code=422, detail="project_id is required")
        result = await build_scenario_assistant(project_id, db, include_llm=False)
        return cast(dict[str, object], result.model_dump(mode="json"))

    async def support(_: dict[str, object]) -> dict[str, object]:
        from app.services.support_service import build_support_evidence

        return await build_support_evidence(project_id, integration_id, context, db)

    if agent_type == "architecture_review":
        return "load_architecture_review_evidence", "Load governed architecture evidence.", EMPTY_PARAMETERS, architecture
    if agent_type == "integration_design":
        if integration_id is None:
            raise HTTPException(status_code=422, detail="integration_id is required for integration design")
        return "inspect_integration_design", "Inspect the saved canvas and governed route evidence.", EMPTY_PARAMETERS, architecture
    if agent_type == "topology_investigation":
        if not isinstance(context.get("graph_context"), dict):
            raise HTTPException(status_code=422, detail="context.graph_context is required for topology investigation")
        return "inspect_topology_context", "Inspect a selected topology node or dependency path.", EMPTY_PARAMETERS, architecture
    if agent_type == "service_verification":
        return "verify_official_service_sources", "Fetch allowlisted Oracle sources and create findings.", EMPTY_PARAMETERS, verification
    if agent_type == "import_quality":
        return "inspect_import_quality", "Inspect import parsing and quality evidence.", EMPTY_PARAMETERS, import_quality
    if agent_type == "bom_scenario":
        return "inspect_bom_scenario", "Inspect the governed scenario draft and missing inputs.", EMPTY_PARAMETERS, bom
    return (
        "answer_app_support_question",
        "Load bounded App, route, project, integration, and BOM evidence for one support question.",
        EMPTY_PARAMETERS,
        support,
    )
