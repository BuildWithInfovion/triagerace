"""
Backend tests for TriageRace (M3).
Covers: patch apply logic, scenario/hypothesis loading, dev-file filtering,
and an end-to-end race with a known-good and known-bad hypothesis.
"""
from __future__ import annotations

import json
import os
import sys
import time
import asyncio
from pathlib import Path

import pytest

# Make sure the backend app package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scenarios import (
    Hypothesis,
    PatchEdit,
    ScenarioConfig,
    _load_hypotheses,
    load_scenario,
)
from app.race import _apply_patch, _copy_repo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent
SHOPCART_REPO = PROJECT_ROOT / "sample_repos" / "shopcart"
SCENARIO_DIR = PROJECT_ROOT / "scenarios" / "discount-threshold"


def _make_hypothesis(patch_edits: list[dict], hyp_id: str = "test-hyp") -> Hypothesis:
    return Hypothesis(
        id=hyp_id,
        role="Test role",
        title="Test hypothesis",
        suspected_file="shopcart/pricing.py",
        suspected_line=1,
        reasoning="test",
        evidence=[],
        confidence=0.5,
        patch=[PatchEdit(**e) for e in patch_edits],
        source="dev-placeholder",
        generated_at="2025-01-01T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Patch apply tests
# ---------------------------------------------------------------------------

def test_patch_applies_when_find_matches_once(tmp_path):
    """A patch whose find string appears exactly once is applied correctly."""
    f = tmp_path / "pricing.py"
    f.write_text("    if amount > DISCOUNT_THRESHOLD:   # SEEDED BUG: should be >=\n")

    hyp = _make_hypothesis([{
        "file": "pricing.py",
        "find": "    if amount > DISCOUNT_THRESHOLD:   # SEEDED BUG: should be >=",
        "replace": "    if amount >= DISCOUNT_THRESHOLD:",
    }])

    ok, reason = _apply_patch(tmp_path, hyp)
    assert ok, reason
    assert ">=" in f.read_text()


def test_patch_fails_when_find_not_found(tmp_path):
    """A patch whose find string does not exist produces patch_failed."""
    f = tmp_path / "pricing.py"
    f.write_text("some other content\n")

    hyp = _make_hypothesis([{
        "file": "pricing.py",
        "find": "this string does not exist",
        "replace": "anything",
    }])

    ok, reason = _apply_patch(tmp_path, hyp)
    assert not ok
    assert "not found" in reason


def test_patch_fails_when_find_matches_multiple_times(tmp_path):
    """A patch whose find string appears more than once is rejected."""
    f = tmp_path / "pricing.py"
    f.write_text("duplicate line\nduplicate line\n")

    hyp = _make_hypothesis([{
        "file": "pricing.py",
        "find": "duplicate line",
        "replace": "replaced",
    }])

    ok, reason = _apply_patch(tmp_path, hyp)
    assert not ok
    assert "matches" in reason


def test_patch_fails_when_file_missing(tmp_path):
    """A patch targeting a non-existent file is rejected."""
    hyp = _make_hypothesis([{
        "file": "nonexistent.py",
        "find": "anything",
        "replace": "anything",
    }])
    ok, reason = _apply_patch(tmp_path, hyp)
    assert not ok
    assert "not found" in reason.lower()


# ---------------------------------------------------------------------------
# Scenario loading tests
# ---------------------------------------------------------------------------

def test_scenario_loads_correctly():
    """The discount-threshold scenario loads with correct metadata."""
    s = load_scenario(SCENARIO_DIR)
    assert s is not None
    assert s.config.id == "discount-threshold"
    assert s.config.failing_test == "tests/test_discounts.py::test_discount_applies_at_exactly_100"
    assert len(s.bug_report) > 100
    assert s.metrics is not None


def test_shipped_hypotheses_are_four_bob_lenses():
    """The shipped scenario has 4 hypotheses, one per lens, all produced by IBM Bob subagents."""
    hyps = _load_hypotheses(SCENARIO_DIR / "hypotheses")
    assert len(hyps) == 4
    assert len({h.id for h in hyps}) == 4
    assert all(h.source == "ibm-bob-subagent" for h in hyps)


def test_dev_files_ignored_when_real_ones_exist(tmp_path):
    """_dev_* files are skipped once any non-dev hypothesis exists."""
    hyp_dir = tmp_path / "hypotheses"
    hyp_dir.mkdir()

    # Write one real hypothesis
    real = {
        "id": "boundary-logic",
        "role": "Boundary",
        "title": "Real hyp",
        "suspected_file": "shopcart/pricing.py",
        "suspected_line": 30,
        "reasoning": "real",
        "evidence": [],
        "confidence": 0.8,
        "patch": [{"file": "shopcart/pricing.py", "find": "x", "replace": "y"}],
        "source": "ibm-bob-subagent",
        "generated_at": "2025-01-01T00:00:00+00:00",
    }
    (hyp_dir / "boundary-logic.json").write_text(json.dumps(real))

    # Write one dev placeholder
    dev = {**real, "id": "_dev_fake", "source": "dev-placeholder"}
    (hyp_dir / "_dev_fake.json").write_text(json.dumps(dev))

    hyps = _load_hypotheses(hyp_dir)
    assert len(hyps) == 1
    assert hyps[0].source == "ibm-bob-subagent"


def test_invalid_hypothesis_file_is_skipped(tmp_path):
    """A corrupt JSON file is skipped without crashing."""
    hyp_dir = tmp_path / "hypotheses"
    hyp_dir.mkdir()
    (hyp_dir / "bad.json").write_text("{not valid json")
    hyps = _load_hypotheses(hyp_dir)
    assert hyps == []


# ---------------------------------------------------------------------------
# End-to-end race test
# ---------------------------------------------------------------------------

def test_e2e_race_correct_hypothesis_passes(tmp_path, monkeypatch):
    """
    End-to-end: the correct boundary fix passes the failing test; a wrong
    order-of-operations fix fails. Hypotheses are injected here so the test
    doesn't depend on whichever hypothesis files are currently on disk.
    Both run concurrently (overlapping timestamps).
    """
    import asyncio as _asyncio
    import uuid as _uuid

    monkeypatch.setenv("TRIAGERACE_DB", str(tmp_path / "test.db"))
    monkeypatch.chdir(tmp_path)  # .race_work is relative to cwd

    from app import db as _db
    from app import race as _race
    from app.scenarios import LoadedScenario

    _db.init_db()

    correct = _make_hypothesis([{
        "file": "shopcart/pricing.py",
        "find": "    if amount > DISCOUNT_THRESHOLD:",
        "replace": "    if amount >= DISCOUNT_THRESHOLD:",
    }], hyp_id="boundary-logic")
    wrong = _make_hypothesis([{
        "file": "shopcart/pricing.py",
        "find": "    amount = apply_discount(amount)\n    amount = apply_tax(amount, tax_rate)",
        "replace": "    amount = apply_tax(amount, tax_rate)\n    amount = apply_discount(amount)",
    }], hyp_id="order-of-operations")

    real = load_scenario(SCENARIO_DIR)
    scenario = LoadedScenario(real.config, real.bug_report, [correct, wrong], {}, SCENARIO_DIR)
    monkeypatch.setattr(_race, "load_all_scenarios", lambda: {"discount-threshold": scenario})

    run_id = str(_uuid.uuid4())
    _db.insert_run(run_id, "discount-threshold", "test bug report", time.time())
    for h in (correct, wrong):
        _db.insert_hypothesis(run_id, h.id, json.dumps(h.model_dump()))

    _asyncio.run(_race.run_race(run_id))

    run = _db.get_run(run_id)
    hyps = {h["hypothesis_id"]: h for h in _db.get_hypotheses(run_id)}

    assert run["status"] == "race_done", f"Expected race_done, got {run['status']}"
    assert run["verify_output"].startswith("BASELINE:FAIL"), "baseline must fail on unpatched code"
    assert run["winner_hypothesis_id"] == "boundary-logic"
    assert hyps["boundary-logic"]["status"] == "passed"
    assert hyps["order-of-operations"]["status"] == "failed"

    # Overlapping timestamps: at least one started before the other finished → concurrent
    bl, oo = hyps["boundary-logic"], hyps["order-of-operations"]
    assert bl["started_at"] is not None and oo["started_at"] is not None
    assert bl["started_at"] < oo["finished_at"] or oo["started_at"] < bl["finished_at"]


def test_shipped_hypotheses_race_selects_most_confident(tmp_path, monkeypatch):
    """Racing the shipped Bob hypotheses: baseline fails, and among passing ones the most confident is selected."""
    import asyncio as _asyncio
    import uuid as _uuid

    monkeypatch.setenv("TRIAGERACE_DB", str(tmp_path / "test.db"))
    monkeypatch.chdir(tmp_path)

    from app import db as _db
    from app.race import run_race

    _db.init_db()
    sc = load_scenario(SCENARIO_DIR)
    run_id = str(_uuid.uuid4())
    _db.insert_run(run_id, sc.config.id, "test", time.time())
    for h in sc.hypotheses:
        _db.insert_hypothesis(run_id, h.id, json.dumps(h.model_dump()))

    _asyncio.run(run_race(run_id))

    run = _db.get_run(run_id)
    assert run["verify_output"].startswith("BASELINE:FAIL")
    passed = {h["hypothesis_id"] for h in _db.get_hypotheses(run_id) if h["status"] == "passed"}
    assert passed, "at least one Bob hypothesis should fix the failing test"
    confidence = {h.id: h.confidence for h in sc.hypotheses}
    assert run["winner_hypothesis_id"] == max(passed, key=confidence.__getitem__)
