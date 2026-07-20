"""Deployment scenario assistance and governed OCI Bill of Materials generation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
import json
import math
from typing import Iterable, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pricing_engine import (
    CurrencyRule,
    PriceTier,
    PricingModel,
    PricingRequest,
    QuantityBehavior,
    QuantityRampPhase,
    QuantityRule,
    RampInterpolation,
    RampPhase,
    expand_ramp,
    expand_quantity_ramp,
    normalize_quantity,
    price_line,
    price_line_quantity_schedule,
    price_line_schedule,
)
from app.models import (
    BomJob,
    BomLinePeriod,
    BomLineItem,
    BomSnapshot,
    CatalogIntegration,
    CommercialEvidenceReference,
    CommercialException,
    CommercialRelease,
    CommercialRuleFamily,
    DeploymentScenario,
    DeploymentEnvironmentPlan,
    DeploymentRampPhase,
    DeploymentRampPeriodQuantity,
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    Project,
    ServiceCommercialPolicy,
    ServiceProductSkuMapping,
    SkuCommercialConstraint,
    SkuCommercialTerm,
    VolumetrySnapshot,
)
from app.schemas.pricing import (
    BomJobListResponse,
    BomJobResponse,
    BomComparisonResponse,
    BomLineItemResponse,
    BomLinePeriodResponse,
    BomPeriodSummary,
    BomReviewRequest,
    BomSnapshotListResponse,
    BomSnapshotResponse,
    DeploymentEnvironmentInput,
    DeploymentMonthlyQuantityInput,
    DeploymentRampPhaseInput,
    DeploymentScenarioCreateRequest,
    DeploymentScenarioListResponse,
    DeploymentScenarioResponse,
    ScenarioAssistantResponse,
    CurrentBomContextResponse,
    ScenarioMetricOptionResponse,
    ScenarioSkuVariantResponse,
    ScenarioCommercialCoverageResponse,
    QuantityPresetResponse,
)
from app.schemas.ai_review import AiReviewActionCandidate, AiReviewActionWorkspace
from app.services import audit_service, pricing_governance_service


BOM_ENGINE_VERSION = "pricing-engine-3.0.0"
DEFAULT_MONTH_DAYS = 31.0
DEFAULT_QUEUE_BILLING_UNIT_KB = 64.0


@dataclass(frozen=True)
class BomCalculation:
    """Complete deterministic BOM calculation before optional persistence."""

    price_snapshot: PriceCatalogSnapshot
    commercial_release: CommercialRelease
    line_payloads: list[dict[str, object]]
    period_payloads: list[list[dict[str, object]]]
    coverage_pct: float
    monthly_total: float
    annual_total: float
    contract_total: float
    peak_monthly_total: float
    full_capacity_contract: float
    ramp_deferred_amount: float
    first_active_period: int | None
    steady_state_period: int | None
    monthly_series: list[dict[str, object]]
    detected_services: list[str]
    by_service: dict[str, float]
    by_environment: dict[str, float]
    warnings: list[str]


@dataclass(frozen=True)
class GovernedSkuCommercialContract:
    """Approved public commercial semantics compiled for one mapped OCI SKU."""

    release: CommercialRelease
    term: SkuCommercialTerm
    rule: CommercialRuleFamily
    constraints: tuple[SkuCommercialConstraint, ...]
    evidence_reference_ids: tuple[str, ...]


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


def _as_dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [_as_dict(item) for item in value if isinstance(item, dict)]


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


def _integration_tools_with_overrides(
    row: CatalogIntegration,
    tool_overrides: dict[str, tuple[str, str]] | None = None,
) -> set[str]:
    override = (tool_overrides or {}).get(row.id)
    if override is None:
        return _integration_tools(row)
    core_tools, canvas_state = override
    return _split_tools(core_tools) | _canvas_tools(canvas_state)


def _mapping_predicates_match(mapping: ServiceProductSkuMapping, config: dict[str, object]) -> bool:
    for key, expected in mapping.predicates.items():
        actual = config.get(key)
        if isinstance(expected, str):
            if str(actual or "").lower() != expected.lower():
                return False
        elif actual != expected:
            return False
    return True


def _mapping_selection_policy(mapping: ServiceProductSkuMapping) -> str:
    return str(getattr(mapping, "selection_policy", None) or "required")


def _mapping_variant_label(mapping: ServiceProductSkuMapping) -> str:
    """Return a concise commercial label without assuming OIC-only predicates."""

    parts: list[str] = []
    ordered_predicates = sorted(
        mapping.predicates.items(),
        key=lambda item: ({"edition": 0, "byol": 1, "license_model": 2}.get(item[0], 10), item[0]),
    )
    for key, value in ordered_predicates:
        if key == "byol":
            parts.append("BYOL" if bool(value) else "PAYG")
        elif isinstance(value, bool):
            parts.append(key.replace("_", " ").title() if value else f"No {key.replace('_', ' ')}")
        else:
            parts.append(str(value).replace("_", " ").title())
    if not parts:
        parts.append("Default")
    if mapping.part_number:
        parts.append(mapping.part_number)
    return " · ".join(parts)


def _mapping_provenance(mapping: ServiceProductSkuMapping) -> dict[str, object]:
    return {
        "mapping_id": mapping.id,
        "mapping_version": mapping.version,
        "commercial_variant": _mapping_variant_label(mapping),
        "mapping_predicates": mapping.predicates,
        "part_number": mapping.part_number,
        "aggregation_window": mapping.aggregation_window,
        "proration_policy": mapping.proration_policy,
        "free_tier_scope": mapping.free_tier_scope,
        "metering_policy": mapping.metering_policy,
    }


def _mapping_quantity_presets(mapping: ServiceProductSkuMapping) -> list[QuantityPresetResponse]:
    return [
        QuantityPresetResponse.model_validate(item)
        for item in mapping.quantity_presets
        if isinstance(item, dict)
    ]


def _planning_envelope(quantity: float, increment: float | None) -> float | None:
    """Return an optional conservative reserve without changing billable demand."""

    if increment is None or increment <= 0 or quantity <= 0:
        return None
    return math.ceil((quantity / increment) - 1e-12) * increment


def _environment_phase_payloads(environment: dict[str, object]) -> list[dict[str, object]]:
    value = environment.get("phases")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    return date(value.year + month_index // 12, month_index % 12 + 1, 1)


async def _scenario_environments(
    scenario_id: str,
    db: AsyncSession,
) -> list[DeploymentEnvironmentInput]:
    plans = list(
        (
            await db.scalars(
                select(DeploymentEnvironmentPlan)
                .where(DeploymentEnvironmentPlan.scenario_id == scenario_id)
                .order_by(DeploymentEnvironmentPlan.sequence, DeploymentEnvironmentPlan.name)
            )
        ).all()
    )
    if not plans:
        return []
    phases = list(
        (
            await db.scalars(
                select(DeploymentRampPhase)
                .where(DeploymentRampPhase.environment_plan_id.in_([plan.id for plan in plans]))
                .order_by(
                    DeploymentRampPhase.environment_plan_id,
                    DeploymentRampPhase.service_id,
                    DeploymentRampPhase.start_month,
                )
            )
        ).all()
    )
    phases_by_plan: dict[str, list[DeploymentRampPhaseInput]] = defaultdict(list)
    quantities = list(
        (
            await db.scalars(
                select(DeploymentRampPeriodQuantity)
                .where(DeploymentRampPeriodQuantity.ramp_phase_id.in_([phase.id for phase in phases]))
                .order_by(
                    DeploymentRampPeriodQuantity.ramp_phase_id,
                    DeploymentRampPeriodQuantity.period_index,
                )
            )
        ).all()
    ) if phases else []
    quantities_by_phase: dict[str, list[DeploymentMonthlyQuantityInput]] = defaultdict(list)
    for quantity in quantities:
        quantities_by_phase[quantity.ramp_phase_id].append(
            DeploymentMonthlyQuantityInput(
                period_index=quantity.period_index,
                quantity=quantity.quantity,
            )
        )
    for phase in phases:
        phases_by_plan[phase.environment_plan_id].append(
            DeploymentRampPhaseInput(
                service_id=phase.service_id,
                metric_key=phase.metric_key,
                sku_mapping_id=phase.sku_mapping_id,
                start_month=phase.start_month,
                end_month=phase.end_month,
                start_multiplier=phase.start_multiplier,
                end_multiplier=phase.end_multiplier,
                interpolation=phase.interpolation,
                start_quantity=phase.start_quantity,
                end_quantity=phase.end_quantity,
                quantity_unit=phase.quantity_unit,
                monthly_quantities=quantities_by_phase[phase.id],
                rationale=phase.rationale,
            )
        )
    return [
        DeploymentEnvironmentInput(
            name=plan.name,
            active_hours_month=plan.active_hours_month,
            demand_share=plan.demand_share,
            ha_multiplier=plan.ha_multiplier,
            dr_role=plan.dr_role,
            phases=phases_by_plan[plan.id],
        )
        for plan in plans
    ]


async def serialize_scenario(
    scenario: DeploymentScenario,
    db: AsyncSession,
) -> DeploymentScenarioResponse:
    """Serialize one deployment scenario."""

    return DeploymentScenarioResponse(
        id=scenario.id,
        project_id=scenario.project_id,
        name=scenario.name,
        status=scenario.status,
        currency=scenario.currency,
        region=scenario.region,
        price_mode=scenario.price_mode,
        commitment_model=scenario.commitment_model,
        technical_snapshot_id=scenario.technical_snapshot_id,
        contract_months=scenario.contract_months,
        start_date=scenario.start_date,
        proration_policy=scenario.proration_policy,
        consumption_model=scenario.consumption_model,
        environments=await _scenario_environments(scenario.id, db),
        service_config=cast(dict[str, dict[str, object]], scenario.service_config),
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


def serialize_bom_period(period: BomLinePeriod) -> BomLinePeriodResponse:
    """Serialize one immutable monthly BOM period."""

    return BomLinePeriodResponse(
        id=period.id,
        period_index=period.period_index,
        period_start=period.period_start,
        multiplier=period.multiplier,
        quantity=period.quantity,
        active_hours=period.active_hours,
        unit_price=period.unit_price,
        amount=period.amount,
        selected_price_item_id=period.selected_price_item_id,
        formula=period.formula,
        inputs=period.inputs,
        status=period.status,
        warnings=period.warnings,
        provenance=period.provenance,
    )


def serialize_bom_line(
    line: BomLineItem,
    periods: Iterable[BomLinePeriod] = (),
) -> BomLineItemResponse:
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
        periods=[serialize_bom_period(period) for period in periods],
    )


def _monthly_series_from_line_periods(
    lines: Iterable[BomLineItem],
    periods_by_line: dict[str, list[BomLinePeriod]],
) -> list[dict[str, object]]:
    """Rebuild aggregate chart evidence for snapshots created before monthly summaries."""

    period_starts: dict[int, date] = {}
    totals: dict[int, Decimal] = defaultdict(Decimal)
    by_environment: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    by_service: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for line in lines:
        for period in periods_by_line.get(line.id, []):
            amount = Decimal(str(period.amount))
            period_starts[period.period_index] = period.period_start
            totals[period.period_index] += amount
            by_environment[period.period_index][line.environment] += amount
            by_service[period.period_index][line.service_id] += amount

    cumulative = Decimal("0")
    result: list[dict[str, object]] = []
    for period_index in sorted(period_starts):
        total = totals[period_index].quantize(Decimal("0.01"))
        cumulative += total
        result.append(
            {
                "period_index": period_index,
                "period_start": period_starts[period_index],
                "total": float(total),
                "cumulative_total": float(cumulative.quantize(Decimal("0.01"))),
                "by_environment": {
                    key: float(value.quantize(Decimal("0.01")))
                    for key, value in sorted(by_environment[period_index].items())
                },
                "by_service": {
                    key: float(value.quantize(Decimal("0.01")))
                    for key, value in sorted(by_service[period_index].items())
                },
            }
        )
    return result


def serialize_bom_snapshot(
    snapshot: BomSnapshot,
    lines: Iterable[BomLineItem],
    periods_by_line: dict[str, list[BomLinePeriod]] | None = None,
) -> BomSnapshotResponse:
    """Serialize a BOM snapshot and its line items."""

    line_rows = list(lines)
    period_rows = periods_by_line or {}
    monthly_series = _as_dict_list(snapshot.summary.get("monthly_series"))
    if not monthly_series:
        monthly_series = _monthly_series_from_line_periods(line_rows, period_rows)

    return BomSnapshotResponse(
        id=snapshot.id,
        project_id=snapshot.project_id,
        scenario_id=snapshot.scenario_id,
        technical_snapshot_id=snapshot.technical_snapshot_id,
        price_catalog_snapshot_id=snapshot.price_catalog_snapshot_id,
        commercial_release_id=snapshot.commercial_release_id,
        mapping_version=snapshot.mapping_version,
        engine_version=snapshot.engine_version,
        currency=snapshot.currency,
        coverage_pct=snapshot.coverage_pct,
        monthly_total=snapshot.monthly_total,
        annual_total=snapshot.annual_total,
        contract_total=snapshot.contract_total,
        steady_state_monthly_total=snapshot.steady_state_monthly_total,
        peak_monthly_total=snapshot.peak_monthly_total,
        ramp_deferred_amount=snapshot.ramp_deferred_amount,
        first_active_period=snapshot.first_active_period,
        steady_state_period=snapshot.steady_state_period,
        monthly_series=[
            BomPeriodSummary.model_validate(
                {
                    **item,
                    "period_start": (
                        date.fromisoformat(str(item["period_start"]))
                        if isinstance(item.get("period_start"), str)
                        else item.get("period_start")
                    ),
                }
            )
            for item in monthly_series
        ],
        recommendation_workspace=_bom_action_workspace(snapshot),
        summary=snapshot.summary,
        warnings=snapshot.warnings,
        publication_status=snapshot.publication_status,
        approved_by=snapshot.approved_by,
        approved_at=snapshot.approved_at,
        line_items=[
            serialize_bom_line(line, period_rows.get(line.id, []))
            for line in line_rows
        ],
        created_at=snapshot.created_at,
    )


def _bom_action_workspace(snapshot: BomSnapshot) -> AiReviewActionWorkspace:
    """Translate immutable BOM evidence into a bounded commercial action plan."""

    candidates: list[AiReviewActionCandidate] = []
    blocked_count = int(_as_float(snapshot.summary.get("blocked_line_count")))
    if snapshot.coverage_pct < 100 or blocked_count:
        candidates.append(
            AiReviewActionCandidate(
                id="bom-action-coverage",
                priority="now",
                status="blocked",
                title="Close pricing coverage before commercial sign-off",
                summary=(
                    f"{blocked_count} BOM line(s) remain blocked and governed coverage is "
                    f"{snapshot.coverage_pct:.1f}%."
                ),
                what_to_change=[
                    "Map every detected Service Product to an approved SKU and billing metric.",
                    "Capture missing real-unit monthly quantities for every active environment.",
                ],
                implementation_steps=[
                    "Open the blocked BOM lines and identify missing SKU mappings, price items, or quantities.",
                    "Update the governed mapping or deployment scenario; do not patch published line totals.",
                    "Generate a new BOM snapshot and compare it with this immutable estimate.",
                ],
                validation_plan=[
                    "Require 100% governed line coverage before approval.",
                    "Verify each line retains price-catalog, mapping, formula, and period provenance.",
                ],
                expected_impact=["Removes unpriced architecture from the contractual estimate."],
                evidence_ids=[snapshot.id, snapshot.price_catalog_snapshot_id, snapshot.mapping_version],
                action_label="Review BOM coverage",
                action_href=f"/projects/{snapshot.project_id}/bom",
                confidence="high",
            )
        )
    by_service = {
        str(key): _as_float(value)
        for key, value in _as_dict(snapshot.summary.get("by_service_monthly")).items()
    }
    if by_service:
        service_id, amount = max(by_service.items(), key=lambda item: item[1])
        share = amount / snapshot.monthly_total * 100 if snapshot.monthly_total else 0.0
        candidates.append(
            AiReviewActionCandidate(
                id="bom-action-top-driver",
                priority="next" if candidates else "now",
                status="review",
                title=f"Validate the {service_id} cost driver",
                summary=f"{service_id} contributes {share:.1f}% of steady-state monthly cost.",
                what_to_change=[
                    "Confirm the selected SKU, billing metric, quantity behavior, and environment allocation.",
                    "Compare the current sizing with one lower-footprint alternative before approval.",
                ],
                implementation_steps=[
                    "Open the service line and inspect its monthly quantity and formula provenance.",
                    "Validate workload evidence against payload, executions, active hours, HA, and DR posture.",
                    "Create a governed comparison scenario if an alternative is operationally valid.",
                ],
                validation_plan=[
                    "Compare monthly and contract deltas without changing the original snapshot.",
                    "Confirm the alternative still passes service limits and resilience requirements.",
                ],
                expected_impact=["Focuses architecture review on the material cost driver without optimizing blindly."],
                evidence_ids=[snapshot.id, snapshot.technical_snapshot_id, snapshot.price_catalog_snapshot_id],
                action_label="Inspect cost driver",
                action_href=f"/projects/{snapshot.project_id}/bom",
                confidence="high",
            )
        )
    candidates.append(
        AiReviewActionCandidate(
            id="bom-action-ramp",
            priority="next" if len(candidates) < 2 else "monitor",
            status="ready" if snapshot.first_active_period is not None else "review",
            title="Validate environment activation and consumption ramp",
            summary=(
                f"Consumption starts in month {snapshot.first_active_period or 'not set'}, reaches steady state in "
                f"month {snapshot.steady_state_period or 'not set'}, and defers {snapshot.currency} "
                f"{snapshot.ramp_deferred_amount:,.2f} versus day-one full capacity."
            ),
            what_to_change=[
                "Align DEV, QA, PROD, and DR activation months with the delivery plan.",
                "Use real SKU units per product and month; keep timing effects separate from negotiated savings.",
            ],
            implementation_steps=[
                "Review the monthly matrix by environment and Service Product.",
                "Confirm overlap months, package increments, minimum quantities, HA, and DR multipliers.",
                "Regenerate the BOM whenever the implementation calendar changes.",
            ],
            validation_plan=[
                "Check peak month, steady-state month, contract bridge, and environment subtotals.",
                "Confirm the exported monthly BOM reproduces the approved in-App scenario.",
            ],
            expected_impact=["Makes phased consumption explicit and prevents a day-one capacity overstatement."],
            evidence_ids=[snapshot.id, snapshot.scenario_id],
            action_label="Review monthly ramp",
            action_href=f"/projects/{snapshot.project_id}/bom",
            confidence="high" if snapshot.first_active_period is not None else "medium",
        )
    )
    return AiReviewActionWorkspace(
        context="bom",
        title="BOM decision workspace",
        recommendation_basis=(
            "Actions are derived from immutable monthly line periods, governed SKU mappings, pricing coverage, "
            "Service Product concentration, and the approved environment ramp."
        ),
        candidates=candidates[:3],
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
    """Load only integrations explicitly eligible for the economic exercise."""

    return list(
        (
            await db.scalars(
                select(CatalogIntegration)
                .where(
                    CatalogIntegration.project_id == project_id,
                    CatalogIntegration.tbq == "Y",
                )
                .order_by(CatalogIntegration.seq_number)
            )
        ).all()
    )


def _commercial_consolidated(snapshot: VolumetrySnapshot) -> dict[str, object]:
    """Return the immutable TBQ=Y aggregate, with compatibility for legacy snapshots."""

    metadata = snapshot.snapshot_metadata or {}
    commercial = metadata.get("commercial_consolidated")
    if isinstance(commercial, dict):
        return commercial
    return snapshot.consolidated


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


async def _active_commercial_policies(db: AsyncSession) -> list[ServiceCommercialPolicy]:
    return list(
        (
            await db.scalars(
                select(ServiceCommercialPolicy)
                .where(ServiceCommercialPolicy.status == "approved")
                .order_by(ServiceCommercialPolicy.service_id)
            )
        ).all()
    )


async def _resolve_commercial_release(
    *,
    price_snapshot: PriceCatalogSnapshot,
    price_source: PriceSource,
    currency: str,
    db: AsyncSession,
) -> CommercialRelease:
    """Resolve the immutable public commercial semantics used by a new BOM."""

    statement = (
        select(CommercialRelease)
        .join(
            PriceCatalogSnapshot,
            PriceCatalogSnapshot.id == CommercialRelease.price_catalog_snapshot_id,
        )
        .join(PriceSource, PriceSource.id == PriceCatalogSnapshot.source_id)
        .where(
            CommercialRelease.status == "approved",
            CommercialRelease.validation_status == "passed",
            CommercialRelease.open_exception_count == 0,
            PriceCatalogSnapshot.currency == currency,
            PriceSource.source_type == "public_list",
        )
        .order_by(CommercialRelease.approved_at.desc(), CommercialRelease.created_at.desc())
    )
    if price_source.source_type == "public_list":
        statement = statement.where(
            CommercialRelease.price_catalog_snapshot_id == price_snapshot.id
        )
    release = await db.scalar(statement)
    if release is None:
        detail = (
            f"matching public price snapshot {price_snapshot.id}"
            if price_source.source_type == "public_list"
            else f"approved public commercial terms for {currency}"
        )
        raise ValueError(f"No approved CommercialRelease exists for {detail}")
    return release


async def _governed_sku_contracts(
    *,
    release: CommercialRelease,
    part_numbers: set[str],
    currency: str,
    db: AsyncSession,
) -> dict[str, GovernedSkuCommercialContract]:
    """Load complete approved term, rule, constraint, and evidence contracts."""

    if not part_numbers:
        return {}
    release_scope = set(_as_string_list(release.release_metadata.get("part_numbers")))
    term_ids_payload = release.release_metadata.get("term_ids_by_part")
    rule_ids_payload = release.release_metadata.get("rule_ids_by_part")
    term_ids_by_part = (
        {str(key): str(value) for key, value in term_ids_payload.items()}
        if isinstance(term_ids_payload, dict)
        else {}
    )
    rule_ids_by_part = (
        {str(key): str(value) for key, value in rule_ids_payload.items()}
        if isinstance(rule_ids_payload, dict)
        else {}
    )
    outside_scope = sorted(part_numbers - release_scope) if release_scope else []
    unresolved_exceptions = list(
        (
            await db.scalars(
                select(CommercialException).where(
                    CommercialException.document_snapshot_id == release.document_snapshot_id,
                    CommercialException.part_number.in_(part_numbers),
                    CommercialException.status.notin_(("resolved", "accepted_risk")),
                )
            )
        ).all()
    )
    selected_term_ids = {
        term_ids_by_part[part_number]
        for part_number in part_numbers
        if part_number in term_ids_by_part
    }
    terms = list(
        (
            await db.scalars(
                select(SkuCommercialTerm)
                .where(
                    SkuCommercialTerm.id.in_(selected_term_ids),
                    SkuCommercialTerm.document_snapshot_id == release.document_snapshot_id,
                    SkuCommercialTerm.price_catalog_snapshot_id
                    == release.price_catalog_snapshot_id,
                    SkuCommercialTerm.part_number.in_(part_numbers),
                    SkuCommercialTerm.currency == currency,
                    SkuCommercialTerm.status == "approved",
                )
            )
        ).all()
    ) if selected_term_ids else []
    terms_by_part = {term.part_number: term for term in terms}

    selected_rule_ids = {
        rule_ids_by_part[part_number]
        for part_number in part_numbers
        if part_number in rule_ids_by_part
    }
    rules = list(
        (
            await db.scalars(
                select(CommercialRuleFamily)
                .where(
                    CommercialRuleFamily.id.in_(selected_rule_ids),
                    CommercialRuleFamily.status == "approved",
                    CommercialRuleFamily.fixture_status == "passed",
                )
            )
        ).all()
    ) if selected_rule_ids else []
    rules_by_id = {rule.id: rule for rule in rules}

    term_ids = {term.id for term in terms_by_part.values()}
    constraints = list(
        (
            await db.scalars(
                select(SkuCommercialConstraint).where(
                    SkuCommercialConstraint.term_id.in_(term_ids),
                    SkuCommercialConstraint.status == "approved",
                )
            )
        ).all()
    ) if term_ids else []
    constraints_by_term: dict[str, list[SkuCommercialConstraint]] = defaultdict(list)
    for constraint in constraints:
        constraints_by_term[constraint.term_id].append(constraint)

    rule_ids = set(rules_by_id)
    governed_entity_ids = term_ids | rule_ids
    references = list(
        (
            await db.scalars(
                select(CommercialEvidenceReference).where(
                    CommercialEvidenceReference.entity_id.in_(governed_entity_ids)
                )
            )
        ).all()
    ) if governed_entity_ids else []
    evidence_by_entity: dict[str, list[str]] = defaultdict(list)
    for reference in references:
        evidence_by_entity[reference.entity_id].append(reference.id)

    missing_terms = sorted(part_numbers - set(terms_by_part))
    missing_rules: list[str] = []
    missing_evidence: list[str] = []
    contracts: dict[str, GovernedSkuCommercialContract] = {}
    for part_number, term in terms_by_part.items():
        selected_rule = rules_by_id.get(rule_ids_by_part.get(part_number, ""))
        if selected_rule is None:
            missing_rules.append(part_number)
            continue
        evidence_ids = tuple(
            dict.fromkeys(
                [*evidence_by_entity[term.id], *evidence_by_entity[selected_rule.id]]
            )
        )
        if not evidence_ids:
            missing_evidence.append(part_number)
            continue
        contracts[part_number] = GovernedSkuCommercialContract(
            release=release,
            term=term,
            rule=selected_rule,
            constraints=tuple(constraints_by_term[term.id]),
            evidence_reference_ids=evidence_ids,
        )

    if outside_scope or unresolved_exceptions or missing_terms or missing_rules or missing_evidence:
        details = {
            "outside_release_scope": outside_scope,
            "unresolved_exception_parts": sorted(
                {item.part_number or "catalog" for item in unresolved_exceptions}
            ),
            "missing_approved_terms": missing_terms,
            "missing_approved_rules": sorted(missing_rules),
            "missing_evidence": sorted(missing_evidence),
        }
        raise ValueError(
            "CommercialRelease cannot price the selected SKU scope: "
            + json.dumps(details, sort_keys=True)
        )
    return contracts


def _validate_release_mapping_scope(
    release: CommercialRelease,
    mappings: Iterable[ServiceProductSkuMapping],
) -> None:
    """Require every selected mapping to be pinned by the immutable release."""

    raw_mapping_ids = release.release_metadata.get("mapping_ids_by_part")
    mapping_ids_by_part = (
        {
            str(part_number): {
                str(mapping_id)
                for mapping_id in mapping_ids
                if isinstance(mapping_id, str)
            }
            for part_number, mapping_ids in raw_mapping_ids.items()
            if isinstance(mapping_ids, list)
        }
        if isinstance(raw_mapping_ids, dict)
        else {}
    )
    missing = sorted(
        {
            f"{mapping.part_number or 'unmapped'}:{mapping.id}"
            for mapping in mappings
            if mapping.is_billable
            and (
                not mapping.part_number
                or mapping.id
                not in mapping_ids_by_part.get(str(mapping.part_number), set())
            )
        }
    )
    if missing:
        raise ValueError(
            "CommercialRelease does not pin the selected SKU mappings: "
            + json.dumps(missing)
        )


def _compiled_quantity_rule(
    contract: GovernedSkuCommercialContract,
    mapping: ServiceProductSkuMapping,
) -> QuantityRule:
    """Compile approved normalized constraints over the approved rule family."""

    increment = Decimal(contract.rule.quantity_increment)
    minimum = Decimal(contract.rule.minimum_quantity)
    metric_key = mapping.billing_metric_key.casefold()
    quantity_unit = mapping.quantity_unit.casefold()
    pricing_model = _compiled_pricing_model(contract)
    for constraint in contract.constraints:
        if constraint.numeric_value is None:
            continue
        value = Decimal(constraint.numeric_value)
        if constraint.constraint_type == "purchase_increment":
            scope_matches = (
                constraint.scope == "commercial_quantity"
                or constraint.scope == "backup_storage_quantity"
                and "backup" in metric_key
                or constraint.scope == "database_storage_quantity"
                and "storage" in metric_key
                and "backup" not in metric_key
            )
            unit_matches = (
                not constraint.unit
                or str(constraint.unit).casefold() in quantity_unit
                or quantity_unit in str(constraint.unit).casefold()
            )
            if scope_matches and unit_matches:
                increment = max(increment, value)
        elif constraint.constraint_type == "metric_minimum":
            scope_matches = (
                constraint.scope in {"billed_quantity", "monthly_billed_quantity"}
                and pricing_model not in {PricingModel.HOURLY, PricingModel.HOUR_UTILIZED}
                or constraint.scope == "provisioned_capacity"
                and pricing_model in {PricingModel.HOURLY, PricingModel.HOUR_UTILIZED}
            )
            if scope_matches:
                minimum = max(minimum, value)
    if contract.term.allow_decimal_quantity is False:
        increment = max(increment, Decimal("1"))
    return QuantityRule(
        behavior=QuantityBehavior(contract.rule.quantity_behavior),
        increment=increment,
        minimum=minimum,
    )


def _compiled_pricing_model(
    contract: GovernedSkuCommercialContract,
) -> PricingModel:
    """Translate approved OCI semantics into the existing Decimal engine model."""

    formula_key = contract.rule.formula_key.casefold()
    price_type = (contract.term.price_type or "").strip().upper()
    if formula_key == "hourly_capacity":
        return PricingModel.HOURLY
    if formula_key in {"hour_utilized_capacity", "hourly_utilized_capacity"}:
        return PricingModel.HOUR_UTILIZED
    if price_type in {"MONTH", "MONTHLY"}:
        return PricingModel.MONTHLY
    return PricingModel.PER_ITEM


def _detected_services(
    integrations: Iterable[CatalogIntegration],
    mappings: Iterable[ServiceProductSkuMapping],
    policies: Iterable[ServiceCommercialPolicy] = (),
    tool_overrides: dict[str, tuple[str, str]] | None = None,
) -> tuple[list[str], set[str]]:
    tool_keys: set[str] = set()
    for row in integrations:
        tool_keys.update(_integration_tools_with_overrides(row, tool_overrides))
    normalized_tools = {key.casefold() for key in tool_keys}
    detected_service_ids = {
        policy.service_id
        for policy in policies
        if any(str(alias).casefold() in normalized_tools for alias in policy.tool_aliases)
    }
    detected_service_ids.update(
        mapping.service_id for mapping in mappings if mapping.tool_key.casefold() in normalized_tools
    )
    return sorted(detected_service_ids), tool_keys


def _commercial_coverage(
    service_ids: list[str],
    policies: list[ServiceCommercialPolicy],
    mappings: list[ServiceProductSkuMapping],
) -> list[ScenarioCommercialCoverageResponse]:
    detected = set(service_ids)
    policy_by_service = {policy.service_id: policy for policy in policies}
    result: list[ScenarioCommercialCoverageResponse] = []
    for service_id in service_ids:
        policy = policy_by_service.get(service_id)
        approved = [mapping for mapping in mappings if mapping.service_id == service_id]
        if policy is None:
            result.append(ScenarioCommercialCoverageResponse(
                service_id=service_id, product_name=service_id, classification="unclassified",
                readiness="blocked", publication_policy="policy_required",
                approved_mapping_count=len(approved), required_inputs=["approved commercial policy"],
                dependent_service_ids=[], dependencies_present=[],
                guidance="Commercial policy is missing; BOM publication is blocked.", source_urls=[],
            ))
            continue
        dependencies = [str(item) for item in policy.dependent_service_ids]
        aliases = [str(item) for item in policy.tool_aliases]
        result.append(ScenarioCommercialCoverageResponse(
            service_id=service_id,
            product_name=aliases[0] if aliases else service_id,
            classification=policy.classification,
            readiness=policy.readiness,
            publication_policy=policy.publication_policy,
            approved_mapping_count=len(approved),
            required_inputs=[str(item) for item in policy.required_inputs],
            dependent_service_ids=dependencies,
            dependencies_present=[item for item in dependencies if item in detected],
            guidance=policy.guidance,
            source_urls=[str(item) for item in policy.source_urls],
        ))
    return result


def _default_service_config(service_ids: Iterable[str]) -> dict[str, dict[str, object]]:
    service_config: dict[str, dict[str, object]] = {}
    for service_id in service_ids:
        if service_id == "OIC3":
            service_config[service_id] = {"edition": "standard", "byol": False, "instance_count": 1}
        elif service_id == "DATA_INTEGRATION":
            service_config[service_id] = {"workspace_count": 1, "operator_execution_hours_month": 0}
        elif service_id == "STREAMING":
            service_config[service_id] = {}
        elif service_id == "QUEUE":
            service_config[service_id] = {}
        elif service_id == "GOLDENGATE":
            service_config[service_id] = {"byol": False, "ocpu_count": 1}
        else:
            service_config[service_id] = {}
    return service_config


def _required_questions(service_ids: Iterable[str]) -> list[str]:
    services = set(service_ids)
    questions = [
        "Which environments, active hours, and HA/DR roles should the estimate include?",
        "In which contract month does each product activate, and what real SKU quantity is required in each environment?",
        "Which products remain constant, ramp linearly, or require an explicit monthly step schedule?",
        "Can this estimate consume tenancy-level Free Tier allowances, or are they already allocated elsewhere?",
    ]
    if "OIC3" in services:
        questions.append("Should Oracle Integration use Standard or Enterprise edition, and is BYOL contractually available?")
    if "DATA_INTEGRATION" in services:
        questions.append("How many Data Integration workspaces and operator execution hours are required per month?")
    if "GOLDENGATE" in services:
        questions.append("How many GoldenGate OCPUs are required per environment, and is BYOL available?")
    if "STREAMING" in services:
        questions.append("What Streaming retention period and evidenced PUT/GET transfer quantities should be used?")
    if "QUEUE" in services:
        questions.append("Which Queue operations occur per message (push, get, delete, or update), and what is each payload size?")
    return questions


async def _current_bom_state(
    project_id: str,
    technical_snapshot_id: str,
    db: AsyncSession,
) -> tuple[CurrentBomContextResponse | None, DeploymentScenario | None]:
    """Resolve the most relevant persisted BOM without inventing a new scenario state."""

    snapshots = list(
        (
            await db.scalars(
                select(BomSnapshot)
                .where(BomSnapshot.project_id == project_id)
                .order_by(BomSnapshot.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    if not snapshots:
        return None, None

    selected = next(
        (
            item
            for item in snapshots
            if item.technical_snapshot_id == technical_snapshot_id
            and item.publication_status in {"approved", "published"}
        ),
        None,
    )
    selected = selected or next(
        (item for item in snapshots if item.technical_snapshot_id == technical_snapshot_id),
        None,
    )
    selected = selected or next(
        (item for item in snapshots if item.publication_status in {"approved", "published"}),
        snapshots[0],
    )
    scenario = await db.get(DeploymentScenario, selected.scenario_id)
    if scenario is None:
        return None, None

    environments = await _scenario_environments(scenario.id, db)
    lines = list(
        (
            await db.scalars(
                select(BomLineItem).where(BomLineItem.bom_snapshot_id == selected.id)
            )
        ).all()
    )
    # BOM coverage and publication use `blocked` as the sole unresolved state.
    # Included and non-billable evidence are terminal governed lines, not gaps.
    unresolved_count = sum(1 for line in lines if line.status == "blocked")
    technical_current = selected.technical_snapshot_id == technical_snapshot_id
    ready_for_use = (
        scenario.status == "approved"
        and selected.publication_status in {"approved", "published"}
        and selected.coverage_pct >= 100
        and unresolved_count == 0
        and technical_current
    )
    return (
        CurrentBomContextResponse(
            snapshot_id=selected.id,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            scenario_status=scenario.status,
            publication_status=selected.publication_status,
            technical_snapshot_id=selected.technical_snapshot_id,
            technical_snapshot_current=technical_current,
            coverage_pct=selected.coverage_pct,
            currency=selected.currency,
            monthly_total=selected.monthly_total,
            contract_total=selected.contract_total,
            environment_names=[environment.name for environment in environments],
            line_item_count=len(lines),
            unresolved_line_count=unresolved_count,
            warnings_count=len(selected.warnings or []),
            ready_for_use=ready_for_use,
            created_at=selected.created_at,
        ),
        scenario,
    )


async def _scenario_clone_request(
    scenario: DeploymentScenario,
    db: AsyncSession,
) -> DeploymentScenarioCreateRequest:
    """Return an editable copy of a governed scenario without mutating it."""

    return DeploymentScenarioCreateRequest(
        name=f"{scenario.name} alternative",
        technical_snapshot_id=scenario.technical_snapshot_id,
        currency=scenario.currency,
        region=scenario.region,
        price_mode=scenario.price_mode,
        commitment_model=scenario.commitment_model,
        contract_months=scenario.contract_months,
        start_date=scenario.start_date,
        proration_policy=scenario.proration_policy,
        consumption_model=scenario.consumption_model,
        environments=await _scenario_environments(scenario.id, db),
        service_config=cast(dict[str, dict[str, object]], scenario.service_config),
        assumptions={**scenario.scenario_assumptions, "cloned_from_scenario_id": scenario.id},
    )


def _metric_label(metric_key: str) -> str:
    return metric_key.replace("_", " ").replace(" 10k ", " 10K ").title()


def _metric_options(
    service_ids: list[str],
    mappings: list[ServiceProductSkuMapping],
    technical: dict[str, object],
    integrations: list[CatalogIntegration],
    service_config: dict[str, dict[str, object]],
) -> list[ScenarioMetricOptionResponse]:
    """Resolve governed commercial metrics and their full-demand baseline quantities."""

    environment = {
        "name": "Production",
        "active_hours_month": 744.0,
        "demand_share": 1.0,
        "ha_multiplier": 1.0,
        "dr_role": "primary",
    }
    options: list[ScenarioMetricOptionResponse] = []
    grouped: dict[tuple[str, str], list[ServiceProductSkuMapping]] = defaultdict(list)
    for mapping in mappings:
        if mapping.service_id in service_ids:
            grouped[(mapping.service_id, mapping.billing_metric_key)].append(mapping)
    for key, variants in grouped.items():
        config = service_config.get(key[0], {})
        mapping = next(
            (candidate for candidate in variants if _mapping_selection_policy(candidate) == "required" and _mapping_predicates_match(candidate, config)),
            next((candidate for candidate in variants if _mapping_predicates_match(candidate, config)), variants[0]),
        )
        quantity: float | None
        resolved_unit: str
        if mapping.requires_explicit_quantity:
            quantity, resolved_unit = 0.0, mapping.quantity_unit
        else:
            quantity, resolved_unit, _ = _demand_for_metric(
                mapping.billing_metric_key,
                environment,
                technical,
                integrations,
                config,
            )
        source_quantity = max(quantity or 0.0, 0.0)
        baseline_quantity = float(
            normalize_quantity(
                Decimal(str(source_quantity)),
                QuantityRule(
                    behavior=QuantityBehavior(mapping.quantity_behavior),
                    increment=Decimal(str(mapping.quantity_increment)),
                    minimum=Decimal(str(mapping.minimum_quantity)),
                ),
            )
        )
        options.append(
            ScenarioMetricOptionResponse(
                service_id=mapping.service_id,
                product_name=mapping.tool_key,
                metric_key=mapping.billing_metric_key,
                metric_label=_metric_label(mapping.billing_metric_key),
                quantity_unit=mapping.quantity_unit or resolved_unit,
                source_baseline_quantity=source_quantity,
                baseline_quantity=baseline_quantity,
                planning_envelope_quantity=_planning_envelope(
                    source_quantity,
                    mapping.planning_envelope_increment,
                ),
                quantity_behavior=mapping.quantity_behavior,
                quantity_increment=mapping.quantity_increment,
                minimum_quantity=mapping.minimum_quantity,
                usage_basis=mapping.usage_basis,
                quote_rounding=mapping.quote_rounding,
                aggregation_window=mapping.aggregation_window,
                proration_policy=mapping.proration_policy,
                free_tier_scope=mapping.free_tier_scope,
                planning_envelope_increment=mapping.planning_envelope_increment,
                metering_policy=mapping.metering_policy,
                requires_explicit_quantity=mapping.requires_explicit_quantity,
                entry_guidance=mapping.entry_guidance,
                quantity_presets=_mapping_quantity_presets(mapping),
                default_sku_mapping_id=mapping.id,
                default_selected=any(_mapping_selection_policy(variant) == "required" for variant in variants),
                variants=[
                    ScenarioSkuVariantResponse(
                        sku_mapping_id=variant.id,
                        label=_mapping_variant_label(variant),
                        part_number=variant.part_number,
                        predicates=variant.predicates,
                        is_billable=variant.is_billable,
                        selection_policy=_mapping_selection_policy(variant),
                        quantity_behavior=variant.quantity_behavior,
                        quantity_increment=variant.quantity_increment,
                        minimum_quantity=variant.minimum_quantity,
                        quantity_unit=variant.quantity_unit,
                        usage_basis=variant.usage_basis,
                        quote_rounding=variant.quote_rounding,
                        aggregation_window=variant.aggregation_window,
                        proration_policy=variant.proration_policy,
                        free_tier_scope=variant.free_tier_scope,
                        planning_envelope_increment=variant.planning_envelope_increment,
                        metering_policy=variant.metering_policy,
                        requires_explicit_quantity=variant.requires_explicit_quantity,
                        entry_guidance=variant.entry_guidance,
                        quantity_presets=_mapping_quantity_presets(variant),
                    )
                    for variant in variants
                ],
            )
        )
    return sorted(options, key=lambda item: (item.product_name, item.metric_label))


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
    policies = await _active_commercial_policies(db)
    service_ids, _ = _detected_services(integrations, mappings, policies)
    current_bom, current_scenario = await _current_bom_state(project_id, snapshot.id, db)
    service_config: dict[str, dict[str, object]] = (
        cast(dict[str, dict[str, object]], current_scenario.service_config)
        if current_scenario is not None and current_bom is not None and current_bom.technical_snapshot_current
        else _default_service_config(service_ids)
    )
    metric_options = _metric_options(
        service_ids,
        mappings,
        _commercial_consolidated(snapshot),
        integrations,
        service_config,
    )
    warnings = ["The draft is a deployment proposal, not an Oracle quote."]
    if current_bom is None or not current_bom.ready_for_use:
        warnings.append("Free Tier is disabled until tenancy-level allocation is confirmed.")
    if "GOLDENGATE" in service_ids:
        warnings.append("GoldenGate defaults to one OCPU only as an architect-review starting point.")
    if "DATA_INTEGRATION" in service_ids:
        warnings.append("Data Integration operator execution hours remain zero until supplied.")
    default_draft = DeploymentScenarioCreateRequest(
        name="Governed baseline",
        technical_snapshot_id=snapshot.id,
        currency="USD",
        region="global",
        price_mode="public_list",
        commitment_model="pay_as_you_go",
        contract_months=12,
        start_date=date.today().replace(day=1),
        environments=[
            DeploymentEnvironmentInput(
                name="Production",
                phases=[
                    DeploymentRampPhaseInput(
                        service_id=option.service_id,
                        metric_key=option.metric_key,
                        sku_mapping_id=option.default_sku_mapping_id,
                        start_month=1,
                        end_month=12,
                        interpolation="step",
                        start_quantity=option.baseline_quantity,
                        end_quantity=option.baseline_quantity,
                        quantity_unit=option.quantity_unit,
                        rationale="Governed full-demand baseline in the commercial metric unit.",
                    )
                    for option in metric_options
                    if option.default_selected
                ],
            )
        ],
        consumption_model="explicit_units",
        service_config=service_config,
        assumptions={"free_tier_enabled": False, "drafted_from": snapshot.id},
    )
    draft = (
        await _scenario_clone_request(current_scenario, db)
        if current_scenario is not None and current_bom is not None and current_bom.technical_snapshot_current
        else default_draft
    )
    required_questions = [] if current_bom is not None and current_bom.ready_for_use else _required_questions(service_ids)
    if current_bom is not None and current_bom.ready_for_use:
        warnings = [
            "The published BOM is a governed planning estimate, not an Oracle quote. Regenerate it after architecture, scenario, or approved price evidence changes."
        ]
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
                "current_bom": current_bom.model_dump(mode="json") if current_bom else None,
                "required_questions": required_questions,
                "warnings": warnings,
            },
            safety_subject=safety_subject,
        )
        ai_status = result.status
        ai_summary = result.summary
    return ScenarioAssistantResponse(
        draft=draft,
        detected_services=service_ids,
        metric_options=metric_options,
        commercial_coverage=_commercial_coverage(service_ids, policies, mappings),
        current_bom=current_bom,
        required_questions=required_questions,
        warnings=warnings,
        confidence="high" if current_bom is not None and current_bom.ready_for_use else "medium" if service_ids else "low",
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
    if request.consumption_model == "explicit_units" and not any(
        environment.phases for environment in environments
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "At least one explicit product quantity plan is required",
                "error_code": "SCENARIO_EXPLICIT_QUANTITY_REQUIRED",
            },
        )
    if request.consumption_model == "legacy_share" and abs(demand_share_total - 1.0) > 0.0001:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "Environment demand shares must total exactly 1.0; use HA multiplier for replicated capacity",
                "error_code": "SCENARIO_DEMAND_SHARE_INVALID",
            },
        )
    approved_mappings = await _active_mappings(db)
    mappings_by_id = {mapping.id: mapping for mapping in approved_mappings}
    scenario = DeploymentScenario(
        project_id=project_id,
        name=request.name,
        status="draft",
        currency=request.currency.upper(),
        region=request.region,
        price_mode=request.price_mode,
        commitment_model=request.commitment_model,
        technical_snapshot_id=snapshot.id,
        contract_months=request.contract_months,
        start_date=request.start_date.replace(day=1),
        proration_policy=request.proration_policy,
        consumption_model=request.consumption_model,
        service_config=request.service_config,
        scenario_assumptions=request.assumptions,
        created_by=actor_id,
    )
    db.add(scenario)
    await db.flush()
    environment_payloads: list[dict[str, object]] = []
    for sequence, environment in enumerate(environments, start=1):
        plan = DeploymentEnvironmentPlan(
            scenario_id=scenario.id,
            name=environment.name,
            sequence=sequence,
            active_hours_month=environment.active_hours_month,
            demand_share=environment.demand_share,
            ha_multiplier=environment.ha_multiplier,
            dr_role=environment.dr_role,
        )
        db.add(plan)
        await db.flush()
        phases = environment.phases or ([
            DeploymentRampPhaseInput(
                start_month=1,
                end_month=request.contract_months,
                start_multiplier=1.0,
                end_multiplier=1.0,
                rationale="Default full-capacity schedule.",
            )
        ] if request.consumption_model == "legacy_share" else [])
        for phase in phases:
            selected_mapping: ServiceProductSkuMapping | None = None
            if phase.service_id and phase.metric_key:
                if phase.sku_mapping_id:
                    selected_mapping = mappings_by_id.get(phase.sku_mapping_id)
                    if (
                        selected_mapping is None
                        or selected_mapping.service_id != phase.service_id
                        or selected_mapping.billing_metric_key != phase.metric_key
                    ):
                        raise HTTPException(
                            status_code=422,
                            detail={
                                "detail": "The selected SKU does not govern this product metric",
                                "error_code": "SCENARIO_SKU_MAPPING_INVALID",
                            },
                        )
                else:
                    candidates = [
                        mapping
                        for mapping in approved_mappings
                        if mapping.service_id == phase.service_id
                        and mapping.billing_metric_key == phase.metric_key
                    ]
                    config = request.service_config.get(phase.service_id, {})
                    matches = [
                        mapping for mapping in candidates if _mapping_predicates_match(mapping, config)
                    ]
                    selected_mapping = matches[0] if len(matches) == 1 else None
                    if selected_mapping is None and len(candidates) == 1:
                        selected_mapping = candidates[0]
                    if candidates and selected_mapping is None and request.consumption_model == "explicit_units":
                        raise HTTPException(
                            status_code=422,
                            detail={
                                "detail": "Select an approved commercial variant for every product metric",
                                "error_code": "SCENARIO_SKU_MAPPING_REQUIRED",
                            },
                        )
            phase_row = DeploymentRampPhase(
                environment_plan_id=plan.id,
                service_id=phase.service_id,
                metric_key=phase.metric_key,
                sku_mapping_id=selected_mapping.id if selected_mapping else None,
                start_month=phase.start_month,
                end_month=phase.end_month,
                start_multiplier=phase.start_multiplier,
                end_multiplier=phase.end_multiplier,
                interpolation=phase.interpolation,
                start_quantity=phase.start_quantity,
                end_quantity=phase.end_quantity,
                quantity_unit=phase.quantity_unit,
                rationale=phase.rationale,
            )
            db.add(phase_row)
            await db.flush()
            for monthly_quantity in phase.monthly_quantities:
                db.add(
                    DeploymentRampPeriodQuantity(
                        ramp_phase_id=phase_row.id,
                        period_index=monthly_quantity.period_index,
                        quantity=monthly_quantity.quantity,
                    )
                )
        environment_payloads.append(
            environment.model_copy(update={"phases": phases}).model_dump(mode="json")
        )
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
            "start_date": scenario.start_date.isoformat(),
            "commitment_model": scenario.commitment_model,
            "consumption_model": scenario.consumption_model,
            "environments": environment_payloads,
        },
        project_id=project_id,
        db=db,
    )
    await db.refresh(scenario)
    return await serialize_scenario(scenario, db)


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
    return DeploymentScenarioListResponse(
        scenarios=[await serialize_scenario(row, db) for row in rows],
        total=len(rows),
    )


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
    return await serialize_scenario(scenario, db)


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
    tool_overrides: dict[str, tuple[str, str]] | None = None,
) -> float:
    if "request_operations_per_message" not in config:
        raise ValueError("Queue request operations per message require explicit flow evidence")
    operations = max(_as_float(config.get("request_operations_per_message")), 1.0)
    total = 0.0
    for row in integrations:
        if "OCI Queue" not in _integration_tools_with_overrides(row, tool_overrides):
            continue
        executions = _as_float(row.executions_per_day)
        payload = _as_float(row.payload_per_execution_kb)
        if executions <= 0 or payload <= 0:
            continue
        request_units = max(math.ceil(payload / DEFAULT_QUEUE_BILLING_UNIT_KB), 1)
        total += executions * DEFAULT_MONTH_DAYS * request_units * operations
    return total / 1_000_000.0


def _api_call_millions(
    integrations: Iterable[CatalogIntegration],
    tool_overrides: dict[str, tuple[str, str]] | None = None,
) -> float:
    total = 0.0
    for row in integrations:
        if "OCI API Gateway" not in _integration_tools_with_overrides(row, tool_overrides):
            continue
        total += _as_float(row.executions_per_day) * DEFAULT_MONTH_DAYS
    return total / 1_000_000.0


def _demand_for_metric(
    metric_key: str,
    environment: dict[str, object],
    technical: dict[str, object],
    integrations: list[CatalogIntegration],
    service_config: dict[str, object],
    tool_overrides: dict[str, tuple[str, str]] | None = None,
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
        warnings.append(
            "OIC demand uses the governed technical baseline; confirm trigger/invoke role, same-instance calls, file behavior, and Process Automation activity before approval."
        )
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
        if "transfer_multiplier" not in service_config:
            return None, "GB transferred", ["Streaming PUT/GET transfer requires an explicit operation multiplier."]
        multiplier = _as_float(service_config.get("transfer_multiplier"))
        warnings.append("Streaming transfer includes the approved PUT/GET multiplier.")
        return _as_float(streaming.get("total_gb_month")) * share * multiplier, "GB transferred", warnings
    if metric_key == "streaming_storage_gb_hours":
        if "retention_days" not in service_config:
            return None, "GB-hours", ["Streaming retention days are required to derive storage GB-hours."]
        retention_days = max(_as_float(service_config.get("retention_days")), 0.0)
        daily_gb = _as_float(streaming.get("total_gb_month")) / DEFAULT_MONTH_DAYS
        warnings.append("Streaming storage is inferred from monthly flow and retention days.")
        return daily_gb * retention_days * 24.0 * share, "GB-hours", warnings
    if metric_key == "queue_request_millions":
        if "request_operations_per_message" not in service_config:
            return None, "million requests", ["Queue push/get/delete/update operations per message are required."]
        warnings.append("Queue requests are derived from payload billing units and enqueue/dequeue operations.")
        return (
            _queue_request_millions(integrations, service_config, tool_overrides) * share,
            "million requests",
            warnings,
        )
    if metric_key == "goldengate_ocpu_hours":
        if "ocpu_count" not in service_config:
            return None, "OCPU-hours", ["GoldenGate OCPU count is required."]
        return _as_float(service_config.get("ocpu_count")) * active_hours * ha, "OCPU-hours", warnings
    if metric_key == "api_gateway_call_millions":
        return _api_call_millions(integrations, tool_overrides) * share, "million API calls", warnings
    if metric_key == "process_automation":
        return 0.0, "included", ["Process Automation has no direct SKU line, but its activity must be included in the selected OIC message-pack demand."]
    if metric_key == "events":
        return 0.0, "included", warnings
    return None, "unknown", [f"No demand resolver exists for {metric_key}."]


def _selected_price_tiers(
    items: list[PriceItem],
    commitment_model: str,
    *,
    rate_card_override: bool = False,
) -> tuple[tuple[PriceTier, ...], float, list[PriceItem], list[PriceItem]]:
    expected_model = commitment_model.upper()
    if expected_model not in {
        "PAY_AS_YOU_GO",
        "ANNUAL_COMMITMENT",
        "ANNUAL_FLEX",
        "MONTHLY_FLEX",
    }:
        raise ValueError(f"Unsupported commercial commitment model: {commitment_model}")
    selected_items = [
        item
        for item in items
        if item.model.upper()
        in (
            {"CONTRACT_RATE", "MANUAL_RATE_CARD"}
            if rate_card_override
            else {expected_model}
        )
    ]
    free_tier = 0.0
    paid_items: list[PriceItem] = []
    for item in selected_items:
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
    return tiers, free_tier, paid_items, selected_items


def _tiers_after_shared_free_allowance(
    tiers: tuple[PriceTier, ...],
    free_tier: float,
) -> tuple[PriceTier, ...]:
    """Express source tier boundaries in the post-free, chargeable quantity domain."""

    allowance = Decimal(str(free_tier))
    return tuple(
        PriceTier(
            unit_price=tier.unit_price,
            range_min_exclusive=(
                None
                if index == 0 or tier.range_min_exclusive is None
                else max(tier.range_min_exclusive - allowance, Decimal("0"))
            ),
            range_max_inclusive=(
                max(tier.range_max_inclusive - allowance, Decimal("0"))
                if tier.range_max_inclusive is not None
                else None
            ),
            source_item_id=tier.source_item_id,
        )
        for index, tier in enumerate(tiers)
    )


def _allocate_tenant_month_free_tier(
    *,
    mapping: ServiceProductSkuMapping,
    quantities: tuple[Decimal, ...],
    free_tier: float,
    enabled: bool,
    remaining_by_sku_period: dict[tuple[str, int], Decimal],
) -> tuple[Decimal, ...]:
    """Allocate one SKU allowance pool across ordered environments in each month."""

    if not enabled or mapping.free_tier_scope != "tenant_month" or free_tier <= 0:
        return tuple(Decimal("0") for _ in quantities)
    sku = mapping.part_number or mapping.service_id
    initial = Decimal(str(free_tier))
    allocations: list[Decimal] = []
    for period_index, quantity in enumerate(quantities, start=1):
        key = (sku, period_index)
        remaining = remaining_by_sku_period.setdefault(key, initial)
        allocation = min(max(quantity, Decimal("0")), remaining)
        remaining_by_sku_period[key] = remaining - allocation
        allocations.append(allocation)
    return tuple(allocations)


def _ramp_multipliers(
    environment: dict[str, object],
    service_id: str,
    contract_months: int,
) -> tuple[Decimal, ...]:
    raw_phases = environment.get("phases")
    phase_rows = [item for item in raw_phases if isinstance(item, dict)] if isinstance(raw_phases, list) else []
    service_phases = [item for item in phase_rows if item.get("service_id") == service_id]
    selected = service_phases or [item for item in phase_rows if not item.get("service_id")]
    if not selected:
        selected = [
            {
                "start_month": 1,
                "end_month": contract_months,
                "start_multiplier": 1,
                "end_multiplier": 1,
                "interpolation": "step",
            }
        ]
    phases = tuple(
        RampPhase(
            start_month=_as_int(item.get("start_month")),
            end_month=_as_int(item.get("end_month")),
            start_multiplier=Decimal(str(_as_float(item.get("start_multiplier")))),
            end_multiplier=Decimal(str(_as_float(item.get("end_multiplier")))),
            interpolation=RampInterpolation(str(item.get("interpolation") or "step")),
        )
        for item in selected
    )
    return expand_ramp(phases, contract_months)


def _explicit_quantity_schedule(
    environment: dict[str, object],
    service_id: str,
    metric_key: str,
    contract_months: int,
) -> tuple[Decimal, ...] | None:
    """Expand an explicit service metric plan, including normalized monthly overrides."""

    raw_phases = environment.get("phases")
    phase_rows = [item for item in raw_phases if isinstance(item, dict)] if isinstance(raw_phases, list) else []
    selected = [
        item
        for item in phase_rows
        if item.get("service_id") == service_id and item.get("metric_key") == metric_key
    ]
    if not selected:
        return None
    values = [Decimal("0") for _ in range(contract_months)]
    assigned: set[int] = set()
    regular_phases: list[QuantityRampPhase] = []
    for item in selected:
        interpolation = str(item.get("interpolation") or "step")
        if interpolation == "monthly":
            for monthly in _as_dict_list(item.get("monthly_quantities")):
                period_index = _as_int(monthly.get("period_index"))
                if period_index < 1 or period_index > contract_months or period_index in assigned:
                    raise ValueError(f"Invalid or overlapping monthly quantity at month {period_index}")
                assigned.add(period_index)
                values[period_index - 1] = Decimal(str(_as_float(monthly.get("quantity"))))
            continue
        regular_phases.append(
            QuantityRampPhase(
                start_month=_as_int(item.get("start_month")),
                end_month=_as_int(item.get("end_month")),
                start_quantity=Decimal(str(_as_float(item.get("start_quantity")))),
                end_quantity=Decimal(str(_as_float(item.get("end_quantity")))),
                interpolation=RampInterpolation(interpolation),
            )
        )
    if regular_phases:
        expanded = expand_quantity_ramp(tuple(regular_phases), contract_months)
        for index, quantity in enumerate(expanded, start=1):
            if quantity == 0:
                continue
            if index in assigned:
                raise ValueError(f"Explicit quantity phases overlap at month {index}")
            assigned.add(index)
            values[index - 1] = quantity
    return tuple(values)


def _zero_period_payloads(
    contract_months: int,
    multipliers: tuple[Decimal, ...],
    line: dict[str, object],
    quantities: tuple[Decimal, ...] | None = None,
) -> list[dict[str, object]]:
    return [
        {
            "period_index": index,
            "multiplier": float(multiplier),
            "quantity": float(quantities[index - 1]) if quantities is not None else 0.0,
            "active_hours": 0.0,
            "unit_price": 0.0,
            "amount": 0.0,
            "selected_price_item_id": None,
            "formula": str(line["formula"]),
            "inputs": _as_dict(line.get("inputs")),
            "status": str(line["status"]),
            "warnings": _as_string_list(line.get("warnings")),
            "provenance": _as_dict(line.get("provenance")),
        }
        for index, multiplier in enumerate(multipliers[:contract_months], start=1)
    ]


def _price_mapping_line(
    mapping: ServiceProductSkuMapping,
    items: list[PriceItem],
    quantity: float,
    unit: str,
    environment: dict[str, object],
    scenario: DeploymentScenario,
    demand_warnings: list[str],
    multipliers: tuple[Decimal, ...],
    explicit_quantities: tuple[Decimal, ...] | None = None,
    free_tier_remaining: dict[tuple[str, int], Decimal] | None = None,
    commercial_contract: GovernedSkuCommercialContract | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    effective_quantity = max(
        [Decimal(str(quantity)), *(explicit_quantities or ())],
        default=Decimal("0"),
    )
    if not mapping.is_billable:
        line: dict[str, object] = {
            "environment": str(environment.get("name") or "Unspecified"),
            "service_id": mapping.service_id,
            "part_number": None,
            "description": f"{mapping.tool_key} - included or non-billable",
            "metric_name": mapping.billing_metric_key,
            "quantity": float(effective_quantity),
            "unit": unit,
            "unit_price": 0.0,
            "monthly_amount": 0.0,
            "annual_amount": 0.0,
            "contract_amount": 0.0,
            "price_item_id": None,
            "formula": "non_billable",
            "inputs": {"quantity": float(effective_quantity)},
            "status": "non_billable",
            "warnings": demand_warnings,
            "provenance": _mapping_provenance(mapping),
        }
        return line, _zero_period_payloads(
            scenario.contract_months,
            multipliers,
            line,
            explicit_quantities,
        )
    if not items:
        line = _blocked_line(mapping, environment, float(effective_quantity), unit, [*demand_warnings, "Approved price item not found."])
        return line, _zero_period_payloads(scenario.contract_months, multipliers, line, explicit_quantities)

    tiers, free_tier, paid_items, selected_items = _selected_price_tiers(
        items,
        scenario.commitment_model or "pay_as_you_go",
        rate_card_override=scenario.price_mode in {"contract_rate", "manual_rate_card"},
    )
    if not selected_items:
        line = _blocked_line(
            mapping,
            environment,
            float(effective_quantity),
            unit,
            [
                *demand_warnings,
                "No price tier exists for commercial model "
                f"{scenario.commitment_model or 'pay_as_you_go'}.",
            ],
        )
        return line, _zero_period_payloads(
            scenario.contract_months,
            multipliers,
            line,
            explicit_quantities,
        )
    primary_item = paid_items[0] if paid_items else selected_items[0]
    if not paid_items and effective_quantity > Decimal(str(free_tier)):
        line = _blocked_line(mapping, environment, float(effective_quantity), unit, [*demand_warnings, "No paid price tier covers this demand."])
        return line, _zero_period_payloads(scenario.contract_months, multipliers, line, explicit_quantities)
    use_free_tier = _as_bool(scenario.scenario_assumptions.get("free_tier_enabled"), False)
    if tiers and use_free_tier and free_tier > 0:
        tiers = _tiers_after_shared_free_allowance(tiers, free_tier)
    elif tiers and free_tier > 0:
        tiers = tuple(
            PriceTier(
                unit_price=tier.unit_price,
                range_min_exclusive=None if index == 0 else tier.range_min_exclusive,
                range_max_inclusive=tier.range_max_inclusive,
                source_item_id=tier.source_item_id,
            )
            for index, tier in enumerate(tiers)
        )
    pricing_model = (
        _compiled_pricing_model(commercial_contract)
        if commercial_contract is not None
        else PricingModel.HOURLY if mapping.formula_key == "hourly_capacity" else PricingModel.MONTHLY
    )
    active_hours = (
        Decimal(str(_as_float(environment.get("active_hours_month"), 744.0)))
        if pricing_model in {PricingModel.HOURLY, PricingModel.HOUR_UTILIZED}
        else None
    )
    request = PricingRequest(
        sku=mapping.part_number or mapping.service_id,
        model=pricing_model,
        currency=CurrencyRule(scenario.currency, 2),
        quantity=effective_quantity,
        unit_price=(Decimal(str(primary_item.value)) if not tiers else None),
        billing_unit=Decimal("1"),
        hours=active_hours,
        utilization_ratio=(Decimal("1") if pricing_model is PricingModel.HOUR_UTILIZED else None),
        free_tier_allocation=Decimal("0"),
        tiers=tiers,
        tier_basis_quantity=(effective_quantity if tiers and not use_free_tier else None),
        annual_active_months=12,
        contract_months=scenario.contract_months,
    )
    quantity_rule = (
        _compiled_quantity_rule(commercial_contract, mapping)
        if commercial_contract is not None
        else QuantityRule(
            behavior=QuantityBehavior(mapping.quantity_behavior),
            increment=Decimal(str(mapping.quantity_increment)),
            minimum=Decimal(str(mapping.minimum_quantity)),
        )
    )
    normalized_capacity = normalize_quantity(effective_quantity, quantity_rule)
    normalized_period_quantities = tuple(
        normalize_quantity(current, quantity_rule)
        for current in (
            explicit_quantities
            if explicit_quantities is not None
            else tuple(effective_quantity * multiplier for multiplier in multipliers)
        )
    )
    free_allocations = _allocate_tenant_month_free_tier(
        mapping=mapping,
        quantities=normalized_period_quantities,
        free_tier=free_tier,
        enabled=use_free_tier,
        remaining_by_sku_period=free_tier_remaining if free_tier_remaining is not None else {},
    )
    full_capacity_result = price_line(
        replace(
            request,
            quantity=normalized_capacity,
            free_tier_allocation=(free_allocations[-1] if free_allocations else Decimal("0")),
            tier_basis_quantity=(normalized_capacity if tiers and not use_free_tier else None),
        )
    )
    schedule = (
        price_line_quantity_schedule(
            request,
            explicit_quantities,
            rule=quantity_rule,
            free_tier_allocations=free_allocations,
        )
        if explicit_quantities is not None
        else price_line_schedule(request, multipliers, free_tier_allocations=free_allocations)
    )
    final_result = schedule.periods[-1].result
    selected_item_id = final_result.selected_tier.source_item_id if final_result.selected_tier else primary_item.id
    line = {
        "environment": str(environment.get("name") or "Unspecified"),
        "service_id": mapping.service_id,
        "part_number": mapping.part_number,
        "description": primary_item.display_name,
        "metric_name": primary_item.metric_name,
        "quantity": float(final_result.gross_quantity),
        "unit": unit,
        "unit_price": float(final_result.unit_price),
        "monthly_amount": float(final_result.totals.monthly),
        "annual_amount": float(schedule.annual_totals[0]),
        "contract_amount": float(schedule.contract_total),
        "price_item_id": selected_item_id,
        "commercial_term_id": commercial_contract.term.id if commercial_contract else None,
        "commercial_rule_family_id": commercial_contract.rule.id if commercial_contract else None,
        "evidence_reference_ids": (
            list(commercial_contract.evidence_reference_ids) if commercial_contract else []
        ),
        "formula": final_result.formula,
        "inputs": {
            **final_result.inputs,
            "source_quantity": str(effective_quantity),
            "quoted_quantity": str(final_result.gross_quantity),
            "free_quantity": str(final_result.free_quantity_applied),
        },
        "status": "priced",
        "warnings": demand_warnings,
        "provenance": {
            **_mapping_provenance(mapping),
            "quantity_source": "explicit_units" if explicit_quantities is not None else "legacy_multiplier",
            "quantity_behavior": quantity_rule.behavior.value,
            "quantity_increment": str(quantity_rule.increment),
            "minimum_quantity": str(quantity_rule.minimum),
            "commercial_release_id": commercial_contract.release.id if commercial_contract else None,
            "commercial_release_version": (
                commercial_contract.release.version if commercial_contract else None
            ),
            "public_commercial_price_snapshot_id": (
                commercial_contract.release.price_catalog_snapshot_id
                if commercial_contract else None
            ),
            "applied_price_snapshot_id": primary_item.snapshot_id,
            "contract_price_override": bool(
                commercial_contract
                and primary_item.snapshot_id
                != commercial_contract.release.price_catalog_snapshot_id
            ),
            "commercial_term_id": commercial_contract.term.id if commercial_contract else None,
            "commercial_rule_family_id": commercial_contract.rule.id if commercial_contract else None,
            "commercial_constraints": (
                [
                    {
                        "id": constraint.id,
                        "type": constraint.constraint_type,
                        "scope": constraint.scope,
                        "value": (
                            str(constraint.numeric_value)
                            if constraint.numeric_value is not None
                            else None
                        ),
                        "unit": constraint.unit,
                        "behavior": constraint.behavior,
                    }
                    for constraint in commercial_contract.constraints
                ]
                if commercial_contract
                else []
            ),
            "usage_basis": mapping.usage_basis,
            "quote_rounding": mapping.quote_rounding,
            "aggregation_window": mapping.aggregation_window,
            "proration_policy": mapping.proration_policy,
            "free_tier_scope": mapping.free_tier_scope,
            "planning_envelope_quantity": _planning_envelope(
                float(effective_quantity), mapping.planning_envelope_increment
            ),
        },
        "_full_capacity_monthly": float(full_capacity_result.totals.monthly),
    }
    raw_period_quantities = (
        list(explicit_quantities)
        if explicit_quantities is not None
        else [effective_quantity * Decimal(str(multiplier)) for multiplier in multipliers]
    )
    periods: list[dict[str, object]] = [
        {
            "period_index": period.period_index,
            "multiplier": float(period.multiplier),
            "quantity": float(period.result.gross_quantity),
            "active_hours": _as_float(period.result.inputs.get("hours")),
            "unit_price": float(period.result.unit_price),
            "amount": float(period.result.totals.monthly),
            "selected_price_item_id": (
                period.result.selected_tier.source_item_id
                if period.result.selected_tier
                else primary_item.id
            ),
            "commercial_term_id": commercial_contract.term.id if commercial_contract else None,
            "commercial_rule_family_id": commercial_contract.rule.id if commercial_contract else None,
            "evidence_reference_ids": (
                list(commercial_contract.evidence_reference_ids) if commercial_contract else []
            ),
            "formula": period.result.formula,
            "inputs": {
                **period.result.inputs,
                "source_quantity": str(raw_quantity),
                "quoted_quantity": str(period.result.gross_quantity),
            },
            "status": "priced",
            "warnings": demand_warnings,
            "provenance": {
                **_mapping_provenance(mapping),
                "price_catalog_item_id": (
                    period.result.selected_tier.source_item_id
                    if period.result.selected_tier
                    else primary_item.id
                ),
                "usage_basis": mapping.usage_basis,
                "quote_rounding": mapping.quote_rounding,
                "aggregation_window": mapping.aggregation_window,
                "proration_policy": mapping.proration_policy,
                "free_tier_scope": mapping.free_tier_scope,
                "commercial_release_id": commercial_contract.release.id if commercial_contract else None,
                "commercial_release_version": (
                    commercial_contract.release.version if commercial_contract else None
                ),
                "public_commercial_price_snapshot_id": (
                    commercial_contract.release.price_catalog_snapshot_id
                    if commercial_contract else None
                ),
                "applied_price_snapshot_id": primary_item.snapshot_id,
                "contract_price_override": bool(
                    commercial_contract
                    and primary_item.snapshot_id
                    != commercial_contract.release.price_catalog_snapshot_id
                ),
            },
        }
        for period, raw_quantity in zip(schedule.periods, raw_period_quantities)
    ]
    return line, periods


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
        "provenance": _mapping_provenance(mapping),
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


def _commercial_policy_line(
    policy: ServiceCommercialPolicy,
    environment: dict[str, object],
    *,
    status: str,
    warning: str,
) -> dict[str, object]:
    """Represent included, dependent, or externally licensed product coverage."""

    aliases = [str(item) for item in policy.tool_aliases]
    return {
        "environment": str(environment.get("name") or "Unspecified"),
        "service_id": policy.service_id,
        "part_number": None,
        "description": aliases[0] if aliases else policy.service_id,
        "metric_name": policy.publication_policy,
        "quantity": 0.0,
        "unit": "included" if status == "included" else "decision",
        "unit_price": 0.0,
        "monthly_amount": 0.0,
        "annual_amount": 0.0,
        "contract_amount": 0.0,
        "price_item_id": None,
        "formula": policy.publication_policy,
        "inputs": {"classification": policy.classification},
        "status": status,
        "warnings": [warning],
        "provenance": {"commercial_policy_id": policy.id, "commercial_policy_version": policy.version},
    }


async def calculate_bom(
    *,
    project_id: str,
    scenario: DeploymentScenario,
    technical: dict[str, object],
    db: AsyncSession,
    tool_overrides: dict[str, tuple[str, str]] | None = None,
) -> BomCalculation:
    """Calculate a complete BOM in memory using the same governed pricing path as persistence."""

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
    price_source = await db.get(PriceSource, price_snapshot.source_id)
    if price_source is None:
        raise ValueError("Approved price catalog source not found")
    if price_source is not None and price_source.source_type == "public_list":
        await pricing_governance_service.ensure_public_snapshot_is_current(price_snapshot, db)
    commercial_release = await _resolve_commercial_release(
        price_snapshot=price_snapshot,
        price_source=price_source,
        currency=scenario.currency,
        db=db,
    )

    integrations = await _project_integrations(project_id, db)
    mappings = await _active_mappings(db)
    policies = await _active_commercial_policies(db)
    policy_by_service = {policy.service_id: policy for policy in policies}
    detected_services, _ = _detected_services(integrations, mappings, policies, tool_overrides)
    mappings_by_id = {mapping.id: mapping for mapping in mappings}
    environments = [
        item.model_dump(mode="json")
        for item in await _scenario_environments(scenario.id, db)
    ]
    default_mappings: list[ServiceProductSkuMapping] = []
    unmapped_services: list[str] = []
    for service_id in detected_services:
        config = _config_for(scenario, service_id)
        candidates = [mapping for mapping in mappings if mapping.service_id == service_id]
        matched = [
            mapping for mapping in candidates
            if _mapping_selection_policy(mapping) == "required" and _mapping_predicates_match(mapping, config)
        ]
        if not matched:
            unmapped_services.append(service_id)
        default_mappings.extend(matched)

    explicit_mapping_ids = {
        str(phase.get("sku_mapping_id"))
        for environment in environments
        for phase in _environment_phase_payloads(environment)
        if phase.get("sku_mapping_id")
    }
    selected_mappings = list({
        mapping.id: mapping
        for mapping in [
            *default_mappings,
            *(mappings_by_id[mapping_id] for mapping_id in explicit_mapping_ids if mapping_id in mappings_by_id),
        ]
    }.values())
    _validate_release_mapping_scope(commercial_release, selected_mappings)

    part_numbers = {mapping.part_number for mapping in selected_mappings if mapping.part_number}
    commercial_contracts = await _governed_sku_contracts(
        release=commercial_release,
        part_numbers={str(part_number) for part_number in part_numbers},
        currency=scenario.currency,
        db=db,
    )
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
    period_payloads: list[list[dict[str, object]]] = []
    free_tier_remaining: dict[tuple[str, int], Decimal] = {}
    for environment in environments:
        explicit_phase_mappings = {
            str(phase.get("sku_mapping_id")): (
                str(phase.get("service_id") or ""),
                str(phase.get("metric_key") or ""),
            )
            for phase in _environment_phase_payloads(environment)
            if phase.get("sku_mapping_id")
        }
        explicitly_mapped_services = {key[0] for key in explicit_phase_mappings.values()}
        for service_id in unmapped_services:
            if service_id in explicitly_mapped_services:
                continue
            multipliers = (
                tuple(Decimal("0") for _ in range(scenario.contract_months))
                if scenario.consumption_model == "explicit_units"
                else _ramp_multipliers(environment, service_id, scenario.contract_months)
            )
            policy = policy_by_service.get(service_id)
            if policy is None:
                line = _blocked_service_line(service_id, environment, "No approved commercial policy exists for this detected product.")
            elif policy.publication_policy == "included_zero":
                line = _commercial_policy_line(policy, environment, status="included", warning=policy.guidance)
            elif policy.publication_policy == "dependencies_required":
                present = [str(item) for item in policy.dependent_service_ids if str(item) in detected_services]
                if present:
                    line = _commercial_policy_line(
                        policy,
                        environment,
                        status="included",
                        warning=f"{policy.guidance} Governed dependency present: {', '.join(present)}.",
                    )
                else:
                    line = _commercial_policy_line(policy, environment, status="blocked", warning=policy.guidance)
            elif policy.publication_policy == "explicit_metric_selection":
                line = _commercial_policy_line(
                    policy,
                    environment,
                    status="blocked",
                    warning=f"{policy.guidance} Select at least one applicable commercial metric or remove the product from the architecture.",
                )
            else:
                line = _commercial_policy_line(policy, environment, status="blocked", warning=policy.guidance)
            line_payloads.append(line)
            period_payloads.append(_zero_period_payloads(scenario.contract_months, multipliers, line))
        explicit_keys = set(explicit_phase_mappings.values())
        environment_mappings = [
            mapping
            for mapping in default_mappings
            if (mapping.service_id, mapping.billing_metric_key) not in explicit_keys
        ]
        environment_mappings.extend(
            mappings_by_id[mapping_id]
            for mapping_id in explicit_phase_mappings
            if mapping_id in mappings_by_id
        )
        environment_mappings = list({mapping.id: mapping for mapping in environment_mappings}.values())
        for mapping in environment_mappings:
            config = {
                **_config_for(scenario, mapping.service_id),
                **mapping.predicates,
            }
            quantity, unit, warnings = _demand_for_metric(
                mapping.billing_metric_key,
                environment,
                technical,
                integrations,
                config,
                tool_overrides,
            )
            explicit_quantities = None
            if scenario.consumption_model == "explicit_units":
                explicit_quantities = _explicit_quantity_schedule(
                    environment,
                    mapping.service_id,
                    mapping.billing_metric_key,
                    scenario.contract_months,
                )
                if explicit_quantities is None:
                    explicit_quantities = tuple(Decimal("0") for _ in range(scenario.contract_months))
                    warnings = [
                        *warnings,
                        "No explicit monthly quantity plan exists for this product metric; all months remain at zero.",
                    ]
                peak_quantity = max(explicit_quantities, default=Decimal("0"))
                multipliers = tuple(
                    current / peak_quantity if peak_quantity > 0 else Decimal("0")
                    for current in explicit_quantities
                )
                unit = mapping.quantity_unit
            else:
                multipliers = _ramp_multipliers(environment, mapping.service_id, scenario.contract_months)
            if quantity is None and explicit_quantities is not None:
                quantity = float(max(explicit_quantities, default=Decimal("0")))
                warnings = [
                    *warnings,
                    "Technical demand was unavailable; pricing uses the explicitly approved monthly quantities.",
                ]
            if quantity is None:
                line = _blocked_line(mapping, environment, 0.0, unit, warnings)
                line_payloads.append(line)
                period_payloads.append(
                    _zero_period_payloads(
                        scenario.contract_months,
                        multipliers,
                        line,
                        explicit_quantities,
                    )
                )
                continue
            line, periods = _price_mapping_line(
                mapping,
                prices_by_part.get(mapping.part_number or "", []),
                quantity,
                unit,
                environment,
                scenario,
                warnings,
                multipliers,
                explicit_quantities,
                free_tier_remaining,
                commercial_contracts.get(mapping.part_number or ""),
            )
            line_payloads.append(line)
            period_payloads.append(periods)

    blocked = [line for line in line_payloads if line["status"] == "blocked"]
    covered = len(line_payloads) - len(blocked)
    coverage_pct = round((covered / len(line_payloads) * 100.0), 1) if line_payloads else 0.0
    monthly_series: list[dict[str, object]] = []
    cumulative = 0.0
    for period_index in range(1, scenario.contract_months + 1):
        by_service_period: dict[str, float] = defaultdict(float)
        by_environment_period: dict[str, float] = defaultdict(float)
        for line, periods in zip(line_payloads, period_payloads):
            period = periods[period_index - 1]
            amount = _as_float(period["amount"])
            by_service_period[str(line["service_id"])] += amount
            by_environment_period[str(line["environment"])] += amount
        total = round(sum(by_service_period.values()), 2)
        cumulative = round(cumulative + total, 2)
        monthly_series.append(
            {
                "period_index": period_index,
                "period_start": _add_months(scenario.start_date, period_index - 1).isoformat(),
                "total": total,
                "cumulative_total": cumulative,
                "by_service": {key: round(value, 2) for key, value in sorted(by_service_period.items())},
                "by_environment": {
                    key: round(value, 2) for key, value in sorted(by_environment_period.items())
                },
            }
        )
    monthly_total = _as_float(monthly_series[-1]["total"]) if monthly_series else 0.0
    annual_total = round(sum(_as_float(item["total"]) for item in monthly_series[:12]), 2)
    contract_total = round(sum(_as_float(item["total"]) for item in monthly_series), 2)
    peak_monthly_total = round(max((_as_float(item["total"]) for item in monthly_series), default=0.0), 2)
    full_capacity_contract = round(
        sum(_as_float(line.get("_full_capacity_monthly")) for line in line_payloads)
        * scenario.contract_months,
        2,
    )
    ramp_deferred_amount = round(max(full_capacity_contract - contract_total, 0.0), 2)
    first_active_period = next(
        (_as_int(item["period_index"]) for item in monthly_series if _as_float(item["total"]) > 0),
        None,
    )
    steady_state_period = next(
        (
            _as_int(item["period_index"])
            for index, item in enumerate(monthly_series)
            if _as_float(item["total"]) > 0
            and all(
                abs(_as_float(later["total"]) - monthly_total) < 0.01
                for later in monthly_series[index:]
            )
        ),
        None,
    )
    by_service: dict[str, float] = defaultdict(float)
    by_environment: dict[str, float] = defaultdict(float)
    if monthly_series:
        by_service.update(
            {
                str(key): _as_float(value)
                for key, value in _as_dict(monthly_series[-1]["by_service"]).items()
            }
        )
        by_environment.update(
            {
                str(key): _as_float(value)
                for key, value in _as_dict(monthly_series[-1]["by_environment"]).items()
            }
        )
    return BomCalculation(
        price_snapshot=price_snapshot,
        commercial_release=commercial_release,
        line_payloads=line_payloads,
        period_payloads=period_payloads,
        coverage_pct=coverage_pct,
        monthly_total=monthly_total,
        annual_total=annual_total,
        contract_total=contract_total,
        peak_monthly_total=peak_monthly_total,
        full_capacity_contract=full_capacity_contract,
        ramp_deferred_amount=ramp_deferred_amount,
        first_active_period=first_active_period,
        steady_state_period=steady_state_period,
        monthly_series=monthly_series,
        detected_services=detected_services,
        by_service=dict(by_service),
        by_environment=dict(by_environment),
        warnings=[warning for line in blocked for warning in _as_string_list(line.get("warnings"))],
    )


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
    job.status = "running"
    job.started_at = _now()
    await db.flush()
    calculation = await calculate_bom(
        project_id=job.project_id,
        scenario=scenario,
        technical=_commercial_consolidated(technical),
        db=db,
    )
    line_payloads = calculation.line_payloads
    period_payloads = calculation.period_payloads
    blocked = [line for line in line_payloads if line["status"] == "blocked"]
    covered = len(line_payloads) - len(blocked)
    snapshot = BomSnapshot(
        project_id=job.project_id,
        scenario_id=scenario.id,
        technical_snapshot_id=technical.id,
        price_catalog_snapshot_id=calculation.price_snapshot.id,
        commercial_release_id=calculation.commercial_release.id,
        mapping_version=calculation.commercial_release.mapping_set_hash,
        engine_version=BOM_ENGINE_VERSION,
        currency=scenario.currency,
        coverage_pct=calculation.coverage_pct,
        monthly_total=calculation.monthly_total,
        annual_total=calculation.annual_total,
        contract_total=calculation.contract_total,
        steady_state_monthly_total=calculation.monthly_total,
        peak_monthly_total=calculation.peak_monthly_total,
        ramp_deferred_amount=calculation.ramp_deferred_amount,
        first_active_period=calculation.first_active_period,
        steady_state_period=calculation.steady_state_period,
        summary={
            "line_count": len(line_payloads),
            "priced_line_count": covered,
            "blocked_line_count": len(blocked),
            "detected_services": calculation.detected_services,
            "commercial_release": {
                "id": calculation.commercial_release.id,
                "version": calculation.commercial_release.version,
                "public_price_catalog_snapshot_id": (
                    calculation.commercial_release.price_catalog_snapshot_id
                ),
                "applied_price_catalog_snapshot_id": calculation.price_snapshot.id,
                "mapping_set_hash": calculation.commercial_release.mapping_set_hash,
                "rule_family_set_hash": calculation.commercial_release.rule_family_set_hash,
                "evidence_hash": calculation.commercial_release.evidence_hash,
            },
            "by_service_monthly": {
                key: round(value, 2) for key, value in sorted(calculation.by_service.items())
            },
            "by_environment_monthly": {
                key: round(value, 2) for key, value in sorted(calculation.by_environment.items())
            },
            "monthly_series": calculation.monthly_series,
            "full_capacity_contract": calculation.full_capacity_contract,
            "ramp_insights": {
                "first_active_period": calculation.first_active_period,
                "steady_state_period": calculation.steady_state_period,
                "peak_monthly_total": calculation.peak_monthly_total,
                "ramp_deferred_amount": calculation.ramp_deferred_amount,
                "deferred_spend_notice": "Timing effect versus day-one full capacity; not a negotiated saving.",
            },
            "estimate_notice": "Planning estimate only; not an Oracle quote.",
        },
        warnings=calculation.warnings,
        publication_status="draft",
    )
    db.add(snapshot)
    await db.flush()
    for line_payload, periods in zip(line_payloads, period_payloads):
        persisted_payload = {key: value for key, value in line_payload.items() if not key.startswith("_")}
        persisted_line = BomLineItem(bom_snapshot_id=snapshot.id, **persisted_payload)
        db.add(persisted_line)
        await db.flush()
        db.add_all(
            [
                BomLinePeriod(
                    bom_line_item_id=persisted_line.id,
                    period_start=_add_months(
                        scenario.start_date,
                        _as_int(period["period_index"]) - 1,
                    ),
                    **period,
                )
                for period in periods
            ]
        )
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
            "price_catalog_snapshot_id": calculation.price_snapshot.id,
            "commercial_release_id": calculation.commercial_release.id,
            "commercial_release_version": calculation.commercial_release.version,
            "coverage_pct": calculation.coverage_pct,
            "monthly_total": calculation.monthly_total,
            "first_active_period": calculation.first_active_period,
            "steady_state_period": calculation.steady_state_period,
            "ramp_deferred_amount": calculation.ramp_deferred_amount,
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
    periods = (
        await db.scalars(
            select(BomLinePeriod)
            .where(BomLinePeriod.bom_line_item_id.in_([line.id for line in lines]))
            .order_by(BomLinePeriod.bom_line_item_id, BomLinePeriod.period_index)
        )
    ).all() if lines else []
    periods_by_line: dict[str, list[BomLinePeriod]] = defaultdict(list)
    for period in periods:
        periods_by_line[period.bom_line_item_id].append(period)
    return serialize_bom_snapshot(snapshot, lines, periods_by_line)


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
    baseline_periods = {item.period_index: item.total for item in baseline.monthly_series}
    comparison_periods = {item.period_index: item.total for item in comparison.monthly_series}
    period_deltas = {
        period: round(comparison_periods.get(period, 0.0) - baseline_periods.get(period, 0.0), 2)
        for period in sorted(set(baseline_periods) | set(comparison_periods))
        if round(comparison_periods.get(period, 0.0) - baseline_periods.get(period, 0.0), 2) != 0
    }
    driver_categories = {
        "price": baseline.price_catalog_snapshot_id != comparison.price_catalog_snapshot_id,
        "timing_or_environment": baseline.scenario_id != comparison.scenario_id,
        "technical_demand": baseline.technical_snapshot_id != comparison.technical_snapshot_id,
        "service_mix": bool(service_deltas),
    }
    if period_deltas:
        drivers.append(f"Monthly rollout changed in {len(period_deltas)} contract period(s).")
    return BomComparisonResponse(
        baseline_snapshot_id=baseline.id,
        comparison_snapshot_id=comparison.id,
        currency=baseline.currency,
        monthly_delta=round(comparison.monthly_total - baseline.monthly_total, 2),
        annual_delta=round(comparison.annual_total - baseline.annual_total, 2),
        contract_delta=round(comparison.contract_total - baseline.contract_total, 2),
        service_monthly_deltas=service_deltas,
        environment_monthly_deltas=environment_deltas,
        period_deltas=period_deltas,
        driver_categories=driver_categories,
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
    if snapshot.commercial_release_id is None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Regenerate this BOM with an approved governed commercial release",
                "error_code": "BOM_COMMERCIAL_RELEASE_REQUIRED",
            },
        )
    release = await db.get(CommercialRelease, snapshot.commercial_release_id)
    if (
        release is None
        or release.status != "approved"
        or release.validation_status != "passed"
        or release.open_exception_count != 0
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The commercial release used by this BOM is not publishable",
                "error_code": "BOM_COMMERCIAL_RELEASE_NOT_PUBLISHABLE",
            },
        )
    scoped_lines = list(
        (
            await db.scalars(
                select(BomLineItem).where(
                    BomLineItem.bom_snapshot_id == snapshot.id,
                    BomLineItem.part_number.is_not(None),
                    BomLineItem.status == "priced",
                )
            )
        ).all()
    )
    incomplete_lines = [
        line.part_number
        for line in scoped_lines
        if line.commercial_term_id is None
        or line.commercial_rule_family_id is None
        or not line.evidence_reference_ids
    ]
    scoped_parts = {str(line.part_number) for line in scoped_lines if line.part_number}
    unresolved_exception = await db.scalar(
        select(CommercialException.id).where(
            CommercialException.document_snapshot_id == release.document_snapshot_id,
            CommercialException.part_number.in_(scoped_parts),
            CommercialException.status.notin_(("resolved", "accepted_risk")),
        ).limit(1)
    ) if scoped_parts else None
    if incomplete_lines or unresolved_exception is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Approved commercial terms, rules, evidence, and resolved exceptions are required for every priced SKU",
                "error_code": "BOM_COMMERCIAL_EVIDENCE_INCOMPLETE",
                "part_numbers": sorted({str(item) for item in incomplete_lines}),
            },
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
