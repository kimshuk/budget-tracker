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


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_apply_dropdown_validation_calls_batchUpdate(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    client = SheetsClient("SHEET_ID", "creds.json")

    client.apply_dropdown_validation(42, col_index=1, source_range="=categories!$A:$A")

    mock_service.spreadsheets().batchUpdate.assert_called_once()
    body = mock_service.spreadsheets().batchUpdate.call_args[1]["body"]
    req = body["requests"][0]["setDataValidation"]
    assert req["range"]["sheetId"] == 42
    assert req["range"]["startColumnIndex"] == 1
    assert req["rule"]["condition"]["type"] == "ONE_OF_RANGE"
    assert req["rule"]["condition"]["values"][0]["userEnteredValue"] == "=categories!$A:$A"
