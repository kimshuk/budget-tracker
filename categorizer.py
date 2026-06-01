from models import Transaction
from sheets import SheetsClient

CATEGORIES_SHEET = "merchant_categories"
UNCATEGORIZED = "미분류"


def categorize(
    transactions: list[Transaction],
    sheets_client: SheetsClient,
) -> list[Transaction]:
    rows = sheets_client.read_sheet(CATEGORIES_SHEET)
    mapping = {row[0]: row[1] for row in rows if len(row) >= 2}
    known_merchants = {row[0] for row in rows if len(row) >= 1}

    new_merchants: list[str] = []
    seen_new: set[str] = set()
    result = []

    for txn in transactions:
        category = mapping.get(txn.merchant) or UNCATEGORIZED
        if txn.merchant not in known_merchants and txn.merchant not in seen_new:
            new_merchants.append(txn.merchant)
            seen_new.add(txn.merchant)

        result.append(Transaction(
            date=txn.date,
            amount=txn.amount,
            merchant=txn.merchant,
            category=category,
            source=txn.source,
            memo=txn.memo,
        ))

    if new_merchants:
        sheets_client.append_rows(
            CATEGORIES_SHEET,
            [[merchant, ""] for merchant in new_merchants],
        )
        print(f"새 가맹점 {len(new_merchants)}개를 merchant_categories 시트에 추가했습니다. 카테고리를 직접 입력해주세요.")

    return result
