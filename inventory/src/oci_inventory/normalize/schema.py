from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class Relationship(TypedDict):
    source_ocid: str
    target_ocid: str
    relation_type: str


class NormalizedRecord(TypedDict, total=False):
    ocid: str
    resourceType: str
    displayName: Optional[str]
    compartmentId: Optional[str]
    region: str
    lifecycleState: Optional[str]
    timeCreated: Optional[str]
    definedTags: Dict[str, Dict[str, Any]] | None
    freeformTags: Dict[str, str] | None
    collectedAt: str
    enrichStatus: str
    enrichError: Optional[str]
    details: Dict[str, Any]
    relationships: List[Relationship]


# Fields to include in CSV export ("report fields only")
CSV_REPORT_FIELDS: List[str] = [
    "ocid",
    "resourceType",
    "displayName",
    "compartmentId",
    "region",
    "lifecycleState",
    "timeCreated",
    "enrichStatus",
]

# Canonical field order used for stable JSON output
CANONICAL_FIELD_ORDER: List[str] = [
    "ocid",
    "resourceType",
    "displayName",
    "compartmentId",
    "region",
    "lifecycleState",
    "timeCreated",
    "definedTags",
    "freeformTags",
    "collectedAt",
    "enrichStatus",
    "enrichError",
    "details",
    "relationships",
]

# Stable output schemas for artifacts under out/<timestamp>/.
INVENTORY_REQUIRED_FIELDS: List[str] = [
    "ocid",
    "resourceType",
    "region",
    "collectedAt",
    "enrichStatus",
    "details",
    "relationships",
]

RELATIONSHIP_FIELDS: List[str] = [
    "source_ocid",
    "relation_type",
    "target_ocid",
]

RUN_SUMMARY_FIELDS: List[str] = [
    "schema_version",
    "total_discovered",
    "enriched_ok",
    "not_implemented",
    "errors",
    "counts_by_resource_type",
    "counts_by_enrich_status",
    "counts_by_resource_type_and_status",
]

GRAPH_NODE_FIELDS: List[str] = [
    "nodeId",
    "nodeType",
    "nodeCategory",
    "name",
    "region",
    "compartmentId",
    "metadata",
    "tags",
    "enrichStatus",
    "enrichError",
]

GRAPH_EDGE_FIELDS: List[str] = [
    "source_ocid",
    "target_ocid",
    "relation_type",
    "source_type",
    "target_type",
    "region",
]

OUT_SCHEMA_FIELD_DOCS: Dict[str, Dict[str, str]] = {
    "inventory.jsonl": {
        "ocid": "Unique OCI resource OCID.",
        "resourceType": "Resource type from OCI Search summary.",
        "region": "Region identifier.",
        "collectedAt": "Run-level timestamp for deterministic exports.",
        "enrichStatus": "OK, NOT_IMPLEMENTED, ERROR, or PENDING.",
        "details": "Enricher-provided metadata payload (service-specific).",
        "relationships": "List of {source_ocid, relation_type, target_ocid}.",
    },
    "relationships.jsonl": {
        "source_ocid": "Source resource OCID.",
        "relation_type": "Relationship type label.",
        "target_ocid": "Target resource OCID.",
    },
    "run_summary.json": {
        "schema_version": "Output schema version.",
        "total_discovered": "Number of normalized records.",
        "enriched_ok": "Count of records enriched successfully.",
        "not_implemented": "Count of NOT_IMPLEMENTED enrich results.",
        "errors": "Count of enrichment errors.",
        "counts_by_resource_type": "Map of resourceType -> count.",
        "counts_by_enrich_status": "Map of enrichStatus -> count.",
        "counts_by_resource_type_and_status": "Nested map of resourceType -> enrichStatus -> count.",
    },
    "graph_nodes.jsonl": {
        "nodeId": "Resource OCID.",
        "nodeType": "Categorized node type (e.g., network.Subnet).",
        "nodeCategory": "High-level class: compute/network/security/compartment/other.",
        "name": "Display label.",
        "region": "Region identifier.",
        "compartmentId": "Compartment OCID.",
        "metadata": "Sanitized metadata payload.",
        "tags": "Sanitized tag payload.",
        "enrichStatus": "Enrichment status.",
        "enrichError": "Enrichment error message, if any.",
    },
    "graph_edges.jsonl": {
        "source_ocid": "Source node OCID.",
        "target_ocid": "Target node OCID.",
        "relation_type": "Relationship type label.",
        "source_type": "Source node type.",
        "target_type": "Target node type.",
        "region": "Region identifier.",
    },
}
