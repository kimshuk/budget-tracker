from unittest.mock import MagicMock, patch
from import_cmd import (
    DEFAULT_CATEGORIES,
    CATEGORIES_LIST_SHEET,
    HEADER,
    build_transaction_id,
    detect_source,
    normalize_transaction,
    recategorize_existing,
    should_process_file,
    setup_categories,
    upsert_transactions,
)


def test_transaction_id_is_stable_from_raw_identity_fields():
    from datetime import date
    from models import Transaction

    txn = Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card")

    first = build_transaction_id(txn)
    second = build_transaction_id(txn)

    assert first == second
    assert len(first) == 64


def test_normalize_transaction_outputs_canonical_row():
    from datetime import date
    from models import Transaction

    txn = Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="카페", source="kb_card")

    row = normalize_transaction(txn, source_file="KB카드내역_5월.csv", imported_at="2026-06-02T12:00:00+09:00")

    assert row[HEADER.index("transaction_id")] == build_transaction_id(txn)
    assert row[HEADER.index("source")] == "kb_card"
    assert row[HEADER.index("source_file")] == "KB카드내역_5월.csv"
    assert row[HEADER.index("merchant_raw")] == "스타벅스"
    assert row[HEADER.index("merchant_normalized")] == "스타벅스"
    assert row[HEADER.index("category")] == "카페"
    assert row[HEADER.index("imported_at")] == "2026-06-02T12:00:00+09:00"


def test_upsert_transactions_preserves_existing_category_and_adds_new_rows():
    from datetime import date
    from models import Transaction

    existing_txn = Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card")
    existing_id = build_transaction_id(existing_txn)
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = [
        HEADER,
        [
            existing_id, "kb_card", "old.csv", "2026-05-15", "스타벅스", "스타벅스",
            4500, "카페", "", "", "", "2026-06-01T00:00:00+09:00", "",
        ],
    ]
    txns = [
        existing_txn,
        Transaction(date=date(2026, 5, 16), amount=3800, merchant="이디야", category="카페", source="kb_card"),
    ]

    inserted, updated = upsert_transactions(
        mock_client,
        txns,
        source_file="new.csv",
        imported_at="2026-06-02T12:00:00+09:00",
    )

    assert inserted == 1
    assert updated == 0
    written = mock_client.clear_and_write.call_args[0][1]
    assert written[0] == HEADER
    assert written[1][HEADER.index("category")] == "카페"
    assert written[2][HEADER.index("merchant_raw")] == "이디야"


def test_should_process_file_detects_unchanged_file(tmp_path):
    filepath = tmp_path / "KB카드내역_5월.csv"
    filepath.write_text("date,amount\n2026-05-15,4500\n", encoding="utf-8")

    state = {
        str(filepath): {
            "file_hash": "wrong",
            "source": "kb",
        }
    }
    assert should_process_file(filepath, "kb", state) is True

    state[str(filepath)]["file_hash"] = __import__("import_cmd")._file_hash(filepath)
    assert should_process_file(filepath, "kb", state) is False


def test_detect_source_from_filename():
    assert detect_source("naver_2026.csv") == "naver"
    assert detect_source("kakao_may.csv") == "kakao"
    assert detect_source("kb_card_05.csv") == "kb"
    assert detect_source("monthly_statement.csv") == "kb"


def test_recategorize_existing_updates_uncategorized():
    mock_client = MagicMock()
    mock_client.read_sheet.side_effect = [
        [
            ["date", "amount", "merchant", "category", "source", "memo"],
            ["2026-05-15", "4500", "스타벅스", "미분류", "kb_card", ""],
            ["2026-05-16", "32000", "쿠팡", "미분류", "kb_card", ""],
        ],
        [["스타벅스", "카페"], ["쿠팡", "쇼핑"]],
    ]

    count = recategorize_existing(mock_client)

    assert count == 2
    written = mock_client.clear_and_write.call_args[0][1]
    assert written[1][3] == "카페"
    assert written[2][3] == "쇼핑"


def test_recategorize_existing_skips_already_categorized():
    mock_client = MagicMock()
    mock_client.read_sheet.side_effect = [
        [
            ["date", "amount", "merchant", "category", "source", "memo"],
            ["2026-05-15", "4500", "스타벅스", "카페", "kb_card", ""],
        ],
        [["스타벅스", "카페"]],
    ]

    count = recategorize_existing(mock_client)

    assert count == 0
    mock_client.clear_and_write.assert_not_called()


def test_recategorize_existing_updates_changed_categories():
    mock_client = MagicMock()
    mock_client.read_sheet.side_effect = [
        [
            ["date", "amount", "merchant", "category", "source", "memo"],
            ["2026-05-15", "4500", "스타벅스", "카페", "kb_card", ""],
            ["2026-05-16", "32000", "쿠팡", "쇼핑", "kb_card", ""],
        ],
        [["스타벅스", "식비"], ["쿠팡", "생활비"]],
    ]

    count = recategorize_existing(mock_client)

    assert count == 2
    written = mock_client.clear_and_write.call_args[0][1]
    assert written[1][3] == "식비"
    assert written[2][3] == "생활비"


def test_recategorize_existing_leaves_unmapped_merchants_unchanged():
    mock_client = MagicMock()
    mock_client.read_sheet.side_effect = [
        [
            ["date", "amount", "merchant", "category", "source", "memo"],
            ["2026-05-15", "4500", "스타벅스", "카페", "kb_card", ""],
        ],
        [["쿠팡", "쇼핑"]],
    ]

    count = recategorize_existing(mock_client)

    assert count == 0
    mock_client.clear_and_write.assert_not_called()


def test_recategorize_existing_no_mapping_does_nothing():
    mock_client = MagicMock()
    mock_client.read_sheet.side_effect = [
        [
            ["date", "amount", "merchant", "category", "source", "memo"],
            ["2026-05-15", "4500", "스타벅스", "미분류", "kb_card", ""],
        ],
        [],
    ]

    count = recategorize_existing(mock_client)

    assert count == 0
    mock_client.clear_and_write.assert_not_called()


def test_setup_categories_populates_defaults_when_empty():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = []

    setup_categories(mock_client)

    mock_client.ensure_sheet_exists.assert_called_with(CATEGORIES_LIST_SHEET)
    saved = mock_client.append_rows.call_args[0][1]
    assert saved == [[c] for c in DEFAULT_CATEGORIES]
    mock_client.apply_dropdown_validation.assert_called_once()


def test_setup_categories_skips_populate_when_already_has_data():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = [["식비"], ["카페"]]

    setup_categories(mock_client)

    mock_client.append_rows.assert_not_called()
    mock_client.apply_dropdown_validation.assert_called_once()
