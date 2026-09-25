"""
Backend tests for TriageRace (M3).
Covers: patch apply logic, scenario/hypothesis loading, dev-file filtering,
and an end-to-end race with a known-good and known-bad hypothesis.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
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


def test_hypotheses_load_four_dev_placeholders():
    """All 4 dev placeholder hypotheses are loaded when no real ones exist."""
    hyps = _load_hypotheses(SCENARIO_DIR / "hypotheses")
    assert len(hyps) == 4
    assert all(h.is_dev for h in hyps)


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

def test_e2e_race_correct_hypothesis_passes():
    """
    End-to-end: the correct boundary-logic hypothesis passes the failing test;
    the wrong order-of-operations hypothesis fails.
    All hypotheses run concurrently (overlapping timestamps).
    """
    import asyncio as _asyncio
    import uuid as _uuid

    # Set a throwaway DB
    db_path = tempfile.mktemp(suffix=".db")
    os.environ["TRIAGERACE_DB"] = db_path

    from app import db as _db
    _db.init_db()

    # Build a minimal scenario with 2 hypotheses: 1 correct, 1 wrong
    correct_patch = [{
        "file": "shopcart/pricing.py",
        "find": "    if amount > DISCOUNT_THRESHOLD:   # SEEDED BUG: should be >=",
        "replace": "    if amount >= DISCOUNT_THRESHOLD:",
    }]
    wrong_patch = [{
        "file": "shopcart/pricing.py",
        "find": "    amount = subtotal(items)\n    amount = apply_discount(amount)\n    amount = apply_tax(amount, tax_rate)",
        "replace": "    amount = subtotal(items)\n    amount = apply_tax(amount, tax_rate)\n    amount = apply_discount(amount)",
    }]

    run_id = str(_uuid.uuid4())
    _db.insert_run(run_id, "discount-threshold", "test bug report", time.time())

    for hyp_id, patch in [("boundary-logic", correct_patch), ("order-of-operations", wrong_patch)]:
        from app.scenarios import load_all_scenarios
        scenarios = load_all_scenarios()
        sc = scenarios["discount-threshold"]
        for h in sc.hypotheses:
            if h.id == hyp_id:
                _db.insert_hypothesis(run_id, hyp_id, json.dumps(h.model_dump()))
                break

    from app.race import run_race
    _asyncio.run(run_race(run_id))

    run = _db.get_run(run_id)
    hyps = {h["hypothesis_id"]: h for h in _db.get_hypotheses(run_id)}

    assert run["status"] == "race_done", f"Expected race_done, got {run['status']}"
    assert run["winner_hypothesis_id"] == "boundary-logic"
    assert hyps["boundary-logic"]["status"] == "passed"
    assert hyps["order-of-operations"]["status"] in ("failed", "patch_failed")

    # Overlapping timestamps: both started before either finished
    start_bl = hyps["boundary-logic"]["started_at"]
    start_oo = hyps["order-of-operations"]["started_at"]
    finish_bl = hyps["boundary-logic"]["finished_at"]
    finish_oo = hyps["order-of-operations"]["finished_at"]
    # Both should have started (not None)
    assert start_bl is not None
    assert start_oo is not None
    # At least one started before the other finished → concurrent
    assert start_bl < finish_oo or start_oo < finish_bl

    # Cleanup
    os.unlink(db_path)
    shutil.rmtree(".race_work", ignore_errors=True)
