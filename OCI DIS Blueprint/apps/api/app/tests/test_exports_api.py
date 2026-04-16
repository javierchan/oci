"""Integration coverage for export endpoints that do not require a seeded snapshot."""

from __future__ import annotations

from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook

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
