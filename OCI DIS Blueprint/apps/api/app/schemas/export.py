"""Export job schemas for generated project artifacts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
