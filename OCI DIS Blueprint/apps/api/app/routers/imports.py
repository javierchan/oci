"""Import router — upload, queue, and inspect import batches."""

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.imports import (
    ImportBatchDeleteResponse,
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportMappingProfileListResponse,
    ImportMappingReviewApproveRequest,
    ImportMappingReviewUpdateRequest,
    ImportQualityAssistantResponse,
    SourceRowListResponse,
)
from app.schemas.agent import AgentCreateRequest, AgentRunResponse
from app.services import agent_service, import_service, storage_service
from app.workers.agent_worker import execute_agent_run_task
from app.workers.import_worker import materialize_import_task, process_import_task

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
    upload_reference = await import_service.save_upload_file(
        file_name=file.filename or "upload.xlsx",
        contents=contents,
        project_id=project_id,
    )
    try:
        async with db.begin():
            batch = await import_service.create_import_batch(
                project_id=project_id,
                filename=file.filename or "upload.xlsx",
                db=db,
                storage_reference=upload_reference,
            )
    except Exception:
        storage_service.delete(upload_reference)
        raise
    try:
        process_import_task.delay(batch.id, upload_reference)
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


@router.get(
    "/{project_id}/mapping-profiles",
    response_model=ImportMappingProfileListResponse,
    summary="List approved project-scoped external import mappings",
)
async def list_mapping_profiles(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> ImportMappingProfileListResponse:
    return await import_service.list_import_mapping_profiles(project_id, db)


@router.get("/{project_id}/{batch_id}", response_model=ImportBatchResponse, summary="Get import batch status and stats")
async def get_import(
    project_id: str,
    batch_id: str,
    db: AsyncSession = Depends(get_db),
) -> ImportBatchResponse:
    return await import_service.get_import_batch(project_id, batch_id, db)


@router.patch(
    "/{project_id}/{batch_id}/mapping-review",
    response_model=ImportBatchResponse,
    summary="Save a draft external workbook mapping review",
)
async def save_mapping_review(
    project_id: str,
    batch_id: str,
    request: ImportMappingReviewUpdateRequest,
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    db: AsyncSession = Depends(get_db),
) -> ImportBatchResponse:
    async with db.begin():
        return await import_service.update_import_mapping_review(
            project_id,
            batch_id,
            request,
            actor_id,
            db,
        )


@router.post(
    "/{project_id}/{batch_id}/mapping-review/approve",
    response_model=ImportBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Approve a reviewed external mapping and queue catalog materialization",
)
async def approve_mapping_review(
    project_id: str,
    batch_id: str,
    request: ImportMappingReviewApproveRequest,
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    db: AsyncSession = Depends(get_db),
) -> ImportBatchResponse:
    async with db.begin():
        batch = await import_service.approve_import_mapping_review(
            project_id,
            batch_id,
            request,
            actor_id,
            db,
        )
    try:
        materialize_import_task.delay(batch.id)
    except Exception as exc:  # pragma: no cover - defensive dispatch path.
        async with db.begin():
            await import_service.mark_import_failed(
                batch.id,
                {"detail": "Approved mapping could not be dispatched.", "error": str(exc)},
                db,
            )
        raise HTTPException(
            status_code=503,
            detail={"detail": "Approved mapping could not be dispatched", "error_code": "IMPORT_MAPPING_DISPATCH_FAILED"},
        ) from exc
    return batch


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
