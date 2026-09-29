from decimal import Decimal

from drone_billing.cost_config import (
    CUSTOM_ESTIMATE_REQUIRED,
    MISSING_ACREAGE_REVIEW,
    TIER_1,
    TIER_2,
    TIER_3,
    TIER_4,
    cost_for_acres,
)


def test_tier_totals_exact():
    assert TIER_1.total == Decimal("2500.00")
    assert TIER_1.billing_total == Decimal("2500.00")
    assert TIER_1.line_items.total == Decimal("2442.94")
    assert TIER_2.total == Decimal("2930.68")
    assert TIER_3.total == Decimal("3805.99")
    assert TIER_4.total == Decimal("6233.02")


def test_boundary_acres():
    cases = {
        0: Decimal("2500.00"),
        1: Decimal("2500.00"),
        200: Decimal("2500.00"),
        201: Decimal("2930.68"),
        300: Decimal("2930.68"),
        301: Decimal("3805.99"),
        500: Decimal("3805.99"),
        501: Decimal("6233.02"),
        800: Decimal("6233.02"),
    }
    for acres, expected in cases.items():
        result = cost_for_acres(acres)
        assert result.total == expected
        assert result.tier is not None


def test_over_800_custom_estimate():
    result = cost_for_acres(801)
    assert result.total is None
    assert result.label == CUSTOM_ESTIMATE_REQUIRED


def test_missing_acreage():
    result = cost_for_acres(None)
    assert result.total is None
    assert result.label == MISSING_ACREAGE_REVIEW


def test_tier1_boundaries():
    at_200 = cost_for_acres(200)
    assert at_200.total == Decimal("2500.00")
    assert at_200.tier_number == 1
    assert at_200.label == "Tier 1"

    at_201 = cost_for_acres(201)
    assert at_201.total == Decimal("2930.68")
    assert at_201.tier_number == 2
    assert at_201.label == "Tier 2"
