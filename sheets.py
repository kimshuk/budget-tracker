from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _rgb(red: int, green: int, blue: int) -> dict:
    return {"red": red / 255, "green": green / 255, "blue": blue / 255}


def _repeat_cell(
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_col: int,
    end_col: int,
    *,
    background: dict | None = None,
    bold: bool | None = None,
    horizontal_alignment: str | None = None,
) -> dict:
    user_format = {}
    fields = []
    if background:
        user_format["backgroundColor"] = background
        fields.append("userEnteredFormat.backgroundColor")
    if bold is not None:
        user_format.setdefault("textFormat", {})["bold"] = bold
        fields.append("userEnteredFormat.textFormat.bold")
    if horizontal_alignment:
        user_format["horizontalAlignment"] = horizontal_alignment
        fields.append("userEnteredFormat.horizontalAlignment")

    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "cell": {"userEnteredFormat": user_format},
            "fields": ",".join(fields),
        }
    }


def _borders(
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_col: int,
    end_col: int,
) -> dict:
    border = {
        "style": "SOLID",
        "width": 1,
        "color": _rgb(0, 0, 0),
    }
    return {
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "top": border,
            "bottom": border,
            "left": border,
            "right": border,
            "innerHorizontal": border,
            "innerVertical": border,
        }
    }


def _dashboard_style_requests(sheet_id: int, rows: list[list]) -> list[dict]:
    blue = _rgb(164, 194, 244)
    green = _rgb(182, 215, 168)
    yellow = _rgb(255, 229, 153)
    requests = [
        _column_width(sheet_id, 0, 1, 140),
        _column_width(sheet_id, 1, 2, 130),
        _column_width(sheet_id, 2, 3, 170),
        _column_width(sheet_id, 3, 4, 120),
        _column_width(sheet_id, 4, 5, 40),
        _column_width(sheet_id, 5, 9, 155),
    ]

    for index, row in enumerate(rows):
        label = str(row[0]) if row else ""
        if label == "최근 2개월 카테고리 비교":
            requests.append(_repeat_cell(sheet_id, index, index + 1, 0, 3, background=blue, bold=True, horizontal_alignment="CENTER"))
            requests.append(_borders(sheet_id, index, index + 1, 0, 3))
        elif label == "카테고리":
            requests.append(_repeat_cell(sheet_id, index, index + 1, 0, 3, background=green, bold=True, horizontal_alignment="CENTER"))
            requests.append(_borders(sheet_id, index, index + 1, 0, 3))
        elif label == "거래 상세":
            requests.append(_repeat_cell(sheet_id, index, index + 1, 0, 3, background=green, bold=True, horizontal_alignment="CENTER"))
            requests.append(_borders(sheet_id, index, index + 1, 0, 3))
        elif label.endswith("년") or label.endswith("월"):
            requests.append(_repeat_cell(sheet_id, index, index + 1, 0, 4, background=blue, bold=True))
            requests.append(_borders(sheet_id, index, index + 1, 0, 4))
            if len(row) > 2 and row[2] in {"연간 총 지출", "월 총 지출"}:
                requests.append(_repeat_cell(sheet_id, index, index + 1, 3, 4, background=yellow, bold=True))

    return requests


def _column_width(sheet_id: int, start_col: int, end_col: int, width: int) -> dict:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": start_col,
                "endIndex": end_col,
            },
            "properties": {"pixelSize": width},
            "fields": "pixelSize",
        }
    }


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

    def clear_and_write(
        self,
        sheet_name: str,
        rows: list[list],
        value_input_option: str = "USER_ENTERED",
    ) -> None:
        self._service.spreadsheets().values().clear(
            spreadsheetId=self._spreadsheet_id,
            range=sheet_name,
            body={},
        ).execute()
        if rows:
            self._service.spreadsheets().values().update(
                spreadsheetId=self._spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption=value_input_option,
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

    def clear_merges(self, sheet_id: int) -> None:
        spreadsheet = (
            self._service.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id, fields="sheets(properties(sheetId),merges)")
            .execute()
        )
        requests = []
        for sheet in spreadsheet["sheets"]:
            if sheet["properties"]["sheetId"] == sheet_id:
                for merge in sheet.get("merges", []):
                    requests.append({"unmergeCells": {"range": merge}})
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
        insight_range: tuple[int, int] | None = None,
        dashboard_rows: list[list] | None = None,
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

        if insight_range:
            start, end = insight_range
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start,
                        "endRowIndex": end,
                        "startColumnIndex": 5,
                        "endColumnIndex": 9,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "wrapStrategy": "WRAP",
                        }
                    },
                    "fields": "userEnteredFormat.wrapStrategy",
                }
            })
            requests.extend([
                _repeat_cell(
                    sheet_id,
                    start,
                    start + 1,
                    5,
                    9,
                    background=_rgb(255, 229, 153),
                    bold=True,
                    horizontal_alignment="CENTER",
                ),
                _borders(sheet_id, start, end, 5, 9),
            ])

        requests.extend(_dashboard_style_requests(sheet_id, dashboard_rows or []))

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
