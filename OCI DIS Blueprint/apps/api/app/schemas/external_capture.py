"""Schemas for governed external-capture review workspaces."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ExternalCaptureStatus = Literal["draft", "in_review", "completed"]
ExternalDraftStatus = Literal["needs_review", "approved", "rejected", "promoted"]


class ExternalCaptureSessionCreate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    client_name: str = Field(min_length=1, max_length=500)
    source_label: str = Field(min_length=1, max_length=500)
    source_hash: str = Field(min_length=64, max_length=64)
    normalization_policy: dict[str, Any] = Field(default_factory=dict)


class ExternalCaptureDraftInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    source_row_number: int = Field(ge=1)
    source_record: dict[str, Any]
    proposed_payload: dict[str, Any]
    normalized_values: dict[str, Any] = Field(default_factory=dict)
    pattern_assessment: dict[str, Any] = Field(default_factory=dict)
    validation_evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class ExternalCaptureDraftBulkCreate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    drafts: list[ExternalCaptureDraftInput] = Field(min_length=1, max_length=500)


class ExternalCaptureDraftPatch(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    proposed_payload: Optional[dict[str, Any]] = None
    normalized_values: Optional[dict[str, Any]] = None
    pattern_assessment: Optional[dict[str, Any]] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class ExternalCaptureDraftReview(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    decision: Literal["approve", "reject"]
    rationale: str = Field(min_length=3, max_length=4000)


class ExternalCaptureSessionResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: str
    name: str
    client_name: str
    source_label: str
    source_hash: str
    status: ExternalCaptureStatus
    normalization_policy: dict[str, Any]
    created_by: str
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ExternalCaptureSummary(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    total: int
    schema_ready: int
    missing_required: int
    qa_review: int
    pattern_changes: int
    needs_review: int
    approved: int
    rejected: int
    promoted: int


class ExternalCaptureSessionDetail(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    session: ExternalCaptureSessionResponse
    summary: ExternalCaptureSummary


class ExternalCaptureSessionList(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    sessions: list[ExternalCaptureSessionResponse]


class ExternalCaptureDraftResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    session_id: str
    source_row_number: int
    source_record: dict[str, Any]
    proposed_payload: dict[str, Any]
    normalized_values: dict[str, Any]
    pattern_assessment: dict[str, Any]
    validation_evidence: dict[str, Any]
    required_field_gaps: list[str]
    qa_preview: dict[str, Any]
    confidence: Optional[float]
    status: ExternalDraftStatus
    reviewer_rationale: Optional[str]
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    promoted_integration_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class ExternalCaptureDraftPage(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    drafts: list[ExternalCaptureDraftResponse]
    total: int
    page: int
    page_size: int


class ExternalCaptureBulkResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    created: int
    updated: int
    total: int
    summary: ExternalCaptureSummary


class ExternalCapturePromotionResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    draft: ExternalCaptureDraftResponse
    integration_id: str
