"""Import router — /imports (PRD-015 to PRD-019)."""
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, status

router = APIRouter(prefix="/imports", tags=["Imports"])


@router.post("/{project_id}", status_code=status.HTTP_202_ACCEPTED, summary="Upload source file and trigger import")
async def upload_and_import(
    project_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Accepts XLSX or CSV. Validates file, persists it to object storage,
    creates an ImportBatch record, then queues import_worker.process_import
    as a background job.

    Rules applied:
    - Headers detected at row 5, data starts at row 6 (PRD-016)
    - Keep TBQ=Y rows, exclude Duplicado 2 (PRD-017)
    - Preserve source order and original # (PRD-018)
    - Normalize frequency, status, destination tech split (PRD-019)
    """
    # TODO: validate, store, dispatch Celery task
    return {
        "import_batch_id": "placeholder",
        "project_id": project_id,
        "filename": file.filename,
        "status": "pending",
    }


@router.get("/{project_id}", summary="List import batches for a project")
async def list_imports(project_id: str):
    return {"import_batches": []}


@router.get("/{project_id}/{batch_id}", summary="Get import batch status and stats")
async def get_import(project_id: str, batch_id: str):
    return {"batch_id": batch_id, "status": "pending"}


@router.get("/{project_id}/{batch_id}/rows", summary="Get source rows with inclusion/exclusion reasons")
async def get_import_rows(project_id: str, batch_id: str, included: bool = True):
    return {"rows": []}
