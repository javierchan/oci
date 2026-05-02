"""API coverage for deterministic justification narratives."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import CatalogIntegration, JustificationRecord, Project


async def _seed_justification_fixture(test_engine: AsyncEngine) -> tuple[str, str]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(
            id="project-justification-1",
            name="Justification Fixture",
            owner_id="architect",
            status="active",
            description=None,
            project_metadata=None,
        )
        integration = CatalogIntegration(
            id="integration-justification-1",
            project_id=project.id,
            seq_number=1,
            interface_name="Order sync",
            interface_id="INT-001",
            brand="Retail",
            business_process="Order Management",
            source_system="POS",
            destination_system="OMS",
            frequency="Hourly",
            payload_per_execution_kb=25.0,
            selected_pattern="#01",
            pattern_rationale="Low-latency operational lookup.",
            type="REST",
            trigger_type="REST Trigger",
            core_tools="OIC Gen3",
            retry_policy="Retry three times.",
            qa_status="OK",
            qa_reasons=[],
        )
        session.add_all([project, integration])
        await session.commit()
        return project.id, integration.id


@pytest.mark.asyncio
async def test_get_justification_returns_english_deterministic_narrative(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Verify the public route calls the service and does not leak Spanish fallback text."""

    project_id, integration_id = await _seed_justification_fixture(test_engine)

    response = await api_client.get(f"/api/v1/justifications/{project_id}/{integration_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "draft"
    assert payload["narrative"]["summary"].startswith("The integration Order sync connects POS to OMS")
    assert [block["title"] for block in payload["narrative"]["methodology_blocks"][:4]] == [
        "Context",
        "Pattern",
        "Implementation",
        "QA Governance",
    ]
    assert "La integracion" not in response.text
    assert "pendiente" not in response.text


@pytest.mark.asyncio
async def test_approve_justification_persists_record(api_client: AsyncClient, test_engine: AsyncEngine) -> None:
    """Verify approval is wired to the service layer and persisted."""

    project_id, integration_id = await _seed_justification_fixture(test_engine)

    response = await api_client.post(
        f"/api/v1/justifications/{project_id}/{integration_id}/approve",
        headers={"X-Actor-Id": "architect-user"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "approved"
    assert payload["approved_by"] == "architect-user"

    get_response = await api_client.get(f"/api/v1/justifications/{project_id}/{integration_id}")
    assert get_response.status_code == 200
    assert get_response.json()["state"] == "approved"


@pytest.mark.asyncio
async def test_legacy_spanish_justification_record_is_regenerated_on_read(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Verify legacy persisted narratives do not leak Spanish text back to users."""

    project_id, integration_id = await _seed_justification_fixture(test_engine)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        legacy_record = JustificationRecord(
            id="legacy-justification-1",
            project_id=project_id,
            integration_id=integration_id,
            state="approved",
            deterministic_text={
                "summary": "La integracion Order sync conecta POS con OMS y actualmente mantiene estado QA OK.",
                "methodology_blocks": [{"title": "Contexto", "body": "Texto heredado."}],
                "evidence": [],
                "qa_status": "OK",
                "qa_reasons": [],
                "override_text": None,
            },
            narrative_text="legacy",
            approved_by="architect-user",
            override_notes=None,
        )
        session.add(legacy_record)
        await session.commit()

    response = await api_client.get(f"/api/v1/justifications/{project_id}/{integration_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "approved"
    assert payload["approved_by"] == "architect-user"
    assert payload["narrative"]["summary"].startswith("The integration Order sync connects POS to OMS")
    assert "La integracion" not in response.text
    assert "Contexto" not in response.text
