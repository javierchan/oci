"""Direct contracts for read-only governed agent tools."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents import tools as agent_tools
from app.services import commercial_catalog_service, service_product_service


class _ScalarRows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _ReadOnlyDb:
    def __init__(self, *, scalars: list[object], rows: list[list[Any]]) -> None:
        self._scalars = iter(scalars)
        self._rows = iter(rows)

    async def scalar(self, _: object) -> object:
        return next(self._scalars)

    async def scalars(self, _: object) -> _ScalarRows:
        return _ScalarRows(next(self._rows))


@pytest.mark.asyncio
async def test_source_governance_dossier_separates_m51_decisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    change_set = SimpleNamespace(
        id="change-set-1",
        created_at=now - timedelta(hours=2),
        approved_at=now - timedelta(hours=1),
        promoted_at=now - timedelta(minutes=30),
        validation_status="passed",
        approval_status="approved",
        drift_classification="commercial",
        materiality_score=0.25,
        drift_summary={"changed_sources": ["products"]},
        impact_summary={"affected_skus": ["B92072"]},
    )
    document = SimpleNamespace(id="document-1", created_at=now - timedelta(hours=2))
    artifacts = [
        SimpleNamespace(
            id=f"artifact-{kind}",
            source_kind=kind,
            retrieval_status="verified",
            retrieved_at=now - timedelta(minutes=20),
        )
        for kind in ("products", "metrics", "presets")
    ]
    regression_runs = [
        SimpleNamespace(
            id="regression-1",
            family_key="api_gateway",
            status="passed",
            fixture_count=2,
            passed_count=2,
            failed_count=0,
        )
    ]
    rules = [
        SimpleNamespace(
            id="rule-1",
            family_key="api_gateway",
            fixture_status="passed",
            created_at=now,
        )
    ]
    exceptions = [
        SimpleNamespace(
            id="exception-1",
            part_number="B92072",
            exception_code="DOCUMENT_TERM_MISSING",
            severity="high",
            status="open",
        )
    ]
    db = _ReadOnlyDb(
        scalars=[change_set, document],
        rows=[artifacts, regression_runs, rules, exceptions],
    )
    monkeypatch.setattr(
        agent_tools,
        "get_settings",
        lambda: SimpleNamespace(OCI_GOVERNANCE_MAX_SOURCE_AGE_HOURS=72),
    )

    dossier = await agent_tools._source_governance_dossier(db)  # type: ignore[arg-type]

    assert dossier["atomic_source_set"]["status"] == "complete"  # type: ignore[index]
    assert dossier["freshness"]["status"] == "current"  # type: ignore[index]
    assert dossier["documentary_drift"] == {  # type: ignore[index]
        "status": "commercial",
        "change_set_id": "change-set-1",
        "materiality_score": 0.25,
        "review_required": False,
        "summary": {"changed_sources": ["products"]},
        "impact": {"affected_skus": ["B92072"]},
    }
    assert dossier["commercial_fixtures"]["status"] == "passed"  # type: ignore[index]
    assert dossier["commercial_exceptions"]["open_items"] == [  # type: ignore[index]
        {
            "id": "exception-1",
            "part_number": "B92072",
            "code": "DOCUMENT_TERM_MISSING",
            "severity": "high",
        }
    ]


@pytest.mark.asyncio
async def test_global_commercial_release_scope_reports_terminal_m51_coverage() -> None:
    now = datetime.now(UTC)
    document = SimpleNamespace(id="document-1", created_at=now)
    release = SimpleNamespace(
        id="release-1",
        version="commercial-20260719",
        status="approved",
        approved_at=now,
        document_snapshot_id="document-1",
        release_metadata={"scope": "global_oci_catalog"},
    )
    candidates = [
        SimpleNamespace(
            id="candidate-approved",
            part_number="B92072",
            status="approved",
            classification="direct_metered",
        ),
        SimpleNamespace(
            id="candidate-blocked",
            part_number="B88299",
            status="blocked",
            classification="external_rate_card",
        ),
    ]
    db = _ReadOnlyDb(scalars=[document, release], rows=[candidates])

    scope = await agent_tools._global_commercial_release_scope(db)  # type: ignore[arg-type]

    assert scope == {
        "status": "complete",
        "scope": "global_oci_catalog",
        "document_snapshot_id": "document-1",
        "release_id": "release-1",
        "release_version": "commercial-20260719",
        "covers_current_document": True,
        "catalog_count": 2,
        "quote_ready_count": 1,
        "blocked_count": 1,
        "pending_count": 0,
        "terminal_count": 2,
        "terminal_coverage_percent": 100.0,
        "candidate_status_counts": {"approved": 1, "blocked": 1},
        "pending_items": [],
        "admin_finalization": {
            "status": "not_required",
            "action": None,
            "location": None,
            "agent_can_execute": False,
            "reason": "Every commercial candidate has an approved or blocked disposition.",
        },
    }


@pytest.mark.asyncio
async def test_global_commercial_release_scope_directs_pending_to_explicit_admin_action() -> (
    None
):
    now = datetime.now(UTC)
    document = SimpleNamespace(id="document-1", created_at=now)
    release = SimpleNamespace(
        id="release-legacy",
        version="commercial-partial",
        status="approved",
        approved_at=now,
        document_snapshot_id="document-1",
        release_metadata={"scope": "approved_app_mappings"},
    )
    candidates = [
        SimpleNamespace(
            id="candidate-pending",
            part_number="B93496",
            status="pending_review",
            classification="dependent_entitlement",
        )
    ]
    db = _ReadOnlyDb(scalars=[document, release], rows=[candidates])

    scope = await agent_tools._global_commercial_release_scope(db)  # type: ignore[arg-type]

    assert scope["status"] == "review_required"
    assert scope["scope"] == "approved_app_mappings"
    assert scope["catalog_count"] == 1
    assert scope["quote_ready_count"] == 0
    assert scope["blocked_count"] == 0
    assert scope["pending_count"] == 1
    assert scope["admin_finalization"] == {
        "status": "required",
        "action": "explicit_admin_finalization",
        "location": "Admin Pricing > Finalize catalog review",
        "agent_can_execute": False,
        "reason": "1 commercial candidate(s) require an explicit terminal disposition.",
    }
    assert scope["pending_items"] == [
        {
            "candidate_id": "candidate-pending",
            "part_number": "B93496",
            "status": "pending_review",
            "classification": "dependent_entitlement",
        }
    ]


@pytest.mark.asyncio
async def test_global_commercial_release_scope_never_claims_empty_catalog_complete() -> (
    None
):
    now = datetime.now(UTC)
    document = SimpleNamespace(id="document-empty", created_at=now)
    release = SimpleNamespace(
        id="release-empty",
        version="commercial-empty",
        status="approved",
        approved_at=now,
        document_snapshot_id="document-empty",
        release_metadata={"scope": "global_oci_catalog"},
    )
    db = _ReadOnlyDb(scalars=[document, release], rows=[[]])

    scope = await agent_tools._global_commercial_release_scope(db)  # type: ignore[arg-type]

    assert scope["status"] == "unavailable"
    assert scope["catalog_count"] == 0
    assert scope["terminal_coverage_percent"] == 0.0
    assert scope["admin_finalization"] == {
        "status": "unavailable",
        "action": None,
        "location": None,
        "agent_can_execute": False,
        "reason": "No generated commercial catalog is available for explicit disposition.",
    }


@pytest.mark.asyncio
async def test_service_governance_tool_reads_existing_evidence_without_running_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def get_job(job_id: str, _: object) -> SimpleNamespace:
        calls.append(f"get:{job_id}")
        return SimpleNamespace(
            model_dump=lambda **__: {
                "id": job_id,
                "status": "completed",
                "sources_checked": 3,
                "changes_detected": 1,
                "findings": [],
                "recommendations": [],
            }
        )

    async def commercial_evidence(_: object) -> dict[str, object]:
        return {
            "readiness": "review_required",
            "commercial_release_scope": {"status": "partial"},
            "candidate_revalidation": {"status": "required", "count": 2},
        }

    async def governance_dossier(_: object) -> dict[str, object]:
        return {
            "atomic_source_set": {"status": "complete"},
            "freshness": {"status": "current"},
            "documentary_drift": {"status": "commercial"},
            "commercial_fixtures": {"status": "passed"},
            "commercial_exceptions": {"status": "review_required"},
        }

    async def global_release_scope(_: object) -> dict[str, object]:
        return {
            "status": "review_required",
            "scope": "global_oci_catalog",
            "catalog_count": 1182,
            "quote_ready_count": 229,
            "blocked_count": 900,
            "pending_count": 53,
            "admin_finalization": {
                "status": "required",
                "action": "explicit_admin_finalization",
                "agent_can_execute": False,
            },
        }

    monkeypatch.setattr(service_product_service, "get_verification_job", get_job)
    monkeypatch.setattr(
        commercial_catalog_service, "commercial_agent_evidence", commercial_evidence
    )
    monkeypatch.setattr(agent_tools, "_source_governance_dossier", governance_dossier)
    monkeypatch.setattr(
        agent_tools, "_global_commercial_release_scope", global_release_scope
    )

    tool_name, description, _, executor = agent_tools.build_tool_executor(
        agent_type="service_verification",
        project_id=None,
        integration_id=None,
        context={"verification_job_id": "verification-1"},
        actor_id="admin-user",
        db=object(),  # type: ignore[arg-type]
    )
    payload: dict[str, Any] = await executor({})

    assert tool_name == "inspect_official_source_governance"
    assert "without mutation" in description
    assert calls == ["get:verification-1"]
    commercial = payload["commercial_governance"]
    assert isinstance(commercial, dict)
    assert commercial["atomic_source_set"] == {"status": "complete"}
    assert commercial["commercial_release_scope"] == {
        "status": "review_required",
        "scope": "global_oci_catalog",
        "catalog_count": 1182,
        "quote_ready_count": 229,
        "blocked_count": 900,
        "pending_count": 53,
        "admin_finalization": {
            "status": "required",
            "action": "explicit_admin_finalization",
            "agent_can_execute": False,
        },
    }
    assert commercial["candidate_revalidation"] == {"status": "required", "count": 2}
    assert commercial["prohibited_actions"] == [
        "finalize_catalog_review",
        "approve_candidate_or_exception",
        "promote_commercial_release",
        "dispose_exception",
        "change_price_or_mapping",
        "mutate_bom",
    ]
