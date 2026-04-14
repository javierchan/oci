"""Pydantic response models for the system dependency graph."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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


class GraphMeta(BaseModel):
    """Summary metadata for the rendered graph."""

    model_config = ConfigDict(strict=True)

    node_count: int
    edge_count: int
    integration_count: int
    business_processes: list[str]
    brands: list[str]


class GraphResponse(BaseModel):
    """Full graph payload returned by the catalog graph endpoint."""

    model_config = ConfigDict(strict=True)

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta: GraphMeta
