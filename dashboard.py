from collections import defaultdict
from dataclasses import dataclass
from datetime import date as date_type
from insights import build_insight_rows
from models import Transaction
from sheets import SheetsClient

TRANSACTIONS_SHEET = "transactions"
DASHBOARD_SHEET = "dashboard"
AI_INSIGHT_ROW_OFFSET = 8


@dataclass(frozen=True)
class BarChartSpec:
    title: str
    category_start_index: int
    category_end_index: int
    first_series_col_index: int
    second_series_col_index: int
    anchor_row_index: int


def build_dashboard(sheets_client: SheetsClient) -> None:
    raw_rows = sheets_client.read_sheet(TRANSACTIONS_SHEET)
    transactions = _parse_transaction_rows(raw_rows)
    insight_rows = build_insight_rows(transactions)
    insight_range = None
    if insight_rows:
        insight_start = _insight_start_row_index(transactions)
        insight_range = (insight_start, insight_start + len(insight_rows))
    dashboard_rows, groups, percent_ranges, bar_charts = _build_rows_and_groups(
        transactions,
        insight_rows=insight_rows,
    )

    sheets_client.ensure_sheet_exists(DASHBOARD_SHEET)
    sheets_client.clear_and_write(DASHBOARD_SHEET, dashboard_rows, value_input_option="RAW")

    sheet_id = sheets_client.get_sheet_id(DASHBOARD_SHEET)
    sheets_client.clear_row_groups(sheet_id)
    sheets_client.clear_charts(sheet_id)
    sheets_client.clear_merges(sheet_id)
    sheets_client.unhide_rows(sheet_id, len(dashboard_rows))
    sheets_client.format_dashboard(
        sheet_id,
        len(dashboard_rows),
        percent_ranges,
        bar_charts,
        insight_range,
        dashboard_rows,
    )
    sheets_client.clear_and_write(DASHBOARD_SHEET, dashboard_rows, value_input_option="RAW")
    sheets_client.apply_row_groups(sheet_id, groups)
    sheets_client.apply_bar_charts(sheet_id, bar_charts)


def _parse_transaction_rows(rows: list[list]) -> list[Transaction]:
    if not rows:
        return []
    header = rows[0]
    if not header:
        return []
    if header[0] == "date":
        indexes = {
            "date": 0,
            "amount": 1,
            "merchant": 2,
            "category": 3,
            "source": 4,
            "memo": 5,
        }
    else:
        indexes = {
            "date": header.index("date"),
            "amount": header.index("amount"),
            "merchant": header.index("merchant_normalized"),
            "category": header.index("category"),
            "source": header.index("source"),
            "memo": header.index("memo"),
        }
    result = []
    for row in rows[1:]:
        if len(row) <= max(indexes["date"], indexes["amount"], indexes["merchant"], indexes["category"], indexes["source"]):
            continue
        result.append(Transaction(
            date=date_type.fromisoformat(row[indexes["date"]]),
            amount=int(row[indexes["amount"]]),
            merchant=row[indexes["merchant"]],
            category=row[indexes["category"]],
            source=row[indexes["source"]],
            memo=row[indexes["memo"]] if len(row) > indexes["memo"] else "",
        ))
    return result


def _build_rows_and_groups(
    transactions: list[Transaction],
    insight_rows: list[list] | None = None,
) -> tuple[list[list], list[tuple[int, int]], list[tuple[int, int]], list[BarChartSpec]]:
    by_month: dict[tuple[int, int], list[Transaction]] = defaultdict(list)
    by_year: dict[int, list[Transaction]] = defaultdict(list)
    for txn in transactions:
        by_month[(txn.date.year, txn.date.month)].append(txn)
        by_year[txn.date.year].append(txn)

    all_rows: list[list] = []
    groups: list[tuple[int, int]] = []
    percent_ranges: list[tuple[int, int]] = []
    bar_charts: list[BarChartSpec] = []

    recent_months = sorted(by_month.keys(), reverse=True)[:2]
    if len(recent_months) == 2:
        latest, previous = recent_months
        latest_label = f"{latest[0]}년 {latest[1]}월"
        previous_label = f"{previous[0]}년 {previous[1]}월"

        all_rows.append(["최근 2개월 카테고리 비교", "", "", ""])
        all_rows.append(["카테고리", latest_label, previous_label, ""])

        latest_totals = _category_totals(by_month[latest])
        previous_totals = _category_totals(by_month[previous])
        category_start = len(all_rows)
        for category in sorted(set(latest_totals) | set(previous_totals)):
            all_rows.append([
                category,
                latest_totals.get(category, 0),
                previous_totals.get(category, 0),
                "",
            ])
        category_end = len(all_rows)

        if category_end > category_start:
            bar_charts.append(BarChartSpec(
                title=f"{latest_label} vs {previous_label} 카테고리 지출 비교",
                category_start_index=category_start,
                category_end_index=category_end,
                first_series_col_index=1,
                second_series_col_index=2,
                anchor_row_index=0,
            ))

        while len(all_rows) < _top_section_row_count(transactions):
            all_rows.append(["", "", "", ""])

    elif insight_rows:
        while len(all_rows) < _top_section_row_count(transactions):
            all_rows.append(["", "", "", ""])

    for year in sorted(by_year.keys(), reverse=True):
        year_total = sum(t.amount for t in by_year[year])
        all_rows.append([f"{year}년", "", "연간 총 지출", year_total])

        months = sorted(
            [month for month_year, month in by_month.keys() if month_year == year],
            reverse=True,
        )
        for month in months:
            month_txns = by_month[(year, month)]
            month_total = sum(t.amount for t in month_txns)

            all_rows.append([f"{year}년 {month}월", "", "월 총 지출", month_total])
            all_rows.append(["카테고리", "비율", "금액", ""])

            by_category: dict[str, list[Transaction]] = defaultdict(list)
            for txn in month_txns:
                by_category[txn.category].append(txn)

            category_start = len(all_rows)
            category_totals: dict[str, int] = {}
            for category in sorted(by_category.keys()):
                total = sum(t.amount for t in by_category[category])
                category_totals[category] = total
                percentage = total / month_total if month_total else 0
                all_rows.append([category, f"{percentage:.1%}", total, ""])
            category_end = len(all_rows)

            if category_end > category_start:
                percent_ranges.append((category_start, category_end))

            all_rows.append(["", "", "", ""])
            all_rows.append(["거래 상세", "", "", ""])

            for category in sorted(by_category.keys()):
                cat_txns = by_category[category]
                all_rows.append([category, "", category_totals[category], ""])

                detail_start = len(all_rows)
                for txn in sorted(cat_txns, key=lambda t: t.date):
                    all_rows.append(["", txn.date.isoformat(), txn.merchant, txn.amount])
                detail_end = len(all_rows)

                if detail_end > detail_start:
                    groups.append((detail_start, detail_end))

            all_rows.append(["", "", "", ""])

        all_rows.append(["", "", "", ""])

    if insight_rows:
        _place_side_panel(
            all_rows,
            _insight_start_row_index(transactions),
            insight_rows,
        )

    return all_rows, groups, percent_ranges, bar_charts


def _place_side_panel(
    rows: list[list],
    start_index: int,
    panel_rows: list[list],
    start_column: int = 5,
) -> None:
    width = start_column + 4
    for offset, panel_row in enumerate(panel_rows):
        row_index = start_index + offset
        while len(rows) <= row_index:
            rows.append(["", "", "", ""])
        if len(rows[row_index]) < width:
            rows[row_index].extend([""] * (width - len(rows[row_index])))
        rows[row_index][start_column:width] = panel_row[:4]


def _recent_comparison_row_count(transactions: list[Transaction]) -> int:
    by_month: dict[tuple[int, int], list[Transaction]] = defaultdict(list)
    for txn in transactions:
        by_month[(txn.date.year, txn.date.month)].append(txn)

    recent_months = sorted(by_month.keys(), reverse=True)[:2]
    if len(recent_months) < 2:
        return 0

    categories = set()
    for month in recent_months:
        categories.update(txn.category for txn in by_month[month])
    return 2 + len(categories)


def _top_section_row_count(transactions: list[Transaction]) -> int:
    return max(_recent_comparison_row_count(transactions) + 1, 12)


def _insight_start_row_index(transactions: list[Transaction]) -> int:
    return _top_section_row_count(transactions) + AI_INSIGHT_ROW_OFFSET


def _category_totals(transactions: list[Transaction]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for txn in transactions:
        totals[txn.category] += txn.amount
    return dict(totals)
