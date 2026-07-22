"""Governed App knowledge drift detection and human review workflow."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.builder import (
    load_curated_knowledge,
    load_derived_manifest,
    validate_knowledge_base,
)
from app.models import KnowledgeMaintenanceFinding, KnowledgeMaintenanceJob
from app.schemas.agent import (
    KnowledgeMaintenanceFindingResponse,
    KnowledgeMaintenanceJobResponse,
    KnowledgeMaintenanceReviewRequest,
)
from app.services import audit_service
from app.services.serializers import sanitize_for_json


SEMANTIC_FIELDS = frozenset(
    {"purpose", "when_to_use", "steps", "supported_actions", "unsupported_claims", "keywords"}
)
SEMANTIC_FINDING_TYPES = frozenset({"semantic_drift", "missing_guidance", "stale_guidance"})
SEMANTIC_SEVERITIES = frozenset({"low", "medium", "high"})
MAX_SEMANTIC_CANDIDATES = 20


def _sections(curated: dict[str, object]) -> list[dict[str, object]]:
    sections = curated.get("sections")
    return [dict(item) for item in sections if isinstance(item, dict)] if isinstance(sections, list) else []


def _records(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _owner_for_route(route: str, sections: list[dict[str, object]]) -> str:
    """Choose the most specific existing parent route with deterministic tie-breaking."""

    candidates: list[tuple[int, str]] = []
    route_parts = [item for item in route.split("/") if item]
    for section in sections:
        section_id = str(section.get("id") or "projects")
        routes = section.get("routes")
        for known in routes if isinstance(routes, list) else []:
            known_parts = [item for item in str(known).split("/") if item]
            common = 0
            for left, right in zip(route_parts, known_parts, strict=False):
                if left == right or (left.startswith("[") and right.startswith("[")):
                    common += 1
                else:
                    break
            candidates.append((common, section_id))
    return sorted(candidates, key=lambda item: (-item[0], item[1]))[0][1] if candidates else "projects"


def build_maintenance_candidates(
    curated: dict[str, object],
    derived: dict[str, object],
) -> list[dict[str, object]]:
    """Translate deterministic drift errors into reviewable, non-executable proposals."""

    sections = _sections(curated)
    candidates: list[dict[str, object]] = []
    for error in validate_knowledge_base(curated, derived):
        section_id = "repository"
        finding_type = "contract_drift"
        severity = "high"
        candidate_value: dict[str, object] = {"operation": "manual_review", "error": error}
        if error.startswith("Next route has no curated knowledge owner: "):
            route = error.split(": ", 1)[1]
            section_id = _owner_for_route(route, sections)
            finding_type = "uncovered_route"
            candidate_value = {"operation": "add_route", "section_id": section_id, "route": route}
        elif error.startswith("Section "):
            parts = error.split()
            section_id = parts[1] if len(parts) > 1 else "repository"
            if "references missing" in error:
                finding_type = "stale_reference"
                candidate_value = {
                    "operation": "remove_or_replace_reference",
                    "section_id": section_id,
                    "error": error,
                }
            elif "is missing" in error:
                finding_type = "missing_explanation"
                candidate_value = {
                    "operation": "complete_section_field",
                    "section_id": section_id,
                    "error": error,
                }
        candidates.append(
            {
                "section_id": section_id,
                "finding_type": finding_type,
                "severity": severity,
                "title": f"App knowledge drift in {section_id}",
                "summary": error,
                "current_value": {"source_hash": derived.get("source_hash")},
                "candidate_value": candidate_value,
                "rationale": (
                    "Executable routes, API contracts, entities, or export media no longer match the "
                    "curated user guidance. A human must decide the documentation change."
                ),
            }
        )
    return candidates


def _derived_reference_index(derived: dict[str, object]) -> set[str]:
    references: set[str] = set()
    for item in _records(derived.get("routes")):
        if isinstance(item, dict) and item.get("route"):
            references.add(f"route:{item['route']}")
    for item in _records(derived.get("endpoints")):
        if isinstance(item, dict) and item.get("method") and item.get("path"):
            references.add(f"endpoint:{str(item['method']).upper()} {item['path']}")
    for item in _records(derived.get("entities")):
        if isinstance(item, dict) and item.get("name"):
            references.add(f"entity:{item['name']}")
    for item in _records(derived.get("exports")):
        if isinstance(item, dict) and item.get("method") and item.get("path"):
            references.add(f"export:{str(item['method']).upper()} {item['path']}")
    return references


def build_semantic_review_context(
    curated: dict[str, object],
    derived: dict[str, object],
) -> dict[str, object]:
    """Build bounded, non-executable evidence for model-assisted semantic review."""

    endpoint_inventory = [
        {
            "ref": f"endpoint:{str(item.get('method')).upper()} {item.get('path')}",
            "summary": item.get("summary"),
        }
        for item in _records(derived.get("endpoints"))
        if isinstance(item, dict) and item.get("method") and item.get("path")
    ]
    return {
        "contract": {
            "allowed_fields": sorted(SEMANTIC_FIELDS),
            "allowed_finding_types": sorted(SEMANTIC_FINDING_TYPES),
            "allowed_severities": sorted(SEMANTIC_SEVERITIES),
            "max_candidates": MAX_SEMANTIC_CANDIDATES,
            "write_policy": "human_review_only_no_yaml_mutation",
        },
        "curated_sections": _sections(curated),
        "derived_contracts": {
            "routes": [
                {"ref": f"route:{item.get('route')}"}
                for item in _records(derived.get("routes"))
                if isinstance(item, dict) and item.get("route")
            ],
            "endpoints": endpoint_inventory,
            "entities": [
                {"ref": f"entity:{item.get('name')}"}
                for item in _records(derived.get("entities"))
                if isinstance(item, dict) and item.get("name")
            ],
            "exports": [
                {
                    "ref": f"export:{str(item.get('method')).upper()} {item.get('path')}",
                    "media_types": item.get("media_types"),
                }
                for item in _records(derived.get("exports"))
                if isinstance(item, dict) and item.get("method") and item.get("path")
            ],
        },
    }


def _parse_semantic_payload(provider_output: str) -> dict[str, object] | None:
    normalized = provider_output.strip()
    if normalized.startswith("```"):
        normalized = normalized.removeprefix("```json").removeprefix("```")
        normalized = normalized.removesuffix("```").strip()
    start = normalized.find("{")
    end = normalized.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(normalized[start : end + 1])
    except json.JSONDecodeError:
        return None
    return cast(dict[str, object], payload) if isinstance(payload, dict) else None


async def persist_semantic_candidates(
    job_id: str,
    provider_output: str,
    db: AsyncSession,
) -> str | None:
    """Persist only evidence-linked model drafts; never mutate curated guidance."""

    job = await db.get(KnowledgeMaintenanceJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Knowledge maintenance job not found")
    payload = _parse_semantic_payload(provider_output)
    if payload is None:
        return None
    curated = load_curated_knowledge()
    derived = load_derived_manifest()
    sections = {str(item.get("id")): item for item in _sections(curated) if item.get("id")}
    valid_references = _derived_reference_index(derived)
    candidates = payload.get("candidates")
    accepted = 0
    rejected = 0
    if isinstance(candidates, list):
        for raw_candidate in candidates[:MAX_SEMANTIC_CANDIDATES]:
            if not isinstance(raw_candidate, dict):
                rejected += 1
                continue
            section_id = str(raw_candidate.get("section_id") or "")
            field = str(raw_candidate.get("field") or "")
            finding_type = str(raw_candidate.get("finding_type") or "")
            severity = str(raw_candidate.get("severity") or "")
            title = str(raw_candidate.get("title") or "").strip()
            summary = str(raw_candidate.get("summary") or "").strip()
            draft = raw_candidate.get("draft")
            rationale = str(raw_candidate.get("rationale") or "").strip()
            evidence_refs = raw_candidate.get("evidence_refs")
            references = (
                [str(item) for item in evidence_refs if isinstance(item, str)]
                if isinstance(evidence_refs, list)
                else []
            )
            valid = (
                section_id in sections
                and field in SEMANTIC_FIELDS
                and finding_type in SEMANTIC_FINDING_TYPES
                and severity in SEMANTIC_SEVERITIES
                and 3 <= len(title) <= 255
                and 3 <= len(summary) <= 4000
                and 3 <= len(rationale) <= 4000
                and isinstance(draft, (str, list))
                and bool(references)
                and all(reference in valid_references for reference in references)
            )
            if not valid:
                rejected += 1
                continue
            db.add(
                KnowledgeMaintenanceFinding(
                    job_id=job.id,
                    section_id=section_id,
                    finding_type=finding_type,
                    severity=severity,
                    title=title,
                    summary=summary,
                    current_value={"field": field, "value": sections[section_id].get(field)},
                    candidate_value={
                        "operation": "revise_curated_guidance",
                        "field": field,
                        "draft": draft,
                        "evidence_refs": references,
                    },
                    rationale=rationale,
                )
            )
            accepted += 1
    await db.flush()
    job.finding_count = int(
        await db.scalar(
            select(func.count())
            .select_from(KnowledgeMaintenanceFinding)
            .where(KnowledgeMaintenanceFinding.job_id == job.id)
        )
        or 0
    )
    await audit_service.emit(
        event_type="app_knowledge_semantic_candidates_recorded",
        entity_type="knowledge_maintenance_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=None,
        new_value={"accepted_count": accepted, "rejected_count": rejected},
        project_id=None,
        correlation_id=job.id,
        db=db,
    )
    await db.flush()
    summary = str(payload.get("summary") or "").strip()
    return summary[:4000] if summary else (
        f"Semantic review recorded {accepted} candidate(s) for explicit human review."
    )


def _finding_response(item: KnowledgeMaintenanceFinding) -> KnowledgeMaintenanceFindingResponse:
    return KnowledgeMaintenanceFindingResponse(
        id=item.id,
        job_id=item.job_id,
        section_id=item.section_id,
        finding_type=item.finding_type,
        severity=item.severity,
        title=item.title,
        summary=item.summary,
        current_value=cast(dict[str, object], item.current_value),
        candidate_value=cast(dict[str, object], item.candidate_value),
        rationale=item.rationale,
        review_status=cast(Literal["pending", "accepted", "rejected"], item.review_status),
        reviewed_by=item.reviewed_by,
        review_note=item.review_note,
        reviewed_at=item.reviewed_at,
        created_at=item.created_at,
    )


async def serialize_job(job: KnowledgeMaintenanceJob, db: AsyncSession) -> KnowledgeMaintenanceJobResponse:
    findings = list(
        (
            await db.scalars(
                select(KnowledgeMaintenanceFinding)
                .where(KnowledgeMaintenanceFinding.job_id == job.id)
                .order_by(KnowledgeMaintenanceFinding.created_at, KnowledgeMaintenanceFinding.id)
            )
        ).all()
    )
    return KnowledgeMaintenanceJobResponse(
        id=job.id,
        requested_by=job.requested_by,
        status=cast(Literal["pending", "running", "completed", "failed"], job.status),
        source_hash=job.source_hash,
        finding_count=job.finding_count,
        error_details=cast(dict[str, object] | None, job.error_details),
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        findings=[_finding_response(item) for item in findings],
    )


async def create_job(actor_id: str, db: AsyncSession) -> KnowledgeMaintenanceJob:
    manifest = load_derived_manifest()
    job = KnowledgeMaintenanceJob(
        requested_by=actor_id or "api-user",
        status="pending",
        source_hash=str(manifest.get("source_hash") or ""),
    )
    db.add(job)
    await db.flush()
    return job


async def execute_job(job_id: str, db: AsyncSession) -> dict[str, object]:
    """Detect drift and persist candidates; never edit the curated YAML."""

    job = await db.get(KnowledgeMaintenanceJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Knowledge maintenance job not found")
    if job.status == "completed":
        return cast(dict[str, object], (await serialize_job(job, db)).model_dump(mode="json"))
    job.status = "running"
    job.started_at = datetime.now(UTC)
    manifest = load_derived_manifest()
    curated = load_curated_knowledge()
    proposals = build_maintenance_candidates(curated, manifest)
    for proposal in proposals:
        db.add(KnowledgeMaintenanceFinding(job_id=job.id, **proposal))
    job.source_hash = str(manifest.get("source_hash") or "")
    job.finding_count = len(proposals)
    job.status = "completed"
    job.completed_at = datetime.now(UTC)
    await audit_service.emit(
        event_type="app_knowledge_maintenance_completed",
        entity_type="knowledge_maintenance_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value={"status": "pending"},
        new_value={"status": "completed", "finding_count": len(proposals), "source_hash": job.source_hash},
        project_id=None,
        correlation_id=job.id,
        db=db,
    )
    await db.flush()
    payload = (await serialize_job(job, db)).model_dump(mode="json")
    payload["authority"] = "derived_repository_contracts"
    payload["write_policy"] = "human_review_only_no_yaml_mutation"
    payload["semantic_review_context"] = build_semantic_review_context(curated, manifest)
    return cast(dict[str, object], sanitize_for_json(payload))


async def list_jobs(db: AsyncSession, *, limit: int = 20) -> list[KnowledgeMaintenanceJobResponse]:
    jobs = list(
        (
            await db.scalars(
                select(KnowledgeMaintenanceJob)
                .order_by(KnowledgeMaintenanceJob.created_at.desc())
                .limit(min(max(limit, 1), 50))
            )
        ).all()
    )
    return [await serialize_job(job, db) for job in jobs]


async def review_finding(
    finding_id: str,
    request: KnowledgeMaintenanceReviewRequest,
    *,
    actor_id: str,
    db: AsyncSession,
) -> KnowledgeMaintenanceFindingResponse:
    finding = await db.get(KnowledgeMaintenanceFinding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Knowledge maintenance finding not found")
    if finding.review_status != "pending":
        raise HTTPException(status_code=409, detail="Knowledge maintenance finding is already reviewed")
    finding.review_status = "accepted" if request.decision == "accept" else "rejected"
    finding.reviewed_by = actor_id or "api-user"
    finding.review_note = request.rationale
    finding.reviewed_at = datetime.now(UTC)
    await audit_service.emit(
        event_type="app_knowledge_candidate_reviewed",
        entity_type="knowledge_maintenance_finding",
        entity_id=finding.id,
        actor_id=finding.reviewed_by,
        old_value={"review_status": "pending"},
        new_value={"review_status": finding.review_status, "section_id": finding.section_id},
        project_id=None,
        correlation_id=finding.job_id,
        db=db,
    )
    await db.flush()
    return _finding_response(finding)
