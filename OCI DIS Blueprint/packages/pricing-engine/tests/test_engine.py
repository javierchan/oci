"""Focused parity and boundary tests for the pure OCI pricing engine."""

from decimal import Decimal

import pytest

from pricing_engine import (
    CurrencyRule,
    FreeTierDemand,
    PriceTier,
    PricingModel,
    PricingRequest,
    QuantityBehavior,
    QuantityRule,
    QuantityRampPhase,
    RampInterpolation,
    RampPhase,
    allocate_free_tier,
    expand_ramp,
    expand_quantity_ramp,
    price_line,
    price_line_quantity_schedule,
    price_line_schedule,
    quantize_currency,
    reconcile_monthly_results,
    select_tier,
)


USD = CurrencyRule("usd", precision=2)


def test_oic_b89639_hourly_workbook_example() -> None:
    """OIC B89639: USD 0.6452/hour x 5 packs x 744 monthly hours."""

    result = price_line(
        PricingRequest(
            sku="B89639",
            model=PricingModel.HOURLY,
            currency=USD,
            quantity=Decimal("5"),
            unit_price=Decimal("0.6452"),
            hours=Decimal("744"),
            contract_months=36,
        )
    )

    assert result.unrounded_monthly == Decimal("2400.1440")
    assert result.totals.monthly == Decimal("2400.14")
    assert result.totals.annual == Decimal("28801.73")
    assert result.totals.contract == Decimal("86405.18")


@pytest.mark.parametrize(
    ("sku", "quantity", "free_quantity", "billing_unit", "unit_price", "expected"),
    [
        ("B90617", "50", "40", "1", "0.1417", "1.42"),
        ("B90618", "3500000", "2000000", "1000000", "0.2", "0.30"),
        ("B95697", "2500000", "1000000", "1000000", "0.22", "0.33"),
    ],
)
def test_oci_free_tier_examples(
    sku: str,
    quantity: str,
    free_quantity: str,
    billing_unit: str,
    unit_price: str,
    expected: str,
) -> None:
    """Functions and Queue subtract the tenancy allocation before unit pricing."""

    result = price_line(
        PricingRequest(
            sku=sku,
            model=PricingModel.PER_ITEM,
            currency=USD,
            quantity=Decimal(quantity),
            free_tier_allocation=Decimal(free_quantity),
            billing_unit=Decimal(billing_unit),
            unit_price=Decimal(unit_price),
        )
    )

    assert result.free_quantity_applied == Decimal(free_quantity)
    assert result.totals.monthly == Decimal(expected)


def test_functions_b90617_free_40_units_then_price_per_10k_gb_seconds() -> None:
    """The 40-unit allowance represents forty 10k GB-second billing units."""

    result = price_line(
        PricingRequest(
            sku="B90617",
            model=PricingModel.PER_ITEM,
            currency=USD,
            quantity=Decimal("500000"),
            free_tier_allocation=Decimal("400000"),
            billing_unit=Decimal("10000"),
            unit_price=Decimal("0.1417"),
        )
    )

    assert result.billing_units == Decimal("10")
    assert result.unrounded_monthly == Decimal("1.4170")
    assert result.totals.monthly == Decimal("1.42")


def test_free_tier_is_allocated_once_in_input_order() -> None:
    """A shared tenancy pool cannot be independently reused by each BOM line."""

    allocation = allocate_free_tier(
        (
            FreeTierDemand("project-a", Decimal("700000")),
            FreeTierDemand("project-b", Decimal("600000")),
        ),
        Decimal("1000000"),
    )

    assert allocation.allocations[0].free_quantity == Decimal("700000")
    assert allocation.allocations[0].chargeable_quantity == Decimal("0")
    assert allocation.allocations[1].free_quantity == Decimal("300000")
    assert allocation.allocations[1].chargeable_quantity == Decimal("300000")
    assert allocation.remaining_quantity == Decimal("0")


def test_tier_boundaries_are_lower_exclusive_and_upper_inclusive() -> None:
    """The exact shared boundary belongs to the lower tier only."""

    lower = PriceTier(
        unit_price=Decimal("1.00"),
        range_min_exclusive=None,
        range_max_inclusive=Decimal("10"),
    )
    upper = PriceTier(
        unit_price=Decimal("0.80"),
        range_min_exclusive=Decimal("10"),
        range_max_inclusive=Decimal("20"),
    )

    assert select_tier(Decimal("10"), (lower, upper)) is lower
    assert select_tier(Decimal("10.0001"), (lower, upper)) is upper
    assert select_tier(Decimal("20"), (lower, upper)) is upper
    with pytest.raises(ValueError, match="no price tier"):
        select_tier(Decimal("20.0001"), (lower, upper))


def test_overlapping_tiers_are_rejected_at_selection() -> None:
    """Ambiguous source tiers never silently choose an arbitrary price."""

    tiers = (
        PriceTier(Decimal("1"), None, Decimal("10")),
        PriceTier(Decimal("2"), Decimal("5"), Decimal("15")),
    )

    with pytest.raises(ValueError, match="multiple price tiers"):
        select_tier(Decimal("8"), tiers)


def test_tiered_line_uses_chargeable_quantity_as_default_basis() -> None:
    """Free-tier allocation precedes volume-tier selection by default."""

    lower = PriceTier(Decimal("1.00"), None, Decimal("10"), "tier-1")
    upper = PriceTier(Decimal("0.80"), Decimal("10"), None, "tier-2")
    result = price_line(
        PricingRequest(
            sku="TIERED",
            model=PricingModel.PER_ITEM,
            currency=USD,
            quantity=Decimal("15"),
            free_tier_allocation=Decimal("5"),
            tiers=(lower, upper),
        )
    )

    assert result.selected_tier is lower
    assert result.totals.monthly == Decimal("10.00")


def test_explicit_zero_tier_basis_is_preserved() -> None:
    """An explicit zero driver is evidence and must not fall back to usage."""

    zero_tier = PriceTier(Decimal("1.00"), None, Decimal("0"), "zero-tier")
    usage_tier = PriceTier(Decimal("0.80"), Decimal("0"), None, "usage-tier")
    result = price_line(
        PricingRequest(
            sku="EXPLICIT-ZERO",
            model=PricingModel.PER_ITEM,
            currency=USD,
            quantity=Decimal("15"),
            tiers=(zero_tier, usage_tier),
            tier_basis_quantity=Decimal("0"),
        )
    )

    assert result.selected_tier is zero_tier
    assert result.totals.monthly == Decimal("15.00")


def test_monthly_and_hour_utilized_models() -> None:
    """Monthly and utilization-adjusted hourly models remain distinct."""

    monthly = price_line(
        PricingRequest(
            sku="MONTHLY",
            model=PricingModel.MONTHLY,
            currency=USD,
            quantity=Decimal("3"),
            unit_price=Decimal("12.50"),
        )
    )
    utilized = price_line(
        PricingRequest(
            sku="UTILIZED",
            model=PricingModel.HOUR_UTILIZED,
            currency=USD,
            quantity=Decimal("2"),
            hours=Decimal("100"),
            utilization_ratio=Decimal("0.25"),
            unit_price=Decimal("0.50"),
        )
    )

    assert monthly.totals.monthly == Decimal("37.50")
    assert utilized.totals.monthly == Decimal("25.00")


def test_zero_usage_tiered_line_does_not_require_a_matching_tier() -> None:
    """A fully free or zero-usage line is valid even when tiers start above zero."""

    result = price_line(
        PricingRequest(
            sku="ZERO",
            model=PricingModel.PER_ITEM,
            currency=USD,
            quantity=Decimal("5"),
            free_tier_allocation=Decimal("5"),
            tiers=(PriceTier(Decimal("1"), Decimal("0"), Decimal("10")),),
        )
    )

    assert result.selected_tier is None
    assert result.totals.monthly == Decimal("0.00")


def test_currency_precision_and_aggregate_reconciliation() -> None:
    """Aggregate reconciliation exposes line-level rounding accumulation."""

    results = tuple(
        price_line(
            PricingRequest(
                sku=f"LINE-{index}",
                model=PricingModel.MONTHLY,
                currency=USD,
                quantity=Decimal("1"),
                unit_price=Decimal("0.004"),
            )
        )
        for index in range(3)
    )

    reconciliation = reconcile_monthly_results(results, Decimal("0.01"), USD)

    assert reconciliation.aggregate_total == Decimal("0.01")
    assert reconciliation.rounded_line_total == Decimal("0.00")
    assert reconciliation.rounding_variance == Decimal("-0.01")
    assert reconciliation.reported_variance == Decimal("0.00")
    assert reconciliation.reconciled is True


def test_currency_half_up_rounding_and_currency_mismatch() -> None:
    """Currency output uses half-up rules and rejects mixed-currency totals."""

    assert quantize_currency(Decimal("1.005"), USD) == Decimal("1.01")
    eur_result = price_line(
        PricingRequest(
            sku="EUR-LINE",
            model=PricingModel.MONTHLY,
            currency=CurrencyRule("EUR"),
            quantity=Decimal("1"),
            unit_price=Decimal("1"),
        )
    )

    with pytest.raises(ValueError, match="reconciliation currency"):
        reconcile_monthly_results((eur_result,), Decimal("1"), USD)


def test_invalid_hour_utilization_is_rejected() -> None:
    """Utilization must be an explicit ratio rather than an unbounded percentage."""

    with pytest.raises(ValueError, match="between zero and one"):
        PricingRequest(
            sku="INVALID",
            model=PricingModel.HOUR_UTILIZED,
            currency=USD,
            quantity=Decimal("1"),
            hours=Decimal("744"),
            utilization_ratio=Decimal("1.1"),
            unit_price=Decimal("1"),
        )


def test_flat_ramp_preserves_existing_contract_parity() -> None:
    """A 100% phase is identical to the pre-ramp constant monthly extension."""

    request = PricingRequest(
        sku="FLAT",
        model=PricingModel.MONTHLY,
        currency=USD,
        quantity=Decimal("3"),
        unit_price=Decimal("26.6683333333"),
        contract_months=12,
    )
    legacy = price_line(request)
    schedule = price_line_schedule(
        request,
        expand_ramp((RampPhase(1, 12, Decimal("1"), Decimal("1")),), 12),
    )

    assert schedule.periods[0].result.totals.monthly == legacy.totals.monthly
    assert schedule.annual_totals == (legacy.totals.annual,)
    assert schedule.contract_total == legacy.totals.contract


def test_delayed_linear_ramp_prices_each_month_independently() -> None:
    """Gaps stay at zero and linear phases include both declared endpoints."""

    multipliers = expand_ramp(
        (
            RampPhase(
                3,
                5,
                Decimal("0.25"),
                Decimal("0.75"),
                RampInterpolation.LINEAR,
            ),
            RampPhase(6, 6, Decimal("1"), Decimal("1")),
        ),
        6,
    )
    schedule = price_line_schedule(
        PricingRequest(
            sku="RAMP",
            model=PricingModel.MONTHLY,
            currency=USD,
            quantity=Decimal("100"),
            unit_price=Decimal("1"),
            contract_months=6,
        ),
        multipliers,
    )

    assert multipliers == (
        Decimal("0"), Decimal("0"), Decimal("0.25"),
        Decimal("0.50"), Decimal("0.75"), Decimal("1"),
    )
    assert [period.result.totals.monthly for period in schedule.periods] == [
        Decimal("0.00"), Decimal("0.00"), Decimal("25.00"),
        Decimal("50.00"), Decimal("75.00"), Decimal("100.00"),
    ]
    assert schedule.contract_total == Decimal("250.00")


def test_monthly_ramp_preserves_the_full_monthly_free_tier_allowance() -> None:
    """A partial rollout does not proportionally shrink a monthly OCI allowance."""

    schedule = price_line_schedule(
        PricingRequest(
            sku="FREE-TIER-RAMP",
            model=PricingModel.PER_ITEM,
            currency=USD,
            quantity=Decimal("500"),
            free_tier_allocation=Decimal("400"),
            unit_price=Decimal("1"),
            contract_months=2,
        ),
        (Decimal("0.25"), Decimal("1")),
    )

    assert schedule.periods[0].result.gross_quantity == Decimal("125.00")
    assert schedule.periods[0].result.free_quantity_applied == Decimal("125.00")
    assert schedule.periods[0].result.totals.monthly == Decimal("0.00")
    assert schedule.periods[1].result.free_quantity_applied == Decimal("400")
    assert schedule.periods[1].result.totals.monthly == Decimal("100.00")


def test_overlapping_or_out_of_horizon_ramps_are_rejected() -> None:
    """Ambiguous phase calendars fail before any commercial total is produced."""

    with pytest.raises(ValueError, match="overlap"):
        expand_ramp(
            (
                RampPhase(1, 3, Decimal("0.5"), Decimal("0.5")),
                RampPhase(3, 4, Decimal("1"), Decimal("1")),
            ),
            6,
        )
    with pytest.raises(ValueError, match="horizon"):
        expand_ramp((RampPhase(1, 7, Decimal("1"), Decimal("1")),), 6)


def test_explicit_package_schedule_rounds_up_each_month() -> None:
    """Package demand is captured in business units and never underprices a partial pack."""

    schedule = price_line_quantity_schedule(
        PricingRequest(
            sku="OIC-PACK",
            model=PricingModel.HOURLY,
            currency=USD,
            quantity=Decimal("1"),
            unit_price=Decimal("0.25"),
            hours=Decimal("10"),
            contract_months=3,
        ),
        (Decimal("0"), Decimal("0.2"), Decimal("1.1")),
        rule=QuantityRule(QuantityBehavior.PACKAGED, increment=Decimal("1"), minimum=Decimal("1")),
    )

    assert [period.result.gross_quantity for period in schedule.periods] == [
        Decimal("0"), Decimal("1"), Decimal("2"),
    ]
    assert [period.result.totals.monthly for period in schedule.periods] == [
        Decimal("0.00"), Decimal("2.50"), Decimal("5.00"),
    ]


def test_explicit_continuous_schedule_preserves_governed_precision() -> None:
    """Continuous usage rounds only to its governed metering increment."""

    schedule = price_line_quantity_schedule(
        PricingRequest(
            sku="REQUESTS",
            model=PricingModel.MONTHLY,
            currency=USD,
            quantity=Decimal("1"),
            unit_price=Decimal("3"),
            contract_months=2,
        ),
        (Decimal("0.0000001"), Decimal("1.2345671")),
        rule=QuantityRule(QuantityBehavior.CONTINUOUS, increment=Decimal("0.000001")),
    )

    assert [period.result.gross_quantity for period in schedule.periods] == [
        Decimal("0.000001"), Decimal("1.234568"),
    ]


def test_real_unit_linear_ramp_keeps_inactive_months_at_zero() -> None:
    """A product can activate after its environment and grow in its own billing unit."""

    quantities = expand_quantity_ramp(
        (
            QuantityRampPhase(
                3,
                5,
                Decimal("10"),
                Decimal("30"),
                RampInterpolation.LINEAR,
            ),
        ),
        6,
    )

    assert quantities == (
        Decimal("0"), Decimal("0"), Decimal("10"),
        Decimal("20"), Decimal("30"), Decimal("0"),
    )
