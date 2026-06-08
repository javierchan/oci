"""Service Products router for governed service library and verification jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.service_products import (
    ServiceVerificationAlertListResponse,
    ServiceVerificationFindingResponse,
    ServiceVerificationFindingReviewRequest,
    ServiceInteroperabilityMatrixResponse,
    ServiceInteroperabilityRuleResponse,
    ServiceLimitResponse,
    ServiceProductDetailResponse,
    ServiceProductListResponse,
    ServiceVerificationJobListResponse,
    ServiceVerificationJobResponse,
    ServiceVerificationRunRequest,
)
from app.services import service_product_service
from app.services.authz import require_admin
from app.workers.service_verification_worker import execute_service_verification_job_task

router = APIRouter(prefix="/service-products", tags=["Service Products"])


@router.get(
    "",
    response_model=ServiceProductListResponse,
    summary="List governed service products",
)
@router.get(
    "/",
    response_model=ServiceProductListResponse,
    summary="List governed service products",
)
async def list_service_products(db: AsyncSession = Depends(get_db)) -> ServiceProductListResponse:
    return await service_product_service.list_service_products(db)


@router.get(
    "/matrix",
    response_model=ServiceInteroperabilityMatrixResponse,
    summary="Get the service interoperability matrix",
)
async def get_service_interoperability_matrix(
    db: AsyncSession = Depends(get_db),
) -> ServiceInteroperabilityMatrixResponse:
    return await service_product_service.get_interoperability_matrix(db)


@router.get(
    "/verification-jobs",
    response_model=ServiceVerificationJobListResponse,
    summary="List service verification jobs",
)
async def list_service_verification_jobs(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> ServiceVerificationJobListResponse:
    return await service_product_service.list_verification_jobs(db, limit=limit)


@router.get(
    "/verification-alerts",
    response_model=ServiceVerificationAlertListResponse,
    summary="List service verification freshness alerts",
)
async def list_service_verification_alerts(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> ServiceVerificationAlertListResponse:
    return await service_product_service.list_verification_alerts(db, limit=limit)


@router.post(
    "/verification-jobs",
    response_model=ServiceVerificationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a service evidence verification job",
)
async def execute_service_verification_job(
    body: ServiceVerificationRunRequest | None = None,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> ServiceVerificationJobResponse:
    require_admin(actor_role)
    request = body or ServiceVerificationRunRequest()
    async with db.begin():
        job = await service_product_service.create_verification_job(request, actor_id, db)
    try:
        execute_service_verification_job_task.apply_async(args=[job.id], task_id=job.id)
    except Exception as exc:  # pragma: no cover - defensive dispatch path
        async with db.begin():
            await service_product_service.mark_verification_job_failed(
                job.id,
                {"detail": f"Unable to dispatch service verification job: {exc}"},
                db,
            )
        raise HTTPException(
            status_code=503,
            detail={
                "detail": "Service verification worker could not be dispatched.",
                "error_code": "SERVICE_VERIFICATION_JOB_DISPATCH_FAILED",
            },
        ) from exc
    return job


@router.get(
    "/verification-jobs/{job_id}",
    response_model=ServiceVerificationJobResponse,
    summary="Get one service verification job",
)
async def get_service_verification_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> ServiceVerificationJobResponse:
    return await service_product_service.get_verification_job(job_id, db)


@router.get(
    "/verification-jobs/{job_id}/findings",
    response_model=list[ServiceVerificationFindingResponse],
    summary="List findings for one service verification job",
)
async def list_service_verification_findings(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ServiceVerificationFindingResponse]:
    return await service_product_service.list_verification_findings(job_id, db)


@router.post(
    "/verification-jobs/{job_id}/findings/{finding_id}/review",
    response_model=ServiceVerificationFindingResponse,
    summary="Record a manual review decision for one verification finding",
)
async def review_service_verification_finding(
    job_id: str,
    finding_id: str,
    body: ServiceVerificationFindingReviewRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> ServiceVerificationFindingResponse:
    require_admin(actor_role)
    async with db.begin():
        return await service_product_service.review_verification_finding(
            job_id,
            finding_id,
            body,
            actor_id,
            db,
        )


@router.get(
    "/{service_id}",
    response_model=ServiceProductDetailResponse,
    summary="Get governed service product detail",
)
async def get_service_product(
    service_id: str,
    db: AsyncSession = Depends(get_db),
) -> ServiceProductDetailResponse:
    return await service_product_service.get_service_product(service_id, db)


@router.get(
    "/{service_id}/limits",
    response_model=list[ServiceLimitResponse],
    summary="Get normalized limits for a service product",
)
async def list_service_product_limits(
    service_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ServiceLimitResponse]:
    return await service_product_service.list_service_product_limits(service_id, db)


@router.get(
    "/{service_id}/interoperability",
    response_model=list[ServiceInteroperabilityRuleResponse],
    summary="Get interoperability rules for a service product",
)
async def list_service_product_interoperability(
    service_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ServiceInteroperabilityRuleResponse]:
    return await service_product_service.list_service_product_interoperability(service_id, db)
