import os
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
