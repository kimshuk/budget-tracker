from collections import defaultdict
from datetime import date as date_type
from models import Transaction
from sheets import SheetsClient

TRANSACTIONS_SHEET = "transactions"
DASHBOARD_SHEET = "dashboard"


def build_dashboard(sheets_client: SheetsClient) -> None:
    raw_rows = sheets_client.read_sheet(TRANSACTIONS_SHEET)
    transactions = _parse_transaction_rows(raw_rows)
    dashboard_rows, groups = _build_rows_and_groups(transactions)

    sheets_client.ensure_sheet_exists(DASHBOARD_SHEET)
    sheets_client.clear_and_write(DASHBOARD_SHEET, dashboard_rows)

    sheet_id = sheets_client.get_sheet_id(DASHBOARD_SHEET)
    sheets_client.clear_row_groups(sheet_id)
    sheets_client.apply_row_groups(sheet_id, groups)


def _parse_transaction_rows(rows: list[list]) -> list[Transaction]:
    if not rows:
        return []
    if rows[0] and rows[0][0] == "date":
        rows = rows[1:]
    result = []
    for row in rows:
        if len(row) < 5:
            continue
        result.append(Transaction(
            date=date_type.fromisoformat(row[0]),
            amount=int(row[1]),
            merchant=row[2],
            category=row[3],
            source=row[4],
            memo=row[5] if len(row) > 5 else "",
        ))
    return result


def _build_rows_and_groups(
    transactions: list[Transaction],
) -> tuple[list[list], list[tuple[int, int]]]:
    by_month: dict[tuple[int, int], list[Transaction]] = defaultdict(list)
    for txn in transactions:
        by_month[(txn.date.year, txn.date.month)].append(txn)

    all_rows: list[list] = []
    groups: list[tuple[int, int]] = []

    for year, month in sorted(by_month.keys(), reverse=True):
        all_rows.append([f"{year}년 {month}월", "", "", ""])

        by_category: dict[str, list[Transaction]] = defaultdict(list)
        for txn in by_month[(year, month)]:
            by_category[txn.category].append(txn)

        for category in sorted(by_category.keys()):
            cat_txns = by_category[category]
            total = sum(t.amount for t in cat_txns)
            all_rows.append([category, "", f"₩{total:,}", ""])

            detail_start = len(all_rows)
            for txn in sorted(cat_txns, key=lambda t: t.date):
                all_rows.append(["", txn.date.isoformat(), txn.merchant, f"₩{txn.amount:,}"])
            detail_end = len(all_rows)

            if detail_end > detail_start:
                groups.append((detail_start, detail_end))

        all_rows.append(["", "", "", ""])

    return all_rows, groups
