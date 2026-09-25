# Shopcart

A small Python package used as a sample repo for TriageRace.

It contains a seeded bug in `pricing.py` — a boundary comparison error in
`apply_discount` that causes orders of exactly $100.00 to miss the promotional
discount. The bug is intentionally subtle and requires reading the business
rule ("10% off orders of **$100 or more**") alongside the log output to find.

Run the tests:

```bash
python -m pytest
```

Expected: **1 failure** (`test_discounts.py::test_discount_applies_at_exactly_100`).
Changing `>` to `>=` in `pricing.py` makes all tests pass.
