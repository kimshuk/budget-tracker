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
