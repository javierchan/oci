"""Governed external-capture review sessions and row drafts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class ExternalCaptureSession(Base, UUIDMixin, TimestampMixin):
    """Project-scoped review workspace for structured external row evidence."""

    __tablename__ = "external_capture_sessions"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_label: Mapped[str] = mapped_column(String(500), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    normalization_policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ExternalCaptureDraft(Base, UUIDMixin, TimestampMixin):
    """Reviewable row proposal that is isolated from the canonical catalog."""

    __tablename__ = "external_capture_drafts"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "source_row_number",
            name="uq_external_capture_drafts_session_row",
        ),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("external_capture_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_record: Mapped[dict] = mapped_column(JSON, nullable=False)
    proposed_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    pattern_assessment: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    validation_evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    required_field_gaps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    qa_preview: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="needs_review", index=True
    )
    reviewer_rationale: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    promoted_integration_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("catalog_integrations.id", ondelete="SET NULL"),
        index=True,
    )
