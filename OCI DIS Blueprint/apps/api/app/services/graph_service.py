"""Dependency graph service for system-to-system catalog relationships."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CatalogIntegration
from app.schemas.graph import GraphEdge, GraphIntegrationSummary, GraphMeta, GraphNode, GraphResponse


def _dominant_qa_status(counts: dict[str, int]) -> str:
    if not counts:
        return "PENDING"
    return max(sorted(counts), key=lambda status: counts[status])


def _risk_qa_status(counts: dict[str, int]) -> str:
    """Return the most severe QA state represented on an edge."""

    for status in ("PENDING", "REVISAR", "OK"):
        if counts.get(status, 0) > 0:
            return status
    return "PENDING"


def _interaction_mode(row: CatalogIntegration) -> str:
    """Classify interaction mode from governed catalog fields without pattern-name inference."""

    text = " ".join(value for value in (row.type, row.trigger_type) if value).lower()
    asynchronous_terms = ("async", "event", "batch", "cdc", "queue", "pub", "stream", "webhook", "schedule")
    synchronous_terms = ("sync", "request-reply", "request reply", "rest", "soap")
    if any(term in text for term in asynchronous_terms):
        return "ASYNCHRONOUS"
    if any(term in text for term in synchronous_terms):
        return "SYNCHRONOUS"
    return "UNSPECIFIED"


def _combined_interaction_mode(modes: set[str]) -> str:
    """Collapse row interaction modes into one edge-level presentation value."""

    known_modes = modes - {"UNSPECIFIED"}
    if len(known_modes) > 1:
        return "MIXED"
    if known_modes:
        return next(iter(known_modes))
    return "UNSPECIFIED"


def _business_process_family(value: str) -> str:
    """Extract the reusable process family from a detailed source-to-target process label."""

    return value.split(" — ", 1)[0].strip()


async def compute_graph(
    project_id: str,
    business_process: Optional[str],
    business_process_family: Optional[str],
    brand: Optional[str],
    qa_status: Optional[str],
    db: AsyncSession,
) -> GraphResponse:
    """Build a filtered system dependency graph from catalog integrations."""

    query = select(CatalogIntegration).where(CatalogIntegration.project_id == project_id)
    if business_process:
        query = query.where(CatalogIntegration.business_process == business_process)
    if business_process_family:
        query = query.where(CatalogIntegration.business_process.like(f"{business_process_family}%"))
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
    graph_business_process_families: set[str] = set()
    contributing_rows = 0
    latest_updated_at = None
    executions_coverage = 0
    payload_coverage = 0

    for row in rows:
        if row.source_system is None or row.destination_system is None:
            continue
        source = row.source_system.strip()
        target = row.destination_system.strip()
        if not source or not target:
            continue

        contributing_rows += 1
        latest_updated_at = max(latest_updated_at, row.updated_at) if latest_updated_at else row.updated_at
        executions_coverage += int(row.executions_per_day is not None)
        payload_coverage += int(row.payload_per_hour_kb is not None)
        if row.brand:
            graph_brands.add(row.brand)
        if row.business_process:
            graph_business_processes.add(row.business_process)
            graph_business_process_families.add(_business_process_family(row.business_process))

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
                    "owners": set(),
                    "technologies": set(),
                },
            )
            current["integration_count"] = int(cast(Any, current["integration_count"])) + 1
            if is_source:
                current["as_source_count"] = int(cast(Any, current["as_source_count"])) + 1
            else:
                current["as_destination_count"] = int(cast(Any, current["as_destination_count"])) + 1
            if row.brand:
                current_brands = current["brands"]
                assert isinstance(current_brands, set)
                current_brands.add(row.brand)
            if row.business_process:
                current_processes = current["business_processes"]
                assert isinstance(current_processes, set)
                current_processes.add(row.business_process)
            owner = row.source_owner if is_source else row.destination_owner
            technology = row.source_technology if is_source else row.destination_technology_1
            if owner:
                current_owners = current["owners"]
                assert isinstance(current_owners, set)
                current_owners.add(owner)
            if technology:
                current_technologies = current["technologies"]
                assert isinstance(current_technologies, set)
                current_technologies.add(technology)

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
                "interaction_modes": set(),
                "total_executions_per_day": 0.0,
                "total_payload_per_hour_kb": 0.0,
                "executions_coverage": 0,
                "payload_coverage": 0,
                "last_updated_at": row.updated_at,
                "integrations": [],
            },
        )
        cast(list[str], edge["integration_ids"]).append(row.id)
        cast(list[str], edge["integration_names"]).append(row.interface_name or row.interface_id or row.id)
        cast(list[str], edge["integration_qa_statuses"]).append(row.qa_status or "PENDING")
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
        interaction_mode = _interaction_mode(row)
        edge_interaction_modes = edge["interaction_modes"]
        assert isinstance(edge_interaction_modes, set)
        edge_interaction_modes.add(interaction_mode)
        if row.executions_per_day is not None:
            edge["total_executions_per_day"] = float(cast(Any, edge["total_executions_per_day"])) + row.executions_per_day
            edge["executions_coverage"] = int(cast(Any, edge["executions_coverage"])) + 1
        if row.payload_per_hour_kb is not None:
            edge["total_payload_per_hour_kb"] = float(cast(Any, edge["total_payload_per_hour_kb"])) + row.payload_per_hour_kb
            edge["payload_coverage"] = int(cast(Any, edge["payload_coverage"])) + 1
        edge["last_updated_at"] = max(cast(Any, edge["last_updated_at"]), row.updated_at)
        edge_integrations = edge["integrations"]
        assert isinstance(edge_integrations, list)
        edge_integrations.append(
            GraphIntegrationSummary(
                id=row.id,
                name=row.interface_name or row.interface_id or row.id,
                qa_status=row.qa_status or "PENDING",
                owner=row.owner,
                pattern=row.selected_pattern,
                trigger_type=row.trigger_type,
                interaction_mode=interaction_mode,
                executions_per_day=row.executions_per_day,
                payload_per_hour_kb=row.payload_per_hour_kb,
                updated_at=row.updated_at,
            )
        )

    nodes = [
        GraphNode(
            id=node_id,
            label=str(state["label"]),
            integration_count=int(cast(Any, state["integration_count"])),
            as_source_count=int(cast(Any, state["as_source_count"])),
            as_destination_count=int(cast(Any, state["as_destination_count"])),
            brands=sorted(cast_set(state["brands"])),
            business_processes=sorted(cast_set(state["business_processes"])),
            owners=sorted(cast_set(state["owners"])),
            technologies=sorted(cast_set(state["technologies"])),
        )
        for node_id, state in sorted(node_state.items())
    ]

    edges = []
    for (source, target), state in sorted(edge_state.items()):
        qa_counts_default = state["qa_statuses"]
        assert isinstance(qa_counts_default, defaultdict)
        qa_counts = {key: int(value) for key, value in qa_counts_default.items()}
        risk_status = _risk_qa_status(qa_counts)
        interaction_modes = state["interaction_modes"]
        assert isinstance(interaction_modes, set)
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
                risk_qa_status=risk_status,
                risk_score=(qa_counts.get("PENDING", 0) * 100) + (qa_counts.get("REVISAR", 0) * 10) + len(cast_list(state["integration_ids"])),
                interaction_mode=_combined_interaction_mode({str(mode) for mode in interaction_modes}),
                total_executions_per_day=float(cast(Any, state["total_executions_per_day"])),
                total_payload_per_hour_kb=float(cast(Any, state["total_payload_per_hour_kb"])),
                executions_coverage=int(cast(Any, state["executions_coverage"])),
                payload_coverage=int(cast(Any, state["payload_coverage"])),
                last_updated_at=cast(Any, state["last_updated_at"]),
                integrations=cast(list[GraphIntegrationSummary], state["integrations"]),
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
            business_process_families=sorted(graph_business_process_families),
            brands=sorted(graph_brands),
            latest_updated_at=latest_updated_at,
            executions_coverage=executions_coverage,
            payload_coverage=payload_coverage,
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
