"""Integration coverage for export endpoints that do not require a seeded snapshot."""

from __future__ import annotations

from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook


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
    assert sheet["A1"].value == "OCI DIS Blueprint — Integration Capture Template"
    assert sheet["A5"].value == "#"
    assert sheet["B5"].value == "ID de Interfaz"
