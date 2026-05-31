import csv
from datetime import datetime
from models import Transaction

DATE_COL = "결제일"
MERCHANT_COL = "상품명"
AMOUNT_COL = "결제금액"
STATUS_COL = "결제상태"
COMPLETED_STATUS = "결제완료"


def parse(filepath: str, encoding: str = "utf-8-sig") -> list[Transaction]:
    transactions = []
    with open(filepath, encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row[STATUS_COL].strip() != COMPLETED_STATUS:
                continue
            dt = datetime.strptime(row[DATE_COL].strip(), "%Y-%m-%d %H:%M:%S")
            transactions.append(Transaction(
                date=dt.date(),
                amount=int(row[AMOUNT_COL].strip()),
                merchant=row[MERCHANT_COL].strip(),
                category="",
                source="naver_pay",
            ))
    return transactions
