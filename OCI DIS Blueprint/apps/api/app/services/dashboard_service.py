"""Dashboard snapshot generation and read services."""

from __future__ import annotations

from collections import Counter
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calc_engine import normalize_trigger_type
from app.models import CatalogIntegration, DashboardSnapshot, PatternDefinition, Project, VolumetrySnapshot
from app.schemas.dashboard import (
    CompletenessChart,
    CoverageMetric,
    CoverageChart,
    DashboardCharts,
    DashboardForecastConfidence,
    DashboardKPIStrip,
    DashboardMaturity,
    DashboardRisk,
    DashboardSnapshotListResponse,
    DashboardSnapshotResponse,
    DashboardSnapshotSummary,
    PatternMixEntry,
    PayloadDistributionBucket,
)


def _has_text(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _coverage_metric(complete: int, total: int) -> CoverageMetric:
    ratio = (complete / total) if total else 0.0
    return CoverageMetric(complete=complete, total=total, ratio=ratio)


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def _dict_value(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [cast(dict[str, object], item) for item in value if isinstance(item, dict)]


def _forecast_confidence(payload_metric: CoverageMetric) -> DashboardForecastConfidence:
    ratio = payload_metric.ratio
    if payload_metric.total == 0:
        return DashboardForecastConfidence(
            level="low",
            title="No forecast evidence yet",
            message="Technical forecasts are blocked because the project has no active catalog rows yet.",
            payload_coverage_ratio=0.0,
        )
    if ratio <= 0.25:
        return DashboardForecastConfidence(
            level="low",
            title="Low forecast confidence",
            message=(
                f"Only {payload_metric.complete} of {payload_metric.total} integrations include payload evidence. "
                "Monthly technical totals remain visible, but treat them as directional until payload coverage improves."
            ),
            payload_coverage_ratio=ratio,
        )
    if ratio < 0.6:
        return DashboardForecastConfidence(
            level="medium",
            title="Medium forecast confidence",
            message=(
                f"{payload_metric.complete} of {payload_metric.total} integrations include payload evidence. "
                "The forecast is usable for planning, but still contains material estimation risk."
            ),
            payload_coverage_ratio=ratio,
        )
    return DashboardForecastConfidence(
        level="high",
        title="High forecast confidence",
        message=(
            f"{payload_metric.complete} of {payload_metric.total} integrations include payload evidence. "
            "Technical forecast quality is strong relative to current workbook coverage."
        ),
        payload_coverage_ratio=ratio,
    )


def _to_risk_label(code: str) -> str:
    return code.replace("_", " ").title()


def _payload_bucket(payload_kb: float | None) -> str:
    if payload_kb is None:
        return "Unknown"
    if payload_kb <= 50:
        return "0-50 KB"
    if payload_kb <= 500:
        return "51-500 KB"
    if payload_kb <= 5_000:
        return "501 KB-5 MB"
    return "> 5 MB"


def _serialize_summary(snapshot: DashboardSnapshot) -> DashboardSnapshotSummary:
    return DashboardSnapshotSummary(
        snapshot_id=snapshot.id,
        volumetry_snapshot_id=snapshot.volumetry_snapshot_id,
        mode=snapshot.mode,
        created_at=snapshot.created_at,
    )


def _normalize_coverage_chart(raw_coverage: dict[str, object]) -> CoverageChart:
    total = _int_value(raw_coverage.get("total_integrations", 0))
    if "payload" in raw_coverage:
        return CoverageChart(**cast(dict[str, Any], raw_coverage))
    return CoverageChart(
        total_integrations=total,
        formal_id=_coverage_metric(_int_value(raw_coverage.get("with_interface_id", 0)), total),
        pattern=_coverage_metric(_int_value(raw_coverage.get("pattern_assigned", 0)), total),
        payload=_coverage_metric(_int_value(raw_coverage.get("payload_informed", 0)), total),
        trigger=_coverage_metric(0, total),
        source_destination=_coverage_metric(_int_value(raw_coverage.get("source_destination_informed", 0)), total),
        fan_out=_coverage_metric(0, total),
    )


def _normalize_dashboard_charts(raw_charts: dict[str, object]) -> DashboardCharts:
    coverage = _normalize_coverage_chart(_dict_value(raw_charts.get("coverage", {})))
    completeness = CompletenessChart(**cast(dict[str, Any], _dict_value(raw_charts.get("completeness", {}))))
    pattern_mix = _dict_list(raw_charts.get("pattern_mix", []))
    payload_distribution = _dict_list(raw_charts.get("payload_distribution", []))
    forecast_confidence = raw_charts.get("forecast_confidence")
    normalized_confidence = (
        DashboardForecastConfidence(**cast(dict[str, Any], forecast_confidence))
        if isinstance(forecast_confidence, dict)
        else _forecast_confidence(coverage.payload)
    )
    return DashboardCharts(
        coverage=coverage,
        completeness=completeness,
        pattern_mix=[PatternMixEntry(**cast(dict[str, Any], entry)) for entry in pattern_mix],
        payload_distribution=[PayloadDistributionBucket(**cast(dict[str, Any], entry)) for entry in payload_distribution],
        forecast_confidence=normalized_confidence,
    )


def serialize_snapshot(snapshot: DashboardSnapshot) -> DashboardSnapshotResponse:
    """Convert a dashboard snapshot model into its response schema."""

    return DashboardSnapshotResponse(
        snapshot_id=snapshot.id,
        project_id=snapshot.project_id,
        volumetry_snapshot_id=snapshot.volumetry_snapshot_id,
        mode=snapshot.mode,
        kpi_strip=DashboardKPIStrip(**snapshot.kpi_strip),
        charts=_normalize_dashboard_charts(snapshot.charts),
        risks=[DashboardRisk(**risk) for risk in (snapshot.risks or [])],
        maturity=DashboardMaturity(**(snapshot.maturity or {})),
        created_at=snapshot.created_at,
    )


async def _load_project(project_id: str, db: AsyncSession) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
        )
    return project


async def _load_catalog_rows(project_id: str, db: AsyncSession) -> list[CatalogIntegration]:
    rows = await db.scalars(
        select(CatalogIntegration)
        .where(CatalogIntegration.project_id == project_id)
        .order_by(CatalogIntegration.seq_number, CatalogIntegration.created_at)
    )
    return list(rows.all())


async def _pattern_name_map(db: AsyncSession) -> dict[str, str]:
    pattern_rows = await db.scalars(select(PatternDefinition).where(PatternDefinition.is_active.is_(True)))
    return {pattern.pattern_id: pattern.name for pattern in pattern_rows.all()}


def _build_kpi_strip(volumetry_snapshot: VolumetrySnapshot) -> dict[str, object]:
    consolidated = volumetry_snapshot.consolidated
    oic = consolidated.get("oic", {})
    data_integration = consolidated.get("data_integration", {})
    functions = consolidated.get("functions", {})
    return DashboardKPIStrip(
        oic_msgs_month=float(oic.get("total_billing_msgs_month", 0.0)),
        peak_packs_hour=float(oic.get("peak_packs_hour", 0.0)),
        di_workspace_active=bool(data_integration.get("workspace_active", False)),
        di_data_processed_gb_month=float(data_integration.get("data_processed_gb_month", 0.0)),
        functions_execution_units_gb_s=float(functions.get("total_execution_units_gb_s", 0.0)),
    ).model_dump()


def _build_charts(rows: list[CatalogIntegration], pattern_names: dict[str, str]) -> dict[str, object]:
    total = len(rows)
    formal_id_complete = sum(1 for row in rows if _has_text(row.interface_id))
    pattern_complete = sum(1 for row in rows if _has_text(row.selected_pattern))
    payload_complete = sum(1 for row in rows if row.payload_per_execution_kb is not None)
    trigger_complete = sum(1 for row in rows if normalize_trigger_type(row.trigger_type) is not None)
    source_destination_complete = sum(
        1 for row in rows if _has_text(row.source_system) and _has_text(row.destination_system)
    )
    fan_out_complete = sum(
        1
        for row in rows
        if row.is_fan_out is False or (row.is_fan_out is True and row.fan_out_targets is not None and row.fan_out_targets >= 2)
    )

    coverage = CoverageChart(
        total_integrations=total,
        formal_id=_coverage_metric(formal_id_complete, total),
        pattern=_coverage_metric(pattern_complete, total),
        payload=_coverage_metric(payload_complete, total),
        trigger=_coverage_metric(trigger_complete, total),
        source_destination=_coverage_metric(source_destination_complete, total),
        fan_out=_coverage_metric(fan_out_complete, total),
    )

    completeness = CompletenessChart(
        qa_ok=sum(1 for row in rows if row.qa_status == "OK"),
        qa_revisar=sum(1 for row in rows if row.qa_status == "REVISAR"),
        qa_pending=sum(1 for row in rows if row.qa_status == "PENDING"),
        rationale_informed=sum(1 for row in rows if _has_text(row.pattern_rationale)),
        core_tools_informed=sum(1 for row in rows if _has_text(row.core_tools)),
        comments_informed=sum(1 for row in rows if _has_text(row.comments)),
        retry_policy_informed=sum(1 for row in rows if _has_text(row.retry_policy)),
    )

    pattern_counts: Counter[str] = Counter(
        (row.selected_pattern or "UNASSIGNED") if _has_text(row.selected_pattern) else "UNASSIGNED"
        for row in rows
    )
    pattern_mix = [
        PatternMixEntry(
            pattern_id=pattern_id,
            name=pattern_names.get(pattern_id, "Unassigned" if pattern_id == "UNASSIGNED" else pattern_id),
            count=count,
        )
        for pattern_id, count in sorted(pattern_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    payload_counts: Counter[str] = Counter(_payload_bucket(row.payload_per_execution_kb) for row in rows)
    ordered_buckets = ["0-50 KB", "51-500 KB", "501 KB-5 MB", "> 5 MB", "Unknown"]
    payload_distribution = [
        PayloadDistributionBucket(label=label, count=payload_counts.get(label, 0))
        for label in ordered_buckets
    ]

    charts = DashboardCharts(
        coverage=coverage,
        completeness=completeness,
        pattern_mix=pattern_mix,
        payload_distribution=payload_distribution,
        forecast_confidence=_forecast_confidence(coverage.payload),
    )
    return charts.model_dump()


def _build_risks(rows: list[CatalogIntegration]) -> list[dict[str, object]]:
    risk_index: dict[str, list[str]] = {}

    for row in rows:
        reasons = row.qa_reasons or []
        for reason in reasons:
            risk_index.setdefault(reason, []).append(row.id)
        if not _has_text(row.interface_id):
            risk_index.setdefault("MISSING_INTERFACE_ID", []).append(row.id)
        if row.payload_per_execution_kb is None:
            risk_index.setdefault("MISSING_PAYLOAD", []).append(row.id)
        if not _has_text(row.selected_pattern):
            risk_index.setdefault("MISSING_PATTERN_ASSIGNMENT", []).append(row.id)

    ranked = sorted(risk_index.items(), key=lambda item: (-len(item[1]), item[0]))
    return [
        DashboardRisk(
            code=code,
            label=_to_risk_label(code),
            count=len(integration_ids),
            integration_ids=integration_ids[:50],
        ).model_dump()
        for code, integration_ids in ranked[:8]
    ]


def _build_maturity(rows: list[CatalogIntegration]) -> dict[str, object]:
    total = len(rows)
    if total == 0:
        return DashboardMaturity().model_dump()

    qa_ok = sum(1 for row in rows if row.qa_status == "OK")
    pattern_assigned = sum(1 for row in rows if _has_text(row.selected_pattern))
    payload_informed = sum(1 for row in rows if row.payload_per_execution_kb is not None)
    governed = sum(
        1
        for row in rows
        if _has_text(row.selected_pattern) and _has_text(row.pattern_rationale) and _has_text(row.core_tools)
    )

    return DashboardMaturity(
        qa_ok_pct=qa_ok / total * 100.0,
        pattern_assigned_pct=pattern_assigned / total * 100.0,
        payload_informed_pct=payload_informed / total * 100.0,
        governed_pct=governed / total * 100.0,
    ).model_dump()


async def create_dashboard_snapshot(
    project_id: str,
    volumetry_snapshot: VolumetrySnapshot,
    db: AsyncSession,
) -> DashboardSnapshot:
    """Persist an immutable technical dashboard snapshot for one volumetry snapshot."""

    existing = await db.scalar(
        select(DashboardSnapshot).where(
            DashboardSnapshot.project_id == project_id,
            DashboardSnapshot.volumetry_snapshot_id == volumetry_snapshot.id,
            DashboardSnapshot.mode == "technical",
        )
    )
    if existing is not None:
        return existing

    rows = await _load_catalog_rows(project_id, db)
    pattern_names = await _pattern_name_map(db)

    snapshot = DashboardSnapshot(
        project_id=project_id,
        volumetry_snapshot_id=volumetry_snapshot.id,
        mode="technical",
        kpi_strip=_build_kpi_strip(volumetry_snapshot),
        charts=_build_charts(rows, pattern_names),
        risks=_build_risks(rows),
        maturity=_build_maturity(rows),
    )
    db.add(snapshot)
    await db.flush()
    await db.refresh(snapshot)
    return snapshot


async def _ensure_project_dashboard_snapshots(project_id: str, db: AsyncSession) -> list[DashboardSnapshot]:
    await _load_project(project_id, db)

    volumetry_snapshots = await db.scalars(
        select(VolumetrySnapshot)
        .where(VolumetrySnapshot.project_id == project_id)
        .order_by(VolumetrySnapshot.created_at.desc())
    )
    volume_list = volumetry_snapshots.all()

    dashboard_snapshots = await db.scalars(
        select(DashboardSnapshot)
        .where(DashboardSnapshot.project_id == project_id)
        .order_by(DashboardSnapshot.created_at.desc())
    )
    existing_list = dashboard_snapshots.all()
    existing_by_volumetry = {snapshot.volumetry_snapshot_id for snapshot in existing_list}

    created: list[DashboardSnapshot] = []
    for volumetry_snapshot in volume_list:
        if volumetry_snapshot.id not in existing_by_volumetry:
            created.append(await create_dashboard_snapshot(project_id, volumetry_snapshot, db))

    if created:
        dashboard_snapshots = await db.scalars(
            select(DashboardSnapshot)
            .where(DashboardSnapshot.project_id == project_id)
            .order_by(DashboardSnapshot.created_at.desc())
        )
        return list(dashboard_snapshots.all())

    return list(existing_list)


async def list_snapshots(project_id: str, db: AsyncSession) -> DashboardSnapshotListResponse:
    """List technical dashboard snapshots for a project."""

    snapshots = await _ensure_project_dashboard_snapshots(project_id, db)
    return DashboardSnapshotListResponse(
        snapshots=[_serialize_summary(snapshot) for snapshot in snapshots],
        total=len(snapshots),
    )


async def get_snapshot(project_id: str, snapshot_id: str, db: AsyncSession) -> DashboardSnapshotResponse:
    """Load one dashboard snapshot by dashboard ID or source volumetry snapshot ID."""

    await _ensure_project_dashboard_snapshots(project_id, db)

    snapshot = await db.scalar(
        select(DashboardSnapshot).where(
            DashboardSnapshot.project_id == project_id,
            DashboardSnapshot.id == snapshot_id,
        )
    )
    if snapshot is None:
        snapshot = await db.scalar(
            select(DashboardSnapshot).where(
                DashboardSnapshot.project_id == project_id,
                DashboardSnapshot.volumetry_snapshot_id == snapshot_id,
            )
        )
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Dashboard snapshot not found", "error_code": "DASHBOARD_SNAPSHOT_NOT_FOUND"},
        )
    return serialize_snapshot(snapshot)
