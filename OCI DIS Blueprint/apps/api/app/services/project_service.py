"""Project CRUD service layer."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project
from app.schemas.project import ProjectCreateRequest, ProjectListResponse, ProjectResponse


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
    )


def serialize_project(project: Project) -> ProjectResponse:
    """Convert a project model into a response schema."""

    return ProjectResponse(
        id=project.id,
        name=project.name,
        owner_id=project.owner_id,
        description=project.description,
        status=project.status.value,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


async def list_projects(db: AsyncSession) -> ProjectListResponse:
    """List all projects ordered by creation time."""

    result = await db.scalars(select(Project).order_by(Project.created_at.desc()))
    return ProjectListResponse(projects=[serialize_project(project) for project in result.all()])


async def create_project(body: ProjectCreateRequest, db: AsyncSession) -> Project:
    """Create and flush a new project."""

    project = Project(
        name=body.name,
        owner_id=body.owner_id,
        description=body.description,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


async def get_project(project_id: str, db: AsyncSession) -> Project:
    """Load a project or raise 404."""

    project = await db.get(Project, project_id)
    if project is None:
        raise _not_found()
    return project
