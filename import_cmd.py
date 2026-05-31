import argparse
from pathlib import Path
from models import Transaction
from sheets import SheetsClient
from categorizer import categorize
from dashboard import build_dashboard
from parsers import kb_card, naver_pay, kakao_pay
from config import SPREADSHEET_ID, CREDENTIALS_FILE

EXPENSE_DIR = Path("expense")

TRANSACTIONS_SHEET = "transactions"
CATEGORIES_SHEET = "merchant_categories"
HEADER = ["date", "amount", "merchant", "category", "source", "memo"]

SOURCE_MAP = {
    "kb": kb_card,
    "naver": naver_pay,
    "kakao": kakao_pay,
}


def deduplicate(
    transactions: list[Transaction],
    existing_keys: set[tuple[str, str, str]],
) -> list[Transaction]:
    return [
        t for t in transactions
        if (t.date.isoformat(), str(t.amount), t.merchant) not in existing_keys
    ]


def detect_source(filepath: str) -> str:
    name = filepath.lower()
    if "naver" in name:
        return "naver"
    if "kakao" in name:
        return "kakao"
    return "kb"


def collect_files(args) -> list[Path]:
    if args.files:
        return [Path(f) for f in args.files]
    if not EXPENSE_DIR.exists():
        raise SystemExit(f"expense/ 폴더가 없습니다. 폴더를 만들고 CSV를 넣어주세요.")
    files = sorted(EXPENSE_DIR.glob("*.csv")) + sorted(EXPENSE_DIR.glob("*.xlsx"))
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
        return

    print(f"{len(new_transactions)}건의 새 거래를 발견했습니다.")
    categorized = categorize(new_transactions, client)

    rows = [
        [t.date.isoformat(), t.amount, t.merchant, t.category, t.source, t.memo]
        for t in categorized
    ]
    client.append_rows(TRANSACTIONS_SHEET, rows)
    print(f"{len(rows)}건 가져오기 완료.")

    build_dashboard(client)
    print("대시보드가 업데이트되었습니다.")


if __name__ == "__main__":
    main()
