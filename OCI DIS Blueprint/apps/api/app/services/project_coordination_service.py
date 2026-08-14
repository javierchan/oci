"""Persist project coordination metadata without changing domain evidence or approvals."""

from __future__ import annotations

from datetime import date
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, ProjectAttentionTask, ProjectSavedView
from app.schemas.project_coordination import (
    ProjectAttentionTaskCreate,
    ProjectAttentionTaskList,
    ProjectAttentionTaskPatch,
    ProjectAttentionTaskResponse,
    ProjectSavedViewCreate,
    ProjectSavedViewList,
    ProjectSavedViewResponse,
)
from app.services import audit_service


async def _project(project_id: str, db: AsyncSession) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"})
    return project


def _view(view: ProjectSavedView) -> ProjectSavedViewResponse:
    return ProjectSavedViewResponse(
        id=view.id, project_id=view.project_id, surface=cast(Literal["catalog", "topology"], view.surface), label=view.label,
        filters=view.filters, is_shared=view.is_shared, created_by=view.created_by,
        created_at=view.created_at, updated_at=view.updated_at,
    )


async def list_views(project_id: str, surface: str | None, db: AsyncSession) -> ProjectSavedViewList:
    await _project(project_id, db)
    query = select(ProjectSavedView).where(ProjectSavedView.project_id == project_id)
    if surface:
        query = query.where(ProjectSavedView.surface == surface)
    result = await db.scalars(query.order_by(ProjectSavedView.updated_at.desc()))
    return ProjectSavedViewList(views=[_view(view) for view in result.all()])


async def create_view(project_id: str, body: ProjectSavedViewCreate, actor_id: str, db: AsyncSession) -> ProjectSavedViewResponse:
    await _project(project_id, db)
    view = ProjectSavedView(project_id=project_id, surface=body.surface, label=body.label, filters=body.filters, is_shared=body.is_shared, created_by=actor_id)
    db.add(view)
    await db.flush()
    response = _view(view)
    await audit_service.emit("project_view_created", "project_saved_view", view.id, actor_id, None, response.model_dump(mode="json"), project_id, db)
    return response


async def delete_view(project_id: str, view_id: str, actor_id: str, db: AsyncSession) -> None:
    view = await db.get(ProjectSavedView, view_id)
    if view is None or view.project_id != project_id:
        raise HTTPException(status_code=404, detail={"detail": "Saved view not found", "error_code": "PROJECT_SAVED_VIEW_NOT_FOUND"})
    old_value = _view(view).model_dump(mode="json")
    await db.delete(view)
    await audit_service.emit("project_view_deleted", "project_saved_view", view_id, actor_id, old_value, None, project_id, db)


def _task(task: ProjectAttentionTask) -> ProjectAttentionTaskResponse:
    return ProjectAttentionTaskResponse(
        id=task.id, project_id=task.project_id, attention_key=task.attention_key, source=cast(Literal["qa", "topology", "coverage", "bom"], task.source),
        title=task.title, evidence_href=task.evidence_href, assignee=task.assignee, due_date=task.due_date,
        status=cast(Literal["open", "in_progress", "resolved"], task.status), note=task.note, evidence=task.evidence, created_by=task.created_by,
        updated_by=task.updated_by, is_overdue=bool(task.due_date and task.due_date < date.today() and task.status != "resolved"),
        created_at=task.created_at, updated_at=task.updated_at,
    )


async def list_tasks(project_id: str, db: AsyncSession) -> ProjectAttentionTaskList:
    await _project(project_id, db)
    result = await db.scalars(select(ProjectAttentionTask).where(ProjectAttentionTask.project_id == project_id).order_by(ProjectAttentionTask.due_date.asc().nulls_last(), ProjectAttentionTask.updated_at.desc()))
    return ProjectAttentionTaskList(tasks=[_task(task) for task in result.all()])


async def create_task(project_id: str, body: ProjectAttentionTaskCreate, actor_id: str, db: AsyncSession) -> ProjectAttentionTaskResponse:
    await _project(project_id, db)
    existing = await db.scalar(select(ProjectAttentionTask).where(ProjectAttentionTask.project_id == project_id, ProjectAttentionTask.attention_key == body.attention_key))
    if existing:
        raise HTTPException(status_code=409, detail={"detail": "An attention task already exists for this evidence", "error_code": "PROJECT_ATTENTION_TASK_EXISTS"})
    task = ProjectAttentionTask(project_id=project_id, attention_key=body.attention_key, source=body.source, title=body.title, evidence_href=body.evidence_href, assignee=body.assignee, due_date=body.due_date, note=body.note, created_by=actor_id, updated_by=actor_id)
    db.add(task)
    await db.flush()
    response = _task(task)
    await audit_service.emit("project_attention_task_created", "project_attention_task", task.id, actor_id, None, response.model_dump(mode="json"), project_id, db)
    return response


async def patch_task(project_id: str, task_id: str, body: ProjectAttentionTaskPatch, actor_id: str, db: AsyncSession) -> ProjectAttentionTaskResponse:
    task = await db.get(ProjectAttentionTask, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=404, detail={"detail": "Attention task not found", "error_code": "PROJECT_ATTENTION_TASK_NOT_FOUND"})
    old_value = _task(task).model_dump(mode="json")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("status") == "resolved" and not (changes.get("evidence") or task.evidence):
        raise HTTPException(status_code=422, detail={"detail": "Resolution requires a concise evidence record", "error_code": "PROJECT_ATTENTION_EVIDENCE_REQUIRED"})
    for field, value in changes.items():
        setattr(task, field, value)
    task.updated_by = actor_id
    await db.flush()
    response = _task(task)
    await audit_service.emit("project_attention_task_updated", "project_attention_task", task.id, actor_id, old_value, response.model_dump(mode="json"), project_id, db)
    return response
