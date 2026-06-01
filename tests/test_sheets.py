from unittest.mock import MagicMock, patch
from dashboard import BarChartSpec
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


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_unhide_rows_updates_hidden_by_user(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    client = SheetsClient("SHEET_ID", "creds.json")

    client.unhide_rows(42, end_index=10)

    mock_service.spreadsheets().batchUpdate.assert_called_once()
    body = mock_service.spreadsheets().batchUpdate.call_args[1]["body"]
    req = body["requests"][0]["updateDimensionProperties"]
    assert req["range"]["sheetId"] == 42
    assert req["range"]["dimension"] == "ROWS"
    assert req["range"]["startIndex"] == 0
    assert req["range"]["endIndex"] == 10
    assert req["properties"]["hiddenByUser"] is False
    assert req["fields"] == "hiddenByUser"


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_unhide_rows_skips_empty_range(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    client = SheetsClient("SHEET_ID", "creds.json")

    client.unhide_rows(42, end_index=0)

    mock_service.spreadsheets().batchUpdate.assert_not_called()


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_clear_charts_deletes_existing_dashboard_charts(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.spreadsheets().get().execute.return_value = {
        "sheets": [
            {"properties": {"sheetId": 42}, "charts": [{"chartId": 101}, {"chartId": 102}]},
            {"properties": {"sheetId": 7}, "charts": [{"chartId": 999}]},
        ]
    }
    client = SheetsClient("SHEET_ID", "creds.json")

    client.clear_charts(42)

    body = mock_service.spreadsheets().batchUpdate.call_args[1]["body"]
    assert body["requests"] == [
        {"deleteEmbeddedObject": {"objectId": 101}},
        {"deleteEmbeddedObject": {"objectId": 102}},
    ]


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_format_dashboard_formats_amount_columns_as_won(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    client = SheetsClient("SHEET_ID", "creds.json")

    client.format_dashboard(42, row_count=20)

    body = mock_service.spreadsheets().batchUpdate.call_args[1]["body"]
    req = body["requests"][0]["repeatCell"]
    assert req["range"]["sheetId"] == 42
    assert req["range"]["startColumnIndex"] == 2
    assert req["range"]["endColumnIndex"] == 4
    assert req["cell"]["userEnteredFormat"]["numberFormat"]["pattern"] == "₩#,##0"


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_format_dashboard_formats_chart_specific_ranges(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    client = SheetsClient("SHEET_ID", "creds.json")
    percent_ranges = [(10, 18)]
    bar_charts = [BarChartSpec(
        title="2026년 5월 vs 2026년 4월 카테고리 지출 비교",
        category_start_index=2,
        category_end_index=10,
        first_series_col_index=1,
        second_series_col_index=2,
        anchor_row_index=0,
    )]

    client.format_dashboard(42, row_count=30, percent_ranges=percent_ranges, bar_charts=bar_charts)

    body = mock_service.spreadsheets().batchUpdate.call_args[1]["body"]
    percent_req = body["requests"][1]["repeatCell"]
    bar_currency_req = body["requests"][2]["repeatCell"]
    assert percent_req["range"]["startRowIndex"] == 10
    assert percent_req["range"]["endRowIndex"] == 18
    assert percent_req["range"]["startColumnIndex"] == 1
    assert percent_req["cell"]["userEnteredFormat"]["numberFormat"]["type"] == "PERCENT"
    assert bar_currency_req["range"]["startRowIndex"] == 2
    assert bar_currency_req["range"]["endRowIndex"] == 10
    assert bar_currency_req["range"]["startColumnIndex"] == 1
    assert bar_currency_req["range"]["endColumnIndex"] == 3
    assert bar_currency_req["cell"]["userEnteredFormat"]["numberFormat"]["type"] == "CURRENCY"


@patch("sheets.build")
@patch("sheets.service_account.Credentials.from_service_account_file")
def test_apply_bar_charts_adds_two_month_comparison_chart(mock_creds, mock_build):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    client = SheetsClient("SHEET_ID", "creds.json")
    charts = [BarChartSpec(
        title="2026년 5월 vs 2026년 4월 카테고리 지출 비교",
        category_start_index=2,
        category_end_index=10,
        first_series_col_index=1,
        second_series_col_index=2,
        anchor_row_index=0,
    )]

    client.apply_bar_charts(42, charts)

    body = mock_service.spreadsheets().batchUpdate.call_args[1]["body"]
    chart = body["requests"][0]["addChart"]["chart"]
    assert chart["spec"]["title"] == "2026년 5월 vs 2026년 4월 카테고리 지출 비교"
    basic = chart["spec"]["basicChart"]
    assert basic["chartType"] == "BAR"
    domain = basic["domains"][0]["domain"]["sourceRange"]["sources"][0]
    first_series = basic["series"][0]["series"]["sourceRange"]["sources"][0]
    second_series = basic["series"][1]["series"]["sourceRange"]["sources"][0]
    assert basic["headerCount"] == 1
    assert domain["startRowIndex"] == 1
    assert domain["endRowIndex"] == 10
    assert first_series["startRowIndex"] == 1
    assert first_series["startColumnIndex"] == 1
    assert first_series["endColumnIndex"] == 2
    assert second_series["startRowIndex"] == 1
    assert second_series["startColumnIndex"] == 2
    assert second_series["endColumnIndex"] == 3
    assert chart["position"]["overlayPosition"]["anchorCell"]["rowIndex"] == 0
    assert chart["position"]["overlayPosition"]["anchorCell"]["columnIndex"] == 5
