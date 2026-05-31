from models import Transaction
from sheets import SheetsClient

CATEGORIES_SHEET = "merchant_categories"


def categorize(
    transactions: list[Transaction],
    sheets_client: SheetsClient,
    prompt_fn=None,
) -> list[Transaction]:
    if prompt_fn is None:
        prompt_fn = _cli_prompt

    rows = sheets_client.read_sheet(CATEGORIES_SHEET)
    mapping = {row[0]: row[1] for row in rows if len(row) >= 2}

    new_mappings: dict[str, str] = {}
    result = []

    for txn in transactions:
        if txn.merchant in mapping:
            category = mapping[txn.merchant]
        elif txn.merchant in new_mappings:
            category = new_mappings[txn.merchant]
        else:
            category = prompt_fn(txn.merchant)
            mapping[txn.merchant] = category
            new_mappings[txn.merchant] = category

        result.append(Transaction(
            date=txn.date,
            amount=txn.amount,
            merchant=txn.merchant,
            category=category,
            source=txn.source,
            memo=txn.memo,
        ))

    if new_mappings:
        sheets_client.append_rows(
            CATEGORIES_SHEET,
            [[merchant, cat] for merchant, cat in new_mappings.items()],
        )

    return result


def _cli_prompt(merchant: str) -> str:
    print(f"\n새 가맹점: {merchant}")
    print("카테고리 입력 (예: 카페, 식비, 쇼핑, 교통, 의료, 기타):")
    return input("> ").strip()
