"""AI review router for governed architecture review board jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.ai_review import (
    AiReviewAcceptRecommendationRequest,
    AiReviewApplyPatchRequest,
    AiReviewApplyPatchResponse,
    AiReviewCreateRequest,
    AiReviewJobListResponse,
    AiReviewJobResponse,
)
from app.services import ai_review_service
from app.workers.ai_review_worker import execute_ai_review_job_task

router = APIRouter(prefix="/ai-reviews", tags=["AI Reviews"])


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
) -> AiReviewJobResponse:
    """Create a persisted review job and dispatch the async worker."""

    request = body or AiReviewCreateRequest()
    async with db.begin():
        job = await ai_review_service.create_ai_review_job(project_id, request, actor_id, db)
    try:
        execute_ai_review_job_task.apply_async(args=[job.id], task_id=job.id)
    except Exception as exc:  # pragma: no cover - defensive dispatch path
        async with db.begin():
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
) -> AiReviewJobListResponse:
    """Return recent review history for the selected project."""

    return await ai_review_service.list_ai_review_jobs(project_id, db, limit=limit)


@router.get(
    "/{job_id}",
    response_model=AiReviewJobResponse,
    summary="Inspect one AI review job",
)
async def get_ai_review_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> AiReviewJobResponse:
    """Return one persisted review job and result payload when complete."""

    return await ai_review_service.get_ai_review_job(job_id, db)


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
) -> AiReviewJobResponse:
    """Record a human approval/audit marker for one finding recommendation."""

    request = body or AiReviewAcceptRecommendationRequest()
    async with db.begin():
        return await ai_review_service.accept_ai_review_finding(job_id, finding_id, request, actor_id, db)


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
) -> AiReviewApplyPatchResponse:
    """Apply a bounded architect-owned patch and audit the human approval."""

    request = body or AiReviewApplyPatchRequest()
    async with db.begin():
        return await ai_review_service.apply_ai_review_finding_patch(job_id, finding_id, request, actor_id, db)
