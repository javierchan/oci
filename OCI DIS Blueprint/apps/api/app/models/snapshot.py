"""Immutable calculation, dashboard, justification, and audit snapshots."""
from __future__ import annotations

from typing import Optional
from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class VolumetrySnapshot(Base, UUIDMixin, TimestampMixin):
    """Immutable result of a full volumetry recalculation for a project (PRD-035)."""
    __tablename__ = "volumetry_snapshots"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    assumption_set_version: Mapped[str] = mapped_column(String(50), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(36), nullable=False)  # user_id
    row_results: Mapped[dict] = mapped_column(JSON, nullable=False)  # {integration_id: {driver: value}}
    consolidated: Mapped[dict] = mapped_column(JSON, nullable=False)  # OIC, DI, Functions, Streaming totals
    snapshot_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON)


class DashboardSnapshot(Base, UUIDMixin, TimestampMixin):
    """Immutable dashboard render — sourced from VolumetrySnapshot (PRD-036)."""
    __tablename__ = "dashboard_snapshots"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    volumetry_snapshot_id: Mapped[str] = mapped_column(ForeignKey("volumetry_snapshots.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), default="technical")  # technical | commercial
    kpi_strip: Mapped[dict] = mapped_column(JSON, nullable=False)
    charts: Mapped[dict] = mapped_column(JSON, nullable=False)
    risks: Mapped[Optional[dict]] = mapped_column(JSON)
    maturity: Mapped[Optional[dict]] = mapped_column(JSON)


class JustificationRecord(Base, UUIDMixin, TimestampMixin):
    """Deterministic narrative record per integration (PRD-040)."""

    __tablename__ = "justification_records"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    integration_id: Mapped[str] = mapped_column(ForeignKey("catalog_integrations.id"), nullable=False)
    state: Mapped[str] = mapped_column("status", String(50), default="draft")  # draft | approved | overridden
    deterministic_text: Mapped[dict] = mapped_column(JSON, nullable=False)  # assembled from structured fields
    narrative_text: Mapped[Optional[str]] = mapped_column("narrative", Text)
    ai_suggestion: Mapped[Optional[dict]] = mapped_column(JSON)  # optional, never auto-applies
    approved_by: Mapped[Optional[str]] = mapped_column(String(36))
    override_notes: Mapped[Optional[str]] = mapped_column(String(4000))


class AuditEvent(Base, UUIDMixin, TimestampMixin):
    """Structured audit trail — every write emits an event (PRD-045)."""
    __tablename__ = "audit_events"

    project_id: Mapped[Optional[str]] = mapped_column(ForeignKey("projects.id"))
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(36))
    old_value: Mapped[Optional[dict]] = mapped_column(JSON)
    new_value: Mapped[Optional[dict]] = mapped_column(JSON)
    audit_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON)
