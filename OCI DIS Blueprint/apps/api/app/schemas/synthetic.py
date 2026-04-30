"""Pydantic contracts for the admin synthetic-lab API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SyntheticGenerationPresetResponse(BaseModel):
    """One governed preset surfaced by the admin synthetic lab."""

    model_config = ConfigDict(strict=True, extra="forbid")

    code: str
    label: str
    description: str
    project_name: str
    seed_value: int
    target_catalog_size: int
    min_distinct_systems: int
    import_target: int
    manual_target: int
    excluded_import_target: int
    include_justifications: bool
    include_exports: bool
    include_design_warnings: bool
    cleanup_policy: Literal["manual", "ephemeral_auto_cleanup"]


class SyntheticGenerationPresetListResponse(BaseModel):
    """Collection response for governed synthetic presets."""

    model_config = ConfigDict(strict=True, extra="forbid")

    presets: list[SyntheticGenerationPresetResponse] = Field(default_factory=list)


class SyntheticGenerationJobCreateRequest(BaseModel):
    """Bounded admin request for a new synthetic-generation job."""

    model_config = ConfigDict(strict=True, extra="forbid")

    project_name: Optional[str] = None
    preset_code: str = "enterprise-default"
    target_catalog_size: Optional[int] = Field(default=None, ge=17, le=2000)
    min_distinct_systems: Optional[int] = Field(default=None, ge=2, le=500)
    import_target: Optional[int] = Field(default=None, ge=1, le=2000)
    manual_target: Optional[int] = Field(default=None, ge=0, le=1000)
    excluded_import_target: Optional[int] = Field(default=None, ge=0, le=500)
    include_justifications: Optional[bool] = None
    include_exports: Optional[bool] = None
    include_design_warnings: Optional[bool] = None
    cleanup_policy: Optional[Literal["manual", "ephemeral_auto_cleanup"]] = None
    seed_value: Optional[int] = Field(default=None, ge=1, le=99_999_999)


class SyntheticArtifactExportJobResponse(BaseModel):
    """One generated export artifact attached to a completed job."""

    model_config = ConfigDict(strict=True, extra="forbid")

    job_id: str
    filename: str
    download_url: str
    file_path: str
    job_file_path: Optional[str] = None


class SyntheticArtifactManifestResponse(BaseModel):
    """Filesystem artifact manifest for a completed or cleaned-up job."""

    model_config = ConfigDict(strict=True, extra="forbid")

    workbook_path: str
    report_json_path: str
    report_markdown_path: str
    export_jobs: dict[str, SyntheticArtifactExportJobResponse] = Field(default_factory=dict)


class SyntheticGenerationJobResponse(BaseModel):
    """Serialized persisted synthetic-generation job."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    requested_by: str
    status: str
    preset_code: str
    input_payload: dict[str, object]
    normalized_payload: dict[str, object]
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    seed_value: int
    catalog_target: int
    manual_target: int
    import_target: int
    excluded_import_target: int
    result_summary: Optional[dict[str, object]] = None
    validation_results: Optional[dict[str, object]] = None
    artifact_manifest: Optional[SyntheticArtifactManifestResponse] = None
    error_details: Optional[dict[str, object]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SyntheticGenerationJobListResponse(BaseModel):
    """Collection response for persisted synthetic-generation jobs."""

    model_config = ConfigDict(strict=True, extra="forbid")

    jobs: list[SyntheticGenerationJobResponse] = Field(default_factory=list)
    total: int = 0
