import argparse
import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from models import Transaction
from sheets import SheetsClient
from categorizer import categorize
from dashboard import build_dashboard
from parsers import kb_card, kb_bank, naver_pay, kakao_pay
from config import SPREADSHEET_ID, CREDENTIALS_FILE, validate_config

EXPENSE_DIR = Path("expense")
IMPORT_STATE_FILE = Path("imported_files.json")

TRANSACTIONS_SHEET = "transactions"
CATEGORIES_SHEET = "merchant_categories"
CATEGORIES_LIST_SHEET = "categories"
HEADER = [
    "transaction_id",
    "source",
    "source_file",
    "date",
    "merchant_raw",
    "merchant_normalized",
    "amount",
    "category",
    "subcategory",
    "payment_method",
    "approval_number",
    "imported_at",
    "memo",
]
LEGACY_HEADER = ["date", "amount", "merchant", "category", "source", "memo"]

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
    merchant_index = _column_index(header, "merchant_normalized", "merchant")
    category_index = _column_index(header, "category")
    updated_count = 0
    new_data: list[list] = []

    for row in rows[1:]:
        row = list(row)
        if len(row) > max(merchant_index, category_index) and row[merchant_index] in mapping:
            category = mapping[row[merchant_index]]
            if row[category_index] != category:
                row[category_index] = category
                updated_count += 1
        new_data.append(row)

    if updated_count:
        client.clear_and_write(TRANSACTIONS_SHEET, [header] + new_data)

    return updated_count


def build_transaction_id(txn: Transaction) -> str:
    merchant_raw = txn.merchant_raw or txn.merchant
    identity = "|".join([
        txn.source,
        txn.date.isoformat(),
        merchant_raw,
        str(txn.amount),
        txn.approval_number,
    ])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def normalize_transaction(
    txn: Transaction,
    source_file: str,
    imported_at: str,
    category: str | None = None,
) -> list:
    merchant_raw = txn.merchant_raw or txn.merchant
    merchant_normalized = txn.merchant_normalized or txn.merchant
    return [
        build_transaction_id(txn),
        txn.source,
        source_file,
        txn.date.isoformat(),
        merchant_raw,
        merchant_normalized,
        txn.amount,
        category if category is not None else txn.category,
        txn.subcategory,
        txn.payment_method,
        txn.approval_number,
        imported_at,
        txn.memo,
    ]


def upsert_transactions(
    client: SheetsClient,
    transactions: list[Transaction],
    source_file: str,
    imported_at: str,
) -> tuple[int, int]:
    existing = _canonical_rows(client.read_sheet(TRANSACTIONS_SHEET))
    existing_by_id = {
        row[HEADER.index("transaction_id")]: row
        for row in existing[1:]
        if len(row) > HEADER.index("transaction_id") and row[HEADER.index("transaction_id")]
    }

    inserted_count = 0
    updated_count = 0
    output_by_id = dict(existing_by_id)

    for txn in transactions:
        txn_id = build_transaction_id(txn)
        existing_row = output_by_id.get(txn_id)
        category = (
            existing_row[HEADER.index("category")]
            if existing_row and len(existing_row) > HEADER.index("category") and existing_row[HEADER.index("category")]
            else txn.category
        )
        row = normalize_transaction(txn, source_file, imported_at, category=category)
        if existing_row:
            merged = list(existing_row)
            preserved_indexes = {
                HEADER.index("source_file"),
                HEADER.index("category"),
                HEADER.index("subcategory"),
                HEADER.index("imported_at"),
                HEADER.index("memo"),
            }
            for idx, value in enumerate(row):
                if idx in preserved_indexes and merged[idx]:
                    continue
                merged[idx] = value
            if merged != existing_row:
                updated_count += 1
            output_by_id[txn_id] = merged
        else:
            inserted_count += 1
            output_by_id[txn_id] = row

    rows = [HEADER] + sorted(output_by_id.values(), key=lambda row: (row[HEADER.index("date")], row[HEADER.index("transaction_id")]))
    client.clear_and_write(TRANSACTIONS_SHEET, rows)
    return inserted_count, updated_count


def update_import_state(
    filepath: Path,
    source: str,
    row_count: int,
    imported_at: str,
    state_file: Path = IMPORT_STATE_FILE,
) -> None:
    state = {}
    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))
    state[str(filepath)] = {
        "filename": filepath.name,
        "file_hash": _file_hash(filepath),
        "imported_at": imported_at,
        "row_count": row_count,
        "source": source,
    }
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_import_state(state_file: Path = IMPORT_STATE_FILE) -> dict:
    if not state_file.exists():
        return {}
    return json.loads(state_file.read_text(encoding="utf-8"))


def should_process_file(filepath: Path, source: str, state: dict) -> bool:
    existing = state.get(str(filepath))
    if not existing:
        return True
    return existing.get("source") != source or existing.get("file_hash") != _file_hash(filepath)


def _canonical_rows(rows: list[list]) -> list[list]:
    if not rows:
        return [HEADER]
    if rows[0] == HEADER:
        return [HEADER] + [_pad_row(row, len(HEADER)) for row in rows[1:]]
    if rows[0] == LEGACY_HEADER:
        canonical = [HEADER]
        for row in rows[1:]:
            if len(row) < 5:
                continue
            txn = Transaction(
                date=datetime.fromisoformat(row[0]).date(),
                amount=int(row[1]),
                merchant=row[2],
                category=row[3],
                source=row[4],
                memo=row[5] if len(row) > 5 else "",
            )
            canonical.append(normalize_transaction(txn, source_file="", imported_at="", category=txn.category))
        return canonical
    return [HEADER] + [_pad_row(row, len(HEADER)) for row in rows[1:]]


def _pad_row(row: list, length: int) -> list:
    return list(row) + [""] * max(length - len(row), 0)


def _column_index(header: list, *names: str) -> int:
    for name in names:
        if name in header:
            return header.index(name)
    raise ValueError(f"Missing expected column, tried: {', '.join(names)}")


def _file_hash(filepath: Path) -> str:
    digest = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _imported_at_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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

    validate_config()
    client = SheetsClient(SPREADSHEET_ID, CREDENTIALS_FILE)
    client.ensure_sheet_exists(TRANSACTIONS_SHEET)
    client.ensure_sheet_exists(CATEGORIES_SHEET)
    setup_categories(client)

    if not client.read_sheet(TRANSACTIONS_SHEET):
        client.append_rows(TRANSACTIONS_SHEET, [HEADER])

    total_inserted = 0
    total_updated = 0
    import_state = load_import_state()
    for filepath in filepaths:
        source = args.source or detect_source(str(filepath))
        if not should_process_file(filepath, source, import_state):
            print(f"변경 없는 파일 건너뜀: {filepath.name}")
            continue
        parsed = SOURCE_MAP[source].parse(str(filepath))
        if not parsed:
            update_import_state(filepath, source, 0, _imported_at_now())
            continue
        categorized = categorize(parsed, client)
        imported_at = _imported_at_now()
        inserted, updated_rows = upsert_transactions(client, categorized, filepath.name, imported_at)
        update_import_state(filepath, source, len(parsed), imported_at)
        total_inserted += inserted
        total_updated += updated_rows

    if total_inserted or total_updated:
        print(f"거래 {total_inserted}건 추가, {total_updated}건 업데이트 완료.")
    else:
        print("가져올 새 거래가 없습니다.")

    updated = recategorize_existing(client)
    if updated:
        print(f"기존 거래 {updated}건 카테고리 동기화 완료.")

    build_dashboard(client)
    print("대시보드가 업데이트되었습니다.")


if __name__ == "__main__":
    main()
