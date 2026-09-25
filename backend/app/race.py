"""
Race engine — applies patches and runs pytest concurrently per hypothesis.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

from .db import (
    get_hypotheses,
    get_run,
    insert_hypothesis,
    update_hypothesis,
    update_run,
)
from .scenarios import Hypothesis, LoadedScenario, load_all_scenarios

_WORK_DIR = Path(".race_work")
_MAX_CONCURRENT_RUNS = 2
_active_runs: set[str] = set()
_TAIL_LINES = 60


def _tail(text: str, n: int = _TAIL_LINES) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-n:]) if len(lines) > n else text


def _copy_repo(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"),
    )


def _apply_patch(repo_copy: Path, hypothesis: Hypothesis) -> tuple[bool, str]:
    """Apply all patch edits. Returns (success, reason)."""
    for edit in hypothesis.patch:
        target = repo_copy / edit.file
        if not target.exists():
            return False, f"File not found: {edit.file}"
        text = target.read_text(encoding="utf-8")
        count = text.count(edit.find)
        if count == 0:
            return False, f"find string not found in {edit.file}"
        if count > 1:
            return False, f"find string matches {count} times in {edit.file} (must match exactly once)"
        target.write_text(text.replace(edit.find, edit.replace, 1), encoding="utf-8")
    return True, ""


async def _run_pytest(
    cwd: Path,
    test_target: str,
    timeout_seconds: int,
) -> tuple[int, str]:
    """Run pytest subprocess. Returns (returncode, output)."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", test_target,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        return proc.returncode, stdout.decode(errors="replace")
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.communicate()
        except Exception:
            pass
        return -1, "TIMEOUT: test exceeded time limit"


async def _run_one_hypothesis(
    run_id: str,
    hypothesis: Hypothesis,
    repo_src: Path,
    failing_test: str,
    timeout: int,
) -> None:
    hyp_id = hypothesis.id
    work_dir = _WORK_DIR / run_id / hyp_id

    update_hypothesis(run_id, hyp_id, status="patching", started_at=time.time())

    # Copy repo
    try:
        _copy_repo(repo_src, work_dir)
    except Exception as exc:
        update_hypothesis(run_id, hyp_id, status="error", finished_at=time.time(),
                          test_output=f"Failed to copy repo: {exc}")
        return

    # Apply patch
    ok, reason = _apply_patch(work_dir, hypothesis)
    if not ok:
        update_hypothesis(run_id, hyp_id, status="patch_failed", finished_at=time.time(),
                          test_output=f"Patch failed: {reason}")
        return

    # Run the failing test
    update_hypothesis(run_id, hyp_id, status="testing")
    rc, output = await _run_pytest(work_dir, failing_test, timeout)

    if rc == -1:
        status = "timeout"
    elif rc == 0:
        status = "passed"
    else:
        status = "failed"

    update_hypothesis(
        run_id, hyp_id,
        status=status,
        finished_at=time.time(),
        test_output=_tail(output),
    )


async def run_race(run_id: str) -> None:
    """Main race coroutine — called as a background asyncio task."""
    _active_runs.add(run_id)
    try:
        run = get_run(run_id)
        if not run:
            return

        scenarios = load_all_scenarios()
        scenario = scenarios.get(run["scenario_id"])
        if not scenario:
            update_run(run_id, status="race_done")
            return

        repo_src = scenario.repo_abs
        cfg = scenario.config
        now = time.time()
        update_run(run_id, status="racing", race_started_at=now)

        # --- Baseline check: run failing test on UNPATCHED copy ---
        baseline_dir = _WORK_DIR / run_id / "_baseline"
        try:
            _copy_repo(repo_src, baseline_dir)
        except Exception as exc:
            update_run(run_id, status="race_done",
                       race_finished_at=time.time(),
                       winner_hypothesis_id=None,
                       verify_output=f"Baseline copy failed: {exc}")
            return

        baseline_rc, baseline_out = await _run_pytest(
            baseline_dir, cfg.failing_test, cfg.test_timeout_seconds
        )
        baseline_output = _tail(baseline_out)

        if baseline_rc == 0:
            # Bug is not reproducible — fail loudly
            update_run(
                run_id,
                status="race_done",
                race_finished_at=time.time(),
                verify_output=(
                    "SCENARIO BROKEN: baseline test PASSED on unpatched code. "
                    "The bug is not reproducible.\n\n" + baseline_output
                ),
            )
            _clean_work(run_id)
            return

        # Store baseline result in verify_output temporarily so the UI can show it
        update_run(
            run_id,
            verify_output=f"BASELINE:FAIL\n{baseline_output}",
        )

        # --- Load snapshotted hypotheses from DB ---
        hyp_rows = get_hypotheses(run_id)
        hypotheses_by_id = {h.id: h for h in scenario.hypotheses}

        # Run all hypotheses concurrently
        tasks = []
        for row in hyp_rows:
            hyp = hypotheses_by_id.get(row["hypothesis_id"])
            if hyp is None:
                update_hypothesis(run_id, row["hypothesis_id"], status="error",
                                  test_output="Hypothesis not found in scenario")
                continue
            tasks.append(
                _run_one_hypothesis(
                    run_id, hyp, repo_src,
                    cfg.failing_test, cfg.test_timeout_seconds,
                )
            )

        await asyncio.gather(*tasks)

        # --- Determine winner ---
        final_hyps = get_hypotheses(run_id)
        passed = [h for h in final_hyps if h["status"] == "passed"]
        winner_id = None
        if passed:
            # Earliest finished_at wins
            winner = min(passed, key=lambda h: h["finished_at"] or float("inf"))
            winner_id = winner["hypothesis_id"]

        update_run(
            run_id,
            status="race_done",
            race_finished_at=time.time(),
            winner_hypothesis_id=winner_id,
        )

    finally:
        _active_runs.discard(run_id)
        # Schedule cleanup after 10 minutes
        asyncio.get_event_loop().call_later(600, _clean_work, run_id)


async def run_verify(run_id: str) -> None:
    """Apply the winning patch to a fresh copy and run the full test suite."""
    try:
        run = get_run(run_id)
        if not run or not run["winner_hypothesis_id"]:
            return

        scenarios = load_all_scenarios()
        scenario = scenarios.get(run["scenario_id"])
        if not scenario:
            return

        winner_id = run["winner_hypothesis_id"]
        hypotheses_by_id = {h.id: h for h in scenario.hypotheses}
        winner_hyp = hypotheses_by_id.get(winner_id)
        if not winner_hyp:
            update_run(run_id, verify_status="verify_failed",
                       verify_finished_at=time.time(),
                       verify_output="Winner hypothesis not found")
            return

        update_run(run_id, status="verifying", verify_status="verifying",
                   verify_started_at=time.time())

        verify_dir = _WORK_DIR / run_id / "_verify"
        try:
            _copy_repo(scenario.repo_abs, verify_dir)
        except Exception as exc:
            update_run(run_id, status="verify_failed", verify_status="verify_failed",
                       verify_finished_at=time.time(),
                       verify_output=f"Copy failed: {exc}")
            return

        ok, reason = _apply_patch(verify_dir, winner_hyp)
        if not ok:
            update_run(run_id, status="verify_failed", verify_status="verify_failed",
                       verify_finished_at=time.time(),
                       verify_output=f"Patch failed during verify: {reason}")
            return

        rc, output = await _run_pytest(
            verify_dir,
            scenario.config.full_suite,
            scenario.config.test_timeout_seconds * 3,
        )

        final_status = "verified" if rc == 0 else "verify_failed"
        update_run(
            run_id,
            status=final_status,
            verify_status=final_status,
            verify_finished_at=time.time(),
            verify_output=output,
        )

        _clean_work(run_id)

    except Exception as exc:
        update_run(run_id, status="verify_failed", verify_status="verify_failed",
                   verify_finished_at=time.time(),
                   verify_output=str(exc))


def _clean_work(run_id: str) -> None:
    work = _WORK_DIR / run_id
    if work.exists():
        try:
            shutil.rmtree(work)
        except Exception:
            pass


def active_run_count() -> int:
    return len(_active_runs)
