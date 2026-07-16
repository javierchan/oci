"""Project APIs for deployment scenarios and governed OCI Bills of Materials."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.pricing import (
    BomGenerationRequest,
    BomComparisonResponse,
    BomJobListResponse,
    BomJobResponse,
    BomReviewRequest,
    BomSnapshotListResponse,
    BomSnapshotResponse,
    DeploymentScenarioCreateRequest,
    DeploymentScenarioListResponse,
    DeploymentScenarioResponse,
    ScenarioAssistantResponse,
)
from app.schemas.agent import AgentCreateRequest, AgentRunResponse
from app.services import agent_service, bom_service, export_service
from app.services.authz import require_roles
from app.workers.pricing_worker import execute_bom_job_task
from app.workers.agent_worker import execute_agent_run_task


router = APIRouter(prefix="/projects/{project_id}", tags=["Bill of Materials"])


def _require_bom_read(role: str | None) -> None:
    require_roles(role, {"Admin", "Architect", "Analyst", "Viewer"}, error_code="BOM_READ_ROLE_REQUIRED")


def _require_bom_run(role: str | None) -> None:
    require_roles(role, {"Admin", "Architect", "Analyst"}, error_code="BOM_RUN_ROLE_REQUIRED")


def _require_bom_approve(role: str | None) -> None:
    require_roles(role, {"Admin", "Architect"}, error_code="BOM_APPROVE_ROLE_REQUIRED")


@router.get("/deployment-scenarios", response_model=DeploymentScenarioListResponse, summary="List deployment scenarios")
async def list_deployment_scenarios(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> DeploymentScenarioListResponse:
    _require_bom_read(actor_role)
    return await bom_service.list_scenarios(project_id, db)


@router.get("/deployment-scenarios/assistant", response_model=ScenarioAssistantResponse, summary="Draft a smart deployment scenario")
async def get_deployment_scenario_assistant(
    project_id: str,
    include_llm: bool = False,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> ScenarioAssistantResponse:
    _require_bom_run(actor_role)
    return await bom_service.build_scenario_assistant(
        project_id,
        db,
        include_llm=include_llm,
        safety_subject=actor_id,
    )


@router.post(
    "/deployment-scenarios/agent",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run the governed BOM scenario agent",
)
async def run_bom_scenario_agent(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> AgentRunResponse:
    _require_bom_run(actor_role)
    async with db.begin():
        run = await agent_service.create_agent_run(
            AgentCreateRequest(agent_type="bom_scenario", project_id=project_id),
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


@router.post("/deployment-scenarios", response_model=DeploymentScenarioResponse, summary="Create a deployment scenario")
async def create_deployment_scenario(
    project_id: str,
    body: DeploymentScenarioCreateRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> DeploymentScenarioResponse:
    _require_bom_run(actor_role)
    async with db.begin():
        return await bom_service.create_scenario(project_id, body, actor_id, db)


@router.post(
    "/deployment-scenarios/{scenario_id}/approve",
    response_model=DeploymentScenarioResponse,
    summary="Approve a deployment scenario",
)
async def approve_deployment_scenario(
    project_id: str,
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> DeploymentScenarioResponse:
    _require_bom_approve(actor_role)
    async with db.begin():
        return await bom_service.approve_scenario(project_id, scenario_id, actor_id, db)


@router.post(
    "/bom-jobs",
    response_model=BomJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a governed OCI BOM",
)
async def create_bom_job(
    project_id: str,
    body: BomGenerationRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> BomJobResponse:
    _require_bom_run(actor_role)
    async with db.begin():
        job = await bom_service.create_bom_job(project_id, body.scenario_id, actor_id, db)
    try:
        execute_bom_job_task.apply_async(args=[job.id], task_id=job.id)
    except Exception as exc:  # pragma: no cover - defensive dispatch path
        async with db.begin():
            await bom_service.mark_bom_job_failed(job.id, {"detail": str(exc)}, db)
        raise HTTPException(
            status_code=503,
            detail={"detail": "BOM worker could not be dispatched", "error_code": "BOM_JOB_DISPATCH_FAILED"},
        ) from exc
    return job


@router.get("/bom-jobs", response_model=BomJobListResponse, summary="List BOM jobs")
async def list_bom_jobs(
    project_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> BomJobListResponse:
    _require_bom_read(actor_role)
    return await bom_service.list_bom_jobs(project_id, db, limit)


@router.get("/bom-jobs/{job_id}", response_model=BomJobResponse, summary="Get one BOM job")
async def get_bom_job(
    project_id: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> BomJobResponse:
    _require_bom_read(actor_role)
    return await bom_service.get_bom_job(project_id, job_id, db)


@router.get("/bom-snapshots", response_model=BomSnapshotListResponse, summary="List BOM snapshots")
async def list_bom_snapshots(
    project_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> BomSnapshotListResponse:
    _require_bom_read(actor_role)
    return await bom_service.list_bom_snapshots(project_id, db, limit)


@router.get("/bom-snapshots/compare", response_model=BomComparisonResponse, summary="Compare two governed BOMs")
async def compare_bom_snapshots(
    project_id: str,
    baseline_id: str,
    comparison_id: str,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> BomComparisonResponse:
    _require_bom_read(actor_role)
    return await bom_service.compare_bom_snapshots(project_id, baseline_id, comparison_id, db)


@router.get("/bom-snapshots/{snapshot_id}", response_model=BomSnapshotResponse, summary="Get one BOM snapshot")
async def get_bom_snapshot(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> BomSnapshotResponse:
    _require_bom_read(actor_role)
    return await bom_service.get_bom_snapshot(project_id, snapshot_id, db)


@router.get("/bom-snapshots/{snapshot_id}/exports/xlsx", summary="Download governed BOM as XLSX")
async def download_bom_xlsx(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> Response:
    _require_bom_read(actor_role)
    job = await export_service.create_bom_xlsx_export(project_id, snapshot_id, db)
    contents, _ = export_service.get_export_content(project_id, job.job_id)
    return Response(
        content=contents,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{job.filename}"'},
    )


@router.get("/bom-snapshots/{snapshot_id}/exports/json", summary="Download governed BOM as JSON")
async def download_bom_json(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> Response:
    _require_bom_read(actor_role)
    job = await export_service.create_bom_json_export(project_id, snapshot_id, db)
    contents, _ = export_service.get_export_content(project_id, job.job_id)
    return Response(
        content=contents,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{job.filename}"'},
    )


@router.get("/bom-snapshots/{snapshot_id}/exports/pdf", summary="Download governed BOM as PDF")
async def download_bom_pdf(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> Response:
    _require_bom_read(actor_role)
    job = await export_service.create_bom_pdf_export(project_id, snapshot_id, db)
    contents, _ = export_service.get_export_content(project_id, job.job_id)
    return Response(
        content=contents,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{job.filename}"'},
    )


@router.post(
    "/bom-snapshots/{snapshot_id}/review",
    response_model=BomSnapshotResponse,
    summary="Approve or publish a complete BOM",
)
async def review_bom_snapshot(
    project_id: str,
    snapshot_id: str,
    body: BomReviewRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> BomSnapshotResponse:
    _require_bom_approve(actor_role)
    async with db.begin():
        return await bom_service.review_bom_snapshot(project_id, snapshot_id, body, actor_id, db)
