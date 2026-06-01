from datetime import date
from unittest.mock import MagicMock
from models import Transaction
from categorizer import categorize, UNCATEGORIZED

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

    result = categorize(SAMPLE, mock_client)

    assert result[0].category == "카페"
    assert result[1].category == "쇼핑"
    assert result[2].category == "편의점"


def test_unknown_merchant_gets_uncategorized():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = []

    result = categorize(SAMPLE, mock_client)

    assert all(t.category == UNCATEGORIZED for t in result)


def test_same_unknown_merchant_added_only_once():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = []
    txns = [
        Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card"),
        Transaction(date=date(2026, 5, 16), amount=3800, merchant="스타벅스", category="", source="kb_card"),
    ]

    result = categorize(txns, mock_client)

    assert all(t.category == UNCATEGORIZED for t in result)
    saved = mock_client.append_rows.call_args[0][1]
    assert saved == [["스타벅스", ""]]


def test_saves_new_merchants_with_empty_category():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = []

    categorize(SAMPLE, mock_client)

    mock_client.append_rows.assert_called_once()
    saved = mock_client.append_rows.call_args[0][1]
    assert ["스타벅스", ""] in saved
    assert ["쿠팡", ""] in saved
    assert ["GS25", ""] in saved


def test_does_not_save_when_no_new_merchants():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = [["스타벅스", "카페"]]
    txns = [Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card")]

    categorize(txns, mock_client)

    mock_client.append_rows.assert_not_called()


def test_merchant_in_sheet_with_empty_category_not_readded():
    mock_client = MagicMock()
    mock_client.read_sheet.return_value = [["스타벅스", ""]]
    txns = [Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card")]

    result = categorize(txns, mock_client)

    assert result[0].category == UNCATEGORIZED
    mock_client.append_rows.assert_not_called()
