from dataclasses import dataclass
from decimal import Decimal


@dataclass
class LineItem:
    sku: str
    name: str
    unit_price: Decimal
    quantity: int
