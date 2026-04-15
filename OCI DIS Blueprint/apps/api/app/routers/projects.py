"""Projects router backed by the project service layer."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.project import (
    ProjectArchiveResponse,
    ProjectCreateRequest,
    ProjectDeleteResponse,
    ProjectListResponse,
    ProjectResponse,
)
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/", response_model=ProjectListResponse, summary="List all projects")
async def list_projects(db: AsyncSession = Depends(get_db)) -> ProjectListResponse:
    """Return all projects ordered by creation date descending."""

    return await project_service.list_projects(db)


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, summary="Create a project")
async def create_project(
    body: ProjectCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create one project and return the serialized resource."""

    project = await project_service.create_project(body, db)
    await db.commit()
    return project_service.serialize_project(project)


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project by ID")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Return one project or raise 404."""

    project = await project_service.get_project(project_id, db)
    return project_service.serialize_project(project)


@router.post(
    "/{project_id}/archive",
    response_model=ProjectArchiveResponse,
    summary="Archive one project",
)
async def archive_project(
    project_id: str,
    x_actor_id: str = Header(default="web-user", alias="X-Actor-Id"),
    db: AsyncSession = Depends(get_db),
) -> ProjectArchiveResponse:
    """Archive one project and emit an audit event."""

    response = await project_service.archive_project(project_id, x_actor_id, db)
    await db.commit()
    return response


@router.delete(
    "/{project_id}",
    response_model=ProjectDeleteResponse,
    summary="Delete one archived project",
)
async def delete_project(
    project_id: str,
    x_actor_id: str = Header(default="web-user", alias="X-Actor-Id"),
    db: AsyncSession = Depends(get_db),
) -> ProjectDeleteResponse:
    """Delete one archived project and all related project-scoped records."""

    response = await project_service.delete_project(project_id, x_actor_id, db)
    await db.commit()
    return response
