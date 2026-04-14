"""Projects router — /projects (PRD-043)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/", summary="List all projects")
async def list_projects():
    # TODO: implement with DB session + RBAC
    return {"projects": []}


@router.post("/", status_code=status.HTTP_201_CREATED, summary="Create a project")
async def create_project(body: dict):
    # TODO: validate DTO, persist, emit AuditEvent
    return {"id": "placeholder", **body}


@router.get("/{project_id}", summary="Get project by ID")
async def get_project(project_id: str):
    # TODO: load from DB
    raise HTTPException(status_code=404, detail="Project not found")


@router.patch("/{project_id}", summary="Update project metadata")
async def update_project(project_id: str, body: dict):
    # TODO: partial update + audit
    return {"id": project_id, **body}
