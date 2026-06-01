import argparse
import unicodedata
from pathlib import Path
from models import Transaction
from sheets import SheetsClient
from categorizer import categorize
from dashboard import build_dashboard
from parsers import kb_card, kb_bank, naver_pay, kakao_pay
from config import SPREADSHEET_ID, CREDENTIALS_FILE

EXPENSE_DIR = Path("expense")

TRANSACTIONS_SHEET = "transactions"
CATEGORIES_SHEET = "merchant_categories"
CATEGORIES_LIST_SHEET = "categories"
HEADER = ["date", "amount", "merchant", "category", "source", "memo"]

DEFAULT_CATEGORIES = [
    "식비", "카페", "쇼핑", "교통", "의료",
    "생활비", "여가/문화", "구독", "기타",
]

SOURCE_MAP = {
    "kb": kb_card,
    "bank": kb_bank,
    "naver": naver_pay,
    "kakao": kakao_pay,
}


def setup_categories(client: SheetsClient) -> None:
    client.ensure_sheet_exists(CATEGORIES_LIST_SHEET)
    if not client.read_sheet(CATEGORIES_LIST_SHEET):
        client.append_rows(CATEGORIES_LIST_SHEET, [[c] for c in DEFAULT_CATEGORIES])
    mc_sheet_id = client.get_sheet_id(CATEGORIES_SHEET)
    client.apply_dropdown_validation(
        mc_sheet_id,
        col_index=1,
        source_range=f"={CATEGORIES_LIST_SHEET}!$A:$A",
    )


def recategorize_existing(client: SheetsClient) -> int:
    rows = client.read_sheet(TRANSACTIONS_SHEET)
    if not rows or len(rows) <= 1:
        return 0

    cat_rows = client.read_sheet(CATEGORIES_SHEET)
    mapping = {row[0]: row[1] for row in cat_rows if len(row) >= 2 and row[1]}
    if not mapping:
        return 0

    header = rows[0]
    updated_count = 0
    new_data: list[list] = []

    for row in rows[1:]:
        row = list(row)
        if len(row) >= 4 and row[3] == "미분류" and len(row) > 2 and row[2] in mapping:
            row[3] = mapping[row[2]]
            updated_count += 1
        new_data.append(row)

    if updated_count:
        client.clear_and_write(TRANSACTIONS_SHEET, [header] + new_data)

    return updated_count


def deduplicate(
    transactions: list[Transaction],
    existing_keys: set[tuple[str, str, str]],
) -> list[Transaction]:
    return [
        t for t in transactions
        if (t.date.isoformat(), str(t.amount), t.merchant) not in existing_keys
    ]


def detect_source(filepath: str) -> str:
    name = unicodedata.normalize("NFC", filepath.lower())
    if "naver" in name:
        return "naver"
    if "kakao" in name:
        return "kakao"
    if "은행" in name or "bank" in name:
        return "bank"
    return "kb"


def collect_files(args) -> list[Path]:
    if args.files:
        return [Path(f) for f in args.files]
    if not EXPENSE_DIR.exists():
        raise SystemExit(f"expense/ 폴더가 없습니다. 폴더를 만들고 CSV를 넣어주세요.")
    files = (
        sorted(EXPENSE_DIR.rglob("*.csv"))
        + sorted(EXPENSE_DIR.rglob("*.xlsx"))
        + sorted(EXPENSE_DIR.rglob("*.xls"))
    )
    if not files:
        raise SystemExit("expense/ 폴더에 CSV 파일이 없습니다.")
    return files


def main():
    parser = argparse.ArgumentParser(description="Import spending CSV to Google Sheets")
    parser.add_argument("--files", nargs="+", help="CSV 파일 경로 (생략 시 expense/ 폴더 전체)")
    parser.add_argument("--source", choices=list(SOURCE_MAP.keys()))
    args = parser.parse_args()

    filepaths = collect_files(args)
    print(f"파일 {len(filepaths)}개 발견: {[f.name for f in filepaths]}")

    client = SheetsClient(SPREADSHEET_ID, CREDENTIALS_FILE)
    client.ensure_sheet_exists(TRANSACTIONS_SHEET)
    client.ensure_sheet_exists(CATEGORIES_SHEET)
    setup_categories(client)

    existing = client.read_sheet(TRANSACTIONS_SHEET)
    if not existing:
        client.append_rows(TRANSACTIONS_SHEET, [HEADER])
        existing = [HEADER]

    existing_keys = {
        (row[0], row[1], row[2])
        for row in existing[1:]
        if len(row) >= 3
    }

    all_transactions: list[Transaction] = []
    for filepath in filepaths:
        source = args.source or detect_source(str(filepath))
        all_transactions.extend(SOURCE_MAP[source].parse(str(filepath)))

    new_transactions = deduplicate(all_transactions, existing_keys)

    if not new_transactions:
        print("가져올 새 거래가 없습니다.")
    else:
        print(f"{len(new_transactions)}건의 새 거래를 발견했습니다.")
        categorized = categorize(new_transactions, client)
        rows = [
            [t.date.isoformat(), t.amount, t.merchant, t.category, t.source, t.memo]
            for t in categorized
        ]
        client.append_rows(TRANSACTIONS_SHEET, rows)
        print(f"{len(rows)}건 가져오기 완료.")

    updated = recategorize_existing(client)
    if updated:
        print(f"기존 미분류 거래 {updated}건 카테고리 업데이트 완료.")

    build_dashboard(client)
    print("대시보드가 업데이트되었습니다.")


if __name__ == "__main__":
    main()
