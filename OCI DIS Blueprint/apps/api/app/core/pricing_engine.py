"""Helpers that make the pure pricing-engine package importable from the API."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_pricing_engine_path() -> None:
    """Add the pricing-engine src directory to ``sys.path`` locally and in Docker."""

    resolved_file = Path(__file__).resolve()
    candidates = [Path("/pricing-engine/src")]
    candidates.extend(parent / "packages" / "pricing-engine" / "src" for parent in resolved_file.parents)
    for candidate in candidates:
        if candidate.exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            return
    raise RuntimeError("Unable to locate packages/pricing-engine/src for API imports.")


_ensure_pricing_engine_path()

from pricing_engine import (  # noqa: E402
    CurrencyRule,
    PriceTier,
    PricingModel,
    PricingRequest,
    PricingResult,
    QuantityBehavior,
    QuantityRule,
    QuantityRampPhase,
    RampInterpolation,
    RampPhase,
    ScheduledPricingResult,
    expand_ramp,
    expand_quantity_ramp,
    normalize_quantity,
    price_line,
    price_line_quantity_schedule,
    price_line_schedule,
)

__all__ = [
    "CurrencyRule",
    "PriceTier",
    "PricingModel",
    "PricingRequest",
    "PricingResult",
    "QuantityBehavior",
    "QuantityRule",
    "QuantityRampPhase",
    "RampInterpolation",
    "RampPhase",
    "ScheduledPricingResult",
    "expand_ramp",
    "expand_quantity_ramp",
    "normalize_quantity",
    "price_line",
    "price_line_quantity_schedule",
    "price_line_schedule",
]
