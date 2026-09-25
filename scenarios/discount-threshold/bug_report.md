# Support Ticket #4821

**Reported by:** Customer Support Team  
**Priority:** High  
**Component:** Checkout / Promotions  
**Date:** 2025-09-24

---

## Customer complaint

A customer contacted support after purchasing two "Desk Lamp" units at $50.00 each. Their cart total was exactly **$100.00**. The promotional banner on the site clearly states:

> **"10% off orders of $100 or more"**

The customer expected to be charged **$90.00** but was billed the full **$100.00**. They noted that a colleague who bought a single $120.00 item did receive the discount without any issue.

The customer has asked for a refund of the $10.00 difference and wants to know when the issue will be fixed.

---

## Reproduction steps

1. Add 2 × "Desk Lamp" ($50.00 each) to the cart → cart total = $100.00.
2. Proceed to checkout with no coupon code.
3. Observe: no discount is applied, total remains $100.00.

Compare with:

1. Add 1 × any item priced at $120.00 to the cart.
2. Proceed to checkout.
3. Observe: 10% discount **is** applied correctly → total = $108.00.

---

## Application log excerpt (order ID: ORD-20250924-8821)

```
2025-09-24T14:32:11+05:30 INFO  checkout: starting order calculation customer_id=C-1047
2025-09-24T14:32:11+05:30 INFO  checkout: subtotal=100.00 discount_applied=false total=100.00
2025-09-24T14:32:11+05:30 INFO  checkout: payment charged amount=100.00 currency=INR customer_id=C-1047
```

---

## CI failure (reported same day by automated test run)

```
FAILED tests/test_discounts.py::test_discount_applies_at_exactly_100 - AssertionError: assert Decimal('100.00') == Decimal('90.00')
```

This test was added as part of the promo feature acceptance criteria. It has been failing since the promo was deployed to production on 2025-09-22.

---

## Notes

- The issue is **not** reproducible for orders above $100.00 (e.g. $100.01, $120.00).
- No coupon codes are involved — this is the threshold discount only.
- Tax rate is 0% in the test environment.
- The promo banner copy has been double-checked and is correct: "10% off orders of **$100 or more**".
