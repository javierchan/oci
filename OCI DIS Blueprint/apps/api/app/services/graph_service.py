"""Dependency graph service for system-to-system catalog relationships."""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CatalogIntegration
from app.schemas.graph import GraphEdge, GraphMeta, GraphNode, GraphResponse


def _dominant_qa_status(counts: dict[str, int]) -> str:
    if not counts:
        return "PENDING"
    return max(sorted(counts), key=lambda status: counts[status])


async def compute_graph(
    project_id: str,
    business_process: Optional[str],
    brand: Optional[str],
    qa_status: Optional[str],
    db: AsyncSession,
) -> GraphResponse:
    """Build a filtered system dependency graph from catalog integrations."""

    query = select(CatalogIntegration).where(CatalogIntegration.project_id == project_id)
    if business_process:
        query = query.where(CatalogIntegration.business_process == business_process)
    if brand:
        query = query.where(CatalogIntegration.brand == brand)
    if qa_status:
        query = query.where(CatalogIntegration.qa_status == qa_status)

    rows = (
        await db.scalars(
            query.order_by(CatalogIntegration.seq_number, CatalogIntegration.created_at, CatalogIntegration.id)
        )
    ).all()

    node_state: dict[str, dict[str, object]] = {}
    edge_state: dict[tuple[str, str], dict[str, object]] = {}
    graph_brands: set[str] = set()
    graph_business_processes: set[str] = set()
    contributing_rows = 0

    for row in rows:
        if row.source_system is None or row.destination_system is None:
            continue
        source = row.source_system.strip()
        target = row.destination_system.strip()
        if not source or not target:
            continue

        contributing_rows += 1
        if row.brand:
            graph_brands.add(row.brand)
        if row.business_process:
            graph_business_processes.add(row.business_process)

        for node_id, is_source in ((source, True), (target, False)):
            current = node_state.setdefault(
                node_id,
                {
                    "label": node_id,
                    "integration_count": 0,
                    "as_source_count": 0,
                    "as_destination_count": 0,
                    "brands": set(),
                    "business_processes": set(),
                },
            )
            current["integration_count"] = int(current["integration_count"]) + 1
            if is_source:
                current["as_source_count"] = int(current["as_source_count"]) + 1
            else:
                current["as_destination_count"] = int(current["as_destination_count"]) + 1
            if row.brand:
                current_brands = current["brands"]
                assert isinstance(current_brands, set)
                current_brands.add(row.brand)
            if row.business_process:
                current_processes = current["business_processes"]
                assert isinstance(current_processes, set)
                current_processes.add(row.business_process)

        edge_key = (source, target)
        edge = edge_state.setdefault(
            edge_key,
            {
                "integration_ids": [],
                "integration_names": [],
                "integration_qa_statuses": [],
                "business_processes": set(),
                "patterns": set(),
                "qa_statuses": defaultdict(int),
            },
        )
        edge["integration_ids"].append(row.id)
        edge["integration_names"].append(row.interface_name or row.interface_id or row.id)
        edge["integration_qa_statuses"].append(row.qa_status or "PENDING")
        if row.business_process:
            edge_business_processes = edge["business_processes"]
            assert isinstance(edge_business_processes, set)
            edge_business_processes.add(row.business_process)
        if row.selected_pattern:
            edge_patterns = edge["patterns"]
            assert isinstance(edge_patterns, set)
            edge_patterns.add(row.selected_pattern)
        edge_qa_statuses = edge["qa_statuses"]
        assert isinstance(edge_qa_statuses, defaultdict)
        edge_qa_statuses[row.qa_status or "PENDING"] += 1

    nodes = [
        GraphNode(
            id=node_id,
            label=str(state["label"]),
            integration_count=int(state["integration_count"]),
            as_source_count=int(state["as_source_count"]),
            as_destination_count=int(state["as_destination_count"]),
            brands=sorted(cast_set(state["brands"])),
            business_processes=sorted(cast_set(state["business_processes"])),
        )
        for node_id, state in sorted(node_state.items())
    ]

    edges = []
    for (source, target), state in sorted(edge_state.items()):
        qa_counts_default = state["qa_statuses"]
        assert isinstance(qa_counts_default, defaultdict)
        qa_counts = {key: int(value) for key, value in qa_counts_default.items()}
        edges.append(
            GraphEdge(
                id=f"{source}__{target}",
                source=source,
                target=target,
                integration_count=len(cast_list(state["integration_ids"])),
                integration_ids=list(cast_list(state["integration_ids"])),
                integration_names=list(cast_list(state["integration_names"])),
                integration_qa_statuses=list(cast_list(state["integration_qa_statuses"])),
                business_processes=sorted(cast_set(state["business_processes"])),
                patterns=sorted(cast_set(state["patterns"])),
                qa_statuses=qa_counts,
                dominant_qa_status=_dominant_qa_status(qa_counts),
            )
        )

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        meta=GraphMeta(
            node_count=len(nodes),
            edge_count=len(edges),
            integration_count=contributing_rows,
            business_processes=sorted(graph_business_processes),
            brands=sorted(graph_brands),
        ),
    )


def cast_list(value: object) -> list[str]:
    """Narrow a list payload stored in an aggregation dictionary."""

    assert isinstance(value, list)
    return [str(item) for item in value]


def cast_set(value: object) -> set[str]:
    """Narrow a set payload stored in an aggregation dictionary."""

    assert isinstance(value, set)
    return {str(item) for item in value}
