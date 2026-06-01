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

    def clear_charts(self, sheet_id: int) -> None:
        spreadsheet = (
            self._service.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id, fields="sheets(properties(sheetId),charts(chartId))")
            .execute()
        )
        requests = []
        for sheet in spreadsheet["sheets"]:
            if sheet["properties"]["sheetId"] == sheet_id:
                for chart in sheet.get("charts", []):
                    requests.append(
                        {"deleteEmbeddedObject": {"objectId": chart["chartId"]}}
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

    def unhide_rows(self, sheet_id: int, end_index: int) -> None:
        if end_index <= 0:
            return
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={
                "requests": [{
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": 0,
                            "endIndex": end_index,
                        },
                        "properties": {"hiddenByUser": False},
                        "fields": "hiddenByUser",
                    }
                }]
            },
        ).execute()

    def format_dashboard(
        self,
        sheet_id: int,
        row_count: int,
        percent_ranges: list[tuple[int, int]] | None = None,
        bar_charts: list | None = None,
    ) -> None:
        if row_count <= 0:
            return
        requests = [{
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": row_count,
                    "startColumnIndex": 2,
                    "endColumnIndex": 4,
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {
                            "type": "CURRENCY",
                            "pattern": "₩#,##0",
                        }
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        }]

        for start, end in percent_ranges or []:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start,
                        "endRowIndex": end,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {
                                "type": "PERCENT",
                                "pattern": "0.0%",
                            }
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            })

        for chart in bar_charts or []:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": chart.category_start_index,
                        "endRowIndex": chart.category_end_index,
                        "startColumnIndex": chart.first_series_col_index,
                        "endColumnIndex": chart.second_series_col_index + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {
                                "type": "CURRENCY",
                                "pattern": "₩#,##0",
                            }
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            })

        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"requests": requests},
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

    def apply_bar_charts(self, sheet_id: int, charts: list) -> None:
        if not charts:
            return
        requests = []
        for chart in charts:
            header_start_index = chart.category_start_index - 1
            requests.append({
                "addChart": {
                    "chart": {
                        "spec": {
                            "title": chart.title,
                            "basicChart": {
                                "chartType": "BAR",
                                "legendPosition": "RIGHT_LEGEND",
                                "axis": [
                                    {
                                        "position": "BOTTOM_AXIS",
                                        "title": "지출",
                                    },
                                    {
                                        "position": "LEFT_AXIS",
                                        "title": "카테고리",
                                    },
                                ],
                                "domains": [{
                                    "domain": {
                                        "sourceRange": {
                                            "sources": [{
                                                "sheetId": sheet_id,
                                                "startRowIndex": header_start_index,
                                                "endRowIndex": chart.category_end_index,
                                                "startColumnIndex": 0,
                                                "endColumnIndex": 1,
                                            }]
                                        }
                                    }
                                }],
                                "series": [
                                    {
                                        "series": {
                                            "sourceRange": {
                                                "sources": [{
                                                    "sheetId": sheet_id,
                                                    "startRowIndex": header_start_index,
                                                    "endRowIndex": chart.category_end_index,
                                                    "startColumnIndex": chart.first_series_col_index,
                                                    "endColumnIndex": chart.first_series_col_index + 1,
                                                }]
                                            }
                                        },
                                        "targetAxis": "BOTTOM_AXIS",
                                    },
                                    {
                                        "series": {
                                            "sourceRange": {
                                                "sources": [{
                                                    "sheetId": sheet_id,
                                                    "startRowIndex": header_start_index,
                                                    "endRowIndex": chart.category_end_index,
                                                    "startColumnIndex": chart.second_series_col_index,
                                                    "endColumnIndex": chart.second_series_col_index + 1,
                                                }]
                                            }
                                        },
                                        "targetAxis": "BOTTOM_AXIS",
                                    },
                                ],
                                "headerCount": 1,
                            },
                        },
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {
                                    "sheetId": sheet_id,
                                    "rowIndex": chart.anchor_row_index,
                                    "columnIndex": 5,
                                },
                                "offsetXPixels": 0,
                                "offsetYPixels": 0,
                                "widthPixels": 640,
                                "heightPixels": 360,
                            }
                        },
                    }
                }
            })
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"requests": requests},
        ).execute()
