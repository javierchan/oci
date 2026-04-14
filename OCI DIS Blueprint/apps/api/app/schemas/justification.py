"""Justification narrative request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MethodologyBlock(BaseModel):
    """One deterministic narrative section."""

    model_config = ConfigDict(strict=True, extra="forbid")

    title: str
    body: str


class JustificationNarrative(BaseModel):
    """Structured deterministic narrative content."""

    model_config = ConfigDict(strict=True, extra="forbid")

    summary: str
    methodology_blocks: list[MethodologyBlock] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    qa_status: str
    qa_reasons: list[str] = Field(default_factory=list)
    override_text: Optional[str] = None


class JustificationRecordResponse(BaseModel):
    """Serialized justification record or generated draft narrative."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: Optional[str] = None
    project_id: str
    integration_id: str
    state: str
    approved_by: Optional[str] = None
    override_notes: Optional[str] = None
    narrative: JustificationNarrative
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class JustificationListResponse(BaseModel):
    """Project-level collection of justification narratives."""

    model_config = ConfigDict(strict=True, extra="forbid")

    records: list[JustificationRecordResponse] = Field(default_factory=list)
    total: int = 0


class ApproveJustificationRequest(BaseModel):
    """Approval request payload."""

    model_config = ConfigDict(strict=True, extra="forbid")

    actor_id: str = "api-user"


class OverrideJustificationRequest(BaseModel):
    """Override request payload."""

    model_config = ConfigDict(strict=True, extra="forbid")

    actor_id: str = "api-user"
    override_text: str
    override_notes: Optional[str] = None


class ResetJustificationRequest(BaseModel):
    """Reset request payload."""

    model_config = ConfigDict(strict=True, extra="forbid")

    actor_id: str = "api-user"


class PromptTemplateVersionResponse(BaseModel):
    """Serialized narrative template version."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    version: str
    name: str
    is_default: bool
    template_config: dict[str, object]
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PromptTemplateVersionListResponse(BaseModel):
    """List of versioned narrative templates."""

    model_config = ConfigDict(strict=True, extra="forbid")

    templates: list[PromptTemplateVersionResponse] = Field(default_factory=list)
    total: int = 0


class PromptTemplateVersionCreate(BaseModel):
    """Admin payload to create a versioned narrative template."""

    model_config = ConfigDict(strict=True, extra="forbid")

    version: str
    name: str
    is_default: bool = False
    template_config: dict[str, object]
    notes: Optional[str] = None


class PromptTemplateVersionUpdate(BaseModel):
    """Admin payload to update a versioned narrative template."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: Optional[str] = None
    is_default: Optional[bool] = None
    template_config: Optional[dict[str, object]] = None
    notes: Optional[str] = None
