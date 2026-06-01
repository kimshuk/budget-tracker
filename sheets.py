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
                        {"deleteDimensionGroup": {"range": group["range"]}}
                    )
        if requests:
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": requests},
            ).execute()

    def apply_dropdown_validation(self, sheet_id: int, col_index: int, source_range: str) -> None:
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={
                "requests": [{
                    "setDataValidation": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "startColumnIndex": col_index,
                            "endColumnIndex": col_index + 1,
                        },
                        "rule": {
                            "condition": {
                                "type": "ONE_OF_RANGE",
                                "values": [{"userEnteredValue": source_range}],
                            },
                            "showCustomUi": True,
                            "strict": False,
                        },
                    }
                }]
            },
        ).execute()

    def apply_row_groups(self, sheet_id: int, groups: list[tuple[int, int]]) -> None:
        if not groups:
            return
        add_requests = [
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
        collapse_requests = [
            {
                "updateDimensionGroup": {
                    "dimensionGroup": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": start,
                            "endIndex": end,
                        },
                        "depth": 1,
                        "collapsed": True,
                    },
                    "fields": "collapsed",
                }
            }
            for start, end in groups
        ]
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"requests": add_requests + collapse_requests},
        ).execute()
