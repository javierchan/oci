"""AI review router for governed architecture review board jobs."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import AiReviewJob
from app.schemas.ai_review import (
    AiReviewAcceptRecommendationRequest,
    AiReviewApplyPatchRequest,
    AiReviewApplyPatchResponse,
    AiReviewBaselineCreateRequest,
    AiReviewBaselineListResponse,
    AiReviewBaselineLookupResponse,
    AiReviewBaselineResponse,
    AiReviewCreateRequest,
    AiReviewDraftSimulationRequest,
    AiReviewDraftSimulationResponse,
    AiReviewJobCompareResponse,
    AiReviewJobListResponse,
    AiReviewJobResponse,
    AiReviewProviderStatus,
    AiReviewSelectDraftRequest,
    AiReviewSelectDraftResponse,
    AiReviewScope,
)
from app.services import agent_service, ai_review_service, ai_review_simulation
from app.schemas.agent import AgentCreateRequest, AgentType
from app.services.authz import require_ai_review_mutation, require_ai_review_read, require_ai_review_run
from app.workers.agent_worker import execute_agent_run_task

router = APIRouter(prefix="/ai-reviews", tags=["AI Reviews"])


@router.get(
    "/provider-status",
    response_model=AiReviewProviderStatus,
    summary="Inspect configured AI review provider status and caller quota",
)
async def get_ai_review_provider_status(
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewProviderStatus:
    """Return non-secret provider and budget status for the current actor."""

    require_ai_review_read(actor_role)
    return await ai_review_service.get_ai_review_provider_status(actor_id, db)


@router.post(
    "/projects/{project_id}/integrations/{integration_id}/simulate-draft",
    response_model=AiReviewDraftSimulationResponse,
    summary="Simulate technical and commercial impact for an unsaved canvas draft",
)
async def simulate_integration_canvas_draft(
    project_id: str,
    integration_id: str,
    body: AiReviewDraftSimulationRequest,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewDraftSimulationResponse:
    """Run the governed calculation engines without writing snapshots or catalog changes."""

    require_ai_review_read(actor_role)
    return await ai_review_simulation.simulate_canvas_draft(
        project_id=project_id,
        integration_id=integration_id,
        body=body,
        db=db,
    )


@router.get(
    "/projects/{project_id}/baseline",
    response_model=AiReviewBaselineLookupResponse,
    summary="Get the active planned baseline for one AI review scope",
)
async def get_project_ai_review_baseline(
    project_id: str,
    scope: AiReviewScope = Query("project"),
    integration_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewBaselineLookupResponse:
    """Return the current approved planned-state baseline, if one exists."""

    require_ai_review_read(actor_role)
    return await ai_review_service.get_active_ai_review_baseline(project_id, scope, integration_id, db)


@router.get(
    "/projects/{project_id}/baselines",
    response_model=AiReviewBaselineListResponse,
    summary="List active and historical planned baselines for one AI review scope",
)
async def list_project_ai_review_baselines(
    project_id: str,
    scope: AiReviewScope = Query("project"),
    integration_id: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewBaselineListResponse:
    """Return baseline history for governance comparison and audit review."""

    require_ai_review_read(actor_role)
    return await ai_review_service.list_ai_review_baselines(
        project_id,
        scope,
        integration_id,
        db,
        limit=limit,
    )


@router.post(
    "/projects/{project_id}/baseline",
    response_model=AiReviewBaselineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Approve the current project or integration state as the planned baseline",
)
async def create_project_ai_review_baseline(
    project_id: str,
    body: AiReviewBaselineCreateRequest | None = None,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewBaselineResponse:
    """Persist the current governed state as the active planned baseline for drift detection."""

    require_ai_review_mutation(actor_role)
    request = body or AiReviewBaselineCreateRequest()
    async with db.begin():
        return await ai_review_service.create_ai_review_baseline(project_id, request, actor_id, db)


@router.post(
    "/projects/{project_id}",
    response_model=AiReviewJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a governed project or integration AI review job",
)
async def create_project_ai_review(
    project_id: str,
    body: AiReviewCreateRequest | None = None,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewJobResponse:
    """Create a persisted review job and dispatch the async worker."""

    require_ai_review_run(actor_role)
    request = body or AiReviewCreateRequest()
    async with db.begin():
        job = await ai_review_service.create_ai_review_job(project_id, request, actor_id, db)
        agent_type: AgentType = (
            "topology_investigation"
            if request.graph_context is not None
            else "integration_design"
            if request.scope == "integration"
            else "architecture_review"
        )
        agent_run = await agent_service.create_agent_run(
            AgentCreateRequest(
                agent_type=agent_type,
                project_id=project_id,
                integration_id=request.integration_id,
                context={
                    "graph_context": request.graph_context.model_dump(mode="json") if request.graph_context else None,
                    "reviewer_personas": list(request.reviewer_personas),
                },
                include_provider=request.include_llm,
            ),
            actor_id,
            actor_role,
            db,
        )
        await agent_service.link_agent_run(
            agent_run.id, legacy_job_type="ai_review", legacy_job_id=job.id, db=db
        )
        job_model = await db.get(AiReviewJob, job.id)
        if job_model is not None:
            job_model.input_payload = {
                **cast(dict[str, object], job_model.input_payload),
                "agent_run_id": agent_run.id,
            }
    try:
        execute_agent_run_task.apply_async(args=[agent_run.id], task_id=agent_run.id, queue="agents")
    except Exception as exc:  # pragma: no cover - defensive dispatch path
        async with db.begin():
            await agent_service.mark_agent_run_failed(
                agent_run.id,
                {"detail": "Unable to dispatch architecture agent."},
                db,
            )
            await ai_review_service.mark_ai_review_job_failed(
                job.id,
                {"detail": f"Unable to dispatch AI review job: {exc}"},
                db,
            )
        raise HTTPException(
            status_code=503,
            detail={
                "detail": "AI review worker could not be dispatched.",
                "error_code": "AI_REVIEW_JOB_DISPATCH_FAILED",
            },
        ) from exc
    return job


@router.get(
    "/projects/{project_id}/jobs",
    response_model=AiReviewJobListResponse,
    summary="List persisted AI review jobs for one project",
)
async def list_project_ai_reviews(
    project_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewJobListResponse:
    """Return recent review history for the selected project."""

    require_ai_review_read(actor_role)
    return await ai_review_service.list_ai_review_jobs(project_id, db, limit=limit)


@router.get(
    "/projects/{project_id}/jobs/compare",
    response_model=AiReviewJobCompareResponse,
    summary="Compare two completed AI review jobs for trend/evolution analysis",
)
async def compare_project_ai_review_jobs(
    project_id: str,
    base_job_id: str = Query(...),
    target_job_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewJobCompareResponse:
    """Return readiness and finding deltas between two completed jobs."""

    require_ai_review_read(actor_role)
    return await ai_review_service.compare_ai_review_jobs(project_id, base_job_id, target_job_id, db)


@router.get(
    "/{job_id}",
    response_model=AiReviewJobResponse,
    summary="Inspect one AI review job",
)
async def get_ai_review_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewJobResponse:
    """Return one persisted review job and result payload when complete."""

    require_ai_review_read(actor_role)
    return await ai_review_service.get_ai_review_job(job_id, db)


@router.get(
    "/{job_id}/export",
    summary="Export one completed AI review job as Markdown",
)
async def export_ai_review_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> Response:
    """Return a portable Markdown brief for one persisted AI review job."""

    require_ai_review_read(actor_role)
    async with db.begin():
        content, filename, _project_id = await ai_review_service.export_ai_review_markdown(job_id, actor_id, db)
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post(
    "/{job_id}/findings/{finding_id}/accept",
    response_model=AiReviewJobResponse,
    summary="Accept one AI review recommendation without catalog mutation",
)
async def accept_ai_review_finding(
    job_id: str,
    finding_id: str,
    body: AiReviewAcceptRecommendationRequest | None = None,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewJobResponse:
    """Record a human approval/audit marker for one finding recommendation."""

    require_ai_review_mutation(actor_role)
    request = body or AiReviewAcceptRecommendationRequest()
    async with db.begin():
        return await ai_review_service.accept_ai_review_finding(job_id, finding_id, request, actor_id, db)


@router.post(
    "/{job_id}/recommendations/{candidate_id}/select-draft",
    response_model=AiReviewSelectDraftResponse,
    summary="Select a governed integration recommendation for local canvas preview",
)
async def select_ai_review_candidate_for_draft(
    job_id: str,
    candidate_id: str,
    body: AiReviewSelectDraftRequest | None = None,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewSelectDraftResponse:
    """Audit candidate selection while leaving the governed integration unchanged."""

    require_ai_review_mutation(actor_role)
    request = body or AiReviewSelectDraftRequest()
    async with db.begin():
        return await ai_review_service.select_ai_review_candidate_for_draft(
            job_id,
            candidate_id,
            request,
            actor_id,
            db,
        )


@router.post(
    "/{job_id}/findings/{finding_id}/apply-patch",
    response_model=AiReviewApplyPatchResponse,
    summary="Apply one deterministic suggested patch after human confirmation",
)
async def apply_ai_review_finding_patch(
    job_id: str,
    finding_id: str,
    body: AiReviewApplyPatchRequest | None = None,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
) -> AiReviewApplyPatchResponse:
    """Apply a bounded architect-owned patch and audit the human approval."""

    require_ai_review_mutation(actor_role)
    request = body or AiReviewApplyPatchRequest()
    async with db.begin():
        return await ai_review_service.apply_ai_review_finding_patch(job_id, finding_id, request, actor_id, db)
