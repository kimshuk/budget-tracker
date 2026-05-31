import csv
from datetime import date
from pathlib import Path
from models import Transaction

DATE_COL = "이용일"
MERCHANT_COL = "이용가맹점명"
AMOUNT_COL = "이용금액"


def parse(filepath: str, encoding: str = "euc-kr") -> list[Transaction]:
    if Path(filepath).suffix.lower() in (".xlsx", ".xls"):
        return _parse_excel(filepath)
    return _parse_csv(filepath, encoding)


def _parse_csv(filepath: str, encoding: str) -> list[Transaction]:
    transactions = []
    with open(filepath, encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append(_make_transaction(row))
    return transactions


def _parse_excel(filepath: str) -> list[Transaction]:
    from openpyxl import load_workbook
    wb = load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))

    # Find header row — first row that contains DATE_COL
    header_idx = next(
        (i for i, row in enumerate(all_rows)
         if row and DATE_COL in [str(c).strip() for c in row if c is not None]),
        None,
    )
    if header_idx is None:
        raise ValueError(
            f"'{DATE_COL}' 컬럼을 찾을 수 없습니다. "
            "DATE_COL 상수를 실제 엑셀 컬럼명으로 수정해주세요."
        )

    headers = [str(c).strip() if c is not None else "" for c in all_rows[header_idx]]
    transactions = []
    for row in all_rows[header_idx + 1:]:
        if not row or not any(c for c in row if c is not None):
            continue
        row_dict = {
            headers[i]: (str(row[i]).strip() if i < len(row) and row[i] is not None else "")
            for i in range(len(headers))
        }
        if not row_dict.get(DATE_COL):
            continue
        transactions.append(_make_transaction(row_dict))
    return transactions


def _make_transaction(row: dict) -> Transaction:
    amount = int(row[AMOUNT_COL].replace(",", "").strip())
    year, month, day = row[DATE_COL].strip().split(".")
    return Transaction(
        date=date(int(year), int(month), int(day)),
        amount=amount,
        merchant=row[MERCHANT_COL].strip(),
        category="",
        source="kb_card",
    )
