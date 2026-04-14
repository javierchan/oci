"""Import router — upload, process, and inspect import batches."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.imports import ImportBatchListResponse, ImportBatchResponse, SourceRowListResponse
from app.services import import_service

router = APIRouter(prefix="/imports", tags=["Imports"])


@router.post(
    "/{project_id}",
    response_model=ImportBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload source file and trigger import",
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
        async with db.begin():
            batch = await import_service.process_import(batch_id=batch.id, file_path=upload_path, db=db)
    except HTTPException:
        async with db.begin():
            await import_service.mark_import_failed(batch.id, {"detail": "Import failed."}, db)
        raise
    except Exception as exc:
        async with db.begin():
            await import_service.mark_import_failed(batch.id, {"detail": str(exc)}, db)
        raise HTTPException(
            status_code=500,
            detail={"detail": "Import processing failed", "error_code": "IMPORT_PROCESSING_FAILED"},
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
