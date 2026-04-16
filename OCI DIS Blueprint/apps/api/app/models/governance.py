"""Governance models: patterns, dictionaries, assumptions, and templates."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text
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
    """Versioned calculation assumptions from TPL - Supuestos."""

    __tablename__ = "assumption_sets"

    version: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    assumptions: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Structure: {
    #   "oic_rest_max_payload_kb": 51200,
    #   "oic_ftp_max_payload_kb": 51200,
    #   "oic_kafka_max_payload_kb": 10240,
    #   "oic_timeout_s": 300,
    #   "oic_billing_threshold_kb": 50,
    #   "oic_pack_size_msgs_per_hour": 5000,
    #   "oic_byol_pack_size_msgs_per_hour": 20000,
    #   "month_days": 31,
    #   "streaming_partition_throughput_mb_s": 1,
    #   "queue_billing_unit_kb": 64,
    #   "functions_default_duration_ms": 2000,
    #   "functions_max_timeout_s": 300,
    #   "source_references": {...},
    #   "service_metadata": {...},
    # }
    notes: Mapped[Optional[str]] = mapped_column(Text)


class PromptTemplateVersion(Base, UUIDMixin, TimestampMixin):
    """Versioned deterministic narrative templates."""

    __tablename__ = "prompt_template_versions"

    version: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    template_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
