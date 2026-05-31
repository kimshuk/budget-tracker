from datetime import date
from models import Transaction

def test_transaction_fields():
    txn = Transaction(
        date=date(2026, 5, 15),
        amount=4500,
        merchant="스타벅스 강남점",
        category="카페",
        source="kb_card",
        memo=""
    )
    assert txn.date == date(2026, 5, 15)
    assert txn.amount == 4500
    assert txn.merchant == "스타벅스 강남점"
    assert txn.category == "카페"
    assert txn.source == "kb_card"
    assert txn.memo == ""

def test_transaction_memo_defaults_to_empty():
    txn = Transaction(
        date=date(2026, 5, 15),
        amount=1000,
        merchant="GS25",
        category="편의점",
        source="kakao_pay"
    )
    assert txn.memo == ""
