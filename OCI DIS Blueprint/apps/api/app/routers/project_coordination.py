"""Project-scoped shared views and attention coordination endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.project_coordination import ProjectAttentionTaskCreate, ProjectAttentionTaskList, ProjectAttentionTaskPatch, ProjectAttentionTaskResponse, ProjectSavedViewCreate, ProjectSavedViewList, ProjectSavedViewResponse
from app.services import project_coordination_service
from app.services.authz import require_roles

router = APIRouter(prefix="/projects/{project_id}", tags=["Project Coordination"])

def _read(role: str) -> None:
    require_roles(role, {"Admin", "Architect", "Analyst", "Viewer"}, error_code="PROJECT_COORDINATION_READ_ROLE_REQUIRED")

def _write(role: str) -> None:
    require_roles(role, {"Admin", "Architect", "Analyst"}, error_code="PROJECT_COORDINATION_WRITE_ROLE_REQUIRED")

@router.get("/saved-views", response_model=ProjectSavedViewList)
async def list_views(project_id: str, surface: str | None = Query(None, pattern="^(catalog|topology)$"), actor_role: str = Header("Viewer", alias="X-Actor-Role"), db: AsyncSession = Depends(get_db)) -> ProjectSavedViewList:
    _read(actor_role)
    return await project_coordination_service.list_views(project_id, surface, db)

@router.post("/saved-views", response_model=ProjectSavedViewResponse, status_code=status.HTTP_201_CREATED)
async def create_view(project_id: str, body: ProjectSavedViewCreate, actor_id: str = Header("api-user", alias="X-Actor-Id"), actor_role: str = Header("Analyst", alias="X-Actor-Role"), db: AsyncSession = Depends(get_db)) -> ProjectSavedViewResponse:
    _write(actor_role)
    async with db.begin():
        return await project_coordination_service.create_view(project_id, body, actor_id, db)

@router.delete("/saved-views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_view(project_id: str, view_id: str, actor_id: str = Header("api-user", alias="X-Actor-Id"), actor_role: str = Header("Analyst", alias="X-Actor-Role"), db: AsyncSession = Depends(get_db)) -> Response:
    _write(actor_role)
    async with db.begin():
        await project_coordination_service.delete_view(project_id, view_id, actor_id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/attention-tasks", response_model=ProjectAttentionTaskList)
async def list_tasks(project_id: str, actor_role: str = Header("Viewer", alias="X-Actor-Role"), db: AsyncSession = Depends(get_db)) -> ProjectAttentionTaskList:
    _read(actor_role)
    return await project_coordination_service.list_tasks(project_id, db)

@router.post("/attention-tasks", response_model=ProjectAttentionTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(project_id: str, body: ProjectAttentionTaskCreate, actor_id: str = Header("api-user", alias="X-Actor-Id"), actor_role: str = Header("Analyst", alias="X-Actor-Role"), db: AsyncSession = Depends(get_db)) -> ProjectAttentionTaskResponse:
    _write(actor_role)
    async with db.begin():
        return await project_coordination_service.create_task(project_id, body, actor_id, db)

@router.patch("/attention-tasks/{task_id}", response_model=ProjectAttentionTaskResponse)
async def patch_task(project_id: str, task_id: str, body: ProjectAttentionTaskPatch, actor_id: str = Header("api-user", alias="X-Actor-Id"), actor_role: str = Header("Analyst", alias="X-Actor-Role"), db: AsyncSession = Depends(get_db)) -> ProjectAttentionTaskResponse:
    _write(actor_role)
    async with db.begin():
        return await project_coordination_service.patch_task(project_id, task_id, body, actor_id, db)
