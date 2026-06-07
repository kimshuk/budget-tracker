from dataclasses import dataclass
from datetime import date

@dataclass
class Transaction:
    date: date
    amount: int
    merchant: str
    category: str
    source: str
    memo: str = ""
    source_file: str = ""
    merchant_raw: str = ""
    merchant_normalized: str = ""
    subcategory: str = ""
    payment_method: str = ""
    approval_number: str = ""
