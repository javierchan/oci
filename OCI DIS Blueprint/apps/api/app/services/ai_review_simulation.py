"""Side-effect-free technical and commercial simulation for unsaved canvas drafts."""

from __future__ import annotations

from datetime import date
from typing import cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CatalogIntegration, DeploymentScenario
from app.schemas.ai_review import (
    AiReviewDraftCommercialImpact,
    AiReviewDraftCostPeriod,
    AiReviewDraftMetricDelta,
    AiReviewDraftSimulationRequest,
    AiReviewDraftSimulationResponse,
)
from app.services import bom_service, recalc_service
from app.services.canvas_interoperability import derive_canvas_semantics, parse_canvas_state


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _metric_value(payload: dict[str, object], group: str, key: str) -> float:
    grouped = payload.get(group)
    if not isinstance(grouped, dict):
        return 0.0
    return _as_float(grouped.get(key))


def _warnings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _metric_deltas(
    current: dict[str, object],
    proposed: dict[str, object],
) -> list[AiReviewDraftMetricDelta]:
    definitions = (
        ("oic_messages", "OIC billing messages", "messages / month", "oic", "total_billing_msgs_month"),
        ("di_gb", "Data Integration processed data", "GB / month", "data_integration", "data_processed_gb_month"),
        ("functions_invocations", "Functions invocations", "invocations / month", "functions", "total_invocations_month"),
        ("functions_units", "Functions execution units", "GB-s / month", "functions", "total_execution_units_gb_s"),
        ("streaming_gb", "Streaming throughput", "GB / month", "streaming", "total_gb_month"),
        ("streaming_partitions", "Streaming peak partitions", "partitions", "streaming", "partition_count"),
    )
    result: list[AiReviewDraftMetricDelta] = []
    for metric_key, label, unit, group, value_key in definitions:
        current_value = _metric_value(current, group, value_key)
        proposed_value = _metric_value(proposed, group, value_key)
        if current_value == proposed_value == 0:
            continue
        result.append(
            AiReviewDraftMetricDelta(
                key=metric_key,
                label=label,
                unit=unit,
                current=round(current_value, 4),
                proposed=round(proposed_value, 4),
                delta=round(proposed_value - current_value, 4),
            )
        )
    return result


async def _approved_scenario(
    project_id: str,
    scenario_id: str | None,
    db: AsyncSession,
) -> DeploymentScenario | None:
    query = select(DeploymentScenario).where(
        DeploymentScenario.project_id == project_id,
        DeploymentScenario.status == "approved",
    )
    if scenario_id:
        query = query.where(DeploymentScenario.id == scenario_id)
    scenario = await db.scalar(query.order_by(DeploymentScenario.approved_at.desc().nullslast()))
    if scenario_id and scenario is None:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "Approved deployment scenario not found for this project",
                "error_code": "APPROVED_DEPLOYMENT_SCENARIO_NOT_FOUND",
            },
        )
    return scenario


def _cost_periods(
    current: bom_service.BomCalculation,
    proposed: bom_service.BomCalculation,
) -> list[AiReviewDraftCostPeriod]:
    periods: list[AiReviewDraftCostPeriod] = []
    for current_period, proposed_period in zip(current.monthly_series, proposed.monthly_series):
        current_total = _as_float(current_period.get("total"))
        proposed_total = _as_float(proposed_period.get("total"))
        period_start = current_period.get("period_start")
        periods.append(
            AiReviewDraftCostPeriod(
                period_index=int(_as_float(current_period.get("period_index"))),
                period_start=(
                    date.fromisoformat(period_start)
                    if isinstance(period_start, str)
                    else cast(date, period_start)
                ),
                current=round(current_total, 2),
                proposed=round(proposed_total, 2),
                delta=round(proposed_total - current_total, 2),
            )
        )
    return periods


async def simulate_canvas_draft(
    *,
    project_id: str,
    integration_id: str,
    body: AiReviewDraftSimulationRequest,
    db: AsyncSession,
) -> AiReviewDraftSimulationResponse:
    """Compare saved and unsaved designs without snapshots, jobs, audit writes, or catalog mutation."""

    integration = await db.scalar(
        select(CatalogIntegration).where(
            CatalogIntegration.project_id == project_id,
            CatalogIntegration.id == integration_id,
        )
    )
    if integration is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Integration not found", "error_code": "INTEGRATION_NOT_FOUND"},
        )
    parsed = parse_canvas_state(body.canvas_state, body.core_tools)
    semantics = derive_canvas_semantics(parsed.nodes, parsed.edges, parsed.overlay_keys)
    if not semantics.has_connected_route:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "The draft must contain a directed source-to-destination route",
                "error_code": "CANVAS_ROUTE_INCOMPLETE",
            },
        )

    current = await recalc_service.calculate_project_volumetry(project_id, db)
    proposed = await recalc_service.calculate_project_volumetry(
        project_id,
        db,
        recalc_service.DraftIntegrationOverride(
            integration_id=integration_id,
            core_tools=",".join(body.core_tools),
            additional_tools_overlays=body.canvas_state,
        ),
    )
    current_warnings = _warnings(current.row_results[integration_id]["design_constraint_warnings"])
    proposed_warnings = _warnings(proposed.row_results[integration_id]["design_constraint_warnings"])
    scenario = await _approved_scenario(project_id, body.deployment_scenario_id, db)
    if scenario is None:
        commercial = AiReviewDraftCommercialImpact(
            status="scenario_required",
            warnings=[],
            detail=(
                "Technical impact is calculated. Approve a deployment scenario to compare monthly, contractual, "
                "and ramp timing amounts before saving."
            ),
        )
    else:
        current_bom = await bom_service.calculate_bom(
            project_id=project_id,
            scenario=scenario,
            technical=current.consolidated,
            db=db,
        )
        proposed_bom = await bom_service.calculate_bom(
            project_id=project_id,
            scenario=scenario,
            technical=proposed.consolidated,
            db=db,
            tool_overrides={integration_id: (",".join(body.core_tools), body.canvas_state)},
        )
        warnings = list(dict.fromkeys([*current_bom.warnings, *proposed_bom.warnings]))
        if scenario.consumption_model == "explicit_units":
            warnings.append(
                "The approved real-unit monthly plan remains authoritative. New products need explicit quantities "
                "before their commercial delta can be treated as complete."
            )
        blocked = current_bom.coverage_pct < 100 or proposed_bom.coverage_pct < 100
        commercial = AiReviewDraftCommercialImpact(
            status="blocked" if blocked else "computed",
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            consumption_model=scenario.consumption_model,
            currency=scenario.currency,
            current_monthly=current_bom.monthly_total,
            proposed_monthly=proposed_bom.monthly_total,
            monthly_delta=round(proposed_bom.monthly_total - current_bom.monthly_total, 2),
            current_contract=current_bom.contract_total,
            proposed_contract=proposed_bom.contract_total,
            contract_delta=round(proposed_bom.contract_total - current_bom.contract_total, 2),
            current_ramp_deferred=current_bom.ramp_deferred_amount,
            proposed_ramp_deferred=proposed_bom.ramp_deferred_amount,
            ramp_deferred_delta=round(
                proposed_bom.ramp_deferred_amount - current_bom.ramp_deferred_amount,
                2,
            ),
            periods=_cost_periods(current_bom, proposed_bom),
            warnings=warnings,
            detail=(
                "Pricing coverage is incomplete; resolve blocked SKU mappings or quantities before relying on the delta."
                if blocked
                else "Calculated with the approved scenario, immutable price catalog, governed SKU mappings, and monthly ramp."
            ),
        )

    service_rule_metadata = cast(dict[str, object], proposed.metadata["service_rules"])
    return AiReviewDraftSimulationResponse(
        project_id=project_id,
        integration_id=integration_id,
        assumption_set_version=proposed.assumption_set_version,
        service_rules_version=str(service_rule_metadata.get("version") or "unknown"),
        metrics=_metric_deltas(current.consolidated, proposed.consolidated),
        current_project=recalc_service.serialize_consolidated_calculation(current.consolidated),
        proposed_project=recalc_service.serialize_consolidated_calculation(proposed.consolidated),
        current_warnings=current_warnings,
        proposed_warnings=proposed_warnings,
        commercial_impact=commercial,
    )
