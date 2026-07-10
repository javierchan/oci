"""Governance models: patterns, dictionaries, assumptions, and service products."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class PatternDefinition(Base, UUIDMixin, TimestampMixin):
    """17 OCI integration patterns from TPL - Patrones."""

    __tablename__ = "pattern_definitions"

    pattern_id: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    oci_components: Mapped[Optional[str]] = mapped_column(Text)
    when_to_use: Mapped[Optional[str]] = mapped_column(Text)
    when_not_to_use: Mapped[Optional[str]] = mapped_column(Text)
    technical_flow: Mapped[Optional[str]] = mapped_column(Text)
    business_value: Mapped[Optional[str]] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")


class DictionaryOption(Base, UUIDMixin, TimestampMixin):
    """Governed dropdown values for catalog fields."""

    __tablename__ = "dictionary_options"

    category: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    executions_per_day: Mapped[Optional[float]] = mapped_column(Float)
    is_volumetric: Mapped[Optional[bool]] = mapped_column(Boolean)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")


class AssumptionSet(Base, UUIDMixin, TimestampMixin):
    """Versioned client workload inputs that are not Service Product rules."""

    __tablename__ = "assumption_sets"

    version: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    assumptions: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Service limits and interoperability constraints belong to the normalized
    # Service Product Library tables and must not be copied into this JSON.
    notes: Mapped[Optional[str]] = mapped_column(Text)


class ServiceCapabilityProfile(Base, UUIDMixin, TimestampMixin):
    """OCI service product profile and backward-compatible canvas capability source.

    Sourced from Oracle official documentation (March 2026 Pillar Document,
    product docs, pricing pages). Labels: "documented limit" = Oracle publishes
    a hard number; "best practice" = Oracle operational guidance;
    "inference" = conclusion from documented behavior.
    """

    __tablename__ = "service_capability_profiles"

    service_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    sla_uptime_pct: Mapped[Optional[float]] = mapped_column(Float)
    pricing_model: Mapped[Optional[str]] = mapped_column(String(200))
    limits: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    architectural_fit: Mapped[Optional[str]] = mapped_column(Text)
    anti_patterns: Mapped[Optional[str]] = mapped_column(Text)
    interoperability_notes: Mapped[Optional[str]] = mapped_column(Text)
    oracle_docs_urls: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")


class ServiceProductVersion(Base, UUIDMixin, TimestampMixin):
    """Versioned service-product metadata snapshot for reproducible reviews."""

    __tablename__ = "service_product_versions"

    service_profile_id: Mapped[str] = mapped_column(
        ForeignKey("service_capability_profiles.id"),
        nullable=False,
    )
    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    capabilities: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    use_cases: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    anti_patterns: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    regional_availability: Mapped[Optional[str]] = mapped_column(Text)
    commercial_notes: Mapped[Optional[str]] = mapped_column(Text)
    security_notes: Mapped[Optional[str]] = mapped_column(Text)
    deprecation_notes: Mapped[Optional[str]] = mapped_column(Text)
    product_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(100), default="seed", nullable=False)


class ServiceLimit(Base, UUIDMixin, TimestampMixin):
    """Normalized service constraint used by QA, canvas, AI Review, and exports."""

    __tablename__ = "service_limits"

    service_profile_id: Mapped[str] = mapped_column(
        ForeignKey("service_capability_profiles.id"),
        nullable=False,
    )
    limit_key: Mapped[str] = mapped_column(String(150), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), default="service", nullable=False)
    limit_type: Mapped[str] = mapped_column(String(50), default="operational", nullable=False)
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    default_value: Mapped[Optional[object]] = mapped_column(JSON)
    can_request_increase: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    source_retrieved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ServiceInteroperabilityRule(Base, UUIDMixin, TimestampMixin):
    """Directional compatibility rule between two service products."""

    __tablename__ = "service_interoperability_rules"

    source_service_profile_id: Mapped[str] = mapped_column(
        ForeignKey("service_capability_profiles.id"),
        nullable=False,
    )
    target_service_profile_id: Mapped[str] = mapped_column(
        ForeignKey("service_capability_profiles.id"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    supported: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    directionality: Mapped[str] = mapped_column(String(50), default="source_to_target", nullable=False)
    patterns: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    required_components: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    constraints: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    risk_notes: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ServiceEvidenceSource(Base, UUIDMixin, TimestampMixin):
    """Governed evidence source used by the service verification agent."""

    __tablename__ = "service_evidence_sources"

    service_profile_id: Mapped[str] = mapped_column(
        ForeignKey("service_capability_profiles.id"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(80), default="official_docs", nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    publisher: Mapped[str] = mapped_column(String(120), default="Oracle", nullable=False)
    trust_tier: Mapped[str] = mapped_column(String(80), default="tier_1_official_docs", nullable=False)
    retrieval_strategy: Mapped[str] = mapped_column(String(80), default="http_fetch", nullable=False)
    expected_update_frequency_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(50), default="pending_verification", nullable=False)


class ServiceVerificationJob(Base, UUIDMixin, TimestampMixin):
    """Async verification-agent job record for service-product evidence checks."""

    __tablename__ = "service_verification_jobs"

    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), default="all", nullable=False)
    request_payload: Mapped[Optional[dict[str, object]]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    services_checked: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    sources_checked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    changes_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    findings: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    recommendations: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    error_details: Mapped[Optional[dict[str, object]]] = mapped_column(JSON)


class ServiceVerificationFinding(Base, UUIDMixin, TimestampMixin):
    """Human-reviewable finding produced by service verification jobs."""

    __tablename__ = "service_verification_findings"

    job_id: Mapped[str] = mapped_column(ForeignKey("service_verification_jobs.id"), nullable=False)
    service_profile_id: Mapped[Optional[str]] = mapped_column(ForeignKey("service_capability_profiles.id"))
    finding_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[Optional[object]] = mapped_column(JSON)
    new_value: Mapped[Optional[object]] = mapped_column(JSON)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    evidence_excerpt: Mapped[Optional[str]] = mapped_column(Text)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class PromptTemplateVersion(Base, UUIDMixin, TimestampMixin):
    """Versioned deterministic narrative templates."""

    __tablename__ = "prompt_template_versions"

    version: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    template_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
