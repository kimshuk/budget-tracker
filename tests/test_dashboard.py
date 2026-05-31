from datetime import date
from unittest.mock import MagicMock
from models import Transaction
from dashboard import _build_rows_and_groups

SAMPLE_TRANSACTIONS = [
    Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="카페", source="kb_card"),
    Transaction(date=date(2026, 5, 16), amount=3800, merchant="이디야커피", category="카페", source="kb_card"),
    Transaction(date=date(2026, 5, 18), amount=25000, merchant="배달의민족", category="식비", source="kakao_pay"),
]


def test_month_header_is_first_row():
    rows, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    assert rows[0][0] == "2026년 5월"


def test_category_summary_row_has_total():
    rows, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    # Categories are sorted by Unicode — find 카페 by content, not index
    cafe_rows = [r for r in rows if r[0] == "카페"]
    assert len(cafe_rows) == 1
    assert cafe_rows[0][2] == "₩8,300"


def test_detail_rows_follow_category_summary():
    rows, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    # Find 카페 summary row, verify its detail rows immediately follow
    cafe_idx = next(i for i, r in enumerate(rows) if r[0] == "카페")
    assert rows[cafe_idx + 1][2] == "스타벅스"
    assert rows[cafe_idx + 1][3] == "₩4,500"
    assert rows[cafe_idx + 2][2] == "이디야커피"


def test_row_groups_cover_detail_rows():
    rows, groups = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    # 카페 summary is at some index; its 2 details immediately follow → group is (idx+1, idx+3)
    cafe_idx = next(i for i, r in enumerate(rows) if r[0] == "카페")
    assert (cafe_idx + 1, cafe_idx + 3) in groups


def test_multiple_categories_each_get_a_group():
    rows, groups = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    assert len(groups) == 2


def test_detail_rows_sorted_by_date():
    txns = [
        Transaction(date=date(2026, 5, 20), amount=1000, merchant="B", category="기타", source="kb_card"),
        Transaction(date=date(2026, 5, 15), amount=2000, merchant="A", category="기타", source="kb_card"),
    ]
    rows, _ = _build_rows_and_groups(txns)
    detail_merchants = [r[2] for r in rows if r[0] == ""]
    assert detail_merchants[0] == "A"
    assert detail_merchants[1] == "B"


def test_blank_separator_row_after_month():
    rows, _ = _build_rows_and_groups(SAMPLE_TRANSACTIONS)
    last = rows[-1]
    assert all(cell == "" for cell in last)


def test_multiple_months_descending():
    txns = [
        Transaction(date=date(2026, 4, 10), amount=5000, merchant="A", category="기타", source="kb_card"),
        Transaction(date=date(2026, 5, 15), amount=4500, merchant="B", category="기타", source="kb_card"),
    ]
    rows, _ = _build_rows_and_groups(txns)
    month_headers = [r[0] for r in rows if "년" in r[0]]
    assert month_headers[0] == "2026년 5월"
    assert month_headers[1] == "2026년 4월"
