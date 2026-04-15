"""Projects router — thin HTTP layer over project services."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.project import (
    ProjectArchiveResponse,
    ProjectCreateRequest,
    ProjectDeleteResponse,
    ProjectListResponse,
    ProjectPatchRequest,
    ProjectResponse,
)
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/", response_model=ProjectListResponse, summary="List all projects")
async def list_projects(db: AsyncSession = Depends(get_db)) -> ProjectListResponse:
    return await project_service.list_projects(db)


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, summary="Create a project")
async def create_project(
    body: ProjectCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    async with db.begin():
        project = await project_service.create_project(body, db)
    return project_service.serialize_project(project)


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project by ID")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)) -> ProjectResponse:
    project = await project_service.get_project(project_id, db)
    return project_service.serialize_project(project)


@router.post("/{project_id}/archive", response_model=ProjectArchiveResponse, summary="Archive a project")
async def archive_project(
    project_id: str,
    actor_id: str = "api-user",
    db: AsyncSession = Depends(get_db),
) -> ProjectArchiveResponse:
    async with db.begin():
        return await project_service.archive_project(project_id, actor_id, db)


@router.delete("/{project_id}", response_model=ProjectDeleteResponse, summary="Delete an archived project")
async def delete_project(
    project_id: str,
    actor_id: str = "api-user",
    db: AsyncSession = Depends(get_db),
) -> ProjectDeleteResponse:
    async with db.begin():
        return await project_service.delete_project(project_id, actor_id, db)


@router.patch("/{project_id}", response_model=ProjectResponse, summary="Update project metadata")
async def update_project(
    project_id: str,
    body: ProjectPatchRequest,
    actor_id: str = "api-user",
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    async with db.begin():
        return await project_service.update_project(project_id, body, actor_id, db)
