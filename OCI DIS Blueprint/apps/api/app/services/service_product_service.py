"""Service product library read services and verification agent execution."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import hashlib
import re
from typing import Iterable, cast
from urllib.parse import urlparse

from fastapi import HTTPException
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ServiceCapabilityProfile,
    ServiceEvidenceSource,
    ServiceInteroperabilityRule,
    ServiceLimit,
    ServiceProductVersion,
    ServiceVerificationFinding,
    ServiceVerificationJob,
)
from app.schemas.service_products import (
    ServiceEvidenceSourceResponse,
    ServiceVerificationAlertListResponse,
    ServiceVerificationAlertResponse,
    ServiceVerificationFindingResponse,
    ServiceVerificationFindingReviewRequest,
    ServiceInteroperabilityMatrixResponse,
    ServiceInteroperabilityRuleResponse,
    ServiceLimitResponse,
    ServiceProductDetailResponse,
    ServiceProductListResponse,
    ServiceProductSummaryResponse,
    ServiceProductVersionResponse,
    ServiceVerificationJobListResponse,
    ServiceVerificationJobResponse,
    ServiceVerificationRunRequest,
)
from app.services import audit_service


ALLOWED_EVIDENCE_HOSTS = {
    "docs.oracle.com",
    "oracle.com",
    "www.oracle.com",
}
EVIDENCE_FETCH_TIMEOUT_SECONDS = 12.0
EVIDENCE_USER_AGENT = "OCI-DIS-Blueprint-Service-Verification/1.0"
CLAIM_PARSER_VERSION = "oracle_http_claim_parser_v1"
TERMINAL_JOB_STATUSES = {"completed", "failed"}


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _summary_text(value: str | None, max_length: int = 240) -> str | None:
    """Return a compact first-sentence-ish summary for cards."""

    if not value:
        return None
    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1].rstrip()}…"


def _last_datetime(values: Iterable[datetime | None]) -> datetime | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return max(present)


def _verification_status(evidence_sources: list[ServiceEvidenceSource]) -> str:
    if not evidence_sources:
        return "no_sources"
    statuses = {source.status for source in evidence_sources}
    if any(status in {"failed", "source_unavailable", "pending_review"} for status in statuses):
        return "needs_attention"
    if any(status in {"stale", "seeded_pending_verification", "pending_verification"} for status in statuses):
        return "pending_verification"
    return "verified"


def _is_allowed_evidence_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        return False
    host = parsed.hostname or ""
    return host in ALLOWED_EVIDENCE_HOSTS or host.endswith(".oracle.com")


def _normalize_evidence_text(content: str) -> str:
    without_scripts = re.sub(r"<(script|style).*?</\1>", " ", content, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return re.sub(r"\s+", " ", without_tags).strip()


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evidence_excerpt(text: str, max_length: int = 500) -> str:
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1].rstrip()}…"


def _canonical_unit(value: str | None) -> str | None:
    """Normalize common Oracle documentation units for governed comparisons."""

    if value is None:
        return None
    normalized = value.strip().lower().replace(".", "")
    aliases = {
        "kb": "KB",
        "kib": "KB",
        "mb": "MB",
        "mib": "MB",
        "gb": "GB",
        "gib": "GB",
        "second": "s",
        "seconds": "s",
        "sec": "s",
        "secs": "s",
        "minute": "min",
        "minutes": "min",
        "min": "min",
        "mins": "min",
        "hour": "h",
        "hours": "h",
        "day": "days",
        "days": "days",
        "partition": "partitions",
        "partitions": "partitions",
        "message": "messages",
        "messages": "messages",
        "request": "requests",
        "requests": "requests",
        "workspace": "workspaces",
        "workspaces": "workspaces",
        "task": "tasks",
        "tasks": "tasks",
    }
    return aliases.get(normalized, value.strip())


def _convert_numeric_unit(value: float, source_unit: str | None, target_unit: str | None) -> float:
    """Convert units only for common compatible service-limit families."""

    if source_unit is None or target_unit is None or source_unit == target_unit:
        return value
    size_to_kb = {"KB": 1.0, "MB": 1024.0, "GB": 1024.0 * 1024.0}
    if source_unit in size_to_kb and target_unit in size_to_kb:
        return value * size_to_kb[source_unit] / size_to_kb[target_unit]
    time_to_s = {"s": 1.0, "min": 60.0, "h": 3600.0, "days": 86400.0}
    if source_unit in time_to_s and target_unit in time_to_s:
        return value * time_to_s[source_unit] / time_to_s[target_unit]
    return value


def _clean_numeric(value: float) -> int | float:
    return int(value) if float(value).is_integer() else round(value, 4)


def _values_match(left: object, right: object) -> bool:
    try:
        return abs(float(cast(float, left)) - float(cast(float, right))) < 0.0001
    except (TypeError, ValueError):
        return left == right


def _label_pattern(value: str) -> str:
    tokens = [re.escape(token) for token in re.findall(r"[a-zA-Z0-9]+", value.lower())]
    if not tokens:
        return r"$^"
    return r"\b" + r"[\s/_-]+".join(tokens) + r"\b"


def _limit_label_candidates(limit: ServiceLimit) -> list[str]:
    candidates = [limit.label, limit.limit_key.replace("_", " ")]
    if limit.notes:
        candidates.append(limit.notes.split(".")[0])
    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        normalized = " ".join(candidate.split()).strip()
        if normalized and normalized.lower() not in seen:
            seen.add(normalized.lower())
            result.append(normalized)
    return result


def _extract_limit_claims(
    text: str,
    limits: list[ServiceLimit],
    source: ServiceEvidenceSource,
    now: datetime,
) -> list[dict[str, object]]:
    """Extract conservative limit-change proposals tied to existing governed limits."""

    proposals: list[dict[str, object]] = []
    unit_pattern = (
        r"(?P<value>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>KB|KiB|MB|MiB|GB|GiB|seconds?|secs?|minutes?|mins?|hours?|days?|"
        r"partitions?|messages?|requests?|workspaces?|tasks?)\b"
    )
    for limit in limits:
        if not isinstance(limit.value, (int, float)):
            continue
        for label in _limit_label_candidates(limit):
            label_pattern = _label_pattern(label)
            patterns = [
                rf"{label_pattern}.{{0,140}}?(?:is|are|:|=|up to|maximum|max|limit|default)?\s*{unit_pattern}",
                rf"{unit_pattern}.{{0,140}}?{label_pattern}",
            ]
            match: re.Match[str] | None = None
            for pattern in patterns:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    break
            if match is None:
                continue
            raw_value = float(match.group("value"))
            raw_unit = _canonical_unit(match.group("unit"))
            target_unit = _canonical_unit(limit.unit) or raw_unit
            proposed_value = _clean_numeric(_convert_numeric_unit(raw_value, raw_unit, target_unit))
            if _values_match(limit.value, proposed_value):
                continue
            proposals.append(
                {
                    "target": "service_limit",
                    "operation": "update",
                    "limit_id": limit.id,
                    "limit_key": limit.limit_key,
                    "label": limit.label,
                    "value": proposed_value,
                    "unit": target_unit,
                    "raw_value": _clean_numeric(raw_value),
                    "raw_unit": raw_unit,
                    "source_url": source.url,
                    "source_retrieved_at": now.isoformat(),
                    "confidence": max(limit.confidence, 0.86),
                    "parser": CLAIM_PARSER_VERSION,
                }
            )
            break
    return proposals


def _extract_deprecation_claim(text: str, source: ServiceEvidenceSource) -> dict[str, object] | None:
    """Return a deprecation claim when official text contains explicit deprecation language."""

    if "/General/service-limits/" in source.url:
        return None
    match = re.search(
        r"(.{0,160}\b(?:deprecated|desupported|end of life|end-of-life)\b.{0,220})",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return {
        "target": "service_product",
        "operation": "review_deprecation",
        "source_url": source.url,
        "evidence": match.group(1).strip(),
        "parser": CLAIM_PARSER_VERSION,
    }


def _source_is_stale(source: ServiceEvidenceSource, now: datetime) -> bool:
    if source.last_checked_at is None:
        return True
    last_checked_at = source.last_checked_at
    if last_checked_at.tzinfo is None:
        last_checked_at = last_checked_at.replace(tzinfo=UTC)
    return (now - last_checked_at).days >= source.expected_update_frequency_days


async def _fetch_evidence_text(url: str) -> tuple[int, str]:
    async with httpx.AsyncClient(
        timeout=EVIDENCE_FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": EVIDENCE_USER_AGENT},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.status_code, response.text


def serialize_service_version(version: ServiceProductVersion) -> ServiceProductVersionResponse:
    """Serialize one version row."""

    return ServiceProductVersionResponse(
        id=version.id,
        version_label=version.version_label,
        description=version.description,
        capabilities=version.capabilities,
        use_cases=version.use_cases,
        anti_patterns=version.anti_patterns,
        regional_availability=version.regional_availability,
        commercial_notes=version.commercial_notes,
        security_notes=version.security_notes,
        deprecation_notes=version.deprecation_notes,
        metadata=version.product_metadata,
        effective_from=version.effective_from,
        created_by=version.created_by,
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def serialize_service_limit(limit: ServiceLimit) -> ServiceLimitResponse:
    """Serialize one normalized service limit."""

    return ServiceLimitResponse(
        id=limit.id,
        limit_key=limit.limit_key,
        label=limit.label,
        scope=limit.scope,
        limit_type=limit.limit_type,
        value=limit.value,
        unit=limit.unit,
        default_value=limit.default_value,
        can_request_increase=limit.can_request_increase,
        source_url=limit.source_url,
        source_retrieved_at=limit.source_retrieved_at,
        confidence=limit.confidence,
        notes=limit.notes,
        is_active=limit.is_active,
        updated_at=limit.updated_at,
    )


def serialize_evidence_source(source: ServiceEvidenceSource) -> ServiceEvidenceSourceResponse:
    """Serialize one evidence source."""

    return ServiceEvidenceSourceResponse(
        id=source.id,
        source_type=source.source_type,
        url=source.url,
        title=source.title,
        publisher=source.publisher,
        trust_tier=source.trust_tier,
        retrieval_strategy=source.retrieval_strategy,
        expected_update_frequency_days=source.expected_update_frequency_days,
        last_checked_at=source.last_checked_at,
        last_changed_at=source.last_changed_at,
        content_hash=source.content_hash,
        status=source.status,
        updated_at=source.updated_at,
    )


def serialize_verification_finding(finding: ServiceVerificationFinding) -> ServiceVerificationFindingResponse:
    """Serialize one service verification finding."""

    return ServiceVerificationFindingResponse(
        id=finding.id,
        job_id=finding.job_id,
        service_profile_id=finding.service_profile_id,
        finding_type=finding.finding_type,
        severity=finding.severity,
        title=finding.title,
        summary=finding.summary,
        old_value=finding.old_value,
        new_value=finding.new_value,
        source_url=finding.source_url,
        evidence_excerpt=finding.evidence_excerpt,
        recommended_action=finding.recommended_action,
        review_status=finding.review_status,
        reviewed_by=finding.reviewed_by,
        reviewed_at=finding.reviewed_at,
        created_at=finding.created_at,
        updated_at=finding.updated_at,
    )


def serialize_interoperability_rule(
    rule: ServiceInteroperabilityRule,
    profiles_by_id: dict[str, ServiceCapabilityProfile],
) -> ServiceInteroperabilityRuleResponse:
    """Serialize one directional interoperability rule."""

    source = profiles_by_id[rule.source_service_profile_id]
    target = profiles_by_id[rule.target_service_profile_id]
    return ServiceInteroperabilityRuleResponse(
        id=rule.id,
        source_service_id=source.service_id,
        source_service_name=source.name,
        target_service_id=target.service_id,
        target_service_name=target.name,
        relationship_type=rule.relationship_type,
        supported=rule.supported,
        directionality=rule.directionality,
        patterns=rule.patterns,
        required_components=rule.required_components,
        constraints=rule.constraints,
        risk_notes=rule.risk_notes,
        source_url=rule.source_url,
        confidence=rule.confidence,
        last_verified_at=rule.last_verified_at,
        is_active=rule.is_active,
        updated_at=rule.updated_at,
    )


def serialize_service_summary(
    profile: ServiceCapabilityProfile,
    limits: list[ServiceLimit],
    evidence_sources: list[ServiceEvidenceSource],
    interoperability_rules: list[ServiceInteroperabilityRule],
) -> ServiceProductSummaryResponse:
    """Serialize one service product list summary."""

    return ServiceProductSummaryResponse(
        id=profile.id,
        service_id=profile.service_id,
        name=profile.name,
        category=profile.category,
        architecture_role=profile.category,
        summary=_summary_text(profile.architectural_fit),
        pricing_model=profile.pricing_model,
        sla_uptime_pct=profile.sla_uptime_pct,
        version=profile.version,
        is_active=profile.is_active,
        limits_count=len(limits),
        evidence_count=len(evidence_sources),
        interoperability_count=len(interoperability_rules),
        verification_status=_verification_status(evidence_sources),
        last_verified_at=_last_datetime(
            [source.last_checked_at for source in evidence_sources]
            + [rule.last_verified_at for rule in interoperability_rules]
        ),
        updated_at=profile.updated_at,
    )


async def _load_service_library(
    db: AsyncSession,
) -> tuple[
    list[ServiceCapabilityProfile],
    dict[str, list[ServiceLimit]],
    dict[str, list[ServiceEvidenceSource]],
    dict[str, list[ServiceInteroperabilityRule]],
    dict[str, ServiceProductVersion],
    dict[str, ServiceCapabilityProfile],
]:
    profile_rows = (
        await db.scalars(
            select(ServiceCapabilityProfile)
            .where(ServiceCapabilityProfile.is_active.is_(True))
            .order_by(ServiceCapabilityProfile.category, ServiceCapabilityProfile.service_id)
        )
    ).all()
    profiles: list[ServiceCapabilityProfile] = list(profile_rows)
    profile_ids = [profile.id for profile in profiles]
    if not profile_ids:
        return [], {}, {}, {}, {}, {}

    limits = (
        await db.scalars(
            select(ServiceLimit)
            .where(ServiceLimit.service_profile_id.in_(profile_ids), ServiceLimit.is_active.is_(True))
            .order_by(ServiceLimit.limit_type, ServiceLimit.limit_key)
        )
    ).all()
    evidence_sources = (
        await db.scalars(
            select(ServiceEvidenceSource)
            .where(ServiceEvidenceSource.service_profile_id.in_(profile_ids))
            .order_by(ServiceEvidenceSource.trust_tier, ServiceEvidenceSource.url)
        )
    ).all()
    rules = (
        await db.scalars(
            select(ServiceInteroperabilityRule)
            .where(ServiceInteroperabilityRule.is_active.is_(True))
            .order_by(ServiceInteroperabilityRule.relationship_type)
        )
    ).all()
    versions = (
        await db.scalars(
            select(ServiceProductVersion)
            .where(ServiceProductVersion.service_profile_id.in_(profile_ids))
            .order_by(ServiceProductVersion.created_at.desc())
        )
    ).all()

    limits_by_profile: dict[str, list[ServiceLimit]] = defaultdict(list)
    for limit in limits:
        limits_by_profile[limit.service_profile_id].append(limit)

    evidence_by_profile: dict[str, list[ServiceEvidenceSource]] = defaultdict(list)
    for source in evidence_sources:
        evidence_by_profile[source.service_profile_id].append(source)

    rules_by_profile: dict[str, list[ServiceInteroperabilityRule]] = defaultdict(list)
    for rule in rules:
        rules_by_profile[rule.source_service_profile_id].append(rule)
        rules_by_profile[rule.target_service_profile_id].append(rule)

    current_version_by_profile: dict[str, ServiceProductVersion] = {}
    for version in versions:
        current_version_by_profile.setdefault(version.service_profile_id, version)

    profiles_by_id = {profile.id: profile for profile in profiles}
    return (
        profiles,
        dict(limits_by_profile),
        dict(evidence_by_profile),
        dict(rules_by_profile),
        current_version_by_profile,
        profiles_by_id,
    )


async def list_service_products(db: AsyncSession) -> ServiceProductListResponse:
    """Return all governed service products."""

    profiles, limits_by_profile, evidence_by_profile, rules_by_profile, _, _ = await _load_service_library(db)
    products = [
        serialize_service_summary(
            profile,
            limits_by_profile.get(profile.id, []),
            evidence_by_profile.get(profile.id, []),
            rules_by_profile.get(profile.id, []),
        )
        for profile in profiles
    ]
    stale_evidence_count = sum(
        1
        for sources in evidence_by_profile.values()
        for source in sources
            if source.status in {"stale", "seeded_pending_verification", "pending_verification"}
    )
    open_findings_count = await _open_verification_findings_count(db)
    return ServiceProductListResponse(
        products=products,
        total=len(products),
        stale_evidence_count=stale_evidence_count,
        open_findings_count=open_findings_count,
    )


async def _open_verification_findings_count(db: AsyncSession) -> int:
    rows = (
        await db.scalars(
            select(ServiceVerificationFinding).where(ServiceVerificationFinding.review_status == "open")
        )
    ).all()
    return len(rows)


async def get_service_product(service_id: str, db: AsyncSession) -> ServiceProductDetailResponse:
    """Return one service product with normalized governance details."""

    (
        profiles,
        limits_by_profile,
        evidence_by_profile,
        rules_by_profile,
        current_version_by_profile,
        profiles_by_id,
    ) = await _load_service_library(db)
    profile = next((item for item in profiles if item.service_id == service_id.upper()), None)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Service product not found", "error_code": "SERVICE_PRODUCT_NOT_FOUND"},
        )
    summary = serialize_service_summary(
        profile,
        limits_by_profile.get(profile.id, []),
        evidence_by_profile.get(profile.id, []),
        rules_by_profile.get(profile.id, []),
    )
    rules = [
        serialize_interoperability_rule(rule, profiles_by_id)
        for rule in rules_by_profile.get(profile.id, [])
        if rule.source_service_profile_id in profiles_by_id and rule.target_service_profile_id in profiles_by_id
    ]
    return ServiceProductDetailResponse(
        **summary.model_dump(),
        architectural_fit=profile.architectural_fit,
        anti_patterns=profile.anti_patterns,
        interoperability_notes=profile.interoperability_notes,
        oracle_docs_urls=profile.oracle_docs_urls,
        current_version=(
            serialize_service_version(current_version_by_profile[profile.id])
            if profile.id in current_version_by_profile
            else None
        ),
        limits=[serialize_service_limit(limit) for limit in limits_by_profile.get(profile.id, [])],
        evidence_sources=[
            serialize_evidence_source(source) for source in evidence_by_profile.get(profile.id, [])
        ],
        interoperability_rules=rules,
    )


async def list_service_product_limits(service_id: str, db: AsyncSession) -> list[ServiceLimitResponse]:
    """Return normalized limits for one service product."""

    detail = await get_service_product(service_id, db)
    return detail.limits


async def list_service_product_interoperability(
    service_id: str,
    db: AsyncSession,
) -> list[ServiceInteroperabilityRuleResponse]:
    """Return interoperability rules for one service product."""

    detail = await get_service_product(service_id, db)
    return detail.interoperability_rules


async def get_interoperability_matrix(db: AsyncSession) -> ServiceInteroperabilityMatrixResponse:
    """Return all services and active service-to-service rules."""

    profiles, limits_by_profile, evidence_by_profile, rules_by_profile, _, profiles_by_id = await _load_service_library(db)
    summaries = [
        serialize_service_summary(
            profile,
            limits_by_profile.get(profile.id, []),
            evidence_by_profile.get(profile.id, []),
            rules_by_profile.get(profile.id, []),
        )
        for profile in profiles
    ]
    seen_rule_ids: set[str] = set()
    serialized_rules: list[ServiceInteroperabilityRuleResponse] = []
    for rules in rules_by_profile.values():
        for rule in rules:
            if rule.id in seen_rule_ids:
                continue
            if rule.source_service_profile_id not in profiles_by_id or rule.target_service_profile_id not in profiles_by_id:
                continue
            serialized_rules.append(serialize_interoperability_rule(rule, profiles_by_id))
            seen_rule_ids.add(rule.id)
    serialized_rules.sort(key=lambda rule: (rule.source_service_id, rule.target_service_id, rule.relationship_type))
    return ServiceInteroperabilityMatrixResponse(
        services=summaries,
        rules=serialized_rules,
        total_rules=len(serialized_rules),
    )


def serialize_verification_job(job: ServiceVerificationJob) -> ServiceVerificationJobResponse:
    """Serialize a service verification job."""

    return ServiceVerificationJobResponse(
        id=job.id,
        requested_by=job.requested_by,
        scope=job.scope,
        request_payload=job.request_payload,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        services_checked=job.services_checked,
        sources_checked=job.sources_checked,
        changes_detected=job.changes_detected,
        findings=job.findings,
        recommendations=job.recommendations,
        error_details=job.error_details,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def list_verification_jobs(db: AsyncSession, limit: int = 20) -> ServiceVerificationJobListResponse:
    """Return recent service verification jobs."""

    rows = (
        await db.scalars(
            select(ServiceVerificationJob)
            .order_by(ServiceVerificationJob.created_at.desc())
            .limit(max(1, min(limit, 100)))
        )
    ).all()
    return ServiceVerificationJobListResponse(
        jobs=[serialize_verification_job(job) for job in rows],
        total=len(rows),
    )


async def _load_verification_job_model(job_id: str, db: AsyncSession) -> ServiceVerificationJob:
    job = await db.get(ServiceVerificationJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Service verification job not found", "error_code": "SERVICE_VERIFICATION_JOB_NOT_FOUND"},
        )
    return job


async def get_verification_job(job_id: str, db: AsyncSession) -> ServiceVerificationJobResponse:
    """Return one persisted service verification job."""

    return serialize_verification_job(await _load_verification_job_model(job_id, db))


async def list_verification_findings(
    job_id: str,
    db: AsyncSession,
) -> list[ServiceVerificationFindingResponse]:
    """Return persisted findings for one verification job."""

    await _load_verification_job_model(job_id, db)
    rows = (
        await db.scalars(
            select(ServiceVerificationFinding)
            .where(ServiceVerificationFinding.job_id == job_id)
            .order_by(ServiceVerificationFinding.created_at.desc())
        )
    ).all()
    return [serialize_verification_finding(row) for row in rows]


async def list_verification_alerts(
    db: AsyncSession,
    limit: int = 20,
) -> ServiceVerificationAlertListResponse:
    """Return stale evidence and open finding alerts for the Library UI."""

    now = _now_utc()
    profiles = (
        await db.scalars(
            select(ServiceCapabilityProfile).where(ServiceCapabilityProfile.is_active.is_(True))
        )
    ).all()
    profiles_by_id = {profile.id: profile for profile in profiles}
    open_findings = (
        await db.scalars(
            select(ServiceVerificationFinding)
            .where(ServiceVerificationFinding.review_status == "open")
            .order_by(ServiceVerificationFinding.created_at.desc())
        )
    ).all()
    sources = (
        await db.scalars(
            select(ServiceEvidenceSource).order_by(ServiceEvidenceSource.updated_at.desc())
        )
    ).all()

    alerts: list[ServiceVerificationAlertResponse] = []
    for finding in open_findings:
        profile = profiles_by_id.get(finding.service_profile_id or "")
        alerts.append(
            ServiceVerificationAlertResponse(
                id=f"finding:{finding.id}",
                alert_type=finding.finding_type,
                severity=finding.severity,
                title=finding.title,
                summary=finding.summary,
                service_profile_id=finding.service_profile_id,
                service_id=profile.service_id if profile else None,
                source_url=finding.source_url,
                finding_id=finding.id,
                status=finding.review_status,
                created_at=finding.created_at,
            )
        )

    stale_evidence_count = 0
    for source in sources:
        profile = profiles_by_id.get(source.service_profile_id)
        is_stale = _source_is_stale(source, now)
        needs_attention = source.status in {"failed", "source_unavailable", "pending_review"}
        if not is_stale and not needs_attention:
            continue
        stale_evidence_count += 1
        alert_type = "evidence_needs_review" if needs_attention else "stale_evidence"
        severity = "high" if needs_attention else "medium"
        title = "Evidence source needs review" if needs_attention else "Evidence source is due for verification"
        alerts.append(
            ServiceVerificationAlertResponse(
                id=f"source:{source.id}",
                alert_type=alert_type,
                severity=severity,
                title=title,
                summary=(
                    f"{source.title} is {source.status.replace('_', ' ')}."
                    if needs_attention
                    else f"{source.title} has not been verified within its {source.expected_update_frequency_days}-day policy."
                ),
                service_profile_id=source.service_profile_id,
                service_id=profile.service_id if profile else None,
                source_url=source.url,
                finding_id=None,
                status=source.status,
                created_at=source.updated_at,
            )
        )

    alerts.sort(key=lambda alert: alert.created_at, reverse=True)
    return ServiceVerificationAlertListResponse(
        alerts=alerts[: max(1, min(limit, 100))],
        total=len(alerts),
        open_findings_count=len(open_findings),
        stale_evidence_count=stale_evidence_count,
    )


async def _load_profiles_for_verification(
    request: ServiceVerificationRunRequest,
    db: AsyncSession,
) -> list[ServiceCapabilityProfile]:
    query = select(ServiceCapabilityProfile).where(ServiceCapabilityProfile.is_active.is_(True))
    if request.service_ids:
        normalized_ids = [service_id.upper() for service_id in request.service_ids]
        query = query.where(ServiceCapabilityProfile.service_id.in_(normalized_ids))
    rows = (await db.scalars(query.order_by(ServiceCapabilityProfile.service_id.asc()))).all()
    if request.service_ids and len(rows) != len(set(service_id.upper() for service_id in request.service_ids)):
        found = {profile.service_id for profile in rows}
        missing = sorted(set(service_id.upper() for service_id in request.service_ids) - found)
        raise HTTPException(
            status_code=404,
            detail={
                "detail": f"Service products not found: {', '.join(missing)}",
                "error_code": "SERVICE_PRODUCT_NOT_FOUND",
                "missing_service_ids": missing,
            },
        )
    return list(rows)


def _source_should_be_checked(
    source: ServiceEvidenceSource,
    request: ServiceVerificationRunRequest,
    now: datetime,
) -> bool:
    if request.force or source.last_checked_at is None:
        return True
    last_checked_at = source.last_checked_at
    if last_checked_at.tzinfo is None:
        last_checked_at = last_checked_at.replace(tzinfo=UTC)
    elapsed_days = (now - last_checked_at).days
    return elapsed_days >= source.expected_update_frequency_days


async def _create_verification_finding(
    job: ServiceVerificationJob,
    source: ServiceEvidenceSource,
    finding_type: str,
    severity: str,
    title: str,
    summary: str,
    old_value: object,
    new_value: object,
    evidence_excerpt: str | None,
    recommended_action: str,
    db: AsyncSession,
) -> ServiceVerificationFinding:
    finding = ServiceVerificationFinding(
        job_id=job.id,
        service_profile_id=source.service_profile_id,
        finding_type=finding_type,
        severity=severity,
        title=title,
        summary=summary,
        old_value=old_value,
        new_value=new_value,
        source_url=source.url,
        evidence_excerpt=evidence_excerpt,
        recommended_action=recommended_action,
        review_status="open",
    )
    db.add(finding)
    await db.flush()
    return finding


async def create_verification_job(
    request: ServiceVerificationRunRequest,
    actor_id: str,
    db: AsyncSession,
) -> ServiceVerificationJobResponse:
    """Create a pending verification job for Celery execution."""

    profiles = await _load_profiles_for_verification(request, db)
    scope = ",".join(profile.service_id for profile in profiles) if profiles else "none"
    job = ServiceVerificationJob(
        requested_by=actor_id,
        scope=scope if request.service_ids else "all",
        request_payload=request.model_dump(),
        status="pending",
        started_at=None,
        services_checked=[profile.service_id for profile in profiles],
        sources_checked=0,
        changes_detected=0,
        findings=[],
        recommendations=[],
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    await audit_service.emit(
        event_type="service_verification_created",
        entity_type="service_verification_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=None,
        new_value={
            "service_ids": job.services_checked,
            "max_sources": request.max_sources,
            "force": request.force,
        },
        project_id=None,
        db=db,
        correlation_id=job.id,
    )
    return serialize_verification_job(job)


async def mark_verification_job_failed(
    job_id: str,
    error_details: dict[str, object],
    db: AsyncSession,
) -> ServiceVerificationJobResponse:
    """Persist a failed terminal state for a verification job."""

    job = await _load_verification_job_model(job_id, db)
    old_value: dict[str, object] = {"status": job.status, "error_details": job.error_details}
    job.status = "failed"
    job.completed_at = _now_utc()
    job.error_details = error_details
    await audit_service.emit(
        event_type="service_verification_failed",
        entity_type="service_verification_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=old_value,
        new_value={"status": job.status, "error_details": error_details},
        project_id=None,
        db=db,
        correlation_id=job.id,
    )
    return serialize_verification_job(job)


async def run_verification_job(job_id: str, db: AsyncSession) -> ServiceVerificationJobResponse:
    """Execute a persisted verification job against allowlisted official sources."""

    job = await _load_verification_job_model(job_id, db)
    if job.status in TERMINAL_JOB_STATUSES:
        return serialize_verification_job(job)

    request = ServiceVerificationRunRequest.model_validate(job.request_payload or {})
    now = _now_utc()
    old_status = job.status
    job.status = "running"
    job.started_at = job.started_at or now
    job.completed_at = None
    job.error_details = None
    await audit_service.emit(
        event_type="service_verification_started",
        entity_type="service_verification_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value={"status": old_status},
        new_value={"status": job.status, "started_at": job.started_at.isoformat()},
        project_id=None,
        db=db,
        correlation_id=job.id,
    )

    profiles = await _load_profiles_for_verification(request, db)
    profile_ids = [profile.id for profile in profiles]
    job.services_checked = [profile.service_id for profile in profiles]
    sources = (
        await db.scalars(
            select(ServiceEvidenceSource)
            .where(ServiceEvidenceSource.service_profile_id.in_(profile_ids))
            .order_by(ServiceEvidenceSource.trust_tier, ServiceEvidenceSource.url)
        )
    ).all()
    limits = (
        await db.scalars(
            select(ServiceLimit)
            .where(ServiceLimit.service_profile_id.in_(profile_ids), ServiceLimit.is_active.is_(True))
            .order_by(ServiceLimit.limit_key)
        )
    ).all()
    limits_by_profile: dict[str, list[ServiceLimit]] = defaultdict(list)
    for limit in limits:
        limits_by_profile[limit.service_profile_id].append(limit)

    queued_sources = [
        source for source in sources if _source_should_be_checked(source, request, now)
    ][: request.max_sources]

    finding_summaries: list[object] = []
    recommendations: list[object] = []

    for source in queued_sources:
        if not _is_allowed_evidence_url(source.url):
            source.status = "failed"
            finding = await _create_verification_finding(
                job,
                source,
                "source_not_allowlisted",
                "high",
                "Evidence source is outside the verification allowlist",
                "The verification agent only fetches Oracle-controlled sources. This URL was skipped.",
                None,
                {"url": source.url},
                None,
                "Replace the source with an allowlisted Oracle documentation or product page before using it as governed evidence.",
                db,
            )
            finding_summaries.append(serialize_verification_finding(finding).model_dump(mode="json"))
            recommendations.append({"source_url": source.url, "action": "replace_source"})
            continue

        try:
            status_code, raw_text = await _fetch_evidence_text(source.url)
            normalized = _normalize_evidence_text(raw_text)
            new_hash = _content_hash(normalized)
            old_hash = source.content_hash
            source.last_checked_at = now
            source.source_type = source.source_type or "official_docs"
            source_had_findings = False
            if old_hash and old_hash != new_hash:
                source.last_changed_at = now
                source.status = "pending_review"
                job.changes_detected += 1
                source_had_findings = True
                finding = await _create_verification_finding(
                    job,
                    source,
                    "source_content_changed",
                    "medium",
                    "Official source content changed",
                    "The official evidence source returned a different content hash than the last governed check.",
                    {"content_hash": old_hash},
                    {"content_hash": new_hash, "http_status": status_code},
                    _evidence_excerpt(normalized),
                    "Review the source and decide whether service limits or interoperability rules need a governed update.",
                    db,
                )
                finding_summaries.append(serialize_verification_finding(finding).model_dump(mode="json"))
                recommendations.append({"source_url": source.url, "action": "review_changed_source"})

            for proposal in _extract_limit_claims(
                normalized,
                limits_by_profile.get(source.service_profile_id, []),
                source,
                now,
            ):
                job.changes_detected += 1
                source_had_findings = True
                finding = await _create_verification_finding(
                    job,
                    source,
                    "changed_limit",
                    "high",
                    f"Potential service limit change: {proposal['label']}",
                    "The verification agent extracted a limit value from official Oracle evidence that differs from the governed library.",
                    {
                        "target": "service_limit",
                        "limit_id": proposal["limit_id"],
                        "limit_key": proposal["limit_key"],
                    },
                    proposal,
                    _evidence_excerpt(normalized),
                    "Review the source excerpt and accept the finding only if the extracted value matches the official documentation.",
                    db,
                )
                finding_summaries.append(serialize_verification_finding(finding).model_dump(mode="json"))
                recommendations.append(
                    {
                        "source_url": source.url,
                        "action": "review_limit_update",
                        "limit_key": proposal["limit_key"],
                    }
                )

            deprecation_claim = _extract_deprecation_claim(normalized, source)
            if deprecation_claim is not None:
                job.changes_detected += 1
                source_had_findings = True
                finding = await _create_verification_finding(
                    job,
                    source,
                    "deprecated_capability",
                    "high",
                    "Official source mentions deprecation or end-of-life language",
                    "The source contains deprecation language and should be reviewed before architects rely on this service guidance.",
                    None,
                    deprecation_claim,
                    _evidence_excerpt(str(deprecation_claim["evidence"])),
                    "Review the service product description, anti-patterns, and affected interoperability rules.",
                    db,
                )
                finding_summaries.append(serialize_verification_finding(finding).model_dump(mode="json"))
                recommendations.append({"source_url": source.url, "action": "review_deprecation_language"})

            if source_had_findings:
                source.status = "pending_review"
            else:
                source.status = "verified"
                if old_hash is None:
                    source.last_changed_at = now
            source.content_hash = new_hash
            job.sources_checked += 1
        except httpx.HTTPStatusError as exc:
            source.last_checked_at = now
            source.status = "source_unavailable"
            finding = await _create_verification_finding(
                job,
                source,
                "source_unavailable",
                "medium",
                "Official source returned an unsuccessful status",
                f"The verification agent received HTTP {exc.response.status_code} for this evidence source.",
                None,
                {"http_status": exc.response.status_code},
                None,
                "Check whether the source URL moved or should be replaced before relying on this evidence.",
                db,
            )
            finding_summaries.append(serialize_verification_finding(finding).model_dump(mode="json"))
            recommendations.append({"source_url": source.url, "action": "inspect_source_url"})
        except httpx.HTTPError as exc:
            source.last_checked_at = now
            source.status = "source_unavailable"
            finding = await _create_verification_finding(
                job,
                source,
                "source_fetch_failed",
                "medium",
                "Official source could not be fetched",
                f"The verification agent could not retrieve this evidence source: {exc}",
                None,
                {"error": str(exc)},
                None,
                "Retry later or replace the source if it remains unavailable.",
                db,
            )
            finding_summaries.append(serialize_verification_finding(finding).model_dump(mode="json"))
            recommendations.append({"source_url": source.url, "action": "retry_or_replace_source"})

    job.status = "completed"
    job.completed_at = _now_utc()
    job.findings = finding_summaries
    job.recommendations = recommendations
    await audit_service.emit(
        event_type="service_verification_completed",
        entity_type="service_verification_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=None,
        new_value={
            "sources_checked": job.sources_checked,
            "changes_detected": job.changes_detected,
            "findings": len(finding_summaries),
        },
        project_id=None,
        db=db,
        correlation_id=job.id,
    )
    return serialize_verification_job(job)


async def execute_verification_job(
    request: ServiceVerificationRunRequest,
    actor_id: str,
    db: AsyncSession,
) -> ServiceVerificationJobResponse:
    """Create and run a verification job in-process for bounded smoke tests."""

    job = await create_verification_job(request, actor_id, db)
    return await run_verification_job(job.id, db)


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _apply_accepted_finding_update(
    finding: ServiceVerificationFinding,
    actor_id: str,
    db: AsyncSession,
) -> dict[str, object] | None:
    new_value = finding.new_value
    if not isinstance(new_value, dict):
        return None
    if new_value.get("target") != "service_limit" or new_value.get("operation") != "update":
        return None

    limit_id = new_value.get("limit_id")
    if not isinstance(limit_id, str):
        return None
    limit = await db.get(ServiceLimit, limit_id)
    if limit is None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The proposed service limit no longer exists.",
                "error_code": "SERVICE_LIMIT_PROPOSAL_TARGET_MISSING",
            },
        )

    old_limit: dict[str, object] = {
        "value": limit.value,
        "unit": limit.unit,
        "source_url": limit.source_url,
        "source_retrieved_at": limit.source_retrieved_at.isoformat() if limit.source_retrieved_at else None,
        "confidence": limit.confidence,
    }
    limit.value = new_value.get("value")
    unit = new_value.get("unit")
    limit.unit = str(unit) if unit is not None else None
    source_url = new_value.get("source_url")
    if isinstance(source_url, str):
        limit.source_url = source_url
    retrieved_at = _parse_iso_datetime(new_value.get("source_retrieved_at"))
    limit.source_retrieved_at = retrieved_at or _now_utc()
    confidence = new_value.get("confidence")
    if isinstance(confidence, (int, float)):
        limit.confidence = float(confidence)

    if isinstance(source_url, str) and finding.service_profile_id:
        source = await db.scalar(
            select(ServiceEvidenceSource).where(
                ServiceEvidenceSource.service_profile_id == finding.service_profile_id,
                ServiceEvidenceSource.url == source_url,
            )
        )
        if source is not None:
            source.status = "verified"

    new_limit: dict[str, object] = {
        "value": limit.value,
        "unit": limit.unit,
        "source_url": limit.source_url,
        "source_retrieved_at": limit.source_retrieved_at.isoformat() if limit.source_retrieved_at else None,
        "confidence": limit.confidence,
    }
    applied_update: dict[str, object] = {
        "entity_type": "service_limit",
        "entity_id": limit.id,
        "limit_key": limit.limit_key,
        "old_value": old_limit,
        "new_value": new_limit,
    }
    await audit_service.emit(
        event_type="service_limit_updated_from_verification",
        entity_type="service_limit",
        entity_id=limit.id,
        actor_id=actor_id,
        old_value=old_limit,
        new_value=new_limit,
        project_id=None,
        db=db,
        correlation_id=finding.job_id,
    )
    return applied_update


async def review_verification_finding(
    job_id: str,
    finding_id: str,
    request: ServiceVerificationFindingReviewRequest,
    actor_id: str,
    db: AsyncSession,
) -> ServiceVerificationFindingResponse:
    """Record a manual review decision for one verification finding."""

    finding = await db.get(ServiceVerificationFinding, finding_id)
    if finding is None or finding.job_id != job_id:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Service verification finding not found", "error_code": "SERVICE_VERIFICATION_FINDING_NOT_FOUND"},
        )
    old_value: dict[str, object] = {
        "review_status": finding.review_status,
        "reviewed_by": finding.reviewed_by,
        "reviewed_at": finding.reviewed_at.isoformat() if finding.reviewed_at else None,
    }
    applied_update: dict[str, object] | None = None
    if request.review_status == "accepted":
        applied_update = await _apply_accepted_finding_update(finding, actor_id, db)
    finding.review_status = request.review_status
    finding.reviewed_by = actor_id
    finding.reviewed_at = _now_utc()
    await audit_service.emit(
        event_type="service_verification_finding_reviewed",
        entity_type="service_verification_finding",
        entity_id=finding.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value={
            "review_status": finding.review_status,
            "note": request.note,
            "applied_update": applied_update,
        },
        project_id=None,
        db=db,
        correlation_id=job_id,
    )
    return serialize_verification_finding(finding)
