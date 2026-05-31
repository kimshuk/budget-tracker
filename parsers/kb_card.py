import csv
from datetime import date
from models import Transaction

DATE_COL = "이용일"
MERCHANT_COL = "이용가맹점명"
AMOUNT_COL = "이용금액"


def parse(filepath: str, encoding: str = "euc-kr") -> list[Transaction]:
    transactions = []
    with open(filepath, encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            amount = int(row[AMOUNT_COL].replace(",", "").strip())
            year, month, day = row[DATE_COL].strip().split(".")
            txn_date = date(int(year), int(month), int(day))
            transactions.append(Transaction(
                date=txn_date,
                amount=amount,
                merchant=row[MERCHANT_COL].strip(),
                category="",
                source="kb_card",
            ))
    return transactions
