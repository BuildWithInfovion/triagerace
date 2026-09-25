"""
Broad pricing tests — all must pass even with the seeded bug present.
These are strong enough that wrong "fixes" break them.
"""
from decimal import Decimal
import pytest
from shopcart import LineItem, subtotal, apply_discount, apply_tax, order_total, validate_coupon


# ---------------------------------------------------------------------------
# subtotal
# ---------------------------------------------------------------------------

def test_subtotal_single_item():
    items = [LineItem(sku="A1", name="Widget", unit_price=Decimal("9.99"), quantity=3)]
    assert subtotal(items) == Decimal("29.97")


def test_subtotal_multiple_items():
    items = [
        LineItem(sku="A1", name="Widget", unit_price=Decimal("10.00"), quantity=2),
        LineItem(sku="B2", name="Gadget", unit_price=Decimal("5.50"), quantity=4),
    ]
    assert subtotal(items) == Decimal("42.00")


# ---------------------------------------------------------------------------
# apply_discount — boundary: no discount below $100
# ---------------------------------------------------------------------------

def test_no_discount_at_99_99():
    """$99.99 is below the threshold — no discount applied."""
    assert apply_discount(Decimal("99.99")) == Decimal("99.99")


def test_discount_at_150():
    """$150.00 is above the threshold — 10% off → $135.00."""
    assert apply_discount(Decimal("150.00")) == Decimal("135.00")


# ---------------------------------------------------------------------------
# apply_tax — tax applied after discount
# ---------------------------------------------------------------------------

def test_tax_after_discount():
    """
    $150 cart → apply_discount → $135.00 → apply 8% tax → $145.80.
    Verifies tax is applied on the discounted amount, not the original.
    """
    discounted = apply_discount(Decimal("150.00"))
    assert discounted == Decimal("135.00")
    total_with_tax = apply_tax(discounted, Decimal("0.08"))
    assert total_with_tax == Decimal("145.80")


def test_order_total_discount_then_tax():
    """order_total applies discount before tax end-to-end."""
    items = [LineItem(sku="X1", name="Lamp", unit_price=Decimal("75.00"), quantity=2)]
    # subtotal = 150.00, discount → 135.00, tax 8% → 145.80
    assert order_total(items, tax_rate=Decimal("0.08")) == Decimal("145.80")


# ---------------------------------------------------------------------------
# coupon validation
# ---------------------------------------------------------------------------

def test_valid_coupon_accepted():
    assert validate_coupon("SAVE10") is True


def test_none_coupon_accepted():
    assert validate_coupon(None) is True


def test_empty_coupon_accepted():
    assert validate_coupon("") is True


def test_invalid_coupon_raises():
    with pytest.raises(ValueError, match="Invalid coupon code"):
        validate_coupon("BADCODE")


# ---------------------------------------------------------------------------
# rounding half-up
# ---------------------------------------------------------------------------

def test_rounding_half_up():
    """$10.005 should round to $10.01 with ROUND_HALF_UP."""
    items = [LineItem(sku="R1", name="Rounding item", unit_price=Decimal("3.335"), quantity=3)]
    # 3.335 * 3 = 10.005 → rounds to 10.01
    assert subtotal(items) == Decimal("10.01")
