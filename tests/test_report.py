from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from drone_billing.billing import BillableFlight, ReviewItem, SummaryRow, build_monthly_summary
from drone_billing.cost_config import cost_for_acres
from drone_billing.report import build_workbook, report_filename, save_workbook


def test_workbook_generation(tmp_path: Path):
    cost = cost_for_acres(200)
    billable = [
        BillableFlight(
            page_id="p1",
            page_url="https://app.notion.com/p1",
            title="1575-Mid Valley",
            project_number="1575",
            project_name="Mid Valley",
            flight_date=date(2026, 9, 28),
            flight_type="Progress",
            drone_equipment="Wingtra Ray",
            acres=200,
            cost=cost,
        )
    ]
    summary = build_monthly_summary("2026-09", billable, [])
    wb = build_workbook("2026-09", summary, billable, [])
    path = save_workbook(wb, tmp_path / report_filename("2026-09"))

    loaded = load_workbook(path)
    assert "Monthly Summary" in loaded.sheetnames
    assert "Flight Detail" in loaded.sheetnames
    assert "Review Required" in loaded.sheetnames

    ws = loaded["Monthly Summary"]
    assert ws.cell(row=2, column=1).value == "2026-09"
    assert ws.cell(row=2, column=4).value == 200
    assert float(ws.cell(row=2, column=6).value) == 2500.00
    assert float(ws.cell(row=2, column=7).value) == 2500.00

    detail = loaded["Flight Detail"]
    assert detail.cell(row=2, column=1).value == "2026-09-28"
    assert float(detail.cell(row=2, column=8).value) == 2500.00


def test_review_sheet(tmp_path: Path):
    review = [
        ReviewItem(
            page_id="r1",
            page_url="https://app.notion.com/r1",
            title="TEMPLATE x",
            reason="Title starts with TEMPLATE (not billable)",
        )
    ]
    wb = build_workbook("2026-09", [], [], review)
    path = save_workbook(wb, tmp_path / "test.xlsx")
    loaded = load_workbook(path)
    ws = loaded["Review Required"]
    assert ws.max_row >= 2
    assert "TEMPLATE" in str(ws.cell(row=2, column=5).value)
