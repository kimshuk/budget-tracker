import os
import tempfile
from datetime import date
import pytest
from parsers.kb_card import parse as kb_parse
from parsers.naver_pay import parse as naver_parse
from parsers.kakao_pay import parse as kakao_parse

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_kb_card_parse_count():
    txns = kb_parse(os.path.join(FIXTURES, "kb_card_sample.csv"), encoding="utf-8")
    assert len(txns) == 3


def test_kb_card_parse_first_transaction():
    txns = kb_parse(os.path.join(FIXTURES, "kb_card_sample.csv"), encoding="utf-8")
    t = txns[0]
    assert t.date == date(2026, 5, 15)
    assert t.amount == 4500
    assert t.merchant == "스타벅스 강남점"
    assert t.category == ""
    assert t.source == "kb_card"


def test_kb_card_parse_skips_zero_amount():
    # 국내이용금액=0 행(해외 전용 거래)은 스킵
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("이용일,이용하신곳,국내이용금액(원),할부,결제방법\n")
        f.write("2026-05-01,GOOGLE*PLAY,0,일시불,신용카드\n")
        f.write("2026-05-02,스타벅스,4500,일시불,신용카드\n")
        tmp = f.name
    try:
        txns = kb_parse(tmp, encoding="utf-8")
        assert len(txns) == 1
        assert txns[0].merchant == "스타벅스"
    finally:
        os.unlink(tmp)


def test_kb_card_parse_strips_commas_from_amount():
    txns = kb_parse(os.path.join(FIXTURES, "kb_card_sample.csv"), encoding="utf-8")
    assert txns[2].amount == 32000


def test_naver_pay_parse_skips_cancelled():
    txns = naver_parse(os.path.join(FIXTURES, "naver_pay_sample.csv"))
    assert len(txns) == 2  # 결제취소 row excluded


def test_naver_pay_parse_first_transaction():
    txns = naver_parse(os.path.join(FIXTURES, "naver_pay_sample.csv"))
    t = txns[0]
    assert t.date == date(2026, 5, 16)
    assert t.amount == 15600
    assert t.merchant == "올리브영 온라인"
    assert t.source == "naver_pay"
    assert t.category == ""


def test_kakao_pay_parse_skips_cancelled():
    txns = kakao_parse(os.path.join(FIXTURES, "kakao_pay_sample.csv"))
    assert len(txns) == 2  # 취소 row excluded


def test_kakao_pay_parse_first_transaction():
    txns = kakao_parse(os.path.join(FIXTURES, "kakao_pay_sample.csv"))
    t = txns[0]
    assert t.date == date(2026, 5, 15)
    assert t.amount == 1200
    assert t.merchant == "GS25 강남역점"
    assert t.source == "kakao_pay"
    assert t.category == ""


def test_kb_card_parse_xlsx():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    # Simulate real export: a few metadata rows, then header, then data
    ws.append(["국민카드 이용내역", None, None, None, None])
    ws.append(["조회기간: 2026.05.01 ~ 2026.05.31", None, None, None, None])
    ws.append(["이용일", "이용하신곳", "국내이용금액(원)", "할부", "결제방법"])
    ws.append(["2026-05-15", "스타벅스 강남점", 4500, "일시불", "신용카드"])
    ws.append(["2026-05-20", "쿠팡", "32,000", "일시불", "신용카드"])

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        tmp_path = f.name
    try:
        wb.save(tmp_path)
        txns = kb_parse(tmp_path)
        assert len(txns) == 2
        assert txns[0].date == date(2026, 5, 15)
        assert txns[0].amount == 4500
        assert txns[0].merchant == "스타벅스 강남점"
        assert txns[0].source == "kb_card"
        assert txns[1].amount == 32000
    finally:
        os.unlink(tmp_path)
