"""Core domain models — project, import, source row, and catalog entities."""
from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Boolean, Enum as SAEnum, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


class ImportStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IntegrationStatus(str, enum.Enum):
    YA_EXISTE = "Ya existe"
    DEFINITIVA = "Definitiva (End-State)"
    EN_REVISION = "En Revisión"
    TBD = "TBD"
    DUPLICADO_1 = "Duplicado 1"
    DUPLICADO_2 = "Duplicado 2"


class QAStatus(str, enum.Enum):
    OK = "OK"
    REVISAR = "REVISAR"
    PENDING = "PENDING"


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(2000))
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, native_enum=False, values_callable=_enum_values),
        default=ProjectStatus.DRAFT,
    )
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_metadata: Mapped[Optional[dict]] = mapped_column(JSON)

    import_batches: Mapped[list["ImportBatch"]] = relationship(back_populates="project")
    catalog_integrations: Mapped[list["CatalogIntegration"]] = relationship(back_populates="project")


class ImportBatch(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "import_batches"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[ImportStatus] = mapped_column(
        SAEnum(ImportStatus, native_enum=False, values_callable=_enum_values),
        default=ImportStatus.PENDING,
    )
    source_row_count: Mapped[Optional[int]] = mapped_column(Integer)
    tbq_y_count: Mapped[Optional[int]] = mapped_column(Integer)
    excluded_count: Mapped[Optional[int]] = mapped_column(Integer)
    loaded_count: Mapped[Optional[int]] = mapped_column(Integer)
    header_map: Mapped[Optional[dict]] = mapped_column(JSON)  # normalized header map
    error_details: Mapped[Optional[dict]] = mapped_column(JSON)

    project: Mapped["Project"] = relationship(back_populates="import_batches")
    source_rows: Mapped[list["SourceIntegrationRow"]] = relationship(back_populates="import_batch")


class SourceIntegrationRow(Base, UUIDMixin, TimestampMixin):
    """Immutable raw source record — never mutated after import (PRD-023)."""
    __tablename__ = "source_integration_rows"

    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # verbatim row
    included: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(String(500))
    normalization_events: Mapped[Optional[list]] = mapped_column(JSON)  # [{field, old, new, rule}]

    import_batch: Mapped["ImportBatch"] = relationship(back_populates="source_rows")
    catalog_integrations: Mapped[list["CatalogIntegration"]] = relationship(back_populates="source_row")


class CatalogIntegration(Base, UUIDMixin, TimestampMixin):
    """Governed working entity — architect-editable, fully audited (PRD-010, PRD-044)."""
    __tablename__ = "catalog_integrations"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    source_row_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_integration_rows.id"))

    # IDENTIFICATION (columns B-H in workbook)
    seq_number: Mapped[int] = mapped_column(Integer, nullable=False)
    interface_id: Mapped[Optional[str]] = mapped_column(String(100))
    owner: Mapped[Optional[str]] = mapped_column(String(255))
    brand: Mapped[Optional[str]] = mapped_column(String(255))
    business_process: Mapped[Optional[str]] = mapped_column(String(500))
    interface_name: Mapped[Optional[str]] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(String(2000))

    # TRACKING (columns I-L)
    status: Mapped[Optional[str]] = mapped_column(String(100))
    mapping_status: Mapped[Optional[str]] = mapped_column(String(100))
    initial_scope: Mapped[Optional[str]] = mapped_column(String(255))
    complexity: Mapped[Optional[str]] = mapped_column(String(100))

    # TECHNICAL DETAILS (columns M-R)
    frequency: Mapped[Optional[str]] = mapped_column(String(255))
    type: Mapped[Optional[str]] = mapped_column(String(100))
    base: Mapped[Optional[str]] = mapped_column(String(255))
    interface_status: Mapped[Optional[str]] = mapped_column(String(100))
    is_real_time: Mapped[Optional[bool]] = mapped_column(Boolean)
    trigger_type: Mapped[Optional[str]] = mapped_column(String(100))

    # VOLUMETRY — PRIMARY INPUTS (columns S-V)
    response_size_kb: Mapped[Optional[float]] = mapped_column(Float)
    payload_per_execution_kb: Mapped[Optional[float]] = mapped_column(Float)
    is_fan_out: Mapped[Optional[bool]] = mapped_column(Boolean)
    fan_out_targets: Mapped[Optional[int]] = mapped_column(Integer)

    # SOURCE APPLICATION (columns W-Z)
    source_system: Mapped[Optional[str]] = mapped_column(String(255))
    source_technology: Mapped[Optional[str]] = mapped_column(String(255))
    source_api_reference: Mapped[Optional[str]] = mapped_column(String(1000))
    source_owner: Mapped[Optional[str]] = mapped_column(String(255))

    # DESTINATION APPLICATION (columns AA-AD)
    destination_system: Mapped[Optional[str]] = mapped_column(String(255))
    destination_technology_1: Mapped[Optional[str]] = mapped_column(String(255))
    destination_technology_2: Mapped[Optional[str]] = mapped_column(String(255))
    destination_owner: Mapped[Optional[str]] = mapped_column(String(255))

    # DERIVED FIELDS (columns AF-AG — calculated, not typed — PRD-021)
    executions_per_day: Mapped[Optional[float]] = mapped_column(Float)
    payload_per_hour_kb: Mapped[Optional[float]] = mapped_column(Float)

    # ARCHITECTURAL FIELDS — architect-owned (columns AH-AN — PRD-022)
    selected_pattern: Mapped[Optional[str]] = mapped_column(String(100))
    pattern_rationale: Mapped[Optional[str]] = mapped_column(String(2000))
    comments: Mapped[Optional[str]] = mapped_column(String(4000))
    retry_policy: Mapped[Optional[str]] = mapped_column(String(500))
    core_tools: Mapped[Optional[str]] = mapped_column(String(1000))
    additional_tools_overlays: Mapped[Optional[str]] = mapped_column(String(1000))

    # QA (column AN — PRD-025)
    qa_status: Mapped[Optional[str]] = mapped_column(String(50))
    qa_reasons: Mapped[Optional[list]] = mapped_column(JSON)

    # Misc
    calendarization: Mapped[Optional[str]] = mapped_column(String(255))
    uncertainty: Mapped[Optional[str]] = mapped_column(String(255))

    project: Mapped["Project"] = relationship(back_populates="catalog_integrations")
    source_row: Mapped[Optional["SourceIntegrationRow"]] = relationship(back_populates="catalog_integrations")
