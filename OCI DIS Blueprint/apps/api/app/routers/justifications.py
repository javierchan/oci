"""Justifications router — deterministic narratives, approvals, and template governance."""

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.justification import (
    ApproveJustificationRequest,
    JustificationListResponse,
    JustificationRecordResponse,
    OverrideJustificationRequest,
    PromptTemplateVersionCreate,
    PromptTemplateVersionListResponse,
    PromptTemplateVersionResponse,
    PromptTemplateVersionUpdate,
)
from app.services import justification_service
from app.services.authz import require_admin

router = APIRouter(prefix="/justifications", tags=["Justifications"])


@router.get("/templates", response_model=PromptTemplateVersionListResponse, summary="List narrative templates")
async def list_prompt_templates(db: AsyncSession = Depends(get_db)) -> PromptTemplateVersionListResponse:
    return await justification_service.list_prompt_templates(db)


@router.get(
    "/templates/{version}",
    response_model=PromptTemplateVersionResponse,
    summary="Get one narrative template version",
)
async def get_prompt_template(version: str, db: AsyncSession = Depends(get_db)) -> PromptTemplateVersionResponse:
    return await justification_service.get_prompt_template(version, db)


@router.post(
    "/templates",
    response_model=PromptTemplateVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a narrative template version",
)
async def create_prompt_template(
    body: PromptTemplateVersionCreate,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PromptTemplateVersionResponse:
    require_admin(actor_role)
    async with db.begin():
        return await justification_service.create_prompt_template(body, actor_id, db)


@router.patch(
    "/templates/{version}",
    response_model=PromptTemplateVersionResponse,
    summary="Update a narrative template version",
)
async def update_prompt_template(
    version: str,
    body: PromptTemplateVersionUpdate,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PromptTemplateVersionResponse:
    require_admin(actor_role)
    async with db.begin():
        return await justification_service.update_prompt_template(version, body, actor_id, db)


@router.post(
    "/templates/{version}/default",
    response_model=PromptTemplateVersionResponse,
    summary="Promote a narrative template to default",
)
async def set_default_prompt_template(
    version: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PromptTemplateVersionResponse:
    require_admin(actor_role)
    async with db.begin():
        return await justification_service.set_default_prompt_template(version, actor_id, db)


@router.get("/{project_id}", response_model=JustificationListResponse, summary="List justification records")
async def list_justifications(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> JustificationListResponse:
    return await justification_service.list_justifications(project_id, db)


@router.get(
    "/{project_id}/{integration_id}",
    response_model=JustificationRecordResponse,
    summary="Get justification for an integration",
)
async def get_justification(
    project_id: str,
    integration_id: str,
    db: AsyncSession = Depends(get_db),
) -> JustificationRecordResponse:
    return await justification_service.get_justification(project_id, integration_id, db)


@router.post(
    "/{project_id}/{integration_id}/approve",
    response_model=JustificationRecordResponse,
    summary="Approve a justification narrative",
)
async def approve_justification(
    project_id: str,
    integration_id: str,
    body: ApproveJustificationRequest,
    db: AsyncSession = Depends(get_db),
) -> JustificationRecordResponse:
    """Sets state=approved, records approved_by, and emits an AuditEvent."""

    async with db.begin():
        return await justification_service.approve_justification(
            project_id=project_id,
            integration_id=integration_id,
            actor_id=body.actor_id,
            db=db,
        )


@router.post(
    "/{project_id}/{integration_id}/override",
    response_model=JustificationRecordResponse,
    summary="Override with custom narrative",
)
async def override_justification(
    project_id: str,
    integration_id: str,
    body: OverrideJustificationRequest,
    db: AsyncSession = Depends(get_db),
) -> JustificationRecordResponse:
    async with db.begin():
        return await justification_service.override_justification(
            project_id=project_id,
            integration_id=integration_id,
            actor_id=body.actor_id,
            override_text=body.override_text,
            override_notes=body.override_notes,
            db=db,
        )
