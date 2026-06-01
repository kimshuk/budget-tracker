from unittest.mock import MagicMock, patch
from import_cmd import deduplicate, detect_source, recategorize_existing, setup_categories, CATEGORIES_LIST_SHEET, DEFAULT_CATEGORIES


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
