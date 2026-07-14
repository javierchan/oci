"""Immutable domain models for deterministic OCI pricing calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


ZERO = Decimal("0")
ONE = Decimal("1")


class PricingModel(StrEnum):
    """Supported methods for extending an OCI unit price to a monthly amount."""

    HOURLY = "hourly"
    MONTHLY = "monthly"
    PER_ITEM = "per_item"
    HOUR_UTILIZED = "hour_utilized"


class RampInterpolation(StrEnum):
    """Supported deterministic interpolation methods for deployment ramps."""

    STEP = "step"
    LINEAR = "linear"


class QuantityBehavior(StrEnum):
    """Governed commercial behavior for a captured OCI quantity."""

    PACKAGED = "packaged"
    FIXED_CAPACITY = "fixed_capacity"
    HOURLY = "hourly"
    CONTINUOUS = "continuous"
    MANUAL_MONTHLY = "manual_monthly"


@dataclass(frozen=True, slots=True)
class QuantityRule:
    """Minimum and increment used to normalize an explicit commercial quantity."""

    behavior: QuantityBehavior
    increment: Decimal = ONE
    minimum: Decimal = ZERO

    def __post_init__(self) -> None:
        if self.increment <= ZERO:
            raise ValueError("quantity increment must be greater than zero")
        if self.minimum < ZERO:
            raise ValueError("quantity minimum must be non-negative")


@dataclass(frozen=True, slots=True)
class RampPhase:
    """An inclusive contract-month interval with bounded demand multipliers."""

    start_month: int
    end_month: int
    start_multiplier: Decimal
    end_multiplier: Decimal
    interpolation: RampInterpolation = RampInterpolation.STEP

    def __post_init__(self) -> None:
        if self.start_month < 1:
            raise ValueError("ramp phase start month must be at least 1")
        if self.end_month < self.start_month:
            raise ValueError("ramp phase end month must not precede start month")
        if self.start_multiplier < ZERO or self.end_multiplier < ZERO:
            raise ValueError("ramp multipliers must be non-negative")
        if self.start_multiplier > ONE or self.end_multiplier > ONE:
            raise ValueError("ramp multipliers must not exceed 1")
        if self.interpolation is RampInterpolation.STEP and self.start_multiplier != self.end_multiplier:
            raise ValueError("step ramp phases require equal start and end multipliers")


@dataclass(frozen=True, slots=True)
class QuantityRampPhase:
    """An inclusive contract interval expressed in the real commercial unit."""

    start_month: int
    end_month: int
    start_quantity: Decimal
    end_quantity: Decimal
    interpolation: RampInterpolation = RampInterpolation.STEP

    def __post_init__(self) -> None:
        if self.start_month < 1:
            raise ValueError("quantity ramp start month must be at least 1")
        if self.end_month < self.start_month:
            raise ValueError("quantity ramp end month must not precede start month")
        if self.start_quantity < ZERO or self.end_quantity < ZERO:
            raise ValueError("quantity ramp values must be non-negative")
        if self.interpolation is RampInterpolation.STEP and self.start_quantity != self.end_quantity:
            raise ValueError("constant quantity phases require equal start and end quantities")


@dataclass(frozen=True, slots=True)
class CurrencyRule:
    """Currency code and output precision supplied by the price source."""

    code: str
    precision: int = 2

    def __post_init__(self) -> None:
        normalized_code = self.code.strip().upper()
        if len(normalized_code) != 3 or not normalized_code.isalpha():
            raise ValueError("currency code must be a three-letter alphabetic code")
        if self.precision < 0:
            raise ValueError("currency precision must be non-negative")
        object.__setattr__(self, "code", normalized_code)


@dataclass(frozen=True, slots=True)
class PriceTier:
    """A volume tier whose lower bound is exclusive and upper bound inclusive."""

    unit_price: Decimal
    range_min_exclusive: Decimal | None = None
    range_max_inclusive: Decimal | None = None
    source_item_id: str | None = None

    def __post_init__(self) -> None:
        if self.unit_price < ZERO:
            raise ValueError("tier unit price must be non-negative")
        if (
            self.range_min_exclusive is not None
            and self.range_max_inclusive is not None
            and self.range_min_exclusive >= self.range_max_inclusive
        ):
            raise ValueError("tier rangeMin must be less than rangeMax")


@dataclass(frozen=True, slots=True)
class FreeTierDemand:
    """One ordered claim against a shared free-tier allocation pool."""

    reference: str
    quantity: Decimal

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("free-tier demand reference is required")
        if self.quantity < ZERO:
            raise ValueError("free-tier demand quantity must be non-negative")


@dataclass(frozen=True, slots=True)
class FreeTierAllocation:
    """Deterministic allocation result for one free-tier demand."""

    reference: str
    requested_quantity: Decimal
    free_quantity: Decimal
    chargeable_quantity: Decimal


@dataclass(frozen=True, slots=True)
class FreeTierAllocationResult:
    """Ordered allocations plus the unused remainder of the shared pool."""

    allocations: tuple[FreeTierAllocation, ...]
    initial_quantity: Decimal
    remaining_quantity: Decimal


@dataclass(frozen=True, slots=True)
class PricingRequest:
    """Complete immutable input for pricing one monthly OCI BOM line."""

    sku: str
    model: PricingModel
    currency: CurrencyRule
    quantity: Decimal
    unit_price: Decimal | None = None
    billing_unit: Decimal = ONE
    hours: Decimal | None = None
    utilization_ratio: Decimal | None = None
    free_tier_allocation: Decimal = ZERO
    tiers: tuple[PriceTier, ...] = ()
    tier_basis_quantity: Decimal | None = None
    annual_active_months: int = 12
    contract_months: int = 12

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise ValueError("sku is required")
        if self.quantity < ZERO:
            raise ValueError("quantity must be non-negative")
        if self.unit_price is not None and self.unit_price < ZERO:
            raise ValueError("unit price must be non-negative")
        if self.billing_unit <= ZERO:
            raise ValueError("billing unit must be greater than zero")
        if self.hours is not None and self.hours < ZERO:
            raise ValueError("hours must be non-negative")
        if self.free_tier_allocation < ZERO:
            raise ValueError("free-tier allocation must be non-negative")
        if self.tier_basis_quantity is not None and self.tier_basis_quantity < ZERO:
            raise ValueError("tier basis quantity must be non-negative")
        if self.utilization_ratio is not None and not ZERO <= self.utilization_ratio <= ONE:
            raise ValueError("utilization ratio must be between zero and one")
        if self.annual_active_months < 0 or self.annual_active_months > 12:
            raise ValueError("annual active months must be between zero and 12")
        if self.contract_months < 0:
            raise ValueError("contract months must be non-negative")
        if self.unit_price is None and not self.tiers:
            raise ValueError("either unit price or tiers are required")
        if self.unit_price is not None and self.tiers:
            raise ValueError("unit price and tiers are mutually exclusive")
        if self.model in (PricingModel.HOURLY, PricingModel.HOUR_UTILIZED) and self.hours is None:
            raise ValueError(f"hours are required for {self.model.value} pricing")
        if self.model is PricingModel.HOUR_UTILIZED and self.utilization_ratio is None:
            raise ValueError("utilization ratio is required for hour-utilized pricing")


@dataclass(frozen=True, slots=True)
class PriceTotals:
    """Monthly, annual, and contract totals at currency output precision."""

    monthly: Decimal
    annual: Decimal
    contract: Decimal


@dataclass(frozen=True, slots=True)
class PricingResult:
    """Explainable result for a single monthly OCI BOM line."""

    sku: str
    model: PricingModel
    currency: str
    gross_quantity: Decimal
    free_quantity_applied: Decimal
    chargeable_quantity: Decimal
    billing_units: Decimal
    unit_price: Decimal
    unrounded_monthly: Decimal
    totals: PriceTotals
    selected_tier: PriceTier | None
    formula: str
    inputs: dict[str, str]


@dataclass(frozen=True, slots=True)
class ScheduledPricePeriod:
    """One explainable priced month in a deployment schedule."""

    period_index: int
    multiplier: Decimal
    result: PricingResult


@dataclass(frozen=True, slots=True)
class ScheduledPricingResult:
    """Monthly line results and horizon totals for a deployment schedule."""

    periods: tuple[ScheduledPricePeriod, ...]
    annual_totals: tuple[Decimal, ...]
    contract_total: Decimal


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Comparison of calculated and reported totals in one currency."""

    currency: str
    aggregate_total: Decimal
    rounded_line_total: Decimal
    reported_total: Decimal
    rounding_variance: Decimal
    reported_variance: Decimal
    tolerance: Decimal
    reconciled: bool
