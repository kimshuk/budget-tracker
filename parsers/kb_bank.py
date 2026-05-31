import xlrd
from datetime import datetime
from models import Transaction

DATE_COL = "거래일시"
RECIPIENT_COL = "보낸분/받는분"
WITHDRAW_COL = "출금액"

SKIP_RECIPIENTS = {"KB카드출금"}  # 신용카드 결제대금 — 카드 내역에 이미 있음


def parse(filepath: str, **_) -> list[Transaction]:
    wb = xlrd.open_workbook(filepath)
    ws = wb.sheet_by_index(0)

    header_idx = next(
        (i for i in range(ws.nrows)
         if DATE_COL in [str(c).strip() for c in ws.row_values(i)]),
        None,
    )
    if header_idx is None:
        raise ValueError(f"'{DATE_COL}' 컬럼을 찾을 수 없습니다.")

    headers = [str(c).strip() for c in ws.row_values(header_idx)]
    date_idx = headers.index(DATE_COL)
    recipient_idx = headers.index(RECIPIENT_COL)
    withdraw_idx = headers.index(WITHDRAW_COL)

    transactions = []
    for i in range(header_idx + 1, ws.nrows):
        row = ws.row_values(i)
        if not row[date_idx]:
            continue
        withdraw = float(row[withdraw_idx] or 0)
        if withdraw <= 0:
            continue
        recipient = str(row[recipient_idx]).strip()
        if recipient in SKIP_RECIPIENTS:
            continue
        dt = datetime.strptime(str(row[date_idx]).strip()[:10], "%Y.%m.%d")
        transactions.append(Transaction(
            date=dt.date(),
            amount=int(withdraw),
            merchant=recipient,
            category="",
            source="kb_bank",
        ))
    return transactions
