from unittest.mock import MagicMock, patch
from import_cmd import deduplicate, detect_source


def test_deduplicate_removes_existing_transactions():
    from datetime import date
    from models import Transaction

    existing_keys = {("2026-05-15", "4500", "스타벅스")}
    txns = [
        Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card"),
        Transaction(date=date(2026, 5, 16), amount=3800, merchant="이디야", category="", source="kb_card"),
    ]
    result = deduplicate(txns, existing_keys)
    assert len(result) == 1
    assert result[0].merchant == "이디야"


def test_deduplicate_returns_all_when_no_overlap():
    from datetime import date
    from models import Transaction

    txns = [
        Transaction(date=date(2026, 5, 15), amount=4500, merchant="스타벅스", category="", source="kb_card"),
    ]
    result = deduplicate(txns, set())
    assert len(result) == 1


def test_detect_source_from_filename():
    assert detect_source("naver_2026.csv") == "naver"
    assert detect_source("kakao_may.csv") == "kakao"
    assert detect_source("kb_card_05.csv") == "kb"
    assert detect_source("monthly_statement.csv") == "kb"
