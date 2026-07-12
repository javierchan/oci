"""Focused dashboard-service tests for coverage truthfulness and confidence messaging."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from app.models import CatalogIntegration, DashboardSnapshot
from app.services import dashboard_service


def _row(**overrides: object) -> CatalogIntegration:
    defaults: dict[str, object] = {
        "project_id": "project-1",
        "seq_number": 1,
        "qa_status": "OK",
        "qa_reasons": [],
        "interface_id": "INT-001",
        "selected_pattern": "#02",
        "pattern_rationale": "Workbook-aligned rationale",
        "core_tools": "OIC Gen3",
        "payload_per_execution_kb": 128.0,
        "trigger_type": "REST Trigger",
        "source_system": "MFCS",
        "destination_system": "ATP",
        "is_fan_out": False,
        "fan_out_targets": None,
    }
    defaults.update(overrides)
    return CatalogIntegration(**defaults)


def test_build_charts_marks_sparse_payload_coverage_as_low_confidence() -> None:
    rows = [
        _row(interface_id=None, payload_per_execution_kb=None, qa_status="REVISAR"),
        _row(seq_number=2, interface_id=None, payload_per_execution_kb=None, qa_status="REVISAR"),
        _row(seq_number=3, payload_per_execution_kb=64.0),
        _row(seq_number=4, payload_per_execution_kb=None, qa_status="REVISAR"),
    ]

    charts = cast(dict[str, Any], dashboard_service._build_charts(rows, {"#02": "Event Backbone"}))

    assert charts["coverage"]["formal_id"]["complete"] == 2
    assert charts["coverage"]["payload"]["complete"] == 1
    assert charts["coverage"]["trigger"]["complete"] == 4
    assert charts["forecast_confidence"]["level"] == "low"


def test_serialize_snapshot_upgrades_legacy_coverage_shape() -> None:
    snapshot = DashboardSnapshot(
        id="dash-1",
        project_id="project-1",
        volumetry_snapshot_id="vol-1",
        mode="technical",
        kpi_strip={},
        charts={
            "coverage": {
                "total_integrations": 10,
                "with_interface_id": 6,
                "without_interface_id": 4,
                "pattern_assigned": 5,
                "payload_informed": 2,
                "source_destination_informed": 9,
            },
            "completeness": {},
            "pattern_mix": [],
            "payload_distribution": [],
        },
        risks=[],
        maturity={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    response = dashboard_service.serialize_snapshot(snapshot)

    assert response.charts.coverage.formal_id.complete == 6
    assert response.charts.coverage.payload.complete == 2
    assert response.charts.forecast_confidence.level == "low"
    assert response.charts.product_footprint.total_rows == 10
    assert response.charts.product_footprint.products == []


def test_build_charts_represents_every_captured_product_once_per_integration() -> None:
    canvas = (
        '{"v":3,"nodes":['
        '{"instanceId":"oic-1","toolKey":"OIC Gen3"},'
        '{"instanceId":"events-1","toolKey":"OCI Events"},'
        '{"instanceId":"events-2","toolKey":"OCI Events"}'
        '],"edges":[],"coreToolKeys":["OIC Gen3"],'
        '"overlayKeys":["OCI Events","Process Automation"]}'
    )
    rows = [
        _row(
            core_tools="OIC Gen3, Oracle GoldenGate",
            additional_tools_overlays=canvas,
        ),
        _row(
            seq_number=2,
            core_tools="OCI Streaming",
            additional_tools_overlays="OCI API Gateway",
        ),
    ]

    charts = cast(dict[str, Any], dashboard_service._build_charts(rows, {"#02": "Event Backbone"}))
    footprint = charts["product_footprint"]
    products = {item["tool_key"]: item for item in footprint["products"]}

    assert footprint["captured_product_count"] == 6
    assert footprint["represented_product_count"] == 6
    assert footprint["rows_with_products"] == 2
    assert products["OCI Events"]["integration_count"] == 1
    assert products["OCI Events"]["role"] == "overlay"
    assert products["Oracle GoldenGate"]["service_id"] == "GOLDENGATE"
    assert products["Process Automation"]["service_id"] is None
