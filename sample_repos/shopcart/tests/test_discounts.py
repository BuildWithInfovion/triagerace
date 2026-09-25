"""
The one failing test — the seeded boundary bug.
2 × $50.00 = exactly $100.00. Promo says "10% off $100 or more".
With the bug (>) the discount is not applied → total stays $100.00.
The fix (>=) makes the discount apply → total = $90.00.
"""
from decimal import Decimal
from shopcart import LineItem, order_total


def test_discount_applies_at_exactly_100():
    """Cart of exactly $100.00 must receive the 10% promotional discount."""
    items = [
        LineItem(sku="DL-01", name="Desk Lamp", unit_price=Decimal("50.00"), quantity=2),
    ]
    result = order_total(items, tax_rate=Decimal("0"))
    assert result == Decimal("90.00"), (
        f"Expected $90.00 (10% off $100.00 order), got ${result}. "
        "Check the comparison operator in apply_discount."
    )
