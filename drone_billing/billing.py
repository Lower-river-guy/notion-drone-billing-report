"""Billing month, flight classification, tier application, grouping."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable
from zoneinfo import ZoneInfo

from drone_billing.cost_config import CostResult, cost_for_acres

LA_TZ = ZoneInfo("America/Los_Angeles")
REPORTABLE_STATUSES = frozenset({"Completed", "In Process"})

REQUIRED_NOTION_PROPERTIES = frozenset(
    {
        "Project Number",
        "Project",
        "Flight Date",
        "Flight Type",
        "Drone Equipment",
        "Acres",
        "Status",
    }
)


@dataclass
class FlightRecord:
    page_id: str
    page_url: str
    title: str
    project_number: str
    project_name: str
    flight_date: date | None
    flight_type: str | None
    drone_equipment: str | None
    acres: int | None
    status: str | None
    project_relation_ids: list[str] = field(default_factory=list)


@dataclass
class ReviewItem:
    page_id: str
    page_url: str
    title: str
    reason: str
    flight_date: date | None = None
    project_number: str = ""
    project_name: str = ""


@dataclass
class BillableFlight:
    page_id: str
    page_url: str
    title: str
    project_number: str
    project_name: str
    flight_date: date
    flight_type: str | None
    drone_equipment: str | None
    acres: int
    cost: CostResult


def resolve_billing_month(
    now: datetime | None = None,
    override: str | None = None,
) -> tuple[str, date, date]:
    """Return (YYYY-MM label, inclusive start, inclusive end) for billing month."""
    if override:
        parts = override.strip().split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid BILLING_MONTH: {override!r} (expected YYYY-MM)")
        year, month = int(parts[0]), int(parts[1])
        if month < 1 or month > 12:
            raise ValueError(f"Invalid BILLING_MONTH: {override!r}")
        start = date(year, month, 1)
        from datetime import timedelta

        if month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        return f"{year:04d}-{month:02d}", start, end

    if now is None:
        now = datetime.now(LA_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=LA_TZ)
    else:
        now = now.astimezone(LA_TZ)

    if now.month == 1:
        prev_year, prev_month = now.year - 1, 12
    else:
        prev_year, prev_month = now.year, now.month - 1

    start = date(prev_year, prev_month, 1)
    if prev_month == 12:
        end = date(prev_year, 12, 31)
    else:
        from datetime import timedelta

        end = date(prev_year, prev_month + 1, 1) - timedelta(days=1)
    return f"{prev_year:04d}-{prev_month:02d}", start, end


def parse_project_number_and_name(
    title: str,
    related_project_title: str | None,
) -> tuple[str, str]:
    stripped = (title or "").strip()
    if "-" in stripped:
        prefix, remainder = stripped.split("-", 1)
        num = prefix.strip()
        name = remainder.strip()
        if num:
            return num, name or (related_project_title or stripped)
    if related_project_title:
        return stripped, related_project_title.strip()
    return stripped, stripped


def _title_is_template(title: str) -> bool:
    return title.strip().upper().startswith("TEMPLATE")


def _title_is_placeholder(title: str) -> bool:
    return "PLACEHOLDER" in title.upper()


def classify_flight(flight: FlightRecord) -> tuple[BillableFlight | None, ReviewItem | None]:
    reasons: list[str] = []

    if flight.status not in REPORTABLE_STATUSES:
        return None, None
    if flight.status == "In Process":
        reasons.append("Status is In Process — not billed until Completed")

    if _title_is_template(flight.title):
        reasons.append("Title starts with TEMPLATE (not billable)")
    if _title_is_placeholder(flight.title):
        reasons.append("Title contains PLACEHOLDER (not billable)")
    if not flight.project_relation_ids:
        reasons.append("Missing Project relation")
    elif len(flight.project_relation_ids) > 1:
        reasons.append("Multiple project relations")
    if flight.flight_date is None:
        reasons.append("Missing Flight Date")
    if flight.acres is None:
        reasons.append("Missing Acres (rollup)")
    elif flight.acres > 800:
        reasons.append("Acres > 800 — CUSTOM ESTIMATE REQUIRED")

    if reasons:
        return None, ReviewItem(
            page_id=flight.page_id,
            page_url=flight.page_url,
            title=flight.title,
            reason="; ".join(reasons),
            flight_date=flight.flight_date,
            project_number=flight.project_number,
            project_name=flight.project_name,
        )

    cost = cost_for_acres(flight.acres)
    if cost.total is None:
        return None, ReviewItem(
            page_id=flight.page_id,
            page_url=flight.page_url,
            title=flight.title,
            reason=cost.label,
            flight_date=flight.flight_date,
            project_number=flight.project_number,
            project_name=flight.project_name,
        )

    assert flight.flight_date is not None
    assert flight.acres is not None

    return BillableFlight(
        page_id=flight.page_id,
        page_url=flight.page_url,
        title=flight.title,
        project_number=flight.project_number,
        project_name=flight.project_name,
        flight_date=flight.flight_date,
        flight_type=flight.flight_type,
        drone_equipment=flight.drone_equipment,
        acres=flight.acres,
        cost=cost,
    ), None


def dedupe_flights_by_page_id(
    flights: Iterable[FlightRecord],
) -> list[FlightRecord]:
    seen: dict[str, FlightRecord] = {}
    for f in flights:
        seen[f.page_id] = f
    return list(seen.values())


@dataclass
class ProcessResult:
    billable: list[BillableFlight]
    review: list[ReviewItem]
    completed_in_month: int
    in_process_in_month: int
    flights_found: int

    def __iter__(self):
        yield self.billable
        yield self.review
        yield self.completed_in_month
        yield self.flights_found


def process_flights(
    flights: Iterable[FlightRecord],
    billing_start: date,
    billing_end: date,
) -> ProcessResult:
    """Filter by month, dedupe, classify reportable flights."""
    unique = dedupe_flights_by_page_id(flights)

    in_month = [
        f
        for f in unique
        if f.status in REPORTABLE_STATUSES
        and f.flight_date is not None
        and billing_start <= f.flight_date <= billing_end
    ]
    missing_date_reportable = [
        f for f in unique if f.status in REPORTABLE_STATUSES and f.flight_date is None
    ]

    billable: list[BillableFlight] = []
    review: list[ReviewItem] = []
    completed_in_month = 0
    in_process_in_month = 0

    for f in in_month:
        if f.status == "Completed":
            completed_in_month += 1
        elif f.status == "In Process":
            in_process_in_month += 1
        b, r = classify_flight(f)
        if b:
            billable.append(b)
        elif r:
            review.append(r)

    for f in missing_date_reportable:
        _, r = classify_flight(f)
        if r:
            review.append(r)

    return ProcessResult(
        billable=billable,
        review=review,
        completed_in_month=completed_in_month,
        in_process_in_month=in_process_in_month,
        flights_found=len(in_month) + len(missing_date_reportable),
    )


@dataclass
class SummaryRow:
    billing_month: str
    project_number: str
    project_name: str
    acres: int
    completed_flights: int
    cost_per_flight: Decimal
    total_billing_cost: Decimal
    review_note: str | None = None


def build_monthly_summary(
    billing_month: str,
    billable: list[BillableFlight],
    review: list[ReviewItem],
) -> list[SummaryRow]:
    """Group by project + acres + cost; flag incompatible acres per project."""
    from collections import defaultdict

    by_project: dict[str, list[BillableFlight]] = defaultdict(list)
    for b in billable:
        key = f"{b.project_number}|{b.project_name}"
        by_project[key].append(b)

    rows: list[SummaryRow] = []

    for key, flights in sorted(by_project.items()):
        project_number = flights[0].project_number
        project_name = flights[0].project_name
        acre_cost_groups: dict[tuple[int, Decimal], list[BillableFlight]] = defaultdict(list)
        for fl in flights:
            assert fl.cost.total is not None
            acre_cost_groups[(fl.acres, fl.cost.total)].append(fl)

        unique_acres = {fl.acres for fl in flights}
        review_note = None
        if len(unique_acres) > 1:
            review_note = "Conflicting acres/costs across flights — review required"

        for (acres, cost_per), group in sorted(acre_cost_groups.items()):
            count = len(group)
            rows.append(
                SummaryRow(
                    billing_month=billing_month,
                    project_number=project_number,
                    project_name=project_name,
                    acres=acres,
                    completed_flights=count,
                    cost_per_flight=cost_per,
                    total_billing_cost=cost_per * count,
                    review_note=review_note,
                )
            )

    return rows
