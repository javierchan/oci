"""Governed OCI pricing, deployment-scenario, and Bill of Materials models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text
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
    predicates: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="approved", nullable=False)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
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
    technical_snapshot_id: Mapped[str] = mapped_column(ForeignKey("volumetry_snapshots.id"), nullable=False)
    contract_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    environments: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    service_config: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    scenario_assumptions: Mapped[dict[str, object]] = mapped_column("assumptions", JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


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
    mapping_version: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    coverage_pct: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_total: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    annual_total: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
    contract_total: Mapped[float] = mapped_column(Numeric(24, 2, asdecimal=False), nullable=False)
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
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="priced", nullable=False)
    warnings: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
