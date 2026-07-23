"""Governed external-capture review endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.external_capture import (
    ExternalCaptureBulkResult,
    ExternalCaptureDraftBulkCreate,
    ExternalCaptureDraftPage,
    ExternalCaptureDraftPatch,
    ExternalCaptureDraftResponse,
    ExternalCaptureDraftReview,
    ExternalCapturePromotionResponse,
    ExternalCaptureSessionCreate,
    ExternalCaptureSessionDetail,
    ExternalCaptureSessionList,
)
from app.services import external_capture_service
from app.services.authz import require_roles


router = APIRouter(
    prefix="/projects/{project_id}/external-capture",
    tags=["External Capture Review"],
)


def _require_reviewer(actor_role: str) -> None:
    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst"},
        error_code="EXTERNAL_CAPTURE_REVIEW_ROLE_REQUIRED",
    )


def _require_promoter(actor_role: str) -> None:
    require_roles(
        actor_role,
        {"Admin", "Architect"},
        error_code="EXTERNAL_CAPTURE_PROMOTION_ROLE_REQUIRED",
    )


@router.get(
    "/sessions",
    response_model=ExternalCaptureSessionList,
    summary="List governed external-capture review sessions",
)
async def list_sessions(
    project_id: str,
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ExternalCaptureSessionList:
    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst", "Viewer"},
        error_code="EXTERNAL_CAPTURE_READ_ROLE_REQUIRED",
    )
    return await external_capture_service.list_sessions(project_id, db)


@router.post(
    "/sessions",
    response_model=ExternalCaptureSessionDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a governed external-capture review session",
)
async def create_session(
    project_id: str,
    body: ExternalCaptureSessionCreate,
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Analyst", alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ExternalCaptureSessionDetail:
    _require_reviewer(actor_role)
    async with db.begin():
        return await external_capture_service.create_session(
            project_id, body, actor_id, db
        )


@router.get(
    "/sessions/{session_id}",
    response_model=ExternalCaptureSessionDetail,
    summary="Get an external-capture review summary",
)
async def get_session(
    project_id: str,
    session_id: str,
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ExternalCaptureSessionDetail:
    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst", "Viewer"},
        error_code="EXTERNAL_CAPTURE_READ_ROLE_REQUIRED",
    )
    return await external_capture_service.get_session_detail(
        project_id, session_id, db
    )


@router.post(
    "/sessions/{session_id}/drafts/bulk",
    response_model=ExternalCaptureBulkResult,
    summary="Stage or refresh structured external row proposals",
)
async def bulk_stage_drafts(
    project_id: str,
    session_id: str,
    body: ExternalCaptureDraftBulkCreate,
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Analyst", alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ExternalCaptureBulkResult:
    _require_reviewer(actor_role)
    async with db.begin():
        return await external_capture_service.bulk_upsert_drafts(
            project_id, session_id, body, actor_id, db
        )


@router.get(
    "/sessions/{session_id}/drafts",
    response_model=ExternalCaptureDraftPage,
    summary="List reviewable external-capture row proposals",
)
async def list_drafts(
    project_id: str,
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = None,
    actor_role: str = Header("Viewer", alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ExternalCaptureDraftPage:
    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst", "Viewer"},
        error_code="EXTERNAL_CAPTURE_READ_ROLE_REQUIRED",
    )
    return await external_capture_service.list_drafts(
        project_id,
        session_id,
        db,
        page=page,
        page_size=page_size,
        status=status_filter,
        search=search,
    )


@router.patch(
    "/sessions/{session_id}/drafts/{draft_id}",
    response_model=ExternalCaptureDraftResponse,
    summary="Correct one external-capture proposal before review",
)
async def patch_draft(
    project_id: str,
    session_id: str,
    draft_id: str,
    body: ExternalCaptureDraftPatch,
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Analyst", alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ExternalCaptureDraftResponse:
    _require_reviewer(actor_role)
    async with db.begin():
        return await external_capture_service.patch_draft(
            project_id, session_id, draft_id, body, actor_id, db
        )


@router.post(
    "/sessions/{session_id}/drafts/{draft_id}/review",
    response_model=ExternalCaptureDraftResponse,
    summary="Approve or reject one corrected row proposal",
)
async def review_draft(
    project_id: str,
    session_id: str,
    draft_id: str,
    body: ExternalCaptureDraftReview,
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Architect", alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ExternalCaptureDraftResponse:
    _require_promoter(actor_role)
    async with db.begin():
        return await external_capture_service.review_draft(
            project_id, session_id, draft_id, body, actor_id, db
        )


@router.post(
    "/sessions/{session_id}/drafts/{draft_id}/promote",
    response_model=ExternalCapturePromotionResponse,
    summary="Promote one approved proposal through governed manual capture",
)
async def promote_draft(
    project_id: str,
    session_id: str,
    draft_id: str,
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Architect", alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ExternalCapturePromotionResponse:
    _require_promoter(actor_role)
    async with db.begin():
        return await external_capture_service.promote_draft(
            project_id, session_id, draft_id, actor_id, db
        )
