"""Import router — upload, queue, and inspect import batches."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.imports import (
    ImportBatchDeleteResponse,
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportQualityAssistantResponse,
    SourceRowListResponse,
)
from app.schemas.agent import AgentCreateRequest, AgentRunResponse
from app.services import agent_service, import_service
from app.workers.agent_worker import execute_agent_run_task
from app.workers.import_worker import process_import_task

router = APIRouter(prefix="/imports", tags=["Imports"])


@router.post(
    "/{project_id}",
    response_model=ImportBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload source file and queue an import batch",
)
async def upload_and_import(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ImportBatchResponse:
    contents = await file.read()
    upload_path = await import_service.save_upload_file(
        file_name=file.filename or "upload.xlsx",
        contents=contents,
        upload_dir=Path("uploads"),
    )
    async with db.begin():
        batch = await import_service.create_import_batch(
            project_id=project_id,
            filename=file.filename or "upload.xlsx",
            db=db,
        )
    try:
        process_import_task.delay(batch.id, upload_path)
    except Exception as exc:
        async with db.begin():
            await import_service.mark_import_failed(
                batch.id,
                {
                    "detail": "Import dispatch failed.",
                    "error": str(exc),
                },
                db,
            )
        raise HTTPException(
            status_code=500,
            detail={"detail": "Import dispatch failed", "error_code": "IMPORT_DISPATCH_FAILED"},
        ) from exc
    return import_service.serialize_batch(batch)


@router.get("/{project_id}", response_model=ImportBatchListResponse, summary="List import batches for a project")
async def list_imports(project_id: str, db: AsyncSession = Depends(get_db)) -> ImportBatchListResponse:
    return await import_service.list_import_batches(project_id, db)


@router.get("/{project_id}/{batch_id}", response_model=ImportBatchResponse, summary="Get import batch status and stats")
async def get_import(
    project_id: str,
    batch_id: str,
    db: AsyncSession = Depends(get_db),
) -> ImportBatchResponse:
    return await import_service.get_import_batch(project_id, batch_id, db)


@router.get("/{project_id}/{batch_id}/rows", response_model=SourceRowListResponse, summary="Get source rows with inclusion/exclusion reasons")
async def get_import_rows(
    project_id: str,
    batch_id: str,
    page: int = 1,
    page_size: int = 100,
    db: AsyncSession = Depends(get_db),
) -> SourceRowListResponse:
    return await import_service.list_import_rows(project_id, batch_id, db, page=page, page_size=page_size)


@router.get(
    "/{project_id}/{batch_id}/quality-assistant",
    response_model=ImportQualityAssistantResponse,
    summary="Get deterministic import data-quality assistant guidance",
)
async def get_import_quality_assistant(
    project_id: str,
    batch_id: str,
    db: AsyncSession = Depends(get_db),
) -> ImportQualityAssistantResponse:
    return await import_service.get_import_quality_assistant(project_id, batch_id, db)


@router.post(
    "/{project_id}/{batch_id}/quality-agent",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run the governed import quality agent",
)
async def run_import_quality_agent(
    project_id: str,
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Analyst", alias="X-Actor-Role"),
) -> AgentRunResponse:
    async with db.begin():
        run = await agent_service.create_agent_run(
            AgentCreateRequest(
                agent_type="import_quality",
                project_id=project_id,
                context={"batch_id": batch_id},
            ),
            actor_id,
            actor_role,
            db,
        )
    try:
        execute_agent_run_task.apply_async(args=[run.id], task_id=run.id, queue="agents")
    except Exception as exc:  # pragma: no cover - defensive dispatch path.
        async with db.begin():
            await agent_service.mark_agent_run_failed(run.id, {"detail": str(exc)}, db)
        raise HTTPException(status_code=503, detail={"detail": "Agent worker could not be dispatched", "error_code": "AGENT_DISPATCH_FAILED"}) from exc
    return run


@router.delete(
    "/{project_id}/{batch_id}",
    response_model=ImportBatchDeleteResponse,
    summary="Remove an import batch and recalculate the project",
)
async def delete_import(
    project_id: str,
    batch_id: str,
    actor_id: str = "api-user",
    db: AsyncSession = Depends(get_db),
) -> ImportBatchDeleteResponse:
    async with db.begin():
        return await import_service.delete_import_batch(project_id, batch_id, actor_id, db)
