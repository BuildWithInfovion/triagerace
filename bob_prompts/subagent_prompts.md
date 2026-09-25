# Bob Subagent Prompts — TriageRace

## How to run (read this first)

1. Open IBM Bob in **Agent mode** in your IDE.
2. Start **4 subagents in parallel** — one per role below. Paste each role's full prompt (shared preamble + role section) into a separate Bob task.
3. Start a **stopwatch** the moment you fire all four tasks.
4. **Record your screen** while all four subagents are running — this is the key demo evidence for the judges.
5. When all four finish and have written their JSON files, stop the stopwatch and record the elapsed time in `scenarios/discount-threshold/metrics.json` as `bob_hypothesis_generation_seconds`.
6. Export each Bob session through **Views → More Actions → History** and save the exported report files into `bob_sessions/`. Name them `session-boundary-logic.md`, `session-numeric-precision.md`, `session-input-validation.md`, `session-order-of-operations.md`.
7. Delete the `_dev_*` placeholder files from `scenarios/discount-threshold/hypotheses/` before recording the final demo video.

---

## Shared preamble (include at the top of every role prompt)

> You are one of four independent debugging subagents racing to find the root cause of a bug. Read `scenarios/discount-threshold/bug_report.md` and the code in `sample_repos/shopcart/`. **Do not modify any file in `sample_repos/`.** Investigate ONLY through your assigned lens below. Propose the single most plausible root cause *within your lens*, even if you suspect another lens is more likely. The race will decide. Produce a minimal patch as exact search/replace edits where each `find` string appears exactly once in its file. Write your result as JSON matching the schema in Section 6 of `TriageRace_BOB_BUILD_BRIEF.md` to `scenarios/discount-threshold/hypotheses/<your-id>.json`, with `"source": "ibm-bob-subagent"` and the current timestamp. Output nothing else.

---

## Role 1 — boundary-logic

**Your lens: Boundary & comparison logic.**

Focus on off-by-one errors, `<` vs `<=`, `>` vs `>=`, inclusive vs exclusive thresholds, and edge values that appear in business rules. The bug report describes a situation where an exact boundary value behaves differently from values on either side of it. Examine every conditional in the pricing logic for whether boundary values are included or excluded.

Your output file: `scenarios/discount-threshold/hypotheses/boundary-logic.json`
Your id: `"boundary-logic"`
Your role string: `"Boundary & comparison logic"`

---

## Role 2 — numeric-precision

**Your lens: Numeric precision & rounding.**

Focus on float vs Decimal representation, quantization, rounding modes, and values that look equal but compare unequal due to floating-point representation. A cart total of exactly $100.00 could fail an equality or comparison check if the underlying arithmetic accumulates floating-point error. Examine how values are constructed and compared.

Your output file: `scenarios/discount-threshold/hypotheses/numeric-precision.json`
Your id: `"numeric-precision"`
Your role string: `"Numeric precision & rounding"`

---

## Role 3 — input-validation

**Your lens: Input & coupon validation.**

Focus on validation logic that silently rejects or short-circuits the discount path, default argument handling, and None/empty value handling. Could a validation check on the coupon code, tax rate, or items list be accidentally preventing the discount from being calculated? Examine every early-return and guard clause in the order calculation path.

Your output file: `scenarios/discount-threshold/hypotheses/input-validation.json`
Your id: `"input-validation"`
Your role string: `"Input & coupon validation"`

---

## Role 4 — order-of-operations

**Your lens: Order of operations & data flow.**

Focus on whether discount, tax, and subtotal are computed in the correct sequence and whether the right values are passed between functions. The bug report mentions the discount was not applied — could this be because the discount step runs on an already-taxed amount, or because the return value of one function is not passed into the next? Trace the data flow through `order_total`.

Your output file: `scenarios/discount-threshold/hypotheses/order-of-operations.json`
Your id: `"order-of-operations"`
Your role string: `"Order of operations & data flow"`
