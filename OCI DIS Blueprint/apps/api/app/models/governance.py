"""Governance models: patterns, dictionaries, assumptions — PRD-044."""
from __future__ import annotations
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class PatternDefinition(Base, UUIDMixin, TimestampMixin):
    """17 OCI integration patterns from TPL - Patrones."""
    __tablename__ = "pattern_definitions"

    pattern_id: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)  # e.g. #01
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # SÍNCRONO | ASÍNCRONO | etc.
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
    """Governed dropdown values for catalog fields (PRD-044)."""
    __tablename__ = "dictionary_options"

    category: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. FREQUENCY, TOOLS, TRIGGER_TYPE
    code: Mapped[Optional[str]] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    executions_per_day: Mapped[Optional[float]] = mapped_column(Float)  # for FREQUENCY category
    is_volumetric: Mapped[Optional[bool]] = mapped_column(Boolean)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")


class AssumptionSet(Base, UUIDMixin, TimestampMixin):
    """Versioned calculation assumptions from TPL - Supuestos (PRD-035)."""
    __tablename__ = "assumption_sets"

    version: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    assumptions: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Structure: {
    #   "oic_rest_max_payload_kb": 50,
    #   "oic_ftp_max_payload_kb": 50,
    #   "oic_kafka_max_payload_kb": 10,
    #   "oic_timeout_s": 300,
    #   "oic_billing_threshold_kb": 50,
    #   "oic_pack_size": 5000,
    #   "month_days": 30,
    #   "streaming_partition_throughput_mb_s": 1,
    #   "functions_default_duration_ms": 200,
    #   "functions_default_memory_mb": 256
    # }
    notes: Mapped[Optional[str]] = mapped_column(Text)


class PromptTemplateVersion(Base, UUIDMixin, TimestampMixin):
    """Versioned deterministic narrative templates for M6 justification assembly."""

    __tablename__ = "prompt_template_versions"

    version: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    template_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
