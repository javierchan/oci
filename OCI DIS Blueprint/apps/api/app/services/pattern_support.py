"""Pattern certification projection shared by API and product surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.calc_engine import PATTERN_CERTIFICATIONS, get_pattern_certification


PatternCertificationStatus = Literal["certified", "unverified"]


@dataclass(frozen=True)
class PatternSupportDimensions:
    """Operational surfaces covered by a pattern certification."""

    capture_selection: bool
    qa_validation: bool
    volumetry: bool
    dashboard: bool
    narratives: bool
    exports: bool


@dataclass(frozen=True)
class PatternSupportProfile:
    """Serializable certification and product-coverage profile for one pattern."""

    badge_label: str
    summary: str
    dimensions: PatternSupportDimensions
    certification_status: PatternCertificationStatus
    certification_version: str | None
    sizing_strategy: str | None
    required_evidence: tuple[str, ...]
    approved_core_tool_groups: tuple[tuple[str, ...], ...]
    approved_overlay_groups: tuple[tuple[str, ...], ...]
    commercial_service_ids: tuple[str, ...]
    external_dependencies: tuple[str, ...]
    validation_controls: tuple[str, ...]


FULL_SUPPORT = PatternSupportDimensions(
    capture_selection=True,
    qa_validation=True,
    volumetry=True,
    dashboard=True,
    narratives=True,
    exports=True,
)

UNVERIFIED_SUPPORT = PatternSupportDimensions(
    capture_selection=True,
    qa_validation=False,
    volumetry=False,
    dashboard=True,
    narratives=True,
    exports=True,
)

DEFAULT_UNVERIFIED_PROFILE = PatternSupportProfile(
    badge_label="Not certified",
    summary=(
        "This custom pattern is not covered by a versioned OCI DIS Architect certification "
        "contract. It remains selectable for documentation, but cannot produce certified sizing "
        "or architecture-readiness evidence."
    ),
    dimensions=UNVERIFIED_SUPPORT,
    certification_status="unverified",
    certification_version=None,
    sizing_strategy=None,
    required_evidence=(),
    approved_core_tool_groups=(),
    approved_overlay_groups=(),
    commercial_service_ids=(),
    external_dependencies=(),
    validation_controls=(),
)


def _certified_profile(pattern_id: str) -> PatternSupportProfile:
    certification = PATTERN_CERTIFICATIONS[pattern_id]
    return PatternSupportProfile(
        badge_label="Certified",
        summary=certification.summary,
        dimensions=FULL_SUPPORT,
        certification_status="certified",
        certification_version=certification.certification_version,
        sizing_strategy=certification.sizing_strategy,
        required_evidence=certification.required_evidence,
        approved_core_tool_groups=certification.approved_core_tool_groups,
        approved_overlay_groups=certification.approved_overlay_groups,
        commercial_service_ids=certification.commercial_service_ids,
        external_dependencies=certification.external_dependencies,
        validation_controls=certification.validation_controls,
    )


PATTERN_SUPPORT_MATRIX: dict[str, PatternSupportProfile] = {
    pattern_id: _certified_profile(pattern_id) for pattern_id in PATTERN_CERTIFICATIONS
}


def get_pattern_support(pattern_id: str | None) -> PatternSupportProfile:
    """Return the versioned certification boundary for one pattern ID."""

    if not pattern_id or get_pattern_certification(pattern_id) is None:
        return DEFAULT_UNVERIFIED_PROFILE
    return PATTERN_SUPPORT_MATRIX[pattern_id]


def support_reason_code(pattern_id: str | None) -> str | None:
    """Return a QA reason when a selected pattern has no governed certification."""

    if not pattern_id:
        return None
    if get_pattern_certification(pattern_id) is not None:
        return None
    return "PATTERN_NOT_CERTIFIED"
