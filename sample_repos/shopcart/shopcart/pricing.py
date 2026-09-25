from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from .models import LineItem

DISCOUNT_THRESHOLD = Decimal("100.00")
DISCOUNT_RATE = Decimal("0.10")

# Known valid coupon codes
_VALID_COUPONS = {"SAVE10", "WELCOME", "LOYALTY5"}


def subtotal(items: list[LineItem]) -> Decimal:
    """Return sum of unit_price * quantity for all items, quantized to cents."""
    total = sum(item.unit_price * item.quantity for item in items)
    return Decimal(total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_coupon(code: Optional[str]) -> bool:
    """Return True for None/empty (no coupon) or a known code. Raise ValueError for unknown."""
    if code is None or code == "":
        return True
    if code in _VALID_COUPONS:
        return True
    raise ValueError(f"Invalid coupon code: {code!r}")


def apply_discount(amount: Decimal) -> Decimal:
    """Apply 10% discount to orders of $100.00 or more."""
    # Promo policy: "10% off orders of $100.00 or more"
    if amount > DISCOUNT_THRESHOLD:   # SEEDED BUG: should be >=
        amount = amount * (1 - DISCOUNT_RATE)
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def apply_tax(amount: Decimal, rate: Decimal) -> Decimal:
    """Apply tax rate to amount, rounded to cents."""
    return (amount * (1 + rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def order_total(
    items: list[LineItem],
    coupon: Optional[str] = None,
    tax_rate: Decimal = Decimal("0"),
) -> Decimal:
    """
    Compute the final order total.
    Steps: validate coupon → subtotal → apply_discount → apply_tax.
    Tax is applied AFTER the discount.
    Raises ValueError for an invalid coupon.
    """
    validate_coupon(coupon)
    amount = subtotal(items)
    amount = apply_discount(amount)
    amount = apply_tax(amount, tax_rate)
    return amount
