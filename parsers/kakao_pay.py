import csv
from datetime import datetime
from models import Transaction

DATE_COL = "거래일시"
MERCHANT_COL = "가맹점명"
AMOUNT_COL = "금액"
TYPE_COL = "구분"
COMPLETED_TYPE = "결제"


def parse(filepath: str, encoding: str = "utf-8") -> list[Transaction]:
    transactions = []
    with open(filepath, encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row[TYPE_COL].strip() != COMPLETED_TYPE:
                continue
            dt = datetime.strptime(row[DATE_COL].strip(), "%Y-%m-%d %H:%M")
            transactions.append(Transaction(
                date=dt.date(),
                amount=int(row[AMOUNT_COL].strip()),
                merchant=row[MERCHANT_COL].strip(),
                category="",
                source="kakao_pay",
            ))
    return transactions
