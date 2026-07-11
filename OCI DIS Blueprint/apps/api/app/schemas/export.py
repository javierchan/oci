"""Export job schemas for generated project artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CaptureTemplateColumnMetadata(BaseModel):
    """Public metadata for one governed capture column."""

    model_config = ConfigDict(strict=True, extra="forbid")

    field: str
    header: str
    section: str
    requirement: str
    data_type: str
    description: str


class CaptureTemplateMetadata(BaseModel):
    """Version and governed-source metadata for the downloadable template."""

    model_config = ConfigDict(strict=True, extra="forbid")

    template_version: str
    importer_min_version: str
    filename: str
    generated_at: datetime
    capture_sheet: str
    capture_row_limit: int
    pattern_count: int
    service_product_count: int
    service_limit_count: int
    interoperability_rule_count: int
    evidence_source_count: int
    stale_evidence_count: int
    last_verified_at: Optional[datetime]
    columns: list[CaptureTemplateColumnMetadata] = Field(default_factory=list)


class ExportJobResponse(BaseModel):
    """Metadata for one generated export artifact."""

    model_config = ConfigDict(strict=True, extra="forbid")

    job_id: str
    project_id: str
    snapshot_id: str
    format: str
    status: str
    filename: str
    download_url: str
    created_at: datetime
