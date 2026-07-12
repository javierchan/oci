"""Pure Decimal-based calculations for OCI pricing and BOM reconciliation."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

from .models import (
    ONE,
    ZERO,
    CurrencyRule,
    FreeTierAllocation,
    FreeTierAllocationResult,
    FreeTierDemand,
    PriceTier,
    PriceTotals,
    PricingModel,
    PricingRequest,
    PricingResult,
    ReconciliationResult,
)


def currency_quantum(currency: CurrencyRule) -> Decimal:
    """Return the smallest representable amount for a currency rule."""

    return ONE.scaleb(-currency.precision)


def quantize_currency(amount: Decimal, currency: CurrencyRule) -> Decimal:
    """Round an amount at the output boundary using commercial half-up rounding."""

    return amount.quantize(currency_quantum(currency), rounding=ROUND_HALF_UP)


def select_tier(quantity: Decimal, tiers: Sequence[PriceTier]) -> PriceTier:
    """Select the sole tier satisfying rangeMin < quantity <= rangeMax."""

    if quantity < ZERO:
        raise ValueError("tier quantity must be non-negative")
    if not tiers:
        raise ValueError("at least one tier is required")

    matches = tuple(
        tier
        for tier in tiers
        if (tier.range_min_exclusive is None or quantity > tier.range_min_exclusive)
        and (tier.range_max_inclusive is None or quantity <= tier.range_max_inclusive)
    )
    if not matches:
        raise ValueError(f"no price tier covers quantity {quantity}")
    if len(matches) > 1:
        raise ValueError(f"multiple price tiers cover quantity {quantity}")
    return matches[0]


def allocate_free_tier(
    demands: Sequence[FreeTierDemand],
    available_quantity: Decimal,
) -> FreeTierAllocationResult:
    """Allocate a shared free tier in caller-provided deterministic order."""

    if available_quantity < ZERO:
        raise ValueError("available free-tier quantity must be non-negative")

    remaining = available_quantity
    allocations: list[FreeTierAllocation] = []
    for demand in demands:
        free_quantity = min(demand.quantity, remaining)
        chargeable_quantity = demand.quantity - free_quantity
        allocations.append(
            FreeTierAllocation(
                reference=demand.reference,
                requested_quantity=demand.quantity,
                free_quantity=free_quantity,
                chargeable_quantity=chargeable_quantity,
            )
        )
        remaining -= free_quantity

    return FreeTierAllocationResult(
        allocations=tuple(allocations),
        initial_quantity=available_quantity,
        remaining_quantity=remaining,
    )


def extend_totals(
    unrounded_monthly: Decimal,
    currency: CurrencyRule,
    *,
    annual_active_months: int = 12,
    contract_months: int = 12,
) -> PriceTotals:
    """Extend an unrounded monthly amount without compounding prior rounding."""

    if unrounded_monthly < ZERO:
        raise ValueError("monthly amount must be non-negative")
    if annual_active_months < 0 or annual_active_months > 12:
        raise ValueError("annual active months must be between zero and 12")
    if contract_months < 0:
        raise ValueError("contract months must be non-negative")

    return PriceTotals(
        monthly=quantize_currency(unrounded_monthly, currency),
        annual=quantize_currency(unrounded_monthly * annual_active_months, currency),
        contract=quantize_currency(unrounded_monthly * contract_months, currency),
    )


def price_line(request: PricingRequest) -> PricingResult:
    """Price one OCI BOM line and return explainable monthly and horizon totals."""

    free_quantity = min(request.quantity, request.free_tier_allocation)
    chargeable_quantity = request.quantity - free_quantity
    tier_basis = (
        request.tier_basis_quantity
        if request.tier_basis_quantity is not None
        else chargeable_quantity
    )

    selected_tier: PriceTier | None = None
    if chargeable_quantity == ZERO:
        unit_price = request.unit_price if request.unit_price is not None else ZERO
    elif request.tiers:
        selected_tier = select_tier(tier_basis, request.tiers)
        unit_price = selected_tier.unit_price
    else:
        if request.unit_price is None:
            raise ValueError("unit price is required for a non-tiered line")
        unit_price = request.unit_price

    billing_units = chargeable_quantity / request.billing_unit
    factors: list[Decimal] = [billing_units]
    formula = "(quantity - free_tier) / billing_unit * unit_price"

    if request.model is PricingModel.HOURLY:
        if request.hours is None:
            raise ValueError("hours are required for hourly pricing")
        factors.append(request.hours)
        formula += " * hours"
    elif request.model is PricingModel.HOUR_UTILIZED:
        if request.hours is None or request.utilization_ratio is None:
            raise ValueError("hours and utilization ratio are required for hour-utilized pricing")
        factors.extend((request.hours, request.utilization_ratio))
        formula += " * hours * utilization_ratio"
    elif request.model is PricingModel.MONTHLY:
        formula = "(quantity - free_tier) / billing_unit * unit_price per month"

    unrounded_monthly = unit_price
    for factor in factors:
        unrounded_monthly *= factor

    totals = extend_totals(
        unrounded_monthly,
        request.currency,
        annual_active_months=request.annual_active_months,
        contract_months=request.contract_months,
    )
    return PricingResult(
        sku=request.sku,
        model=request.model,
        currency=request.currency.code,
        gross_quantity=request.quantity,
        free_quantity_applied=free_quantity,
        chargeable_quantity=chargeable_quantity,
        billing_units=billing_units,
        unit_price=unit_price,
        unrounded_monthly=unrounded_monthly,
        totals=totals,
        selected_tier=selected_tier,
        formula=formula,
        inputs={
            "quantity": str(request.quantity),
            "free_tier_allocation": str(request.free_tier_allocation),
            "billing_unit": str(request.billing_unit),
            "hours": str(request.hours) if request.hours is not None else "",
            "utilization_ratio": (
                str(request.utilization_ratio) if request.utilization_ratio is not None else ""
            ),
            "annual_active_months": str(request.annual_active_months),
            "contract_months": str(request.contract_months),
        },
    )


def reconcile_monthly_results(
    results: Sequence[PricingResult],
    reported_total: Decimal,
    currency: CurrencyRule,
    *,
    tolerance: Decimal | None = None,
) -> ReconciliationResult:
    """Reconcile line results with a reported monthly total in one currency."""

    if reported_total < ZERO:
        raise ValueError("reported total must be non-negative")
    if any(result.currency != currency.code for result in results):
        raise ValueError("all pricing results must use the reconciliation currency")

    effective_tolerance = currency_quantum(currency) if tolerance is None else tolerance
    if effective_tolerance < ZERO:
        raise ValueError("reconciliation tolerance must be non-negative")

    aggregate_total = quantize_currency(
        sum((result.unrounded_monthly for result in results), start=ZERO),
        currency,
    )
    rounded_line_total = quantize_currency(
        sum((result.totals.monthly for result in results), start=ZERO),
        currency,
    )
    normalized_reported = quantize_currency(reported_total, currency)
    rounding_variance = rounded_line_total - aggregate_total
    reported_variance = normalized_reported - aggregate_total
    return ReconciliationResult(
        currency=currency.code,
        aggregate_total=aggregate_total,
        rounded_line_total=rounded_line_total,
        reported_total=normalized_reported,
        rounding_variance=rounding_variance,
        reported_variance=reported_variance,
        tolerance=effective_tolerance,
        reconciled=abs(reported_variance) <= effective_tolerance,
    )
