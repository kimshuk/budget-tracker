from datetime import date
from models import Transaction
from dashboard import _build_rows_and_groups, _recent_comparison_row_count

SAMPLE_TRANSACTIONS = [
    Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="카페", source="kb_card"),
    Transaction(date=date(2026, 5, 16), amount=3800, merchant="이디야커피", category="카페", source="kb_card"),
    Transaction(date=date(2026, 5, 18), amount=25000, merchant="배달의민족", category="식비", source="kakao_pay"),
]


def test_year_total_is_first_row():
    rows, _, _, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    assert rows[0] == ["2026년", "", "연간 총 지출", 33300]


def test_month_total_follows_year_total():
    rows, _, _, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    assert rows[1] == ["2026년 5월", "", "월 총 지출", 33300]


def test_category_summary_row_has_total():
    rows, _, _, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    cafe_rows = [r for r in rows if r[0] == "카페"]
    assert cafe_rows[0] == ["카페", "24.9%", 8300, ""]


def test_category_summary_rows_show_monthly_percentages():
    rows, _, _, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    food_rows = [r for r in rows if r[0] == "식비"]
    assert food_rows[0] == ["식비", "75.1%", 25000, ""]


def test_detail_rows_follow_detail_category_section():
    rows, _, _, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    detail_header_idx = next(i for i, r in enumerate(rows) if r[0] == "거래 상세")
    cafe_idx = next(i for i, r in enumerate(rows[detail_header_idx:], start=detail_header_idx) if r[0] == "카페")
    assert rows[cafe_idx + 1][2] == "스타벅스"
    assert rows[cafe_idx + 1][3] == 4500
    assert rows[cafe_idx + 2][2] == "이디야커피"


def test_row_groups_cover_detail_rows():
    rows, groups, _, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    detail_header_idx = next(i for i, r in enumerate(rows) if r[0] == "거래 상세")
    cafe_idx = next(i for i, r in enumerate(rows[detail_header_idx:], start=detail_header_idx) if r[0] == "카페")
    assert (cafe_idx + 1, cafe_idx + 3) in groups


def test_multiple_categories_each_get_a_group():
    _, groups, _, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    assert len(groups) == 2


def test_detail_rows_sorted_by_date():
    txns = [
        Transaction(date=date(2026, 5, 20), amount=1000, merchant="B", category="기타", source="kb_card"),
        Transaction(date=date(2026, 5, 15), amount=2000, merchant="A", category="기타", source="kb_card"),
    ]
    rows, _, _, _ = _build_rows_and_groups(txns)
    detail_merchants = [r[2] for r in rows if r[0] == "" and r[2]]
    assert detail_merchants[0] == "A"
    assert detail_merchants[1] == "B"


def test_blank_separator_row_after_month():
    rows, _, _, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    last = rows[-1]
    assert all(cell == "" for cell in last)


def test_multiple_months_descending():
    txns = [
        Transaction(date=date(2026, 4, 10), amount=5000, merchant="A", category="기타", source="kb_card"),
        Transaction(date=date(2026, 5, 15), amount=4500, merchant="B", category="기타", source="kb_card"),
    ]
    rows, _, _, _ = _build_rows_and_groups(txns)
    month_headers = [r[0] for r in rows if r[0].startswith("2026년") and "월" in r[0]]
    assert month_headers == ["2026년 5월", "2026년 4월"]


def test_recent_two_month_comparison_rows_are_added_at_top():
    txns = [
        Transaction(date=date(2026, 5, 10), amount=5000, merchant="A", category="식비", source="kb_card"),
        Transaction(date=date(2026, 5, 11), amount=3000, merchant="B", category="카페", source="kb_card"),
        Transaction(date=date(2026, 4, 10), amount=7000, merchant="C", category="식비", source="kb_card"),
        Transaction(date=date(2026, 4, 11), amount=2000, merchant="D", category="교통", source="kb_card"),
    ]

    rows, _, _, _ = _build_rows_and_groups(txns)

    assert rows[0] == ["최근 2개월 카테고리 비교", "", "", ""]
    assert rows[1] == ["카테고리", "2026년 5월", "2026년 4월", ""]
    assert ["교통", 0, 2000, ""] in rows
    assert ["식비", 5000, 7000, ""] in rows
    assert ["카페", 3000, 0, ""] in rows


def test_ai_insight_rows_start_below_recent_two_month_comparison_chart():
    txns = [
        Transaction(date=date(2026, 5, 10), amount=60000, merchant="배달의민족", category="식비", source="kb_card"),
        Transaction(date=date(2026, 4, 10), amount=10000, merchant="배달의민족", category="식비", source="kb_card"),
    ]

    rows, _, _, charts = _build_rows_and_groups(
        txns,
        insight_rows=[
            ["AI 월간 인사이트", "", "", ""],
            ["- 식비 증가분 대부분이 배달의민족에서 나왔습니다.", "", "", ""],
            ["", "", "", ""],
        ],
    )

    assert rows[20][5:9] == ["AI 월간 인사이트", "", "", ""]
    assert rows[21][5:9] == ["- 식비 증가분 대부분이 배달의민족에서 나왔습니다.", "", "", ""]
    assert charts[0].category_start_index == 2
    assert charts[0].category_end_index == 3


def test_recent_comparison_row_count_matches_comparison_table_height():
    txns = [
        Transaction(date=date(2026, 5, 10), amount=5000, merchant="A", category="식비", source="kb_card"),
        Transaction(date=date(2026, 5, 11), amount=3000, merchant="B", category="카페", source="kb_card"),
        Transaction(date=date(2026, 4, 10), amount=7000, merchant="C", category="식비", source="kb_card"),
        Transaction(date=date(2026, 4, 11), amount=2000, merchant="D", category="교통", source="kb_card"),
    ]

    assert _recent_comparison_row_count(txns) == 5


def test_builds_percentage_format_ranges_from_monthly_summary_rows():
    _, _, percent_ranges, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    assert percent_ranges == [(3, 5)]


def test_builds_bar_chart_spec_from_recent_two_month_comparison():
    txns = [
        Transaction(date=date(2026, 5, 10), amount=5000, merchant="A", category="식비", source="kb_card"),
        Transaction(date=date(2026, 4, 10), amount=7000, merchant="C", category="식비", source="kb_card"),
    ]

    _, _, _, charts = _build_rows_and_groups(txns)

    assert len(charts) == 1
    chart = charts[0]
    assert chart.title == "2026년 5월 vs 2026년 4월 카테고리 지출 비교"
    assert chart.category_start_index == 2
    assert chart.category_end_index == 3
    assert chart.first_series_col_index == 1
    assert chart.second_series_col_index == 2
    assert chart.anchor_row_index == 0
