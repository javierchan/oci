"""Persisted AI review job tracking models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class AiReviewJobStatus(str, enum.Enum):
    """Lifecycle states for governed AI review jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AiReviewJob(Base, UUIDMixin, TimestampMixin):
    """Persisted architecture review board job and immutable result payload."""

    __tablename__ = "ai_review_jobs"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[AiReviewJobStatus] = mapped_column(
        SAEnum(
            AiReviewJobStatus,
            native_enum=False,
            values_callable=_enum_values,
        ),
        default=AiReviewJobStatus.PENDING,
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="project")
    integration_id: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_integrations.id"))
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    accepted_recommendations: Mapped[Optional[list]] = mapped_column(JSON)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
