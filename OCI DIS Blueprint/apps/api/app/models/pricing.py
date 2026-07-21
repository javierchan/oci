"""Governed OCI pricing, deployment-scenario, and Bill of Materials models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class PriceSource(Base, UUIDMixin, TimestampMixin):
    """Approved public, subscription, or uploaded OCI pricing source."""

    __tablename__ = "price_sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    source_config: Mapped[dict[str, object]] = mapped_column("config", JSON, nullable=False, default=dict)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(100), default="seed", nullable=False)


class PriceSyncJob(Base, UUIDMixin, TimestampMixin):
    """Terminal asynchronous job that refreshes one governed price source."""

    __tablename__ = "price_sync_jobs"

    source_id: Mapped[str] = mapped_column(ForeignKey("price_sources.id"), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    changes_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(36))
    error_details: Mapped[Optional[dict[str, object]]] = mapped_column(JSON)


class PriceCatalogSnapshot(Base, UUIDMixin, TimestampMixin):
    """Immutable normalized OCI price catalog at a point in time."""

    __tablename__ = "price_catalog_snapshots"

    source_id: Mapped[str] = mapped_column(ForeignKey("price_sources.id"), nullable=False)
    sync_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("price_sync_jobs.id"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(50), default="approved", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    snapshot_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False, default=dict)


class CommercialSku(Base, UUIDMixin, TimestampMixin):
    """Stable OCI part-number identity shared by price, document, and mapping evidence."""

    __tablename__ = "commercial_skus"
    __table_args__ = (
        UniqueConstraint("part_number", name="uq_commercial_sku_part_number"),
        Index("ix_commercial_sku_lifecycle_category", "lifecycle_status", "service_category"),
    )

    part_number: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    service_category: Mapped[Optional[str]] = mapped_column(String(500))
    source_product_id: Mapped[Optional[str]] = mapped_column(String(100))
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    identity_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False, default=dict)


class CommercialDocumentSnapshot(Base, UUIDMixin, TimestampMixin):
    """Immutable official commercial document stored as governed evidence."""

    __tablename__ = "commercial_document_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "document_kind",
            "content_hash",
            "parser_version",
            name="uq_commercial_document_kind_hash_parser",
        ),
        Index("ix_commercial_document_kind_status", "document_kind", "status"),
    )

    document_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_reference: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    effective_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supersedes_snapshot_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("commercial_document_snapshots.id")
    )
    manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class SkuCommercialTerm(Base, UUIDMixin, TimestampMixin):
    """Normalized commercial terms extracted from one official document row."""

    __tablename__ = "sku_commercial_terms"
    __table_args__ = (
        UniqueConstraint(
            "document_snapshot_id",
            "source_sheet",
            "source_row",
            "part_number",
            name="uq_sku_term_document_location",
        ),
        Index("ix_sku_commercial_terms_part_status", "part_number", "status"),
    )

    document_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("commercial_document_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    commercial_sku_id: Mapped[str] = mapped_column(ForeignKey("commercial_skus.id"), nullable=False)
    price_catalog_snapshot_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("price_catalog_snapshots.id")
    )
    part_number: Mapped[str] = mapped_column(String(50), nullable=False)
    service_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    service_category: Mapped[Optional[str]] = mapped_column(String(500))
    commercial_prices: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    metric_name: Mapped[Optional[str]] = mapped_column(String(500))
    price_type: Mapped[Optional[str]] = mapped_column(String(50))
    allow_decimal_quantity: Mapped[Optional[bool]] = mapped_column(Boolean)
    availability: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    additional_information: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    disposition: Mapped[str] = mapped_column(String(40), default="blocked_input_required", nullable=False)
    family_key: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_cells: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    extraction_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class SkuCommercialConstraint(Base, UUIDMixin, TimestampMixin):
    """One typed minimum, increment, duration, or eligibility constraint."""

    __tablename__ = "sku_commercial_constraints"
    __table_args__ = (
        UniqueConstraint(
            "term_id", "constraint_type", "scope", "source_cell",
            name="uq_sku_commercial_constraint_source",
        ),
        Index("ix_sku_commercial_constraint_term_status", "term_id", "status"),
    )

    term_id: Mapped[str] = mapped_column(
        ForeignKey("sku_commercial_terms.id", ondelete="CASCADE"), nullable=False
    )
    constraint_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    numeric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(28, 8))
    text_value: Mapped[Optional[str]] = mapped_column(Text)
    unit: Mapped[Optional[str]] = mapped_column(String(100))
    behavior: Mapped[Optional[str]] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="observed", nullable=False)
    source_cell: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )


class SkuCommercialRelationship(Base, UUIDMixin, TimestampMixin):
    """Entitlement, prerequisite, dependency, or inclusion linked to a SKU."""

    __tablename__ = "sku_commercial_relationships"
    __table_args__ = (
        Index("ix_sku_commercial_relationship_part_type", "part_number", "relationship_type"),
    )

    document_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("commercial_document_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    source_term_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("sku_commercial_terms.id", ondelete="CASCADE")
    )
    source_commercial_sku_id: Mapped[str] = mapped_column(ForeignKey("commercial_skus.id"), nullable=False)
    target_commercial_sku_id: Mapped[Optional[str]] = mapped_column(ForeignKey("commercial_skus.id"))
    part_number: Mapped[str] = mapped_column(String(50), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_part_number: Mapped[Optional[str]] = mapped_column(String(50))
    target_name: Mapped[str] = mapped_column(Text, nullable=False)
    guidance: Mapped[Optional[str]] = mapped_column(Text)
    resolution_status: Mapped[str] = mapped_column(String(32), default="unresolved", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_cell: Mapped[Optional[str]] = mapped_column(String(50))


class CommercialRuleFamily(Base, UUIDMixin, TimestampMixin):
    """Reusable deterministic formula contract for equivalent OCI SKU semantics."""

    __tablename__ = "commercial_rule_families"
    __table_args__ = (
        UniqueConstraint("family_key", "version", name="uq_commercial_rule_family_version"),
    )

    family_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    formula_key: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    price_types: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    quantity_behavior: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity_increment: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    minimum_quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    aggregation_window: Mapped[str] = mapped_column(String(40), nullable=False)
    proration_policy: Mapped[str] = mapped_column(String(40), nullable=False)
    quote_rounding: Mapped[str] = mapped_column(String(40), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    fixture_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class CommercialMappingCandidate(Base, UUIDMixin, TimestampMixin):
    """Generated SKU mapping proposal that requires an explicit disposition."""

    __tablename__ = "commercial_mapping_candidates"
    __table_args__ = (
        UniqueConstraint(
            "document_snapshot_id", "part_number", "generator_version",
            name="uq_commercial_candidate_document_sku_generator",
        ),
        Index("ix_commercial_candidate_status_class", "status", "classification"),
        Index("ix_commercial_candidate_document_part", "document_snapshot_id", "part_number"),
        Index("ix_commercial_candidate_document_status", "document_snapshot_id", "status"),
    )

    document_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("commercial_document_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    commercial_sku_id: Mapped[str] = mapped_column(ForeignKey("commercial_skus.id"), nullable=False)
    term_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sku_commercial_terms.id"))
    price_item_id: Mapped[Optional[str]] = mapped_column(ForeignKey("price_items.id"))
    existing_mapping_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("service_product_sku_mappings.id")
    )
    part_number: Mapped[str] = mapped_column(String(50), nullable=False)
    proposed_service_id: Mapped[Optional[str]] = mapped_column(String(80))
    family_key: Mapped[Optional[str]] = mapped_column(String(100))
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    proposed_mapping: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    generator_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending_review", nullable=False)
    reasons: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class CommercialException(Base, UUIDMixin, TimestampMixin):
    """Auditable ambiguity or source conflict that blocks automatic publication."""

    __tablename__ = "commercial_exceptions"
    __table_args__ = (
        Index("ix_commercial_exception_status_severity", "status", "severity"),
    )

    document_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("commercial_document_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("commercial_mapping_candidates.id", ondelete="CASCADE")
    )
    part_number: Mapped[Optional[str]] = mapped_column(String(50))
    exception_code: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    proposed_resolution: Mapped[Optional[str]] = mapped_column(Text)
    decision_rationale: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class CommercialEvidenceReference(Base, UUIDMixin, TimestampMixin):
    """Fine-grained source pointer supporting a commercial decision."""

    __tablename__ = "commercial_evidence_references"
    __table_args__ = (
        Index("ix_commercial_evidence_entity", "entity_type", "entity_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    document_snapshot_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("commercial_document_snapshots.id", ondelete="CASCADE")
    )
    governance_artifact_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("governance_source_artifacts.id", ondelete="CASCADE")
    )
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    source_sheet: Mapped[Optional[str]] = mapped_column(String(255))
    source_row: Mapped[Optional[int]] = mapped_column(Integer)
    source_cell: Mapped[Optional[str]] = mapped_column(String(50))
    excerpt_hash: Mapped[Optional[str]] = mapped_column(String(128))
    evidence_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False, default=dict)


class CommercialRelease(Base, UUIDMixin, TimestampMixin):
    """Atomic approved combination of prices, documents, mappings, and rule families."""

    __tablename__ = "commercial_releases"
    __table_args__ = (
        UniqueConstraint("version", name="uq_commercial_release_version"),
        Index("ix_commercial_release_status_validation", "status", "validation_status"),
    )

    version: Mapped[str] = mapped_column(String(80), nullable=False)
    price_catalog_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("price_catalog_snapshots.id"), nullable=False
    )
    document_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("commercial_document_snapshots.id"), nullable=False
    )
    governance_change_set_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("governance_change_sets.id")
    )
    mapping_set_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_family_set_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    open_exception_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    release_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class GovernanceChangeSet(Base, UUIDMixin, TimestampMixin):
    """Atomic review unit for official OCI commercial-source changes."""

    __tablename__ = "governance_change_sets"

    sync_job_id: Mapped[str] = mapped_column(ForeignKey("price_sync_jobs.id"), nullable=False, unique=True)
    price_source_id: Mapped[str] = mapped_column(ForeignKey("price_sources.id"), nullable=False)
    price_snapshot_id: Mapped[str] = mapped_column(ForeignKey("price_catalog_snapshots.id"), nullable=False)
    previous_change_set_id: Mapped[Optional[str]] = mapped_column(ForeignKey("governance_change_sets.id"))
    trigger_type: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="validating", nullable=False)
    drift_classification: Mapped[str] = mapped_column(String(32), default="none", nullable=False)
    materiality_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    source_manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    drift_summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    impact_summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    validation_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    regression_summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    approval_status: Mapped[str] = mapped_column(String(32), default="pending_review", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_details: Mapped[Optional[dict[str, object]]] = mapped_column(JSON)


class GovernanceSourceArtifact(Base, UUIDMixin, TimestampMixin):
    """Immutable source evidence captured for one governance change set."""

    __tablename__ = "governance_source_artifacts"
    __table_args__ = (
        UniqueConstraint("change_set_id", "source_kind", name="uq_governance_artifact_change_set_kind"),
    )

    change_set_id: Mapped[str] = mapped_column(
        ForeignKey("governance_change_sets.id", ondelete="CASCADE"), nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_reference: Mapped[str] = mapped_column(Text, nullable=False)
    source_last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retrieval_status: Mapped[str] = mapped_column(String(32), default="verified", nullable=False)
    validation_summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuotationRegressionRun(Base, UUIDMixin, TimestampMixin):
    """Deterministic quote fixture result for one commercial service family."""

    __tablename__ = "quotation_regression_runs"
    __table_args__ = (
        UniqueConstraint("change_set_id", "family_key", name="uq_quote_regression_change_set_family"),
    )

    change_set_id: Mapped[str] = mapped_column(
        ForeignKey("governance_change_sets.id", ondelete="CASCADE"), nullable=False
    )
    family_key: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    fixture_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mapping_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    findings: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PriceItem(Base, UUIDMixin, TimestampMixin):
    """One normalized SKU price or tier inside a price catalog snapshot."""

    __tablename__ = "price_items"

    snapshot_id: Mapped[str] = mapped_column(ForeignKey("price_catalog_snapshots.id"), nullable=False)
    part_number: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(500), nullable=False)
    service_category: Mapped[str] = mapped_column(String(500), nullable=False)
    price_type: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    model: Mapped[str] = mapped_column(String(50), default="PAY_AS_YOU_GO", nullable=False)
    value: Mapped[float] = mapped_column(Numeric(24, 10, asdecimal=False), nullable=False)
    range_min: Mapped[Optional[float]] = mapped_column(Numeric(24, 8, asdecimal=False))
    range_max: Mapped[Optional[float]] = mapped_column(Numeric(24, 8, asdecimal=False))
    range_unit: Mapped[Optional[str]] = mapped_column(String(100))


class ServiceProductSkuMapping(Base, UUIDMixin, TimestampMixin):
    """Versioned rule that maps technical service demand to an OCI SKU."""

    __tablename__ = "service_product_sku_mappings"

    service_profile_id: Mapped[Optional[str]] = mapped_column(ForeignKey("service_capability_profiles.id"))
    service_id: Mapped[str] = mapped_column(String(80), nullable=False)
    tool_key: Mapped[str] = mapped_column(String(120), nullable=False)
    part_number: Mapped[Optional[str]] = mapped_column(String(50))
    billing_metric_key: Mapped[str] = mapped_column(String(150), nullable=False)
    formula_key: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity_behavior: Mapped[str] = mapped_column(String(32), default="continuous", nullable=False)
    quantity_increment: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False), default=0.000001, nullable=False)
    minimum_quantity: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False), default=0, nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(100), default="units", nullable=False)
    usage_basis: Mapped[str] = mapped_column(String(40), default="metered_usage", nullable=False)
    quote_rounding: Mapped[str] = mapped_column(String(40), default="metered", nullable=False)
    aggregation_window: Mapped[str] = mapped_column(String(40), default="calendar_month", nullable=False)
    proration_policy: Mapped[str] = mapped_column(String(40), default="prorated", nullable=False)
    free_tier_scope: Mapped[str] = mapped_column(String(40), default="none", nullable=False)
    planning_envelope_increment: Mapped[Optional[float]] = mapped_column(Numeric(28, 8, asdecimal=False))
    metering_policy: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    selection_policy: Mapped[str] = mapped_column(String(32), default="required", nullable=False)
    requires_explicit_quantity: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    entry_guidance: Mapped[str] = mapped_column(Text, default="Enter the expected monthly usage.", nullable=False)
    quantity_presets: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    predicates: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="approved", nullable=False)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class ServiceCommercialPolicy(Base, UUIDMixin, TimestampMixin):
    """Authoritative product-level rule for detection and BOM publication."""

    __tablename__ = "service_commercial_policies"
    __table_args__ = (
        UniqueConstraint("service_profile_id", name="uq_service_commercial_policy_profile"),
        UniqueConstraint("service_id", name="uq_service_commercial_policy_service"),
    )

    service_profile_id: Mapped[str] = mapped_column(
        ForeignKey("service_capability_profiles.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[str] = mapped_column(String(80), nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    readiness: Mapped[str] = mapped_column(String(32), nullable=False)
    publication_policy: Mapped[str] = mapped_column(String(40), nullable=False)
    tool_aliases: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    dependent_service_ids: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    required_inputs: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    guidance: Mapped[str] = mapped_column(Text, nullable=False)
    source_urls: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), default="approved", nullable=False)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class DeploymentScenario(Base, UUIDMixin, TimestampMixin):
    """Project-level physical deployment assumptions approved before pricing."""

    __tablename__ = "deployment_scenarios"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    region: Mapped[str] = mapped_column(String(100), default="global", nullable=False)
    price_mode: Mapped[str] = mapped_column(String(50), default="public_list", nullable=False)
    commitment_model: Mapped[str] = mapped_column(
        String(32), default="pay_as_you_go", nullable=False
    )
    licensing_model: Mapped[str] = mapped_column(
        String(32), default="license_included", nullable=False
    )
    technical_snapshot_id: Mapped[str] = mapped_column(ForeignKey("volumetry_snapshots.id"), nullable=False)
    contract_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    proration_policy: Mapped[str] = mapped_column(String(32), default="full_month", nullable=False)
    consumption_model: Mapped[str] = mapped_column(String(32), default="explicit_units", nullable=False)
    service_config: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    scenario_assumptions: Mapped[dict[str, object]] = mapped_column("assumptions", JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class DeploymentEnvironmentPlan(Base, UUIDMixin, TimestampMixin):
    """Normalized environment runtime posture owned by a deployment scenario."""

    __tablename__ = "deployment_environment_plans"
    __table_args__ = (UniqueConstraint("scenario_id", "name", name="uq_deployment_environment_scenario_name"),)

    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("deployment_scenarios.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    active_hours_month: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    demand_share: Mapped[float] = mapped_column(Numeric(12, 8, asdecimal=False), nullable=False)
    ha_multiplier: Mapped[float] = mapped_column(Numeric(12, 8, asdecimal=False), nullable=False)
    dr_role: Mapped[str] = mapped_column(String(20), nullable=False)


class DeploymentRampPhase(Base, UUIDMixin, TimestampMixin):
    """Inclusive real-unit quantity phase, with legacy multiplier compatibility."""

    __tablename__ = "deployment_ramp_phases"

    environment_plan_id: Mapped[str] = mapped_column(
        ForeignKey("deployment_environment_plans.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[Optional[str]] = mapped_column(String(80))
    metric_key: Mapped[Optional[str]] = mapped_column(String(150))
    sku_mapping_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("service_product_sku_mappings.id", ondelete="RESTRICT")
    )
    start_month: Mapped[int] = mapped_column(Integer, nullable=False)
    end_month: Mapped[int] = mapped_column(Integer, nullable=False)
    start_multiplier: Mapped[float] = mapped_column(Numeric(8, 6, asdecimal=False), nullable=False)
    end_multiplier: Mapped[float] = mapped_column(Numeric(8, 6, asdecimal=False), nullable=False)
    interpolation: Mapped[str] = mapped_column(String(16), nullable=False)
    start_quantity: Mapped[Optional[float]] = mapped_column(Numeric(28, 8, asdecimal=False))
    end_quantity: Mapped[Optional[float]] = mapped_column(Numeric(28, 8, asdecimal=False))
    quantity_unit: Mapped[Optional[str]] = mapped_column(String(100))
    rationale: Mapped[Optional[str]] = mapped_column(Text)


class DeploymentRampPeriodQuantity(Base, UUIDMixin, TimestampMixin):
    """One normalized explicit monthly quantity inside a deployment ramp plan."""

    __tablename__ = "deployment_ramp_period_quantities"
    __table_args__ = (
        UniqueConstraint("ramp_phase_id", "period_index", name="uq_deployment_ramp_period"),
    )

    ramp_phase_id: Mapped[str] = mapped_column(
        ForeignKey("deployment_ramp_phases.id", ondelete="CASCADE"), nullable=False
    )
    period_index: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=False)


class BomJob(Base, UUIDMixin, TimestampMixin):
    """Terminal asynchronous job that generates one governed BOM snapshot."""

    __tablename__ = "bom_jobs"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("deployment_scenarios.id"), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    bom_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36))
    error_details: Mapped[Optional[dict[str, object]]] = mapped_column(JSON)


class BomSnapshot(Base, UUIDMixin, TimestampMixin):
    """Immutable commercial estimate tied to exact technical and pricing inputs."""

    __tablename__ = "bom_snapshots"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("deployment_scenarios.id"), nullable=False)
    technical_snapshot_id: Mapped[str] = mapped_column(ForeignKey("volumetry_snapshots.id"), nullable=False)
    price_catalog_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("price_catalog_snapshots.id"), nullable=False
    )
    commercial_release_id: Mapped[Optional[str]] = mapped_column(ForeignKey("commercial_releases.id"))
    mapping_version: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    coverage_pct: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_total: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    annual_total: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    contract_total: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    steady_state_monthly_total: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    peak_monthly_total: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    ramp_deferred_amount: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    first_active_period: Mapped[Optional[int]] = mapped_column(Integer)
    steady_state_period: Mapped[Optional[int]] = mapped_column(Integer)
    summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    warnings: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    publication_status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class BomLineItem(Base, UUIDMixin, TimestampMixin):
    """Auditable SKU line in one immutable BOM snapshot."""

    __tablename__ = "bom_line_items"

    bom_snapshot_id: Mapped[str] = mapped_column(ForeignKey("bom_snapshots.id"), nullable=False)
    environment: Mapped[str] = mapped_column(String(100), nullable=False)
    service_id: Mapped[str] = mapped_column(String(80), nullable=False)
    part_number: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=False)
    unit: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(24, 10, asdecimal=False), nullable=False)
    monthly_amount: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    annual_amount: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    contract_amount: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    price_item_id: Mapped[Optional[str]] = mapped_column(ForeignKey("price_items.id"))
    commercial_term_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sku_commercial_terms.id"))
    commercial_rule_family_id: Mapped[Optional[str]] = mapped_column(ForeignKey("commercial_rule_families.id"))
    evidence_reference_ids: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="priced", nullable=False)
    warnings: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class BomLinePeriod(Base, UUIDMixin, TimestampMixin):
    """Immutable monthly quantity, price, and amount for one BOM line."""

    __tablename__ = "bom_line_periods"
    __table_args__ = (UniqueConstraint("bom_line_item_id", "period_index", name="uq_bom_line_period"),)

    bom_line_item_id: Mapped[str] = mapped_column(
        ForeignKey("bom_line_items.id", ondelete="CASCADE"), nullable=False
    )
    period_index: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    multiplier: Mapped[float] = mapped_column(Numeric(8, 6, asdecimal=False), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(28, 8, asdecimal=False), nullable=False)
    active_hours: Mapped[float] = mapped_column(Numeric(12, 4, asdecimal=False), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(24, 10, asdecimal=False), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    selected_price_item_id: Mapped[Optional[str]] = mapped_column(ForeignKey("price_items.id"))
    commercial_term_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sku_commercial_terms.id"))
    commercial_rule_family_id: Mapped[Optional[str]] = mapped_column(ForeignKey("commercial_rule_families.id"))
    evidence_reference_ids: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    warnings: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
