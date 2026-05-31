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
