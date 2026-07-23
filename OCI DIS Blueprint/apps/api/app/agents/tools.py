"""Typed deterministic application tools available to governed agents."""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    CommercialDocumentSnapshot,
    CommercialException,
    CommercialMappingCandidate,
    CommercialRelease,
    CommercialRuleFamily,
    GovernanceChangeSet,
    GovernanceSourceArtifact,
    QuotationRegressionRun,
)
from app.schemas.agent import AgentType
from app.schemas.ai_review import AiReviewGraphContext


ToolExecutor = Callable[[dict[str, object]], Awaitable[dict[str, object]]]
ReviewScope = Literal["project", "integration"]

EMPTY_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}
EXPECTED_ATOMIC_SOURCE_KINDS = frozenset({"products", "metrics", "presets"})
TERMINAL_CANDIDATE_STATUSES = frozenset({"approved", "blocked"})


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def _global_commercial_release_scope(db: AsyncSession) -> dict[str, object]:
    """Describe global M51 disposition coverage without performing governance writes."""

    document = await db.scalar(
        select(CommercialDocumentSnapshot).order_by(
            CommercialDocumentSnapshot.created_at.desc()
        )
    )
    release = await db.scalar(
        select(CommercialRelease)
        .where(CommercialRelease.status == "approved")
        .order_by(CommercialRelease.approved_at.desc())
    )
    candidates = (
        list(
            (
                await db.scalars(
                    select(CommercialMappingCandidate)
                    .where(
                        CommercialMappingCandidate.document_snapshot_id == document.id
                    )
                    .order_by(CommercialMappingCandidate.part_number)
                )
            ).all()
        )
        if document is not None
        else []
    )
    status_counts = Counter(candidate.status for candidate in candidates)
    quote_ready_count = status_counts.get("approved", 0)
    blocked_count = status_counts.get("blocked", 0)
    pending_candidates = [
        candidate
        for candidate in candidates
        if candidate.status not in TERMINAL_CANDIDATE_STATUSES
    ]
    pending_count = len(pending_candidates)
    catalog_count = len(candidates)
    terminal_count = catalog_count - pending_count
    metadata = release.release_metadata if release is not None else {}
    release_scope = metadata.get("scope") if isinstance(metadata, dict) else None
    covers_current_document = bool(
        release is not None
        and document is not None
        and release.document_snapshot_id == document.id
    )
    is_global_release = bool(
        release is not None
        and release_scope == "global_oci_catalog"
        and covers_current_document
    )
    if document is None or not candidates:
        coverage_status = "unavailable"
    elif pending_count:
        coverage_status = "review_required"
    elif is_global_release:
        coverage_status = "complete"
    else:
        coverage_status = "release_required"

    if document is None or not candidates:
        finalization = {
            "status": "unavailable",
            "action": None,
            "location": None,
            "agent_can_execute": False,
            "reason": "No generated commercial catalog is available for explicit disposition.",
        }
    elif pending_count:
        finalization = {
            "status": "required",
            "action": "explicit_admin_finalization",
            "location": "Admin Pricing > Finalize catalog review",
            "agent_can_execute": False,
            "reason": (
                f"{pending_count} commercial candidate(s) require an explicit terminal disposition."
            ),
        }
    else:
        finalization = {
            "status": "not_required",
            "action": None,
            "location": None,
            "agent_can_execute": False,
            "reason": "Every commercial candidate has an approved or blocked disposition.",
        }

    return {
        "status": coverage_status,
        "scope": release_scope,
        "document_snapshot_id": document.id if document is not None else None,
        "release_id": release.id if release is not None else None,
        "release_version": release.version if release is not None else None,
        "covers_current_document": covers_current_document,
        "catalog_count": catalog_count,
        "quote_ready_count": quote_ready_count,
        "blocked_count": blocked_count,
        "pending_count": pending_count,
        "terminal_count": terminal_count,
        "terminal_coverage_percent": (
            round((terminal_count / catalog_count) * 100, 2) if catalog_count else 0.0
        ),
        "candidate_status_counts": dict(sorted(status_counts.items())),
        "pending_items": [
            {
                "candidate_id": candidate.id,
                "part_number": candidate.part_number,
                "status": candidate.status,
                "classification": candidate.classification,
            }
            for candidate in pending_candidates[:20]
        ],
        "admin_finalization": finalization,
    }


async def _source_governance_dossier(db: AsyncSession) -> dict[str, object]:
    """Build bounded read-only evidence for M51 source and commercial governance."""

    change_set = await db.scalar(
        select(GovernanceChangeSet).order_by(GovernanceChangeSet.created_at.desc())
    )
    document = await db.scalar(
        select(CommercialDocumentSnapshot).order_by(
            CommercialDocumentSnapshot.created_at.desc()
        )
    )
    if change_set is None:
        return {
            "atomic_source_set": {
                "status": "unavailable",
                "change_set_id": None,
                "expected_source_kinds": sorted(EXPECTED_ATOMIC_SOURCE_KINDS),
                "observed_source_kinds": [],
                "missing_source_kinds": sorted(EXPECTED_ATOMIC_SOURCE_KINDS),
            },
            "freshness": {"status": "unavailable", "reference_at": None},
            "documentary_drift": {"status": "unavailable", "change_set_id": None},
            "commercial_fixtures": {
                "status": "unavailable",
                "quote_fixture_count": 0,
                "commercial_rule_family_count": 0,
            },
            "commercial_exceptions": {
                "status": "unavailable",
                "document_snapshot_id": document.id if document else None,
                "open_count": 0,
                "open_items": [],
            },
        }

    artifacts = list(
        (
            await db.scalars(
                select(GovernanceSourceArtifact)
                .where(GovernanceSourceArtifact.change_set_id == change_set.id)
                .order_by(GovernanceSourceArtifact.source_kind)
            )
        ).all()
    )
    regression_runs = list(
        (
            await db.scalars(
                select(QuotationRegressionRun)
                .where(QuotationRegressionRun.change_set_id == change_set.id)
                .order_by(QuotationRegressionRun.family_key)
            )
        ).all()
    )
    rule_rows = list(
        (
            await db.scalars(
                select(CommercialRuleFamily).order_by(
                    CommercialRuleFamily.created_at.desc(),
                    CommercialRuleFamily.family_key,
                )
            )
        ).all()
    )
    exception_rows = (
        list(
            (
                await db.scalars(
                    select(CommercialException)
                    .where(CommercialException.document_snapshot_id == document.id)
                    .order_by(
                        CommercialException.severity, CommercialException.part_number
                    )
                )
            ).all()
        )
        if document is not None
        else []
    )

    observed_kinds = {artifact.source_kind for artifact in artifacts}
    missing_kinds = EXPECTED_ATOMIC_SOURCE_KINDS - observed_kinds
    unexpected_kinds = observed_kinds - EXPECTED_ATOMIC_SOURCE_KINDS
    unverified_artifacts = [
        artifact.id for artifact in artifacts if artifact.retrieval_status != "verified"
    ]
    atomic_complete = (
        observed_kinds == EXPECTED_ATOMIC_SOURCE_KINDS and not unverified_artifacts
    )

    max_age_hours = get_settings().OCI_GOVERNANCE_MAX_SOURCE_AGE_HOURS
    reference_at = _aware(
        change_set.promoted_at or change_set.approved_at or change_set.created_at
    )
    age_hours = (
        max(0.0, (datetime.now(UTC) - reference_at).total_seconds() / 3600)
        if reference_at is not None
        else None
    )
    accepted = (
        change_set.validation_status == "passed"
        and change_set.approval_status in {"approved", "not_required"}
    )
    freshness_status = (
        "current"
        if atomic_complete
        and accepted
        and age_hours is not None
        and age_hours <= max_age_hours
        else "stale"
        if atomic_complete and accepted and age_hours is not None
        else "unverified"
    )

    latest_rules: dict[str, CommercialRuleFamily] = {}
    for rule in rule_rows:
        latest_rules.setdefault(rule.family_key, rule)
    rule_statuses = Counter(rule.fixture_status for rule in latest_rules.values())
    regression_failed = sum(run.failed_count for run in regression_runs)
    regression_pending = sum(
        run.status not in {"passed", "failed"} for run in regression_runs
    )
    fixture_status = (
        "failed"
        if regression_failed or rule_statuses.get("failed", 0)
        else "pending"
        if regression_pending or rule_statuses.get("pending", 0) or not latest_rules
        else "passed"
    )

    exception_statuses = Counter(item.status for item in exception_rows)
    open_exceptions = [item for item in exception_rows if item.status == "open"]
    open_severities = Counter(item.severity for item in open_exceptions)
    drift_review_required = change_set.drift_classification not in {
        "none",
        "baseline",
    } and change_set.approval_status not in {"approved", "not_required"}
    artifact_retrieval_times = [
        retrieved_at
        for item in artifacts
        if (retrieved_at := _aware(item.retrieved_at)) is not None
    ]

    return {
        "atomic_source_set": {
            "status": "complete" if atomic_complete else "incomplete",
            "change_set_id": change_set.id,
            "expected_source_kinds": sorted(EXPECTED_ATOMIC_SOURCE_KINDS),
            "observed_source_kinds": sorted(observed_kinds),
            "missing_source_kinds": sorted(missing_kinds),
            "unexpected_source_kinds": sorted(unexpected_kinds),
            "unverified_artifact_ids": unverified_artifacts,
            "validation_status": change_set.validation_status,
            "approval_status": change_set.approval_status,
        },
        "freshness": {
            "status": freshness_status,
            "reference_at": reference_at.isoformat() if reference_at else None,
            "age_hours": round(age_hours, 2) if age_hours is not None else None,
            "max_age_hours": max_age_hours,
            "latest_artifact_retrieved_at": max(artifact_retrieval_times).isoformat()
            if artifact_retrieval_times
            else None,
        },
        "documentary_drift": {
            "status": change_set.drift_classification,
            "change_set_id": change_set.id,
            "materiality_score": change_set.materiality_score,
            "review_required": drift_review_required,
            "summary": change_set.drift_summary,
            "impact": change_set.impact_summary,
        },
        "commercial_fixtures": {
            "status": fixture_status,
            "quote_fixture_count": sum(run.fixture_count for run in regression_runs),
            "quote_passed_count": sum(run.passed_count for run in regression_runs),
            "quote_failed_count": regression_failed,
            "quote_run_ids": [run.id for run in regression_runs],
            "commercial_rule_family_count": len(latest_rules),
            "rule_family_status_counts": dict(sorted(rule_statuses.items())),
            "failed_rule_family_ids": [
                rule.id
                for rule in latest_rules.values()
                if rule.fixture_status == "failed"
            ],
            "pending_rule_family_ids": [
                rule.id
                for rule in latest_rules.values()
                if rule.fixture_status == "pending"
            ],
        },
        "commercial_exceptions": {
            "status": "review_required" if open_exceptions else "clear",
            "document_snapshot_id": document.id if document else None,
            "status_counts": dict(sorted(exception_statuses.items())),
            "open_count": len(open_exceptions),
            "open_severity_counts": dict(sorted(open_severities.items())),
            "open_items": [
                {
                    "id": item.id,
                    "part_number": item.part_number,
                    "code": item.exception_code,
                    "severity": item.severity,
                }
                for item in open_exceptions[:20]
            ],
        },
    }


def _graph_context(value: object) -> AiReviewGraphContext | None:
    return (
        AiReviewGraphContext.model_validate(value) if isinstance(value, dict) else None
    )


def build_tool_executor(
    *,
    agent_type: AgentType,
    project_id: str | None,
    integration_id: str | None,
    context: dict[str, object],
    actor_id: str,
    db: AsyncSession,
) -> tuple[str, str, dict[str, object], ToolExecutor]:
    """Build the one allowlisted deterministic tool for an agent definition."""

    async def architecture(_: dict[str, object]) -> dict[str, object]:
        from app.services.ai_review_service import build_review_result

        if project_id is None:
            raise HTTPException(status_code=422, detail="project_id is required")
        scope: ReviewScope = "integration" if integration_id else "project"
        result = await build_review_result(
            project_id=project_id,
            scope=scope,
            integration_id=integration_id,
            include_llm=False,
            graph_context=_graph_context(context.get("graph_context")),
            reviewer_personas=["architect", "security", "operations", "executive"],
            db=db,
        )
        return cast(dict[str, object], result.model_dump(mode="json"))

    async def verification(_: dict[str, object]) -> dict[str, object]:
        from app.services.commercial_catalog_service import commercial_agent_evidence
        from app.services.service_product_service import (
            get_verification_job,
            list_verification_jobs,
        )

        existing_job_id = context.get("verification_job_id")
        if isinstance(existing_job_id, str) and existing_job_id:
            result = await get_verification_job(existing_job_id, db)
            payload = cast(dict[str, object], result.model_dump(mode="json"))
        else:
            recent = await list_verification_jobs(db, limit=1)
            payload = (
                cast(dict[str, object], recent.jobs[0].model_dump(mode="json"))
                if recent.jobs
                else {
                    "status": "not_run",
                    "sources_checked": 0,
                    "changes_detected": 0,
                    "findings": [],
                    "recommendations": [],
                }
            )
        commercial = await commercial_agent_evidence(db)
        commercial.update(await _source_governance_dossier(db))
        commercial["commercial_release_scope"] = await _global_commercial_release_scope(
            db
        )
        commercial["prohibited_actions"] = [
            "finalize_catalog_review",
            "approve_candidate_or_exception",
            "promote_commercial_release",
            "dispose_exception",
            "change_price_or_mapping",
            "mutate_bom",
        ]
        payload["commercial_governance"] = commercial
        return payload

    async def import_quality(_: dict[str, object]) -> dict[str, object]:
        from app.services.external_capture_service import build_agent_evidence
        from app.services.import_service import get_import_quality_assistant

        external_capture_session_id = context.get("external_capture_session_id")
        if (
            project_id is not None
            and isinstance(external_capture_session_id, str)
            and external_capture_session_id
        ):
            return await build_agent_evidence(
                project_id, external_capture_session_id, db
            )
        batch_id = context.get("batch_id")
        if project_id is None or not isinstance(batch_id, str) or not batch_id:
            raise HTTPException(
                status_code=422, detail="project_id and context.batch_id are required"
            )
        result = await get_import_quality_assistant(project_id, batch_id, db)
        return cast(dict[str, object], result.model_dump(mode="json"))

    async def bom(_: dict[str, object]) -> dict[str, object]:
        from app.services.bom_service import build_scenario_assistant
        from app.services.commercial_catalog_service import commercial_agent_evidence

        if project_id is None:
            raise HTTPException(status_code=422, detail="project_id is required")
        result = await build_scenario_assistant(project_id, db, include_llm=False)
        payload = cast(dict[str, object], result.model_dump(mode="json"))
        payload["commercial_governance"] = await commercial_agent_evidence(db)
        return payload

    async def support(_: dict[str, object]) -> dict[str, object]:
        from app.services.support_service import build_support_evidence

        return await build_support_evidence(project_id, integration_id, context, db)

    async def knowledge_maintenance(_: dict[str, object]) -> dict[str, object]:
        from app.services.knowledge_maintenance_service import create_job, execute_job

        job_id = context.get("knowledge_job_id")
        if not isinstance(job_id, str) or not job_id:
            job = await create_job(actor_id, db)
            job_id = job.id
            context["knowledge_job_id"] = job_id
        return await execute_job(job_id, db)

    if agent_type == "architecture_review":
        return (
            "load_architecture_review_evidence",
            "Load governed architecture evidence.",
            EMPTY_PARAMETERS,
            architecture,
        )
    if agent_type == "integration_design":
        if integration_id is None:
            raise HTTPException(
                status_code=422,
                detail="integration_id is required for integration design",
            )
        return (
            "inspect_integration_design",
            "Inspect the saved canvas and governed route evidence.",
            EMPTY_PARAMETERS,
            architecture,
        )
    if agent_type == "topology_investigation":
        if not isinstance(context.get("graph_context"), dict):
            raise HTTPException(
                status_code=422,
                detail="context.graph_context is required for topology investigation",
            )
        return (
            "inspect_topology_context",
            "Inspect a selected topology node or dependency path.",
            EMPTY_PARAMETERS,
            architecture,
        )
    if agent_type == "service_verification":
        return (
            "inspect_official_source_governance",
            "Inspect persisted OCI source atomicity, global release coverage, fixtures, and exceptions without mutation.",
            EMPTY_PARAMETERS,
            verification,
        )
    if agent_type == "import_quality":
        return (
            "inspect_import_quality",
            "Inspect workbook parsing or governed external-capture correction evidence.",
            EMPTY_PARAMETERS,
            import_quality,
        )
    if agent_type == "bom_scenario":
        return (
            "inspect_bom_scenario",
            "Inspect the current published BOM or the governed scenario draft and genuine missing inputs.",
            EMPTY_PARAMETERS,
            bom,
        )
    if agent_type == "knowledge_maintenance":
        return (
            "inspect_app_knowledge_drift",
            "Compare executable App contracts with curated user guidance and persist reviewable candidates.",
            EMPTY_PARAMETERS,
            knowledge_maintenance,
        )
    return (
        "answer_app_support_question",
        "Load bounded App, route, project, integration, and BOM evidence for one support question.",
        EMPTY_PARAMETERS,
        support,
    )
