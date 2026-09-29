from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from drone_billing.billing import (
    BillableFlight,
    FlightRecord,
    classify_flight,
    dedupe_flights_by_page_id,
    parse_project_number_and_name,
    process_flights,
    resolve_billing_month,
)
from drone_billing.cost_config import cost_for_acres


def _flight(**kwargs) -> FlightRecord:
    defaults = {
        "page_id": "page-1",
        "page_url": "https://app.notion.com/page1",
        "title": "1575-Mid Valley Unit4_PH2",
        "project_number": "1575",
        "project_name": "Mid Valley Unit4_PH2",
        "flight_date": date(2026, 9, 28),
        "flight_type": "Progress",
        "drone_equipment": "Wingtra Ray",
        "acres": 200,
        "status": "Completed",
        "project_relation_ids": ["proj-1"],
    }
    defaults.update(kwargs)
    return FlightRecord(**defaults)


def test_parse_project_number_and_name():
    assert parse_project_number_and_name("1575-Mid Valley", None) == ("1575", "Mid Valley")
    assert parse_project_number_and_name("NoHyphen", "Related Name") == ("NoHyphen", "Related Name")


def test_non_completed_excluded():
    f = _flight(status="Scheduled")
    b, r = classify_flight(f)
    assert b is None and r is None


def test_template_excluded_even_if_completed():
    f = _flight(title="TEMPLATE – 1588-Mesa", status="Completed")
    b, r = classify_flight(f)
    assert b is None
    assert r is not None
    assert "TEMPLATE" in r.reason


def test_placeholder_excluded():
    f = _flight(title="— PLACEHOLDER —", status="Completed")
    b, r = classify_flight(f)
    assert b is None
    assert r is not None


def test_missing_project():
    f = _flight(project_relation_ids=[])
    b, r = classify_flight(f)
    assert r is not None
    assert "Missing Project" in r.reason


def test_missing_flight_date():
    f = _flight(flight_date=None)
    b, r = classify_flight(f)
    assert r is not None
    assert "Missing Flight Date" in r.reason


def test_missing_acreage():
    f = _flight(acres=None)
    b, r = classify_flight(f)
    assert r is not None
    assert "Missing Acres" in r.reason


def test_multiple_projects():
    f = _flight(project_relation_ids=["a", "b"])
    b, r = classify_flight(f)
    assert r is not None
    assert "Multiple project" in r.reason


def test_acres_over_800():
    f = _flight(acres=801)
    b, r = classify_flight(f)
    assert r is not None
    assert "CUSTOM ESTIMATE" in r.reason


def test_billable_flight():
    f = _flight()
    b, r = classify_flight(f)
    assert b is not None
    assert r is None
    assert b.cost.total == Decimal("2442.94")


def test_duplicate_page_id_protection():
    flights = [_flight(page_id="same"), _flight(page_id="same")]
    deduped = dedupe_flights_by_page_id(flights)
    assert len(deduped) == 1


def test_monthly_grouping_and_multiple_flights_same_project():
    flights = [
        _flight(page_id="p1", flight_date=date(2026, 9, 1)),
        _flight(page_id="p2", flight_date=date(2026, 9, 15)),
        _flight(
            page_id="p3",
            flight_date=date(2026, 9, 20),
            status="Scheduled",
        ),
        _flight(page_id="p4", flight_date=date(2026, 10, 1)),
    ]
    billable, review, completed, found = process_flights(
        flights, date(2026, 9, 1), date(2026, 9, 30)
    )
    assert found == 3
    assert completed == 2
    assert len(billable) == 2
    assert len(review) == 0


def test_previous_month_la_timezone():
    now = datetime(2026, 10, 2, 2, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    label, start, end = resolve_billing_month(now=now)
    assert label == "2026-09"
    assert start == date(2026, 9, 1)
    assert end == date(2026, 9, 30)


def test_billing_month_override():
    label, start, end = resolve_billing_month(override="2026-09")
    assert label == "2026-09"
    assert start == date(2026, 9, 1)
    assert end == date(2026, 9, 30)
