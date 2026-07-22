"""Persistence and human-review boundaries for App knowledge maintenance."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.knowledge.builder import CURATED_PATH
from app.models import AuditEvent, KnowledgeMaintenanceFinding
from app.services import knowledge_maintenance_service


HEADERS = {"X-Actor-Id": "knowledge-admin", "X-Actor-Role": "Admin"}


@pytest.mark.asyncio
async def test_knowledge_job_is_deterministic_and_never_writes_curated_yaml(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """A clean repository creates an auditable zero-drift review without network I/O."""

    before = CURATED_PATH.read_bytes()
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            job = await knowledge_maintenance_service.create_job("knowledge-admin", session)
            payload = await knowledge_maintenance_service.execute_job(job.id, session)

    assert payload["status"] == "completed"
    assert payload["finding_count"] == 0
    assert payload["write_policy"] == "human_review_only_no_yaml_mutation"
    assert CURATED_PATH.read_bytes() == before

    response = await api_client.get("/api/v1/agents/knowledge-maintenance/jobs", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()[0]["source_hash"] == payload["source_hash"]


@pytest.mark.asyncio
async def test_knowledge_candidate_requires_explicit_human_disposition(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Candidate acceptance is persisted and audited but cannot edit YAML."""

    before = CURATED_PATH.read_bytes()
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            job = await knowledge_maintenance_service.create_job("knowledge-admin", session)
            finding = KnowledgeMaintenanceFinding(
                job_id=job.id,
                section_id="projects",
                finding_type="uncovered_route",
                severity="high",
                title="App knowledge drift in projects",
                summary="Next route has no curated knowledge owner: /new-surface",
                current_value={},
                candidate_value={"operation": "add_route", "route": "/new-surface"},
                rationale="The executable route needs human-authored guidance.",
            )
            session.add(finding)
            await session.flush()
            finding_id = finding.id

    response = await api_client.post(
        f"/api/v1/agents/knowledge-maintenance/findings/{finding_id}/review",
        headers=HEADERS,
        json={"decision": "accept", "rationale": "Confirmed for the next documentation revision."},
    )

    assert response.status_code == 200
    assert response.json()["review_status"] == "accepted"
    assert CURATED_PATH.read_bytes() == before
    async with session_factory() as session:
        event = await session.scalar(
            select(AuditEvent).where(AuditEvent.entity_id == finding_id)
        )
        assert event is not None
        assert event.event_type == "app_knowledge_candidate_reviewed"


@pytest.mark.asyncio
async def test_semantic_candidates_require_valid_derived_evidence_and_never_write_yaml(
    test_engine: AsyncEngine,
) -> None:
    """Model drafts are persisted only when every claimed reference is executable evidence."""

    before = CURATED_PATH.read_bytes()
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            job = await knowledge_maintenance_service.create_job("knowledge-admin", session)
            await knowledge_maintenance_service.execute_job(job.id, session)
            summary = await knowledge_maintenance_service.persist_semantic_candidates(
                job.id,
                """{
                  "summary": "One supported wording improvement needs human review.",
                  "candidates": [
                    {
                      "section_id": "projects",
                      "finding_type": "missing_guidance",
                      "severity": "medium",
                      "field": "steps",
                      "title": "Clarify project creation",
                      "summary": "The guidance can name the executable creation contract.",
                      "draft": ["Create a project, then open its dashboard."],
                      "rationale": "The project creation endpoint is part of the derived contract.",
                      "evidence_refs": ["endpoint:POST /api/v1/projects/"]
                    },
                    {
                      "section_id": "projects",
                      "finding_type": "semantic_drift",
                      "severity": "high",
                      "field": "purpose",
                      "title": "Invent deployment",
                      "summary": "This unsupported draft must be rejected.",
                      "draft": "Deploy clusters from Projects.",
                      "rationale": "Unsupported reference.",
                      "evidence_refs": ["endpoint:POST /api/v1/deploy-mars"]
                    }
                  ]
                }""",
                session,
            )
            findings = list(
                (
                    await session.scalars(
                        select(KnowledgeMaintenanceFinding).where(
                            KnowledgeMaintenanceFinding.job_id == job.id
                        )
                    )
                ).all()
            )
            await session.refresh(job)

    assert summary == "One supported wording improvement needs human review."
    assert len(findings) == 1
    assert findings[0].candidate_value["evidence_refs"] == ["endpoint:POST /api/v1/projects/"]
    assert job.finding_count == 1
    assert CURATED_PATH.read_bytes() == before


@pytest.mark.asyncio
async def test_invalid_semantic_provider_payload_is_ignored_without_network_or_mutation(
    test_engine: AsyncEngine,
) -> None:
    """Malformed model output cannot create candidates or break deterministic maintenance."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            job = await knowledge_maintenance_service.create_job("knowledge-admin", session)
            await knowledge_maintenance_service.execute_job(job.id, session)
            result = await knowledge_maintenance_service.persist_semantic_candidates(
                job.id,
                "This is not the required JSON contract.",
                session,
            )

    assert result is None
