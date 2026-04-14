"""Projects router — thin HTTP layer over project services."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.project import ProjectCreateRequest, ProjectListResponse, ProjectResponse
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


@router.patch("/{project_id}", summary="Update project metadata")
async def update_project(project_id: str, body: dict):
    # TODO: partial update + audit
    return {"id": project_id, **body}
