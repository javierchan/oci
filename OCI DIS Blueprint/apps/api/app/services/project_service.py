"""Project CRUD service layer."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditEvent,
    CatalogIntegration,
    DashboardSnapshot,
    ImportBatch,
    JustificationRecord,
    Project,
    SourceIntegrationRow,
    VolumetrySnapshot,
)
from app.models.project import ProjectStatus
from app.schemas.project import (
    ProjectArchiveResponse,
    ProjectCreateRequest,
    ProjectDeleteResponse,
    ProjectListResponse,
    ProjectResponse,
)
from app.services import audit_service


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


async def archive_project(project_id: str, actor_id: str, db: AsyncSession) -> ProjectArchiveResponse:
    """Archive one project."""

    project = await get_project(project_id, db)
    if project.status == ProjectStatus.ARCHIVED:
        return ProjectArchiveResponse(
            project=serialize_project(project),
            detail="Project is already archived.",
        )

    old_value = serialize_project(project).model_dump()
    project.status = ProjectStatus.ARCHIVED
    await db.flush()
    await db.refresh(project)
    response = serialize_project(project)
    await audit_service.emit(
        event_type="project_archived",
        entity_type="project",
        entity_id=project.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=response.model_dump(),
        project_id=project.id,
        db=db,
    )
    return ProjectArchiveResponse(project=response, detail="Project archived.")


async def delete_project(project_id: str, actor_id: str, db: AsyncSession) -> ProjectDeleteResponse:
    """Delete an archived project and all project-scoped mutable records."""

    project = await get_project(project_id, db)
    if project.status != ProjectStatus.ARCHIVED:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Archive the project before deleting it.",
                "error_code": "PROJECT_NOT_ARCHIVED",
            },
        )

    old_value = serialize_project(project).model_dump()
    dashboard_snapshots = (
        await db.scalars(select(DashboardSnapshot).where(DashboardSnapshot.project_id == project_id))
    ).all()
    volumetry_snapshots = (
        await db.scalars(select(VolumetrySnapshot).where(VolumetrySnapshot.project_id == project_id))
    ).all()
    justifications = (
        await db.scalars(select(JustificationRecord).where(JustificationRecord.project_id == project_id))
    ).all()
    integrations = (
        await db.scalars(select(CatalogIntegration).where(CatalogIntegration.project_id == project_id))
    ).all()
    import_batches = (
        await db.scalars(select(ImportBatch).where(ImportBatch.project_id == project_id))
    ).all()
    source_rows = (
        await db.scalars(
            select(SourceIntegrationRow)
            .join(ImportBatch, ImportBatch.id == SourceIntegrationRow.import_batch_id)
            .where(ImportBatch.project_id == project_id)
        )
    ).all()
    deleted_audit_events = await db.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.project_id == project_id)
    )

    response = ProjectDeleteResponse(
        project_id=project_id,
        detail="Project deleted.",
        deleted_import_batches=len(import_batches),
        deleted_source_rows=len(source_rows),
        deleted_integrations=len(integrations),
        deleted_justifications=len(justifications),
        deleted_volumetry_snapshots=len(volumetry_snapshots),
        deleted_dashboard_snapshots=len(dashboard_snapshots),
        deleted_audit_events=int(deleted_audit_events or 0),
    )
    await audit_service.emit(
        event_type="project_deleted",
        entity_type="project",
        entity_id=project_id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )

    for snapshot in dashboard_snapshots:
        await db.delete(snapshot)
    for snapshot in volumetry_snapshots:
        await db.delete(snapshot)
    for record in justifications:
        await db.delete(record)
    for integration in integrations:
        await db.delete(integration)
    for source_row in source_rows:
        await db.delete(source_row)
    for batch in import_batches:
        await db.delete(batch)

    await db.execute(delete(AuditEvent).where(AuditEvent.project_id == project_id))
    await db.delete(project)
    await db.flush()
    return response
