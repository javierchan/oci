"""Regression tests for approval-gated external workbook mapping."""

from __future__ import annotations

import json
from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import CatalogIntegration, ImportBatch, ImportMappingProfile, Project, SourceIntegrationRow
from app.models.project import ImportStatus, ProjectStatus
from app.schemas.imports import (
    ImportMappingFieldDecision,
    ImportMappingReviewApproveRequest,
    ImportMappingReviewUpdateRequest,
)
from app.services import import_mapping_service, import_service, project_service


def test_external_contract_requires_payload_semantics_and_keeps_aggregate_evidence() -> None:
    """A client sheet cannot silently treat aggregate volume as payload per operation."""

    headers = {"0": "Interfaz", "1": "Tamaño KB", "2": "Volumetría actual", "3": "Complejidad"}
    rows = [{"Interfaz": "Store stock sync", "Tamaño KB": 128, "Volumetría actual": 480000, "Complejidad": "Muy Alto"}]
    contract = import_mapping_service.build_mapping_contract(headers, rows)

    questions = import_mapping_service.contract_items(contract, "questions")
    question_ids = {str(question["id"]) for question in questions}
    assert "payload:1" in question_ids
    assert "aggregate:2" in question_ids
    assert "complexity:muy alto" in question_ids

    approved = import_mapping_service.validate_contract_update(
        contract,
        [
            {"source_header": "Interfaz", "target_field": "interface_name"},
            {"source_header": "Tamaño KB", "target_field": "payload_per_execution_kb"},
            {"source_header": "Volumetría actual", "target_field": "evidence_only"},
            {"source_header": "Complejidad", "target_field": "complexity"},
        ],
        {
            "payload:1": "per_operation",
            "aggregate:2": "evidence_only",
            "complexity:muy alto": "High",
        },
    )

    approved_fields = import_mapping_service.contract_items(approved, "fields")
    mapped = {field["source_header"]: field["target_field"] for field in approved_fields}
    assert mapped["Tamaño KB"] == "payload_per_execution_kb"
    assert mapped["Volumetría actual"] == "evidence_only"
    assert approved["dictionary_aliases"] == {"muy alto": "High"}


@pytest.mark.asyncio
async def test_external_import_cannot_materialize_until_mapping_approval(test_engine: AsyncEngine) -> None:
    """Staged rows stay outside Catalog until a complete user contract is approved."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    headers = {
        "0": "Interfaz",
        "1": "Sistema de Origen",
        "2": "Sistema de Destino",
        "3": "Tamaño KB",
        "4": "Volumetría actual",
        "5": "Complejidad",
    }
    source_values = {
        "Interfaz": "Store stock sync",
        "Sistema de Origen": "Retail Merchandising",
        "Sistema de Destino": "Oracle Integration",
        "Tamaño KB": 128,
        "Volumetría actual": 480000,
        "Complejidad": "Muy Alto",
    }
    contract = import_mapping_service.build_mapping_contract(headers, [source_values])

    async with session_factory() as session:
        project = Project(id="external-intake-project", name="External intake", owner_id="analyst", status="active", description=None, project_metadata=None)
        batch = ImportBatch(
            id="external-intake-batch",
            project_id=project.id,
            filename="client-catalog.xlsx",
            parser_version="3.1.0",
            status=ImportStatus.MAPPING_REVIEW,
            intake_mode="external_mapping",
            source_row_count=1,
            candidate_count=1,
            loaded_count=0,
            header_map={import_service.RAW_HEADERS_METADATA_KEY: json.dumps(headers)},
            mapping_contract=contract,
        )
        source = SourceIntegrationRow(
            id="external-intake-row",
            import_batch_id=batch.id,
            source_row_number=2,
            raw_data=source_values,
            included=True,
            exclusion_reason=None,
            normalization_events=[],
        )
        session.add_all([project, batch, source])
        await session.commit()

        before = await session.scalar(select(CatalogIntegration).where(CatalogIntegration.source_row_id == source.id))
        assert before is None

        draft = await import_service.update_import_mapping_review(
            project.id,
            batch.id,
            ImportMappingReviewUpdateRequest(
                fields=[ImportMappingFieldDecision(source_header="Interfaz", target_field="interface_name")],
                answers={},
            ),
            "analyst",
            session,
        )
        assert draft.status == "mapping_review"
        assert (await session.scalar(select(CatalogIntegration).where(CatalogIntegration.source_row_id == source.id))) is None

        approved = await import_service.approve_import_mapping_review(
            project.id,
            batch.id,
            ImportMappingReviewApproveRequest(
                fields=[
                    ImportMappingFieldDecision(source_header="Interfaz", target_field="interface_name"),
                    ImportMappingFieldDecision(source_header="Sistema de Origen", target_field="source_system"),
                    ImportMappingFieldDecision(source_header="Sistema de Destino", target_field="destination_system"),
                    ImportMappingFieldDecision(source_header="Tamaño KB", target_field="payload_per_execution_kb"),
                    ImportMappingFieldDecision(source_header="Volumetría actual", target_field="evidence_only"),
                    ImportMappingFieldDecision(source_header="Complejidad", target_field="complexity"),
                ],
                answers={
                    "payload:3": "per_operation",
                    "aggregate:4": "evidence_only",
                    "complexity:muy alto": "High",
                },
                save_profile=True,
                profile_name="Retail client header mapping",
            ),
            "analyst",
            session,
        )
        assert approved.status == "pending"
        await import_service.materialize_approved_import(batch.id, session)
        await session.commit()

        integration = await session.scalar(select(CatalogIntegration).where(CatalogIntegration.source_row_id == source.id))
        assert integration is not None
        assert integration.interface_name == "Store stock sync"
        assert integration.source_system == "Retail Merchandising"
        assert integration.payload_per_execution_kb == 128.0
        assert integration.complexity == "High"
        assert source.raw_data["Volumetría actual"] == 480000

        profiles = await import_service.list_import_mapping_profiles(project.id, session)
        assert [profile.name for profile in profiles.profiles] == ["Retail client header mapping"]


@pytest.mark.asyncio
async def test_non_template_workbook_stages_rows_before_catalog_materialization(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A familiar sheet name alone is not enough to bypass the external mapping gate."""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Client Intake"
    sheet.append(["Interfaz", "Sistema de Origen", "Sistema de Destino", "Tamaño KB", "Volumetría actual", "Complejidad"])
    sheet.append(["Store stock sync", "Retail Merchandising", "Oracle Integration", 128, 480000, "Muy Alto"])
    stream = BytesIO()
    workbook.save(stream)
    monkeypatch.setattr(import_service.storage_service, "read_bytes", lambda _: stream.getvalue())

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(id="staged-workbook-project", name="Staged workbook", owner_id="analyst", status="active", description=None, project_metadata=None)
        batch = ImportBatch(
            id="staged-workbook-batch",
            project_id=project.id,
            filename="client-source.xlsx",
            parser_version="3.1.0",
            status=ImportStatus.PENDING,
        )
        session.add_all([project, batch])
        await session.commit()

        parsed = await import_service.process_import(batch.id, "imports/test.xlsx", session)
        await session.commit()

        assert parsed.status == ImportStatus.MAPPING_REVIEW
        assert parsed.intake_mode == "external_mapping"
        assert parsed.loaded_count == 0
        assert parsed.candidate_count == 1
        assert (await session.scalar(select(CatalogIntegration).where(CatalogIntegration.project_id == project.id))) is None
        assert parsed.mapping_contract is not None
        assert parsed.mapping_contract["source_kind"] == "external_workbook"


@pytest.mark.asyncio
async def test_external_formula_workbook_is_staged_as_protected_evidence(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """External formulas reach guided review without execution or catalog writes."""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Catálogo de Integraciones"
    sheet.append(
        [
            "Interfaz",
            "Sistema de Origen",
            "Sistema de Destino",
            "Tamaño KB",
            "Ejecuciones Total OIC",
            "Mensajes por ejecución OIC",
            "Costo Total $ USD Diario",
        ]
    )
    sheet.append(
        [
            "Store stock sync",
            "Retail Merchandising",
            "Oracle Integration",
            50,
            480,
            "=(D2/50)*E2",
            "=F2*0.0001",
        ]
    )
    stream = BytesIO()
    workbook.save(stream)
    monkeypatch.setattr(import_service.storage_service, "read_bytes", lambda _: stream.getvalue())

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(
            id="formula-evidence-project",
            name="Formula evidence",
            owner_id="analyst",
            status="active",
            description=None,
            project_metadata=None,
        )
        batch = ImportBatch(
            id="formula-evidence-batch",
            project_id=project.id,
            filename="client-formulas.xlsx",
            parser_version="3.1.0",
            status=ImportStatus.PENDING,
        )
        session.add_all([project, batch])
        await session.commit()

        parsed = await import_service.process_import(batch.id, "imports/client-formulas.xlsx", session)
        await session.commit()

        assert parsed.status == ImportStatus.MAPPING_REVIEW
        assert parsed.intake_mode == "external_mapping"
        assert parsed.loaded_count == 0
        assert parsed.mapping_contract is not None
        formula_columns = parsed.mapping_contract["formula_columns"]
        assert [item["source_header"] for item in formula_columns] == [
            "Mensajes por ejecución OIC",
            "Costo Total $ USD Diario",
        ]
        assert formula_columns[0]["classification"] == "derived_demand"
        assert formula_columns[1]["classification"] == "commercial_evidence"
        question_ids = {
            question["id"]
            for question in import_mapping_service.contract_items(
                parsed.mapping_contract,
                "questions",
            )
        }
        assert "execution_total:4" in question_ids

        source = await session.scalar(
            select(SourceIntegrationRow).where(SourceIntegrationRow.import_batch_id == batch.id)
        )
        assert source is not None
        assert any(
            event["rule"] == "external_formula_evidence_only"
            and event["old_value"] == "=(D2/50)*E2"
            for event in (source.normalization_events or [])
        )
        assert await session.scalar(
            select(CatalogIntegration).where(CatalogIntegration.project_id == project.id)
        ) is None

        formula_field = next(
            field
            for field in parsed.mapping_contract["fields"]
            if field["source_header"] == "Mensajes por ejecución OIC"
        )
        with pytest.raises(ValueError, match="immutable evidence"):
            import_mapping_service.validate_contract_update(
                parsed.mapping_contract,
                [
                    {
                        "source_header": formula_field["source_header"],
                        "target_field": "payload_per_execution_kb",
                    }
                ],
                {},
                require_complete=False,
            )


@pytest.mark.asyncio
async def test_project_deletion_removes_project_scoped_mapping_profiles(test_engine: AsyncEngine) -> None:
    """A removed project cannot leave reusable external-workbook mappings behind."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(
            id="external-profile-cleanup-project",
            name="External profile cleanup",
            owner_id="analyst",
            status=ProjectStatus.ARCHIVED,
            description=None,
            project_metadata=None,
        )
        profile = ImportMappingProfile(
            id="external-profile-cleanup-profile",
            project_id=project.id,
            name="Temporary mapping",
            header_fingerprint="a" * 64,
            contract={"version": "1.0.0", "fields": []},
            created_by="analyst",
            is_active=True,
        )
        session.add_all([project, profile])
        await session.commit()

        await project_service.delete_project(project.id, "analyst", session)
        await session.commit()

        assert await session.get(ImportMappingProfile, profile.id) is None
