"""Pattern support matrix used to keep parity claims honest across services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PatternSupportLevel = Literal["full", "partial", "reference"]


@dataclass(frozen=True)
class PatternSupportDimensions:
    """Operational surfaces evaluated for each workbook pattern."""

    capture_selection: bool
    qa_validation: bool
    volumetry: bool
    dashboard: bool
    narratives: bool
    exports: bool


@dataclass(frozen=True)
class PatternSupportProfile:
    """Parity support profile for one pattern."""

    level: PatternSupportLevel
    badge_label: str
    summary: str
    parity_ready: bool
    dimensions: PatternSupportDimensions


FULL_SUPPORT = PatternSupportDimensions(
    capture_selection=True,
    qa_validation=True,
    volumetry=True,
    dashboard=True,
    narratives=True,
    exports=True,
)

REFERENCE_SUPPORT = PatternSupportDimensions(
    capture_selection=True,
    qa_validation=True,
    volumetry=False,
    dashboard=True,
    narratives=True,
    exports=True,
)

DEFAULT_REFERENCE_PROFILE = PatternSupportProfile(
    level="reference",
    badge_label="Reference only",
    summary=(
        "Documented and selectable from the workbook library, but this release still uses generic "
        "sizing and governance behavior instead of pattern-specific parity logic."
    ),
    parity_ready=False,
    dimensions=REFERENCE_SUPPORT,
)

PATTERN_SUPPORT_MATRIX: dict[str, PatternSupportProfile] = {
    "#01": PatternSupportProfile(
        level="full",
        badge_label="Parity ready",
        summary=(
            "Fully supported through the current synchronous OIC sizing, QA, dashboard, narrative, and export paths."
        ),
        parity_ready=True,
        dimensions=FULL_SUPPORT,
    ),
    "#02": PatternSupportProfile(
        level="full",
        badge_label="Parity ready",
        summary=(
            "Fully supported through the governed event-driven tool stack with Streaming, OIC, and Functions coverage."
        ),
        parity_ready=True,
        dimensions=FULL_SUPPORT,
    ),
    "#05": PatternSupportProfile(
        level="full",
        badge_label="Parity ready",
        summary=(
            "Fully supported through the current CDC and data-movement sizing path driven by GoldenGate and Data Integration."
        ),
        parity_ready=True,
        dimensions=FULL_SUPPORT,
    ),
}


def get_pattern_support(pattern_id: str | None) -> PatternSupportProfile:
    """Return the explicit support boundary for one pattern ID."""

    if not pattern_id:
        return DEFAULT_REFERENCE_PROFILE
    return PATTERN_SUPPORT_MATRIX.get(pattern_id, DEFAULT_REFERENCE_PROFILE)


def support_reason_code(pattern_id: str | None) -> str | None:
    """Return a QA reason when the selected pattern is still reference-only."""

    if not pattern_id:
        return None
    profile = get_pattern_support(pattern_id)
    if profile.parity_ready:
        return None
    return "PATTERN_REFERENCE_ONLY"
