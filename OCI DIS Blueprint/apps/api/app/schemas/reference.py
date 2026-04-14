"""Reference-data schemas for patterns, dictionaries, and assumptions."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PatternDefinitionResponse(BaseModel):
    """Serialized pattern definition."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    pattern_id: str
    name: str
    category: str
    description: Optional[str]
    is_active: bool
    version: str


class PatternListResponse(BaseModel):
    """Pattern list response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    patterns: list[PatternDefinitionResponse] = Field(default_factory=list)
    total: int = 0


class DictionaryOptionResponse(BaseModel):
    """Serialized dictionary option."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    category: str
    code: Optional[str]
    value: str
    description: Optional[str]
    executions_per_day: Optional[float]
    sort_order: int
    is_active: bool


class DictionaryCategorySummary(BaseModel):
    """Summary of dictionary category counts."""

    model_config = ConfigDict(strict=True, extra="forbid")

    category: str
    option_count: int


class DictionaryCategoryListResponse(BaseModel):
    """Dictionary category summary list."""

    model_config = ConfigDict(strict=True, extra="forbid")

    categories: list[DictionaryCategorySummary]


class DictionaryOptionListResponse(BaseModel):
    """Dictionary option list response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    category: str
    options: list[DictionaryOptionResponse]


class AssumptionSetResponse(BaseModel):
    """Serialized assumption set."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    version: str
    label: str
    is_default: bool
    assumptions: dict[str, object]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class AssumptionSetListResponse(BaseModel):
    """Assumption set list response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    assumption_sets: list[AssumptionSetResponse] = Field(default_factory=list)
