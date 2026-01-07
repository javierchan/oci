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