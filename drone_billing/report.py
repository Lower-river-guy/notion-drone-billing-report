"""Excel report generation via openpyxl — Samsara-style accounting layout."""

from __future__ import annotations

from calendar import month_name
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.worksheet import Worksheet

from drone_billing.billing import BillableFlight, ReviewItem

FONT_NAME = "Calibri"
ROW_HEIGHT = 18
TITLE_ROW = 1
HEADER_ROW = 3
MONEY_FORMAT = '"$"#,##0.00'
DATE_FORMAT = "MM/DD/YYYY"
ACRES_FORMAT = "#,##0"
TOTAL_LABEL = "TOTAL DRONE BILLING"

BILLING_REPORT_HEADERS = [
    "PROJECT #",
    "PROJECT DESCRIPTION",
    "FLIGHT DATE",
    "FLIGHT TYPE",
    "DRONE",
    "ACRES",
    "STATUS",
    "COST TIER",
    "$ BILLED AMOUNT",
]

FLIGHT_DETAIL_HEADERS = [
    "Flight Date",
    "Project Number",
    "Project Name",
    "Flight Type",
    "Drone Equipment",
    "Acres",
    "Status",
    "Cost Tier",
    "Flight Cost",
    "Notion Page ID",
    "Notion Page URL",
]

REVIEW_HEADERS = [
    "Title",
    "Project Number",
    "Project Name",
    "Flight Date",
    "Status",
    "Reason",
    "Notion Page ID",
    "Notion Page URL",
]

BILLING_COL_WIDTHS = {
    1: 14,
    2: 34,
    3: 14,
    4: 16,
    5: 16,
    6: 10,
    7: 14,
    8: 12,
    9: 18,
}

DETAIL_COL_WIDTHS = {
    1: 14,
    2: 16,
    3: 32,
    4: 16,
    5: 18,
    6: 10,
    7: 14,
    8: 12,
    9: 14,
    10: 36,
    11: 42,
}

REVIEW_COL_WIDTHS = {
    1: 36,
    2: 16,
    3: 28,
    4: 14,
    5: 14,
    6: 52,
    7: 36,
    8: 42,
}

TITLE_FONT = Font(name=FONT_NAME, bold=True, size=16, color="1F4E79")
HEADER_FONT = Font(name=FONT_NAME, bold=True, size=11, color="FFFFFF")
BODY_FONT = Font(name=FONT_NAME, size=11)
TOTAL_FONT = Font(name=FONT_NAME, bold=True, size=11)
HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
TOTAL_FILL = PatternFill("solid", fgColor="D6DCE4")
THIN = Border(
    left=Side(style="thin", color="B0B0B0"),
    right=Side(style="thin", color="B0B0B0"),
    top=Side(style="thin", color="B0B0B0"),
    bottom=Side(style="thin", color="B0B0B0"),
)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center")


def report_filename(billing_month: str) -> str:
    return f"Drone_Billing_Report_{billing_month}.xlsx"


def billing_title(billing_month: str) -> str:
    year_s, month_s = billing_month.split("-", 1)
    return f"DRONE BILLINGS - {month_name[int(month_s)]} {year_s}"


def _money(value: Decimal | None) -> float | str:
    if value is None:
        return ""
    return float(value)


def _apply_column_widths(ws: Worksheet, widths: dict[int, float]) -> None:
    for col, width in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = width


def _set_row_height(ws: Worksheet, row: int) -> None:
    ws.row_dimensions[row].height = ROW_HEIGHT


def _apply_print_setup(ws: Worksheet, header_row: int, last_col: int) -> None:
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{header_row}:{header_row}"
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.65, bottom=0.5, header=0.3, footer=0.3)
    ws.sheet_view.showGridLines = False
    ws.print_options.horizontalCentered = True
    ws.page_setup.scale = None
    last_letter = get_column_letter(last_col)
    ws.print_area = f"A1:{last_letter}{max(ws.max_row, header_row)}"


def _write_header_row(ws: Worksheet, headers: list[str], row: int) -> None:
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = THIN
    _set_row_height(ws, row)


def _style_data_cell(cell, align: Alignment, number_format: str | None = None) -> None:
    cell.font = BODY_FONT
    cell.alignment = align
    cell.border = THIN
    if number_format:
        cell.number_format = number_format


def _sorted_billable(billable: list[BillableFlight]) -> list[BillableFlight]:
    return sorted(billable, key=lambda x: (x.project_number or "", x.flight_date, x.page_id))


def _build_billing_report(ws: Worksheet, billing_month: str, billable: list[BillableFlight]) -> Decimal:
    last_col = len(BILLING_REPORT_HEADERS)
    ws.merge_cells(start_row=TITLE_ROW, start_column=1, end_row=TITLE_ROW, end_column=last_col)
    title_cell = ws.cell(row=TITLE_ROW, column=1, value=billing_title(billing_month))
    title_cell.font = TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[TITLE_ROW].height = 28
    _set_row_height(ws, 2)
    _write_header_row(ws, BILLING_REPORT_HEADERS, HEADER_ROW)
    ws.freeze_panes = "A4"

    row = HEADER_ROW + 1
    month_total = Decimal("0")
    previous_project: str | None = None
    for b in _sorted_billable(billable):
        assert b.cost.total is not None
        if previous_project is not None and b.project_number != previous_project:
            _set_row_height(ws, row)
            row += 1
        values = [
            b.project_number,
            b.project_name,
            b.flight_date,
            b.flight_type or "",
            b.drone_equipment or "",
            b.acres,
            b.status,
            b.cost.label,
            _money(b.cost.total),
        ]
        aligns = [CENTER, LEFT, CENTER, LEFT, LEFT, RIGHT, CENTER, CENTER, RIGHT]
        formats = [None, None, DATE_FORMAT, None, None, ACRES_FORMAT, None, None, MONEY_FORMAT]
        for col, (value, align, fmt) in enumerate(zip(values, aligns, formats), start=1):
            cell = ws.cell(row=row, column=col, value=value)
            _style_data_cell(cell, align, fmt)
        _set_row_height(ws, row)
        month_total += b.cost.total
        previous_project = b.project_number
        row += 1

    if billable:
        _set_row_height(ws, row)
        row += 1

    for col in range(1, last_col + 1):
        cell = ws.cell(row=row, column=col, value=None)
        cell.font = TOTAL_FONT
        cell.fill = TOTAL_FILL
        cell.border = THIN
        cell.alignment = CENTER if col != last_col else RIGHT
    ws.cell(row=row, column=1, value=TOTAL_LABEL)
    total_cell = ws.cell(row=row, column=last_col, value=_money(month_total))
    total_cell.number_format = MONEY_FORMAT
    total_cell.font = TOTAL_FONT
    total_cell.fill = TOTAL_FILL
    total_cell.alignment = RIGHT
    _set_row_height(ws, row)

    _apply_column_widths(ws, BILLING_COL_WIDTHS)
    _apply_print_setup(ws, HEADER_ROW, last_col)
    return month_total


def _build_flight_detail(ws: Worksheet, billable: list[BillableFlight]) -> None:
    _write_header_row(ws, FLIGHT_DETAIL_HEADERS, 1)
    ws.freeze_panes = "A2"
    for row_idx, b in enumerate(_sorted_billable(billable), start=2):
        assert b.cost.total is not None
        values = [
            b.flight_date,
            b.project_number,
            b.project_name,
            b.flight_type or "",
            b.drone_equipment or "",
            b.acres,
            b.status,
            b.cost.label,
            _money(b.cost.total),
            b.page_id,
            b.page_url,
        ]
        aligns = [CENTER, CENTER, LEFT, LEFT, LEFT, RIGHT, CENTER, CENTER, RIGHT, LEFT, LEFT]
        formats = [DATE_FORMAT, None, None, None, None, ACRES_FORMAT, None, None, MONEY_FORMAT, None, None]
        for col, (value, align, fmt) in enumerate(zip(values, aligns, formats), start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            _style_data_cell(cell, align, fmt)
        _set_row_height(ws, row_idx)
    _apply_column_widths(ws, DETAIL_COL_WIDTHS)
    _apply_print_setup(ws, 1, len(FLIGHT_DETAIL_HEADERS))


def _build_review(ws: Worksheet, review: list[ReviewItem]) -> None:
    _write_header_row(ws, REVIEW_HEADERS, 1)
    ws.freeze_panes = "A2"
    for row_idx, r in enumerate(sorted(review, key=lambda x: (x.project_number or "", x.title)), start=2):
        values = [
            r.title,
            r.project_number,
            r.project_name,
            r.flight_date,
            r.status or "",
            r.reason,
            r.page_id,
            r.page_url,
        ]
        aligns = [LEFT, CENTER, LEFT, CENTER, CENTER, LEFT, LEFT, LEFT]
        formats = [None, None, None, DATE_FORMAT if r.flight_date else None, None, None, None, None]
        for col, (value, align, fmt) in enumerate(zip(values, aligns, formats), start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            _style_data_cell(cell, align, fmt)
        _set_row_height(ws, row_idx)
    _apply_column_widths(ws, REVIEW_COL_WIDTHS)
    _apply_print_setup(ws, 1, len(REVIEW_HEADERS))


def build_workbook(
    billing_month: str,
    billable: list[BillableFlight],
    review: list[ReviewItem],
) -> Workbook:
    wb = Workbook()
    ws_bill = wb.active
    ws_bill.title = "Billing Report"
    _build_billing_report(ws_bill, billing_month, billable)

    ws_detail = wb.create_sheet("Flight Detail")
    _build_flight_detail(ws_detail, billable)

    ws_rev = wb.create_sheet("Review Required")
    _build_review(ws_rev, review)
    return wb


def save_workbook(wb: Workbook, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


REQUIRED_SHEETS = ("Billing Report", "Flight Detail", "Review Required")


def validate_workbook(path: Path) -> None:
    """Confirm the generated file is a usable Excel report before upload/email."""
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"Workbook is missing or empty: {path}")
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        missing = [name for name in REQUIRED_SHEETS if name not in wb.sheetnames]
        if missing:
            raise RuntimeError(f"Workbook missing required sheets: {missing}")
        report = wb["Billing Report"]
        headers = [cell.value for cell in next(report.iter_rows(min_row=HEADER_ROW, max_row=HEADER_ROW))]
        for required in ("PROJECT #", "STATUS", "$ BILLED AMOUNT"):
            if required not in headers:
                raise RuntimeError(f"Billing Report is missing required column: {required}")
        found_total = False
        for row in report.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
            if row and row[0] == TOTAL_LABEL:
                found_total = True
                break
        if not found_total:
            raise RuntimeError("Billing Report is missing TOTAL DRONE BILLING")
    finally:
        wb.close()
