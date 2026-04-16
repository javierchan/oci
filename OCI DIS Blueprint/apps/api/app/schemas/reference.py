"""Reference-data schemas for patterns, dictionaries, and assumptions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PatternDefinitionCreate(BaseModel):
    """Admin payload to create a custom pattern definition."""

    model_config = ConfigDict(strict=True, extra="forbid")

    pattern_id: str
    name: str
    category: str
    description: Optional[str] = None
    components: Optional[list[str]] = None
    component_details: Optional[str] = None
    when_to_use: Optional[str] = None
    when_not_to_use: Optional[str] = None
    flow: Optional[str] = None
    business_value: Optional[str] = None


class PatternDefinitionUpdate(BaseModel):
    """Admin payload to update a custom or system pattern definition."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    components: Optional[list[str]] = None
    component_details: Optional[str] = None
    when_to_use: Optional[str] = None
    when_not_to_use: Optional[str] = None
    flow: Optional[str] = None
    business_value: Optional[str] = None


class PatternSupportDimensionsResponse(BaseModel):
    """Per-surface pattern support matrix for parity transparency."""

    model_config = ConfigDict(strict=True, extra="forbid")

    capture_selection: bool
    qa_validation: bool
    volumetry: bool
    dashboard: bool
    narratives: bool
    exports: bool


class PatternSupportResponse(BaseModel):
    """Serialized support boundary for one pattern."""

    model_config = ConfigDict(strict=True, extra="forbid")

    level: Literal["full", "partial", "reference"]
    badge_label: str
    summary: str
    parity_ready: bool
    dimensions: PatternSupportDimensionsResponse


class PatternDefinitionResponse(BaseModel):
    """Serialized pattern definition."""

    model_config = ConfigDict(strict=True, extra="forbid", from_attributes=True)

    id: str
    pattern_id: str
    name: str
    category: str
    description: Optional[str]
    components: Optional[list[str]]
    component_details: Optional[str]
    when_to_use: Optional[str]
    when_not_to_use: Optional[str]
    flow: Optional[str]
    business_value: Optional[str]
    is_system: bool
    is_active: bool
    version: str
    support: PatternSupportResponse
    created_at: datetime
    updated_at: datetime


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
    is_volumetric: Optional[bool]
    sort_order: int
    is_active: bool
    version: str
    updated_at: datetime


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


class CanvasCombinationResponse(BaseModel):
    """Governed canvas combination metadata."""

    model_config = ConfigDict(strict=True, extra="forbid")

    code: str
    name: str
    capture_standard: str
    supported_tool_keys: list[str]
    compatible_pattern_ids: list[str]
    activates_metrics: list[str]
    activates_volumetric_metrics: bool
    recommended_overlays: list[str]
    guidance: str
    status: str


class CanvasGovernanceResponse(BaseModel):
    """Reference payload used by the integration design canvas."""

    model_config = ConfigDict(strict=True, extra="forbid")

    tools: list[DictionaryOptionResponse]
    overlays: list[DictionaryOptionResponse]
    combinations: list[CanvasCombinationResponse]


class DictionaryOptionCreate(BaseModel):
    """Admin payload to create a governed dictionary option."""

    model_config = ConfigDict(strict=True, extra="forbid")

    code: Optional[str] = None
    value: str
    description: Optional[str] = None
    executions_per_day: Optional[float] = None
    is_volumetric: Optional[bool] = None
    sort_order: int = 0
    is_active: bool = True
    version: str = "1.0.0"


class DictionaryOptionUpdate(BaseModel):
    """Admin payload to update one governed dictionary option."""

    model_config = ConfigDict(strict=True, extra="forbid")

    code: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None
    executions_per_day: Optional[float] = None
    is_volumetric: Optional[bool] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    version: Optional[str] = None


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


class AssumptionSetCreate(BaseModel):
    """Admin payload to create a new versioned assumption set."""

    model_config = ConfigDict(strict=True, extra="forbid")

    version: str
    label: str
    is_default: bool = False
    assumptions: dict[str, object]
    notes: Optional[str] = None


class AssumptionSetUpdate(BaseModel):
    """Admin payload to update an existing assumption set."""

    model_config = ConfigDict(strict=True, extra="forbid")

    label: Optional[str] = None
    is_default: Optional[bool] = None
    assumptions: Optional[dict[str, object]] = None
    notes: Optional[str] = None
