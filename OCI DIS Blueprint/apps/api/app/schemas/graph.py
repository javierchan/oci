"""Pydantic response models for the system dependency graph."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GraphIntegrationSummary(BaseModel):
    """Actionable catalog context carried by one graph relationship."""

    model_config = ConfigDict(strict=True)

    id: str
    name: str
    qa_status: str
    owner: str | None
    pattern: str | None
    trigger_type: str | None
    interaction_mode: str
    executions_per_day: float | None
    payload_per_execution_kb: float | None
    payload_per_hour_kb: float | None
    updated_at: datetime


class GraphNode(BaseModel):
    """One system node in the dependency graph."""

    model_config = ConfigDict(strict=True)

    id: str
    label: str
    integration_count: int
    as_source_count: int
    as_destination_count: int
    brands: list[str]
    business_processes: list[str]
    owners: list[str]
    technologies: list[str]


class GraphEdge(BaseModel):
    """One directed source-to-destination relationship in the dependency graph."""

    model_config = ConfigDict(strict=True)

    id: str
    source: str
    target: str
    integration_count: int
    integration_ids: list[str]
    integration_names: list[str]
    integration_qa_statuses: list[str]
    business_processes: list[str]
    patterns: list[str]
    qa_statuses: dict[str, int]
    dominant_qa_status: str
    risk_qa_status: str
    risk_score: int
    interaction_mode: str
    total_executions_per_day: float
    total_payload_per_execution_kb: float
    total_payload_per_hour_kb: float
    executions_coverage: int
    payload_execution_coverage: int
    payload_coverage: int
    last_updated_at: datetime
    integrations: list[GraphIntegrationSummary]


class GraphMeta(BaseModel):
    """Summary metadata for the rendered graph."""

    model_config = ConfigDict(strict=True)

    node_count: int
    edge_count: int
    integration_count: int
    business_processes: list[str]
    business_process_families: list[str]
    brands: list[str]
    latest_updated_at: datetime | None
    executions_coverage: int
    payload_execution_coverage: int
    payload_coverage: int


class GraphResponse(BaseModel):
    """Full graph payload returned by the catalog graph endpoint."""

    model_config = ConfigDict(strict=True)

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta: GraphMeta
