"""Deployment scenario assistance and governed OCI Bill of Materials generation."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
import json
import math
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pricing_engine import CurrencyRule, PriceTier, PricingModel, PricingRequest, price_line
from app.models import (
    BomJob,
    BomLineItem,
    BomSnapshot,
    CatalogIntegration,
    DeploymentScenario,
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    Project,
    ServiceProductSkuMapping,
    VolumetrySnapshot,
)
from app.schemas.pricing import (
    BomJobListResponse,
    BomJobResponse,
    BomComparisonResponse,
    BomLineItemResponse,
    BomReviewRequest,
    BomSnapshotListResponse,
    BomSnapshotResponse,
    DeploymentEnvironmentInput,
    DeploymentScenarioCreateRequest,
    DeploymentScenarioListResponse,
    DeploymentScenarioResponse,
    ScenarioAssistantResponse,
)
from app.services import audit_service


BOM_ENGINE_VERSION = "pricing-engine-1.0.0"
DEFAULT_MONTH_DAYS = 31.0
DEFAULT_QUEUE_BILLING_UNIT_KB = 64.0


def _now() -> datetime:
    return datetime.now(UTC)


def _as_float(value: object, default: float = 0.0) -> float:
    if not isinstance(value, (str, int, float, Decimal)):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _as_int(value: object, default: int = 0) -> int:
    return int(_as_float(value, float(default)))


def _as_bool(value: object, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _split_tools(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def _canvas_tools(value: str | None) -> set[str]:
    if not value:
        return set()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return _split_tools(value)
    if not isinstance(payload, dict):
        return set()
    result: set[str] = set()
    for key in ("coreToolKeys", "overlayKeys"):
        values = payload.get(key)
        if isinstance(values, list):
            result.update(str(item).strip() for item in values if str(item).strip())
    return result


def _integration_tools(row: CatalogIntegration) -> set[str]:
    return _split_tools(row.core_tools) | _canvas_tools(row.additional_tools_overlays)


def _mapping_predicates_match(mapping: ServiceProductSkuMapping, config: dict[str, object]) -> bool:
    for key, expected in mapping.predicates.items():
        actual = config.get(key)
        if isinstance(expected, str):
            if str(actual or "").lower() != expected.lower():
                return False
        elif actual != expected:
            return False
    return True


def serialize_scenario(scenario: DeploymentScenario) -> DeploymentScenarioResponse:
    """Serialize one deployment scenario."""

    return DeploymentScenarioResponse(
        id=scenario.id,
        project_id=scenario.project_id,
        name=scenario.name,
        status=scenario.status,
        currency=scenario.currency,
        region=scenario.region,
        price_mode=scenario.price_mode,
        technical_snapshot_id=scenario.technical_snapshot_id,
        contract_months=scenario.contract_months,
        environments=[dict(item) for item in scenario.environments if isinstance(item, dict)],
        service_config=scenario.service_config,
        assumptions=scenario.scenario_assumptions,
        created_by=scenario.created_by,
        approved_by=scenario.approved_by,
        approved_at=scenario.approved_at,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
    )


def serialize_bom_job(job: BomJob) -> BomJobResponse:
    """Serialize one BOM job."""

    return BomJobResponse(
        id=job.id,
        project_id=job.project_id,
        scenario_id=job.scenario_id,
        requested_by=job.requested_by,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        bom_snapshot_id=job.bom_snapshot_id,
        error_details=job.error_details,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def serialize_bom_line(line: BomLineItem) -> BomLineItemResponse:
    """Serialize one BOM line item."""

    return BomLineItemResponse(
        id=line.id,
        environment=line.environment,
        service_id=line.service_id,
        part_number=line.part_number,
        description=line.description,
        metric_name=line.metric_name,
        quantity=line.quantity,
        unit=line.unit,
        unit_price=line.unit_price,
        monthly_amount=line.monthly_amount,
        annual_amount=line.annual_amount,
        contract_amount=line.contract_amount,
        formula=line.formula,
        inputs=line.inputs,
        status=line.status,
        warnings=line.warnings,
        provenance=line.provenance,
    )


def serialize_bom_snapshot(snapshot: BomSnapshot, lines: Iterable[BomLineItem]) -> BomSnapshotResponse:
    """Serialize a BOM snapshot and its line items."""

    return BomSnapshotResponse(
        id=snapshot.id,
        project_id=snapshot.project_id,
        scenario_id=snapshot.scenario_id,
        technical_snapshot_id=snapshot.technical_snapshot_id,
        price_catalog_snapshot_id=snapshot.price_catalog_snapshot_id,
        mapping_version=snapshot.mapping_version,
        engine_version=snapshot.engine_version,
        currency=snapshot.currency,
        coverage_pct=snapshot.coverage_pct,
        monthly_total=snapshot.monthly_total,
        annual_total=snapshot.annual_total,
        contract_total=snapshot.contract_total,
        summary=snapshot.summary,
        warnings=snapshot.warnings,
        publication_status=snapshot.publication_status,
        approved_by=snapshot.approved_by,
        approved_at=snapshot.approved_at,
        line_items=[serialize_bom_line(line) for line in lines],
        created_at=snapshot.created_at,
    )


async def _project_and_snapshot(
    project_id: str,
    db: AsyncSession,
    snapshot_id: str | None = None,
) -> tuple[Project, VolumetrySnapshot]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"})
    query = select(VolumetrySnapshot).where(VolumetrySnapshot.project_id == project_id)
    if snapshot_id:
        query = query.where(VolumetrySnapshot.id == snapshot_id)
    else:
        query = query.order_by(VolumetrySnapshot.created_at.desc())
    snapshot = await db.scalar(query)
    if snapshot is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "A technical volumetry snapshot is required", "error_code": "TECHNICAL_SNAPSHOT_REQUIRED"},
        )
    return project, snapshot


async def _project_integrations(project_id: str, db: AsyncSession) -> list[CatalogIntegration]:
    return list(
        (
            await db.scalars(
                select(CatalogIntegration)
                .where(CatalogIntegration.project_id == project_id)
                .order_by(CatalogIntegration.seq_number)
            )
        ).all()
    )


async def _active_mappings(db: AsyncSession) -> list[ServiceProductSkuMapping]:
    return list(
        (
            await db.scalars(
                select(ServiceProductSkuMapping)
                .where(ServiceProductSkuMapping.status == "approved")
                .order_by(ServiceProductSkuMapping.service_id, ServiceProductSkuMapping.billing_metric_key)
            )
        ).all()
    )


def _detected_services(
    integrations: Iterable[CatalogIntegration],
    mappings: Iterable[ServiceProductSkuMapping],
) -> tuple[list[str], set[str]]:
    tool_keys: set[str] = set()
    for row in integrations:
        tool_keys.update(_integration_tools(row))
    service_ids = sorted({mapping.service_id for mapping in mappings if mapping.tool_key in tool_keys})
    return service_ids, tool_keys


def _default_service_config(service_ids: Iterable[str]) -> dict[str, dict[str, object]]:
    service_config: dict[str, dict[str, object]] = {}
    for service_id in service_ids:
        if service_id == "OIC3":
            service_config[service_id] = {"edition": "standard", "byol": False, "instance_count": 1}
        elif service_id == "DATA_INTEGRATION":
            service_config[service_id] = {"workspace_count": 1, "operator_execution_hours_month": 0}
        elif service_id == "STREAMING":
            service_config[service_id] = {"retention_days": 7, "transfer_multiplier": 2}
        elif service_id == "QUEUE":
            service_config[service_id] = {"request_operations_per_message": 2}
        elif service_id == "GOLDENGATE":
            service_config[service_id] = {"byol": False, "ocpu_count": 1}
        else:
            service_config[service_id] = {}
    return service_config


def _required_questions(service_ids: Iterable[str]) -> list[str]:
    services = set(service_ids)
    questions = [
        "Which environments, active hours, demand shares, and HA/DR multipliers should the estimate include?",
        "Can this estimate consume tenancy-level Free Tier allowances, or are they already allocated elsewhere?",
    ]
    if "OIC3" in services:
        questions.append("Should Oracle Integration use Standard or Enterprise edition, and is BYOL contractually available?")
    if "DATA_INTEGRATION" in services:
        questions.append("How many Data Integration workspaces and operator execution hours are required per month?")
    if "GOLDENGATE" in services:
        questions.append("How many GoldenGate OCPUs are required per environment, and is BYOL available?")
    if "STREAMING" in services:
        questions.append("What Streaming retention period and PUT/GET transfer multiplier should be used?")
    return questions


async def build_scenario_assistant(
    project_id: str,
    db: AsyncSession,
    *,
    include_llm: bool = False,
    safety_subject: str | None = None,
) -> ScenarioAssistantResponse:
    """Build an evidence-backed baseline scenario and minimum client questions."""

    project, snapshot = await _project_and_snapshot(project_id, db)
    integrations = await _project_integrations(project_id, db)
    mappings = await _active_mappings(db)
    service_ids, _ = _detected_services(integrations, mappings)
    warnings = [
        "The draft is a deployment proposal, not an Oracle quote.",
        "Free Tier is disabled until tenancy-level allocation is confirmed.",
    ]
    if "GOLDENGATE" in service_ids:
        warnings.append("GoldenGate defaults to one OCPU only as an architect-review starting point.")
    if "DATA_INTEGRATION" in service_ids:
        warnings.append("Data Integration operator execution hours remain zero until supplied.")
    draft = DeploymentScenarioCreateRequest(
        name="Governed baseline",
        technical_snapshot_id=snapshot.id,
        currency="USD",
        region="global",
        price_mode="public_list",
        contract_months=12,
        environments=[DeploymentEnvironmentInput(name="Production")],
        service_config=_default_service_config(service_ids),
        assumptions={"free_tier_enabled": False, "drafted_from": snapshot.id},
    )
    ai_status = "skipped"
    ai_summary: str | None = None
    if include_llm:
        from app.core.config import get_settings
        from app.services.genai_client import synthesize_governed_summary

        result = await synthesize_governed_summary(
            settings=get_settings(),
            system_instruction=(
                "You are an OCI commercial architecture assistant. Use only the provided structured evidence. "
                "Explain the proposed deployment scenario in 80-120 words and identify the most important "
                "architect decision. Do not invent prices, discounts, quantities, or contract terms."
            ),
            evidence={
                "project": project.name,
                "technical_snapshot_id": snapshot.id,
                "detected_services": service_ids,
                "draft": draft.model_dump(mode="json"),
                "required_questions": _required_questions(service_ids),
                "warnings": warnings,
            },
            safety_subject=safety_subject,
        )
        ai_status = result.status
        ai_summary = result.summary
    return ScenarioAssistantResponse(
        draft=draft,
        detected_services=service_ids,
        required_questions=_required_questions(service_ids),
        warnings=warnings,
        confidence="medium" if service_ids else "low",
        ai_status=ai_status,
        ai_summary=ai_summary,
    )


async def create_scenario(
    project_id: str,
    request: DeploymentScenarioCreateRequest,
    actor_id: str,
    db: AsyncSession,
) -> DeploymentScenarioResponse:
    """Create an audited project deployment scenario."""

    _, snapshot = await _project_and_snapshot(project_id, db, request.technical_snapshot_id)
    environments = request.environments or [DeploymentEnvironmentInput(name="Production")]
    demand_share_total = sum(environment.demand_share for environment in environments)
    if abs(demand_share_total - 1.0) > 0.0001:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "Environment demand shares must total exactly 1.0; use HA multiplier for replicated capacity",
                "error_code": "SCENARIO_DEMAND_SHARE_INVALID",
            },
        )
    scenario = DeploymentScenario(
        project_id=project_id,
        name=request.name,
        status="draft",
        currency=request.currency.upper(),
        region=request.region,
        price_mode=request.price_mode,
        technical_snapshot_id=snapshot.id,
        contract_months=request.contract_months,
        environments=[environment.model_dump(mode="json") for environment in environments],
        service_config=request.service_config,
        scenario_assumptions=request.assumptions,
        created_by=actor_id,
    )
    db.add(scenario)
    await db.flush()
    await audit_service.emit(
        event_type="deployment_scenario_created",
        entity_type="deployment_scenario",
        entity_id=scenario.id,
        actor_id=actor_id,
        old_value=None,
        new_value={
            "name": scenario.name,
            "technical_snapshot_id": snapshot.id,
            "currency": scenario.currency,
            "environments": scenario.environments,
        },
        project_id=project_id,
        db=db,
    )
    await db.refresh(scenario)
    return serialize_scenario(scenario)


async def list_scenarios(project_id: str, db: AsyncSession) -> DeploymentScenarioListResponse:
    """Return deployment scenarios for one project."""

    await _project_and_snapshot(project_id, db)
    rows = (
        await db.scalars(
            select(DeploymentScenario)
            .where(DeploymentScenario.project_id == project_id)
            .order_by(DeploymentScenario.created_at.desc())
        )
    ).all()
    return DeploymentScenarioListResponse(scenarios=[serialize_scenario(row) for row in rows], total=len(rows))


async def approve_scenario(
    project_id: str,
    scenario_id: str,
    actor_id: str,
    db: AsyncSession,
) -> DeploymentScenarioResponse:
    """Approve a deployment scenario for deterministic pricing."""

    scenario = await db.scalar(
        select(DeploymentScenario).where(
            DeploymentScenario.id == scenario_id,
            DeploymentScenario.project_id == project_id,
        )
    )
    if scenario is None:
        raise HTTPException(status_code=404, detail={"detail": "Deployment scenario not found", "error_code": "DEPLOYMENT_SCENARIO_NOT_FOUND"})
    old_status = scenario.status
    scenario.status = "approved"
    scenario.approved_by = actor_id
    scenario.approved_at = _now()
    await audit_service.emit(
        event_type="deployment_scenario_approved",
        entity_type="deployment_scenario",
        entity_id=scenario.id,
        actor_id=actor_id,
        old_value={"status": old_status},
        new_value={"status": scenario.status, "technical_snapshot_id": scenario.technical_snapshot_id},
        project_id=project_id,
        db=db,
    )
    await db.flush()
    await db.refresh(scenario)
    return serialize_scenario(scenario)


async def create_bom_job(project_id: str, scenario_id: str, actor_id: str, db: AsyncSession) -> BomJobResponse:
    """Persist a pending BOM generation job for an approved scenario."""

    scenario = await db.scalar(
        select(DeploymentScenario).where(
            DeploymentScenario.id == scenario_id,
            DeploymentScenario.project_id == project_id,
        )
    )
    if scenario is None:
        raise HTTPException(status_code=404, detail={"detail": "Deployment scenario not found", "error_code": "DEPLOYMENT_SCENARIO_NOT_FOUND"})
    if scenario.status != "approved":
        raise HTTPException(
            status_code=409,
            detail={"detail": "Approve the deployment scenario before generating a BOM", "error_code": "DEPLOYMENT_SCENARIO_APPROVAL_REQUIRED"},
        )
    job = BomJob(project_id=project_id, scenario_id=scenario_id, requested_by=actor_id, status="pending")
    db.add(job)
    await db.flush()
    await audit_service.emit(
        event_type="bom_generation_requested",
        entity_type="bom_job",
        entity_id=job.id,
        actor_id=actor_id,
        old_value=None,
        new_value={"scenario_id": scenario_id, "status": job.status},
        project_id=project_id,
        correlation_id=job.id,
        db=db,
    )
    await db.refresh(job)
    return serialize_bom_job(job)


def _config_for(scenario: DeploymentScenario, service_id: str) -> dict[str, object]:
    value = scenario.service_config.get(service_id)
    return dict(value) if isinstance(value, dict) else {}


def _queue_request_millions(
    integrations: Iterable[CatalogIntegration],
    config: dict[str, object],
) -> float:
    operations = max(_as_float(config.get("request_operations_per_message"), 2.0), 1.0)
    total = 0.0
    for row in integrations:
        if "OCI Queue" not in _integration_tools(row):
            continue
        executions = _as_float(row.executions_per_day)
        payload = _as_float(row.payload_per_execution_kb)
        if executions <= 0 or payload <= 0:
            continue
        request_units = max(math.ceil(payload / DEFAULT_QUEUE_BILLING_UNIT_KB), 1)
        total += executions * DEFAULT_MONTH_DAYS * request_units * operations
    return total / 1_000_000.0


def _api_call_millions(integrations: Iterable[CatalogIntegration]) -> float:
    total = 0.0
    for row in integrations:
        if "OCI API Gateway" not in _integration_tools(row):
            continue
        total += _as_float(row.executions_per_day) * DEFAULT_MONTH_DAYS
    return total / 1_000_000.0


def _demand_for_metric(
    metric_key: str,
    scenario: DeploymentScenario,
    environment: dict[str, object],
    technical: dict[str, object],
    integrations: list[CatalogIntegration],
    service_config: dict[str, object],
) -> tuple[float | None, str, list[str]]:
    share = _as_float(environment.get("demand_share"), 1.0)
    ha = _as_float(environment.get("ha_multiplier"), 1.0)
    active_hours = _as_float(environment.get("active_hours_month"), 744.0)
    oic = _as_dict(technical.get("oic"))
    di = _as_dict(technical.get("data_integration"))
    functions = _as_dict(technical.get("functions"))
    streaming = _as_dict(technical.get("streaming"))
    warnings: list[str] = []

    if metric_key == "oic_peak_packs_hour":
        return _as_float(oic.get("peak_packs_hour")) * share * ha, "packs", warnings
    if metric_key == "di_workspace_hours":
        count = _as_float(service_config.get("workspace_count"), 1.0)
        return count * active_hours * ha, "workspace-hours", warnings
    if metric_key == "di_data_processed_gb":
        return _as_float(di.get("data_processed_gb_month")) * share, "GB", warnings
    if metric_key == "di_operator_execution_hours":
        if "operator_execution_hours_month" not in service_config:
            return None, "execution-hours", ["Data Integration operator execution hours are required."]
        return _as_float(service_config.get("operator_execution_hours_month")) * share, "execution-hours", warnings
    if metric_key == "functions_execution_10k_gb_s":
        return _as_float(functions.get("total_execution_units_gb_s")) * share / 10_000.0, "10K GB-s", warnings
    if metric_key == "functions_invocation_millions":
        return _as_float(functions.get("total_invocations_month")) * share / 1_000_000.0, "million invocations", warnings
    if metric_key == "streaming_transfer_gb":
        multiplier = _as_float(service_config.get("transfer_multiplier"), 2.0)
        warnings.append("Streaming transfer includes the approved PUT/GET multiplier.")
        return _as_float(streaming.get("total_gb_month")) * share * multiplier, "GB transferred", warnings
    if metric_key == "streaming_storage_gb_hours":
        retention_days = max(_as_float(service_config.get("retention_days"), 7.0), 0.0)
        daily_gb = _as_float(streaming.get("total_gb_month")) / DEFAULT_MONTH_DAYS
        warnings.append("Streaming storage is inferred from monthly flow and retention days.")
        return daily_gb * retention_days * 24.0 * share, "GB-hours", warnings
    if metric_key == "queue_request_millions":
        warnings.append("Queue requests are derived from payload billing units and enqueue/dequeue operations.")
        return _queue_request_millions(integrations, service_config) * share, "million requests", warnings
    if metric_key == "goldengate_ocpu_hours":
        if "ocpu_count" not in service_config:
            return None, "OCPU-hours", ["GoldenGate OCPU count is required."]
        return _as_float(service_config.get("ocpu_count")) * active_hours * ha, "OCPU-hours", warnings
    if metric_key == "api_gateway_call_millions":
        return _api_call_millions(integrations) * share, "million API calls", warnings
    if metric_key in {"events", "process_automation"}:
        return 0.0, "included", warnings
    return None, "unknown", [f"No demand resolver exists for {metric_key}."]


def _selected_price_tiers(items: list[PriceItem]) -> tuple[tuple[PriceTier, ...], float, list[PriceItem]]:
    free_tier = 0.0
    paid_items: list[PriceItem] = []
    for item in items:
        if item.value == 0 and item.range_max is not None:
            free_tier = max(free_tier, item.range_max)
        else:
            paid_items.append(item)
    paid_items.sort(key=lambda item: item.range_min if item.range_min is not None else -1.0)
    tiers = tuple(
        PriceTier(
            unit_price=Decimal(str(item.value)),
            range_min_exclusive=Decimal(str(item.range_min)) if item.range_min is not None else None,
            range_max_inclusive=Decimal(str(item.range_max)) if item.range_max is not None else None,
            source_item_id=item.id,
        )
        for item in paid_items
    )
    return tiers, free_tier, paid_items


def _price_mapping_line(
    mapping: ServiceProductSkuMapping,
    items: list[PriceItem],
    quantity: float,
    unit: str,
    environment: dict[str, object],
    scenario: DeploymentScenario,
    demand_warnings: list[str],
) -> dict[str, object]:
    if not mapping.is_billable:
        return {
            "environment": str(environment.get("name") or "Unspecified"),
            "service_id": mapping.service_id,
            "part_number": None,
            "description": f"{mapping.tool_key} - included or non-billable",
            "metric_name": mapping.billing_metric_key,
            "quantity": quantity,
            "unit": unit,
            "unit_price": 0.0,
            "monthly_amount": 0.0,
            "annual_amount": 0.0,
            "contract_amount": 0.0,
            "price_item_id": None,
            "formula": "non_billable",
            "inputs": {"quantity": quantity},
            "status": "non_billable",
            "warnings": demand_warnings,
            "provenance": {"mapping_id": mapping.id, "mapping_version": mapping.version},
        }
    if not items:
        return _blocked_line(mapping, environment, quantity, unit, [*demand_warnings, "Approved price item not found."])

    tiers, free_tier, paid_items = _selected_price_tiers(items)
    primary_item = paid_items[0] if paid_items else items[0]
    if not paid_items and quantity > free_tier:
        return _blocked_line(mapping, environment, quantity, unit, [*demand_warnings, "No paid price tier covers this demand."])
    use_free_tier = _as_bool(scenario.scenario_assumptions.get("free_tier_enabled"), False)
    free_allocation = min(quantity, free_tier) if use_free_tier else 0.0
    if tiers and not use_free_tier and free_tier > 0:
        tiers = tuple(
            PriceTier(
                unit_price=tier.unit_price,
                range_min_exclusive=None if index == 0 else tier.range_min_exclusive,
                range_max_inclusive=tier.range_max_inclusive,
                source_item_id=tier.source_item_id,
            )
            for index, tier in enumerate(tiers)
        )
    pricing_model = PricingModel.HOURLY if mapping.formula_key == "hourly_capacity" else PricingModel.MONTHLY
    annual_months = _as_int(environment.get("active_months_year"), 12)
    request = PricingRequest(
        sku=mapping.part_number or mapping.service_id,
        model=pricing_model,
        currency=CurrencyRule(scenario.currency, 2),
        quantity=Decimal(str(quantity)),
        unit_price=(Decimal(str(primary_item.value)) if not tiers else None),
        billing_unit=Decimal("1"),
        hours=(Decimal(str(_as_float(environment.get("active_hours_month"), 744.0))) if pricing_model is PricingModel.HOURLY else None),
        free_tier_allocation=Decimal(str(free_allocation)),
        tiers=tiers,
        tier_basis_quantity=Decimal(str(quantity)) if tiers else None,
        annual_active_months=annual_months,
        contract_months=scenario.contract_months,
    )
    result = price_line(request)
    selected_item_id = result.selected_tier.source_item_id if result.selected_tier else primary_item.id
    return {
        "environment": str(environment.get("name") or "Unspecified"),
        "service_id": mapping.service_id,
        "part_number": mapping.part_number,
        "description": primary_item.display_name,
        "metric_name": primary_item.metric_name,
        "quantity": quantity,
        "unit": unit,
        "unit_price": float(result.unit_price),
        "monthly_amount": float(result.totals.monthly),
        "annual_amount": float(result.totals.annual),
        "contract_amount": float(result.totals.contract),
        "price_item_id": selected_item_id,
        "formula": result.formula,
        "inputs": {**result.inputs, "gross_quantity": str(result.gross_quantity), "free_quantity": str(result.free_quantity_applied)},
        "status": "priced",
        "warnings": demand_warnings,
        "provenance": {"mapping_id": mapping.id, "mapping_version": mapping.version},
    }


def _blocked_line(
    mapping: ServiceProductSkuMapping,
    environment: dict[str, object],
    quantity: float,
    unit: str,
    warnings: list[str],
) -> dict[str, object]:
    return {
        "environment": str(environment.get("name") or "Unspecified"),
        "service_id": mapping.service_id,
        "part_number": mapping.part_number,
        "description": f"{mapping.tool_key} - pricing blocked",
        "metric_name": mapping.billing_metric_key,
        "quantity": quantity,
        "unit": unit,
        "unit_price": 0.0,
        "monthly_amount": 0.0,
        "annual_amount": 0.0,
        "contract_amount": 0.0,
        "price_item_id": None,
        "formula": "blocked_missing_input_or_price",
        "inputs": {"quantity": quantity},
        "status": "blocked",
        "warnings": warnings,
        "provenance": {"mapping_id": mapping.id, "mapping_version": mapping.version},
    }


def _blocked_service_line(service_id: str, environment: dict[str, object], warning: str) -> dict[str, object]:
    """Represent a detected service that has no single approved mapping decision."""

    return {
        "environment": str(environment.get("name") or "Unspecified"),
        "service_id": service_id,
        "part_number": None,
        "description": f"{service_id} - SKU mapping blocked",
        "metric_name": "unmapped_service",
        "quantity": 0.0,
        "unit": "unknown",
        "unit_price": 0.0,
        "monthly_amount": 0.0,
        "annual_amount": 0.0,
        "contract_amount": 0.0,
        "price_item_id": None,
        "formula": "blocked_missing_sku_mapping",
        "inputs": {},
        "status": "blocked",
        "warnings": [warning],
        "provenance": {"mapping_id": None, "mapping_version": None},
    }


async def run_bom_job(job_id: str, db: AsyncSession) -> BomJob:
    """Generate an immutable, coverage-aware BOM snapshot."""

    job = await db.get(BomJob, job_id)
    if job is None:
        raise ValueError("BOM job not found")
    scenario = await db.get(DeploymentScenario, job.scenario_id)
    if scenario is None or scenario.status != "approved":
        raise ValueError("Approved deployment scenario not found")
    technical = await db.get(VolumetrySnapshot, scenario.technical_snapshot_id)
    if technical is None:
        raise ValueError("Technical snapshot not found")
    allowed_source_types = {
        "public_list": {"public_list"},
        "contract_rate": {"manual_rate_card", "contract_rate"},
        "manual_rate_card": {"manual_rate_card"},
    }[scenario.price_mode]
    price_snapshot = await db.scalar(
        select(PriceCatalogSnapshot)
        .join(PriceSource, PriceSource.id == PriceCatalogSnapshot.source_id)
        .where(
            PriceCatalogSnapshot.currency == scenario.currency,
            PriceCatalogSnapshot.approval_status == "approved",
            PriceSource.source_type.in_(allowed_source_types),
        )
        .order_by(PriceCatalogSnapshot.created_at.desc())
    )
    if price_snapshot is None:
        raise ValueError(f"No approved {scenario.currency} price catalog is available")

    job.status = "running"
    job.started_at = _now()
    await db.flush()
    integrations = await _project_integrations(job.project_id, db)
    mappings = await _active_mappings(db)
    detected_services, _ = _detected_services(integrations, mappings)
    selected_mappings: list[ServiceProductSkuMapping] = []
    unmapped_services: list[str] = []
    for service_id in detected_services:
        config = _config_for(scenario, service_id)
        candidates = [mapping for mapping in mappings if mapping.service_id == service_id]
        matched = [mapping for mapping in candidates if _mapping_predicates_match(mapping, config)]
        if not matched:
            unmapped_services.append(service_id)
        selected_mappings.extend(matched)

    part_numbers = {mapping.part_number for mapping in selected_mappings if mapping.part_number}
    price_rows = (
        await db.scalars(
            select(PriceItem).where(
                PriceItem.snapshot_id == price_snapshot.id,
                PriceItem.part_number.in_(part_numbers),
            )
        )
    ).all() if part_numbers else []
    prices_by_part: dict[str, list[PriceItem]] = defaultdict(list)
    for price in price_rows:
        prices_by_part[price.part_number].append(price)

    line_payloads: list[dict[str, object]] = []
    environments = [item for item in scenario.environments if isinstance(item, dict)]
    for environment in environments:
        for service_id in unmapped_services:
            line_payloads.append(
                _blocked_service_line(
                    service_id,
                    environment,
                    "No approved SKU mapping matches the deployment scenario configuration.",
                )
            )
        for mapping in selected_mappings:
            config = _config_for(scenario, mapping.service_id)
            quantity, unit, warnings = _demand_for_metric(
                mapping.billing_metric_key,
                scenario,
                environment,
                technical.consolidated,
                integrations,
                config,
            )
            if quantity is None:
                line_payloads.append(_blocked_line(mapping, environment, 0.0, unit, warnings))
                continue
            line_payloads.append(
                _price_mapping_line(
                    mapping,
                    prices_by_part.get(mapping.part_number or "", []),
                    quantity,
                    unit,
                    environment,
                    scenario,
                    warnings,
                )
            )

    blocked = [line for line in line_payloads if line["status"] == "blocked"]
    covered = len(line_payloads) - len(blocked)
    coverage_pct = round((covered / len(line_payloads) * 100.0), 1) if line_payloads else 0.0
    monthly_total = round(sum(_as_float(line["monthly_amount"]) for line in line_payloads), 2)
    annual_total = round(sum(_as_float(line["annual_amount"]) for line in line_payloads), 2)
    contract_total = round(sum(_as_float(line["contract_amount"]) for line in line_payloads), 2)
    by_service: dict[str, float] = defaultdict(float)
    by_environment: dict[str, float] = defaultdict(float)
    for line in line_payloads:
        by_service[str(line["service_id"])] += _as_float(line["monthly_amount"])
        by_environment[str(line["environment"])] += _as_float(line["monthly_amount"])
    snapshot = BomSnapshot(
        project_id=job.project_id,
        scenario_id=scenario.id,
        technical_snapshot_id=technical.id,
        price_catalog_snapshot_id=price_snapshot.id,
        mapping_version="sku-mappings-1.0.0",
        engine_version=BOM_ENGINE_VERSION,
        currency=scenario.currency,
        coverage_pct=coverage_pct,
        monthly_total=monthly_total,
        annual_total=annual_total,
        contract_total=contract_total,
        summary={
            "line_count": len(line_payloads),
            "priced_line_count": covered,
            "blocked_line_count": len(blocked),
            "detected_services": detected_services,
            "by_service_monthly": {key: round(value, 2) for key, value in sorted(by_service.items())},
            "by_environment_monthly": {key: round(value, 2) for key, value in sorted(by_environment.items())},
            "estimate_notice": "Planning estimate only; not an Oracle quote.",
        },
        warnings=[warning for line in blocked for warning in _as_string_list(line.get("warnings"))],
        publication_status="draft",
    )
    db.add(snapshot)
    await db.flush()
    db.add_all([BomLineItem(bom_snapshot_id=snapshot.id, **payload) for payload in line_payloads])
    job.status = "completed"
    job.completed_at = _now()
    job.bom_snapshot_id = snapshot.id
    await audit_service.emit(
        event_type="bom_generation_completed",
        entity_type="bom_snapshot",
        entity_id=snapshot.id,
        actor_id=job.requested_by,
        old_value=None,
        new_value={
            "scenario_id": scenario.id,
            "technical_snapshot_id": technical.id,
            "price_catalog_snapshot_id": price_snapshot.id,
            "coverage_pct": coverage_pct,
            "monthly_total": monthly_total,
            "publication_status": snapshot.publication_status,
        },
        project_id=job.project_id,
        correlation_id=job.id,
        db=db,
    )
    await db.flush()
    return job


async def mark_bom_job_failed(job_id: str, error: dict[str, object], db: AsyncSession) -> None:
    """Persist terminal failure details for a BOM job."""

    job = await db.get(BomJob, job_id)
    if job is None:
        return
    job.status = "failed"
    job.completed_at = _now()
    job.error_details = error
    await db.flush()


async def list_bom_jobs(project_id: str, db: AsyncSession, limit: int = 20) -> BomJobListResponse:
    """Return recent BOM generation jobs."""

    rows = (
        await db.scalars(
            select(BomJob)
            .where(BomJob.project_id == project_id)
            .order_by(BomJob.created_at.desc())
            .limit(min(max(limit, 1), 100))
        )
    ).all()
    return BomJobListResponse(jobs=[serialize_bom_job(row) for row in rows], total=len(rows))


async def get_bom_job(project_id: str, job_id: str, db: AsyncSession) -> BomJobResponse:
    """Return one BOM generation job."""

    job = await db.scalar(select(BomJob).where(BomJob.project_id == project_id, BomJob.id == job_id))
    if job is None:
        raise HTTPException(status_code=404, detail={"detail": "BOM job not found", "error_code": "BOM_JOB_NOT_FOUND"})
    return serialize_bom_job(job)


async def get_bom_snapshot(project_id: str, snapshot_id: str, db: AsyncSession) -> BomSnapshotResponse:
    """Return one immutable BOM with all line items."""

    snapshot = await db.scalar(
        select(BomSnapshot).where(BomSnapshot.project_id == project_id, BomSnapshot.id == snapshot_id)
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail={"detail": "BOM snapshot not found", "error_code": "BOM_SNAPSHOT_NOT_FOUND"})
    lines = (
        await db.scalars(
            select(BomLineItem)
            .where(BomLineItem.bom_snapshot_id == snapshot.id)
            .order_by(BomLineItem.environment, BomLineItem.service_id, BomLineItem.part_number)
        )
    ).all()
    return serialize_bom_snapshot(snapshot, lines)


async def list_bom_snapshots(project_id: str, db: AsyncSession, limit: int = 20) -> BomSnapshotListResponse:
    """Return recent BOM snapshots with compact empty line arrays."""

    rows = (
        await db.scalars(
            select(BomSnapshot)
            .where(BomSnapshot.project_id == project_id)
            .order_by(BomSnapshot.created_at.desc())
            .limit(min(max(limit, 1), 100))
        )
    ).all()
    return BomSnapshotListResponse(snapshots=[serialize_bom_snapshot(row, []) for row in rows], total=len(rows))


async def compare_bom_snapshots(
    project_id: str,
    baseline_snapshot_id: str,
    comparison_snapshot_id: str,
    db: AsyncSession,
) -> BomComparisonResponse:
    """Explain total, service, and environment deltas without generative inference."""

    baseline = await get_bom_snapshot(project_id, baseline_snapshot_id, db)
    comparison = await get_bom_snapshot(project_id, comparison_snapshot_id, db)
    if baseline.currency != comparison.currency:
        raise HTTPException(
            status_code=409,
            detail={"detail": "BOM snapshots use different currencies", "error_code": "BOM_CURRENCY_MISMATCH"},
        )

    def _summary_amounts(snapshot: BomSnapshotResponse, key: str) -> dict[str, float]:
        raw = snapshot.summary.get(key)
        if not isinstance(raw, dict):
            return {}
        return {str(name): _as_float(value) for name, value in raw.items()}

    def _deltas(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
        return {
            key: round(right.get(key, 0.0) - left.get(key, 0.0), 2)
            for key in sorted(set(left) | set(right))
            if round(right.get(key, 0.0) - left.get(key, 0.0), 2) != 0.0
        }

    service_deltas = _deltas(
        _summary_amounts(baseline, "by_service_monthly"),
        _summary_amounts(comparison, "by_service_monthly"),
    )
    environment_deltas = _deltas(
        _summary_amounts(baseline, "by_environment_monthly"),
        _summary_amounts(comparison, "by_environment_monthly"),
    )
    drivers = [f"Service {name}: {amount:+.2f} {baseline.currency}/month" for name, amount in service_deltas.items()]
    drivers.extend(
        f"Environment {name}: {amount:+.2f} {baseline.currency}/month"
        for name, amount in environment_deltas.items()
    )
    if baseline.price_catalog_snapshot_id != comparison.price_catalog_snapshot_id:
        drivers.append("Price catalog snapshot changed.")
    if baseline.scenario_id != comparison.scenario_id:
        drivers.append("Deployment scenario changed.")
    if baseline.technical_snapshot_id != comparison.technical_snapshot_id:
        drivers.append("Technical demand snapshot changed.")
    return BomComparisonResponse(
        baseline_snapshot_id=baseline.id,
        comparison_snapshot_id=comparison.id,
        currency=baseline.currency,
        monthly_delta=round(comparison.monthly_total - baseline.monthly_total, 2),
        annual_delta=round(comparison.annual_total - baseline.annual_total, 2),
        contract_delta=round(comparison.contract_total - baseline.contract_total, 2),
        service_monthly_deltas=service_deltas,
        environment_monthly_deltas=environment_deltas,
        drivers=drivers,
    )


async def review_bom_snapshot(
    project_id: str,
    snapshot_id: str,
    request: BomReviewRequest,
    actor_id: str,
    db: AsyncSession,
) -> BomSnapshotResponse:
    """Approve or publish a complete BOM snapshot."""

    snapshot = await db.scalar(
        select(BomSnapshot).where(BomSnapshot.project_id == project_id, BomSnapshot.id == snapshot_id)
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail={"detail": "BOM snapshot not found", "error_code": "BOM_SNAPSHOT_NOT_FOUND"})
    if snapshot.coverage_pct < 100.0:
        raise HTTPException(
            status_code=409,
            detail={"detail": "Resolve every blocked BOM line before approval or publication", "error_code": "BOM_COVERAGE_INCOMPLETE"},
        )
    old_status = snapshot.publication_status
    snapshot.publication_status = request.publication_status
    snapshot.approved_by = actor_id
    snapshot.approved_at = _now()
    await audit_service.emit(
        event_type="bom_snapshot_reviewed",
        entity_type="bom_snapshot",
        entity_id=snapshot.id,
        actor_id=actor_id,
        old_value={"publication_status": old_status},
        new_value={"publication_status": snapshot.publication_status, "note": request.note},
        project_id=project_id,
        db=db,
    )
    await db.flush()
    return await get_bom_snapshot(project_id, snapshot_id, db)
