from unittest.mock import MagicMock, patch
from sheets import SheetsClient


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
