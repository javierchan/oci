"""Persisted admin synthetic-generation job tracking models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class SyntheticGenerationJobStatus(str, enum.Enum):
    """Lifecycle states for persisted synthetic lab jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CLEANED_UP = "cleaned_up"


class SyntheticGenerationJob(Base, UUIDMixin, TimestampMixin):
    """Admin-owned job record for governed synthetic project generation."""

    __tablename__ = "synthetic_generation_jobs"

    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[SyntheticGenerationJobStatus] = mapped_column(
        SAEnum(
            SyntheticGenerationJobStatus,
            native_enum=False,
            values_callable=_enum_values,
        ),
        default=SyntheticGenerationJobStatus.PENDING,
        nullable=False,
    )
    preset_code: Mapped[str] = mapped_column(String(100), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(ForeignKey("projects.id"))
    project_name: Mapped[Optional[str]] = mapped_column(String(255))
    seed_value: Mapped[int] = mapped_column(Integer, nullable=False)
    catalog_target: Mapped[int] = mapped_column(Integer, nullable=False)
    manual_target: Mapped[int] = mapped_column(Integer, nullable=False)
    import_target: Mapped[int] = mapped_column(Integer, nullable=False)
    excluded_import_target: Mapped[int] = mapped_column(Integer, nullable=False)
    result_summary: Mapped[Optional[dict]] = mapped_column(JSON)
    validation_results: Mapped[Optional[dict]] = mapped_column(JSON)
    artifact_manifest: Mapped[Optional[dict]] = mapped_column(JSON)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
