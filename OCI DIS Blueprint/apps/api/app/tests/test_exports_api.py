"""Integration coverage for export endpoints that do not require a seeded snapshot."""

from __future__ import annotations

from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import CatalogIntegration, DashboardSnapshot, Project, VolumetrySnapshot

pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:datetime.datetime.utcnow\\(\\) is deprecated and scheduled for removal.*:DeprecationWarning:openpyxl.packaging.core"
    ),
    pytest.mark.filterwarnings(
        "ignore:datetime.datetime.utcnow\\(\\) is deprecated and scheduled for removal.*:DeprecationWarning:openpyxl.writer.excel"
    ),
]


@pytest.mark.asyncio
async def test_capture_template_export_returns_valid_workbook(api_client: AsyncClient) -> None:
    """Verify the capture template endpoint returns a readable XLSX workbook."""

    response = await api_client.get("/api/v1/exports/template/xlsx")
    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    workbook = load_workbook(filename=BytesIO(response.content))
    sheet = workbook.active
    assert sheet.title == "Catálogo de Integraciones"
    assert sheet["A1"].value == "#"
    assert sheet["B1"].value == "ID de Interfaz"
    assert sheet["A2"].value == 1
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == "A1:Y2"
    assert "Reference" in workbook.sheetnames


@pytest.mark.asyncio
async def test_project_brief_export_returns_markdown(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Verify the executive brief endpoint creates a governed Markdown artifact."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(
            id="project-brief-1",
            name="Brief Fixture",
            owner_id="architect",
            status="active",
            description=None,
            project_metadata=None,
        )
        integration = CatalogIntegration(
            id="integration-brief-1",
            project_id=project.id,
            seq_number=1,
            interface_name="Order sync",
            interface_id="INT-001",
            source_system="POS",
            destination_system="OMS",
            selected_pattern="#01",
            core_tools="OIC Gen3",
            payload_per_execution_kb=25.0,
            qa_status="OK",
            qa_reasons=[],
        )
        snapshot = VolumetrySnapshot(
            id="snapshot-brief-1",
            project_id=project.id,
            assumption_set_version="1.0.0",
            triggered_by="test",
            row_results={},
            consolidated={
                "oic": {"total_billing_msgs_month": 10, "peak_packs_hour": 1},
                "data_integration": {"workspace_active": False, "data_processed_gb_month": 0},
                "functions": {"total_execution_units_gb_s": 0},
                "streaming": {},
                "queue": {},
            },
            snapshot_metadata={"integration_count": 1},
        )
        dashboard = DashboardSnapshot(
            id="dashboard-brief-1",
            project_id=project.id,
            volumetry_snapshot_id=snapshot.id,
            mode="technical",
            kpi_strip={
                "oic_msgs_month": 10,
                "peak_packs_hour": 1,
                "di_workspace_active": False,
                "di_data_processed_gb_month": 0,
                "functions_execution_units_gb_s": 0,
            },
            charts={
                "coverage": {
                    "total_integrations": 1,
                    "formal_id": {"complete": 1, "total": 1, "ratio": 1.0},
                    "pattern": {"complete": 1, "total": 1, "ratio": 1.0},
                    "payload": {"complete": 1, "total": 1, "ratio": 1.0},
                    "trigger": {"complete": 0, "total": 1, "ratio": 0.0},
                    "source_destination": {"complete": 1, "total": 1, "ratio": 1.0},
                    "fan_out": {"complete": 1, "total": 1, "ratio": 1.0},
                },
                "completeness": {
                    "qa_ok": 1,
                    "qa_revisar": 0,
                    "qa_pending": 0,
                    "rationale_informed": 0,
                    "core_tools_informed": 1,
                    "comments_informed": 0,
                    "retry_policy_informed": 0,
                },
                "pattern_mix": [{"pattern_id": "#01", "name": "Synchronous API", "count": 1}],
                "payload_distribution": [{"label": "0-50 KB", "count": 1}],
                "forecast_confidence": {
                    "level": "high",
                    "title": "High confidence",
                    "message": "Payload coverage is complete.",
                    "payload_coverage_ratio": 1.0,
                },
            },
            risks=[],
            maturity={
                "qa_ok_pct": 100.0,
                "pattern_assigned_pct": 100.0,
                "payload_informed_pct": 100.0,
                "governed_pct": 100.0,
            },
        )
        session.add_all([project, integration, snapshot, dashboard])
        await session.commit()

    response = await api_client.get("/api/v1/exports/project-brief-1/brief")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# OCI DIS Blueprint Executive Brief - Brief Fixture" in response.text
    assert "Catalog integrations: 1" in response.text
