"""Centralized drone billing cost tiers and line-item breakdown."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

CUSTOM_ESTIMATE_REQUIRED: Final[str] = "CUSTOM ESTIMATE REQUIRED"
MISSING_ACREAGE_REVIEW: Final[str] = "MISSING ACREAGE — REVIEW REQUIRED"


@dataclass(frozen=True)
class CostLineItems:
    drone_cost: Decimal
    aero_points: Decimal
    field_crew: Decimal
    field_crew_ot: Decimal
    propeller_platform: Decimal
    propeller_processing: Decimal
    office_processing: Decimal
    consumables_targets: Decimal
    gps_equipment: Decimal

    @property
    def total(self) -> Decimal:
        return (
            self.drone_cost
            + self.aero_points
            + self.field_crew
            + self.field_crew_ot
            + self.propeller_platform
            + self.propeller_processing
            + self.office_processing
            + self.consumables_targets
            + self.gps_equipment
        )


@dataclass(frozen=True)
class CostTier:
    tier_number: int
    min_acres: int
    max_acres: int
    line_items: CostLineItems
    billing_total: Decimal

    @property
    def total(self) -> Decimal:
        return self.billing_total


def _d(value: str) -> Decimal:
    return Decimal(value)


TIER_1 = CostTier(
    tier_number=1,
    min_acres=0,
    max_acres=200,
    billing_total=_d("2442.94"),
    line_items=CostLineItems(
        drone_cost=_d("292.93"),
        aero_points=_d("36.67"),
        field_crew=_d("1242.08"),
        field_crew_ot=_d("0.00"),
        propeller_platform=_d("37.44"),
        propeller_processing=_d("360.00"),
        office_processing=_d("310.52"),
        consumables_targets=_d("20.44"),
        gps_equipment=_d("142.86"),
    ),
)

TIER_2 = CostTier(
    tier_number=2,
    min_acres=201,
    max_acres=300,
    billing_total=_d("2930.68"),
    line_items=CostLineItems(
        drone_cost=_d("439.40"),
        aero_points=_d("36.67"),
        field_crew=_d("1242.08"),
        field_crew_ot=_d("0.00"),
        propeller_platform=_d("112.33"),
        propeller_processing=_d("540.00"),
        office_processing=_d("388.15"),
        consumables_targets=_d("29.20"),
        gps_equipment=_d("142.86"),
    ),
)

TIER_3 = CostTier(
    tier_number=3,
    min_acres=301,
    max_acres=500,
    billing_total=_d("3805.99"),
    line_items=CostLineItems(
        drone_cost=_d("585.87"),
        aero_points=_d("73.33"),
        field_crew=_d("1242.08"),
        field_crew_ot=_d("392.64"),
        propeller_platform=_d("149.77"),
        propeller_processing=_d("540.00"),
        office_processing=_d("621.04"),
        consumables_targets=_d("58.40"),
        gps_equipment=_d("142.86"),
    ),
)

TIER_4 = CostTier(
    tier_number=4,
    min_acres=501,
    max_acres=800,
    billing_total=_d("6233.02"),
    line_items=CostLineItems(
        drone_cost=_d("1025.27"),
        aero_points=_d("73.33"),
        field_crew=_d("2484.16"),
        field_crew_ot=_d("0.00"),
        propeller_platform=_d("224.66"),
        propeller_processing=_d("1440.00"),
        office_processing=_d("621.04"),
        consumables_targets=_d("78.84"),
        gps_equipment=_d("285.71"),
    ),
)

COST_TIERS: tuple[CostTier, ...] = (TIER_1, TIER_2, TIER_3, TIER_4)

MAX_BILLABLE_ACRES: Final[int] = 800


@dataclass(frozen=True)
class CostResult:
    tier: CostTier | None
    total: Decimal | None
    label: str
    tier_number: int | None = None


def cost_for_acres(acres: int | None) -> CostResult:
    if acres is None:
        return CostResult(tier=None, total=None, label=MISSING_ACREAGE_REVIEW)
    if acres > MAX_BILLABLE_ACRES:
        return CostResult(tier=None, total=None, label=CUSTOM_ESTIMATE_REQUIRED)
    for tier in COST_TIERS:
        if tier.min_acres <= acres <= tier.max_acres:
            return CostResult(
                tier=tier,
                total=tier.total,
                label=f"Tier {tier.tier_number}",
                tier_number=tier.tier_number,
            )
    return CostResult(tier=None, total=None, label=CUSTOM_ESTIMATE_REQUIRED)
