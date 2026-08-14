"""Contracts for project coordination metadata, separate from domain approval flows."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ApiTimestamp


class ProjectSavedViewCreate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    surface: Literal["catalog", "topology"]
    label: str = Field(min_length=1, max_length=100)
    filters: dict[str, Any] = Field(default_factory=dict)
    is_shared: bool = True

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("must not be blank")
        return value


class ProjectSavedViewResponse(ProjectSavedViewCreate):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class ProjectSavedViewList(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    views: list[ProjectSavedViewResponse]


AttentionSource = Literal["qa", "topology", "coverage", "bom"]
AttentionTaskStatus = Literal["open", "in_progress", "resolved"]


class ProjectAttentionTaskCreate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    attention_key: str = Field(min_length=1, max_length=255)
    source: AttentionSource
    title: str = Field(min_length=1, max_length=500)
    evidence_href: str = Field(min_length=1, max_length=2048)
    assignee: Optional[str] = Field(default=None, max_length=255)
    due_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("due_date", mode="before")
    @classmethod
    def parse_due_date(cls, value: object) -> object:
        return date.fromisoformat(value) if isinstance(value, str) else value


class ProjectAttentionTaskPatch(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    expected_updated_at: ApiTimestamp
    assignee: Optional[str] = Field(default=None, max_length=255)
    due_date: Optional[date] = None
    status: Optional[AttentionTaskStatus] = None
    note: Optional[str] = Field(default=None, max_length=4000)
    evidence: Optional[dict[str, Any]] = None

    @field_validator("due_date", mode="before")
    @classmethod
    def parse_due_date(cls, value: object) -> object:
        return date.fromisoformat(value) if isinstance(value, str) else value


class ProjectAttentionTaskResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: str
    attention_key: str
    source: AttentionSource
    title: str
    evidence_href: str
    assignee: Optional[str]
    due_date: Optional[date]
    status: AttentionTaskStatus
    note: Optional[str]
    evidence: Optional[dict[str, Any]]
    created_by: str
    updated_by: str
    is_overdue: bool
    created_at: datetime
    updated_at: datetime


class ProjectAttentionTaskList(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    tasks: list[ProjectAttentionTaskResponse]
