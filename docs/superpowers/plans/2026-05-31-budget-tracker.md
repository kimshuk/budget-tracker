# Personal Budget Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that imports Korean card/pay CSV exports, categorizes transactions interactively, and pushes a monthly expandable dashboard to Google Sheets.

**Architecture:** Three-layer pipeline — per-source CSV parsers normalize data into `Transaction` objects, a categorizer does merchant lookups against a `merchant_categories` sheet (prompting for unknowns), and a dashboard builder writes a grouped summary sheet with Sheets Row Groups API for expand/collapse. `import.py` orchestrates all layers.

**Tech Stack:** Python 3.11+, `google-api-python-client`, `google-auth`, `pandas` (CSV parsing), `pytest`

---

## File Map

| File | Responsibility |
|------|----------------|
| `requirements.txt` | Python dependencies |
| `config.py` | SPREADSHEET_ID, CREDENTIALS_FILE from env vars |
| `models.py` | `Transaction` dataclass |
| `sheets.py` | Google Sheets API wrapper (auth + CRUD + row groups) |
| `parsers/__init__.py` | empty |
| `parsers/kb_card.py` | Parse 국민카드 CSV (EUC-KR) → `list[Transaction]` |
| `parsers/naver_pay.py` | Parse 네이버페이 CSV (UTF-8-BOM) → `list[Transaction]` |
| `parsers/kakao_pay.py` | Parse 카카오페이 CSV (UTF-8) → `list[Transaction]` |
| `categorizer.py` | Merchant lookup in Sheets + CLI prompt for unknowns |
| `dashboard.py` | Build grouped dashboard sheet from transactions |
| `import.py` | CLI entry point — orchestrates parse → categorize → upload → dashboard |
| `tests/test_models.py` | Unit tests for Transaction |
| `tests/test_sheets.py` | Unit tests for SheetsClient (mocked API) |
| `tests/test_parsers.py` | Unit tests for all three parsers |
| `tests/test_categorizer.py` | Unit tests for categorizer |
| `tests/test_dashboard.py` | Unit tests for dashboard row/group builder |
| `tests/test_import.py` | Integration test for deduplication logic |
| `tests/fixtures/kb_card_sample.csv` | Sample 국민카드 CSV for parser tests |
| `tests/fixtures/naver_pay_sample.csv` | Sample 네이버페이 CSV for parser tests |
| `tests/fixtures/kakao_pay_sample.csv` | Sample 카카오페이 CSV for parser tests |

---

## Task 1: Project scaffolding + Transaction model

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `config.py`
- Create: `models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
from datetime import date
from models import Transaction

def test_transaction_fields():
    txn = Transaction(
        date=date(2026, 5, 15),
        amount=4500,
        merchant="스타벅스 강남점",
        category="카페",
        source="kb_card",
        memo=""
    )
    assert txn.date == date(2026, 5, 15)
    assert txn.amount == 4500
    assert txn.merchant == "스타벅스 강남점"
    assert txn.category == "카페"
    assert txn.source == "kb_card"
    assert txn.memo == ""

def test_transaction_memo_defaults_to_empty():
    txn = Transaction(
        date=date(2026, 5, 15),
        amount=1000,
        merchant="GS25",
        category="편의점",
        source="kakao_pay"
    )
    assert txn.memo == ""
```

- [ ] **Step 2: Run test to confirm failure**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Create supporting files**

Create `requirements.txt`:

```
google-api-python-client>=2.100.0
google-auth>=2.23.0
pytest>=7.4.0
```

Create `.gitignore`:

```
credentials.json
.env
__pycache__/
*.pyc
.pytest_cache/
```

Create `config.py`:

```python
import os

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")
CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS", "credentials.json")
```

Create `tests/__init__.py` (empty file).

- [ ] **Step 4: Implement `models.py`**

```python
from dataclasses import dataclass, field
from datetime import date

@dataclass
class Transaction:
    date: date
    amount: int
    merchant: str
    category: str
    source: str
    memo: str = ""
```

- [ ] **Step 5: Install dependencies and run tests**

```bash
pip install -r requirements.txt
pytest tests/test_models.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore config.py models.py tests/__init__.py tests/test_models.py
git commit -m "feat: add Transaction model and project scaffolding"
```

---

## Task 2: Google Sheets client

**Files:**
- Create: `sheets.py`
- Create: `tests/test_sheets.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sheets.py`:

```python
from unittest.mock import MagicMock, patch
from sheets import SheetsClient


def _make_client():
    with patch("sheets.service_account.Credentials.from_service_account_file"), \
         patch("sheets.build") as mock_build:
        mock_build.return_value = MagicMock()
        client = SheetsClient("SHEET_ID", "creds.json")
        return client


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_read_sheet_returns_values(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": [["date", "amount"], ["2026-05-15", "4500"]]
    }
    client = SheetsClient("SHEET_ID", "creds.json")
    result = client.read_sheet("transactions")
    assert result == [["date", "amount"], ["2026-05-15", "4500"]]


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_read_sheet_returns_empty_list_when_missing(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.spreadsheets().values().get().execute.return_value = {}
    client = SheetsClient("SHEET_ID", "creds.json")
    assert client.read_sheet("transactions") == []


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_append_rows_calls_api(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    client = SheetsClient("SHEET_ID", "creds.json")
    rows = [["2026-05-15", "4500", "스타벅스", "카페", "kb_card", ""]]
    client.append_rows("transactions", rows)
    mock_service.spreadsheets().values().append.assert_called_once()


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_get_sheet_id_returns_correct_id(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.spreadsheets().get().execute.return_value = {
        "sheets": [
            {"properties": {"title": "transactions", "sheetId": 0}},
            {"properties": {"title": "dashboard", "sheetId": 123}},
        ]
    }
    client = SheetsClient("SHEET_ID", "creds.json")
    assert client.get_sheet_id("dashboard") == 123


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_get_sheet_id_raises_for_missing_sheet(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.spreadsheets().get().execute.return_value = {
        "sheets": [{"properties": {"title": "transactions", "sheetId": 0}}]
    }
    client = SheetsClient("SHEET_ID", "creds.json")
    try:
        client.get_sheet_id("nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_sheets.py -v
```

Expected: `ModuleNotFoundError: No module named 'sheets'`

- [ ] **Step 3: Implement `sheets.py`**

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    def __init__(self, spreadsheet_id: str, credentials_file: str):
        creds = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=SCOPES
        )
        self._service = build("sheets", "v4", credentials=creds)
        self._spreadsheet_id = spreadsheet_id

    def read_sheet(self, sheet_name: str) -> list[list]:
        result = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=sheet_name)
            .execute()
        )
        return result.get("values", [])

    def append_rows(self, sheet_name: str, rows: list[list]) -> None:
        self._service.spreadsheets().values().append(
            spreadsheetId=self._spreadsheet_id,
            range=sheet_name,
            valueInputOption="USER_ENTERED",
            body={"values": rows},
        ).execute()

    def clear_and_write(self, sheet_name: str, rows: list[list]) -> None:
        self._service.spreadsheets().values().clear(
            spreadsheetId=self._spreadsheet_id,
            range=sheet_name,
            body={},
        ).execute()
        if rows:
            self._service.spreadsheets().values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": rows},
            ).execute()

    def get_sheet_id(self, sheet_name: str) -> int:
        spreadsheet = (
            self._service.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id)
            .execute()
        )
        for sheet in spreadsheet["sheets"]:
            if sheet["properties"]["title"] == sheet_name:
                return sheet["properties"]["sheetId"]
        raise ValueError(f"Sheet '{sheet_name}' not found in spreadsheet")

    def ensure_sheet_exists(self, sheet_name: str) -> None:
        try:
            self.get_sheet_id(sheet_name)
        except ValueError:
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
            ).execute()

    def clear_row_groups(self, sheet_id: int) -> None:
        spreadsheet = (
            self._service.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id)
            .execute()
        )
        requests = []
        for sheet in spreadsheet["sheets"]:
            if sheet["properties"]["sheetId"] == sheet_id:
                for group in sheet.get("rowGroups", []):
                    requests.append(
                        {"deleteDimensionGroup": {"range": group["range"], "dimension": "ROWS"}}
                    )
        if requests:
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": requests},
            ).execute()

    def apply_row_groups(self, sheet_id: int, groups: list[tuple[int, int]]) -> None:
        if not groups:
            return
        requests = [
            {
                "addDimensionGroup": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": start,
                        "endIndex": end,
                    }
                }
            }
            for start, end in groups
        ]
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"requests": requests},
        ).execute()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sheets.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add sheets.py tests/test_sheets.py
git commit -m "feat: add Google Sheets API client"
```

---

## Task 3: CSV parsers (국민카드, 네이버페이, 카카오페이)

**Files:**
- Create: `parsers/__init__.py`
- Create: `parsers/kb_card.py`
- Create: `parsers/naver_pay.py`
- Create: `parsers/kakao_pay.py`
- Create: `tests/fixtures/kb_card_sample.csv`
- Create: `tests/fixtures/naver_pay_sample.csv`
- Create: `tests/fixtures/kakao_pay_sample.csv`
- Create: `tests/test_parsers.py`

> **NOTE:** The fixture CSVs below use typical column names from each app's export. If your actual export has different column names, update the parser constants at the top of each parser file accordingly.

- [ ] **Step 1: Create fixture CSV files**

Create `tests/fixtures/kb_card_sample.csv` (save as UTF-8; parser defaults to EUC-KR but tests pass `encoding="utf-8"`):

```
이용일,이용가맹점명,이용금액,할부,결제방법
2026.05.15,스타벅스 강남점,"4,500",일시불,신용카드
2026.05.16,이디야커피 홍대점,"3,800",일시불,신용카드
2026.05.20,쿠팡,"32,000",일시불,신용카드
```

Create `tests/fixtures/naver_pay_sample.csv` (UTF-8):

```
결제일,주문번호,상품명,결제금액,결제상태
2026-05-16 10:23:45,ORDER001,올리브영 온라인,15600,결제완료
2026-05-17 14:30:00,ORDER002,무신사 의류,28000,결제완료
2026-05-18 09:00:00,ORDER003,취소상품,5000,결제취소
```

Create `tests/fixtures/kakao_pay_sample.csv` (UTF-8):

```
거래일시,가맹점명,금액,구분
2026-05-15 10:23,GS25 강남역점,1200,결제
2026-05-18 19:45,배달의민족,25000,결제
2026-05-19 08:30,스타벅스 강남,4500,취소
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_parsers.py`:

```python
import os
from datetime import date
import pytest
from parsers.kb_card import parse as kb_parse
from parsers.naver_pay import parse as naver_parse
from parsers.kakao_pay import parse as kakao_parse

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_kb_card_parse_count():
    txns = kb_parse(os.path.join(FIXTURES, "kb_card_sample.csv"), encoding="utf-8")
    assert len(txns) == 3


def test_kb_card_parse_first_transaction():
    txns = kb_parse(os.path.join(FIXTURES, "kb_card_sample.csv"), encoding="utf-8")
    t = txns[0]
    assert t.date == date(2026, 5, 15)
    assert t.amount == 4500
    assert t.merchant == "스타벅스 강남점"
    assert t.category == ""
    assert t.source == "kb_card"


def test_kb_card_parse_strips_commas_from_amount():
    txns = kb_parse(os.path.join(FIXTURES, "kb_card_sample.csv"), encoding="utf-8")
    assert txns[2].amount == 32000


def test_naver_pay_parse_skips_cancelled():
    txns = naver_parse(os.path.join(FIXTURES, "naver_pay_sample.csv"))
    assert len(txns) == 2  # 결제취소 row excluded


def test_naver_pay_parse_first_transaction():
    txns = naver_parse(os.path.join(FIXTURES, "naver_pay_sample.csv"))
    t = txns[0]
    assert t.date == date(2026, 5, 16)
    assert t.amount == 15600
    assert t.merchant == "올리브영 온라인"
    assert t.source == "naver_pay"
    assert t.category == ""


def test_kakao_pay_parse_skips_cancelled():
    txns = kakao_parse(os.path.join(FIXTURES, "kakao_pay_sample.csv"))
    assert len(txns) == 2  # 취소 row excluded


def test_kakao_pay_parse_first_transaction():
    txns = kakao_parse(os.path.join(FIXTURES, "kakao_pay_sample.csv"))
    t = txns[0]
    assert t.date == date(2026, 5, 15)
    assert t.amount == 1200
    assert t.merchant == "GS25 강남역점"
    assert t.source == "kakao_pay"
    assert t.category == ""
```

- [ ] **Step 3: Run tests to confirm failure**

```bash
pytest tests/test_parsers.py -v
```

Expected: `ModuleNotFoundError: No module named 'parsers'`

- [ ] **Step 4: Create `parsers/__init__.py`** (empty file)

- [ ] **Step 5: Implement `parsers/kb_card.py`**

```python
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
```

- [ ] **Step 6: Implement `parsers/naver_pay.py`**

```python
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
```

- [ ] **Step 7: Implement `parsers/kakao_pay.py`**

```python
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
```

- [ ] **Step 8: Run tests**

```bash
pytest tests/test_parsers.py -v
```

Expected: 8 passed

- [ ] **Step 9: Commit**

```bash
git add parsers/ tests/fixtures/ tests/test_parsers.py
git commit -m "feat: add CSV parsers for KB card, Naver Pay, and Kakao Pay"
```

---

## Task 4: Categorizer

**Files:**
- Create: `categorizer.py`
- Create: `tests/test_categorizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_categorizer.py`:

```python
from datetime import date
from unittest.mock import MagicMock
from models import Transaction
from categorizer import categorize

SAMPLE = [
    Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card"),
    Transaction(date=date(2026, 5, 16), amount=32000, merchant="쿠팡", category="", source="naver_pay"),
    Transaction(date=date(2026, 5, 17), amount=1200, merchant="GS25", category="", source="kakao_pay"),
]


def test_uses_existing_category_from_sheet():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = [
        ["스타벅스", "카페"],
        ["쿠팡", "쇼핑"],
        ["GS25", "편의점"],
    ]
    prompt_fn = MagicMock()

    result = categorize(SAMPLE, mock_client, prompt_fn=prompt_fn)

    assert result[0].category == "카페"
    assert result[1].category == "쇼핑"
    assert result[2].category == "편의점"
    prompt_fn.assert_not_called()


def test_prompts_for_unknown_merchant():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = []
    prompt_fn = MagicMock(side_effect=["카페", "쇼핑", "편의점"])

    result = categorize(SAMPLE, mock_client, prompt_fn=prompt_fn)

    assert result[0].category == "카페"
    assert result[1].category == "쇼핑"
    assert result[2].category == "편의점"
    assert prompt_fn.call_count == 3


def test_same_unknown_merchant_only_prompts_once():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = []
    txns = [
        Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card"),
        Transaction(date=date(2026, 5, 16), amount=3800, merchant="스타벅스", category="", source="kb_card"),
    ]
    prompt_fn = MagicMock(return_value="카페")

    result = categorize(txns, mock_client, prompt_fn=prompt_fn)

    assert result[0].category == "카페"
    assert result[1].category == "카페"
    prompt_fn.assert_called_once()


def test_saves_new_mappings_to_sheet():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = []
    prompt_fn = MagicMock(side_effect=["카페", "쇼핑", "편의점"])

    categorize(SAMPLE, mock_client, prompt_fn=prompt_fn)

    mock_client.append_rows.assert_called_once()
    saved = mock_client.append_rows.call_args[0][1]
    assert ["스타벅스", "카페"] in saved
    assert ["쿠팡", "쇼핑"] in saved
    assert ["GS25", "편의점"] in saved


def test_does_not_save_when_no_new_merchants():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = [["스타벅스", "카페"]]
    txns = [Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card")]
    prompt_fn = MagicMock()

    categorize(txns, mock_client, prompt_fn=prompt_fn)

    mock_client.append_rows.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_categorizer.py -v
```

Expected: `ModuleNotFoundError: No module named 'categorizer'`

- [ ] **Step 3: Implement `categorizer.py`**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_categorizer.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add categorizer.py tests/test_categorizer.py
git commit -m "feat: add merchant categorizer with CLI prompt and Sheets persistence"
```

---

## Task 5: Dashboard builder

**Files:**
- Create: `dashboard.py`
- Create: `tests/test_dashboard.py`

The dashboard sheet layout (0-indexed rows after `clear_and_write`):

```
Row 0: ["2026년 5월", "", "", ""]         ← month header
Row 1: ["카페", "", "₩8,300", ""]         ← category summary
Row 2: ["", "2026-05-15", "스타벅스", "₩4,500"]  ← detail (grouped)
Row 3: ["", "2026-05-16", "이디야커피", "₩3,800"] ← detail (grouped)
Row 4: ["식비", "", "₩25,000", ""]
Row 5: ["", "2026-05-18", "배달의민족", "₩25,000"] ← detail (grouped)
Row 6: ["", "", "", ""]                   ← blank separator
```

Row groups: `(2, 4)` for 카페 details, `(5, 6)` for 식비 details.

- [ ] **Step 1: Write failing tests**

Create `tests/test_dashboard.py`:

```python
from datetime import date
from unittest.mock import MagicMock
from models import Transaction
from dashboard import _build_rows_and_groups

SAMPLE_TRANSACTIONS = [
    Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="카페", source="kb_card"),
    Transaction(date=date(2026, 5, 16), amount=3800, merchant="이디야커피", category="카페", source="kb_card"),
    Transaction(date=date(2026, 5, 18), amount=25000, merchant="배달의민족", category="식비", source="kakao_pay"),
]


def test_month_header_is_first_row():
    rows, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    assert rows[0][0] == "2026년 5월"


def test_category_summary_row_has_total():
    rows, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    # Categories are sorted by Unicode — find 카페 by content, not index
    cafe_rows = [r for r in rows if r[0] == "카페"]
    assert len(cafe_rows) == 1
    assert cafe_rows[0][2] == "₩8,300"


def test_detail_rows_follow_category_summary():
    rows, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    # Find 카페 summary row, verify its detail rows immediately follow
    cafe_idx = next(i for i, r in enumerate(rows) if r[0] == "카페")
    assert rows[cafe_idx + 1][2] == "스타벅스"
    assert rows[cafe_idx + 1][3] == "₩4,500"
    assert rows[cafe_idx + 2][2] == "이디야커피"


def test_row_groups_cover_detail_rows():
    rows, groups = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    # 카페 summary is at some index; its 2 details immediately follow → group is (idx+1, idx+3)
    cafe_idx = next(i for i, r in enumerate(rows) if r[0] == "카페")
    assert (cafe_idx + 1, cafe_idx + 3) in groups


def test_multiple_categories_each_get_a_group():
    rows, groups = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    assert len(groups) == 2


def test_detail_rows_sorted_by_date():
    txns = [
        Transaction(date=date(2026, 5, 20), amount=1000, merchant="B", category="기타", source="kb_card"),
        Transaction(date=date(2026, 5, 15), amount=2000, merchant="A", category="기타", source="kb_card"),
    ]
    rows, _ = _build_rows_and_groups(txns)
    detail_merchants = [r[2] for r in rows if r[0] == ""]
    assert detail_merchants[0] == "A"
    assert detail_merchants[1] == "B"


def test_blank_separator_row_after_month():
    rows, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    last = rows[-1]
    assert all(cell == "" for cell in last)


def test_multiple_months_descending():
    txns = [
        Transaction(date=date(2026, 4, 10), amount=5000, merchant="A", category="기타", source="kb_card"),
        Transaction(date=date(2026, 5, 15), amount=4500, merchant="B", category="기타", source="kb_card"),
    ]
    rows, _ = _build_rows_and_groups(txns)
    # May should come first (descending)
    assert rows[0][0] == "2026년 5월"
    # Find April header
    month_headers = [r[0] for r in rows if "년" in r[0]]
    assert month_headers[0] == "2026년 5월"
    assert month_headers[1] == "2026년 4월"
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_dashboard.py -v
```

Expected: `ModuleNotFoundError: No module named 'dashboard'`

- [ ] **Step 3: Implement `dashboard.py`**

```python
from collections import defaultdict
from datetime import date as date_type
from models import Transaction
from sheets import SheetsClient

TRANSACTIONS_SHEET = "transactions"
DASHBOARD_SHEET = "dashboard"


def build_dashboard(sheets_client: SheetsClient) -> None:
    raw_rows = sheets_client.read_sheet(TRANSACTIONS_SHEET)
    transactions = _parse_transaction_rows(raw_rows)
    dashboard_rows, groups = _build_rows_and_groups(transactions)

    sheets_client.ensure_sheet_exists(DASHBOARD_SHEET)
    sheets_client.clear_and_write(DASHBOARD_SHEET, dashboard_rows)

    sheet_id = sheets_client.get_sheet_id(DASHBOARD_SHEET)
    sheets_client.clear_row_groups(sheet_id)
    sheets_client.apply_row_groups(sheet_id, groups)


def _parse_transaction_rows(rows: list[list]) -> list[Transaction]:
    if not rows:
        return []
    if rows[0] and rows[0][0] == "date":
        rows = rows[1:]
    result = []
    for row in rows:
        if len(row) < 5:
            continue
        result.append(Transaction(
            date=date_type.fromisoformat(row[0]),
            amount=int(row[1]),
            merchant=row[2],
            category=row[3],
            source=row[4],
            memo=row[5] if len(row) > 5 else "",
        ))
    return result


def _build_rows_and_groups(
    transactions: list[Transaction],
) -> tuple[list[list], list[tuple[int, int]]]:
    by_month: dict[tuple[int, int], list[Transaction]] = defaultdict(list)
    for txn in transactions:
        by_month[(txn.date.year, txn.date.month)].append(txn)

    all_rows: list[list] = []
    groups: list[tuple[int, int]] = []

    for year, month in sorted(by_month.keys(), reverse=True):
        all_rows.append([f"{year}년 {month}월", "", "", ""])

        by_category: dict[str, list[Transaction]] = defaultdict(list)
        for txn in by_month[(year, month)]:
            by_category[txn.category].append(txn)

        for category in sorted(by_category.keys()):
            cat_txns = by_category[category]
            total = sum(t.amount for t in cat_txns)
            all_rows.append([category, "", f"₩{total:,}", ""])

            detail_start = len(all_rows)
            for txn in sorted(cat_txns, key=lambda t: t.date):
                all_rows.append(["", txn.date.isoformat(), txn.merchant, f"₩{txn.amount:,}"])
            detail_end = len(all_rows)

            if detail_end > detail_start:
                groups.append((detail_start, detail_end))

        all_rows.append(["", "", "", ""])

    return all_rows, groups
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_dashboard.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat: add dashboard builder with monthly row groups"
```

---

## Task 6: Main import script

**Files:**
- Create: `import.py`
- Create: `tests/test_import.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_import.py`:

```python
from unittest.mock import MagicMock, patch
from import_cmd import deduplicate, detect_source


def test_deduplicate_removes_existing_transactions():
    from datetime import date
    from models import Transaction

    existing_keys = {("2026-05-15", "4500", "스타벅스")}
    txns = [
        Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card"),
        Transaction(date=date(2026, 5, 16), amount=3800, merchant="이디야", category="", source="kb_card"),
    ]
    result = deduplicate(txns, existing_keys)
    assert len(result) == 1
    assert result[0].merchant == "이디야"


def test_deduplicate_returns_all_when_no_overlap():
    from datetime import date
    from models import Transaction

    txns = [
        Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card"),
    ]
    result = deduplicate(txns, set())
    assert len(result) == 1


def test_detect_source_from_filename():
    assert detect_source("naver_2026.csv") == "naver"
    assert detect_source("kakao_may.csv") == "kakao"
    assert detect_source("kb_card_05.csv") == "kb"
    assert detect_source("monthly_statement.csv") == "kb"
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/test_import.py -v
```

Expected: `ModuleNotFoundError: No module named 'import_cmd'`

> **Note:** The file is named `import_cmd.py` (not `import.py`) to avoid shadowing Python's built-in `import` statement in tests.

- [ ] **Step 3: Implement `import_cmd.py`**

```python
import argparse
from models import Transaction
from sheets import SheetsClient
from categorizer import categorize
from dashboard import build_dashboard
from parsers import kb_card, naver_pay, kakao_pay
from config import SPREADSHEET_ID, CREDENTIALS_FILE

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


def main():
    parser = argparse.ArgumentParser(description="Import spending CSV to Google Sheets")
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--source", choices=list(SOURCE_MAP.keys()))
    args = parser.parse_args()

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
    for filepath in args.files:
        source = args.source or detect_source(filepath)
        all_transactions.extend(SOURCE_MAP[source].parse(filepath))

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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_import.py -v
```

Expected: 3 passed

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add import_cmd.py tests/test_import.py
git commit -m "feat: add main import CLI with deduplication"
```

---

## Task 7: Google Sheets setup guide

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```markdown
# Personal Budget Tracker

## Setup

### 1. Google Sheets 준비

1. [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
2. Google Sheets API 활성화
3. Service Account 생성 → JSON 키 다운로드 → `credentials.json`으로 저장
4. Google Sheets에서 새 스프레드시트 생성
5. 스프레드시트 URL의 ID 복사 (`.../spreadsheets/d/<ID>/edit`)
6. 스프레드시트 공유 → service account 이메일에 편집자 권한 부여

### 2. 환경 변수 설정

```bash
export SPREADSHEET_ID="your-spreadsheet-id"
export GOOGLE_CREDENTIALS="credentials.json"  # default
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

## 사용법

```bash
# 국민카드 CSV 가져오기
python import_cmd.py --files kb_card_may.csv

# 여러 파일 동시에
python import_cmd.py --files kb_card.csv naver_pay.csv kakao_pay.csv

# 소스 직접 지정
python import_cmd.py --files statement.csv --source kb
```

처음 실행하면 알 수 없는 가맹점마다 카테고리를 입력하라는 프롬프트가 나타납니다.
같은 가맹점은 다음 실행부터 자동으로 분류됩니다.

## CSV 파일 형식

각 카드사/앱 앱에서 내보낸 CSV를 그대로 사용합니다.
실제 내보낸 CSV의 컬럼명이 다르면 각 파서 파일 상단의 `*_COL` 상수를 수정하세요.

- `parsers/kb_card.py` → `DATE_COL`, `MERCHANT_COL`, `AMOUNT_COL`
- `parsers/naver_pay.py` → `DATE_COL`, `MERCHANT_COL`, `AMOUNT_COL`, `STATUS_COL`
- `parsers/kakao_pay.py` → `DATE_COL`, `MERCHANT_COL`, `AMOUNT_COL`, `TYPE_COL`
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add setup and usage guide"
```

---

## Done ✓

Run the full suite one final time to confirm everything is green:

```bash
pytest -v
```

Expected: all tests pass

The tool is ready to use. Run:

```bash
export SPREADSHEET_ID="<your-id>"
python import_cmd.py --files your_kb_card.csv
```
