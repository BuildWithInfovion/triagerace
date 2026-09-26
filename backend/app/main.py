import asyncio
import json
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from pathlib import Path

from .db import (
    init_db,
    insert_run,
    insert_hypothesis,
    get_run,
    get_hypotheses,
    update_run,
)
from .scenarios import load_all_scenarios
from .race import run_race, run_verify, active_run_count

app = FastAPI(title="TriageRace")

# CORS for local Vite dev server only
if os.getenv("TRIAGERACE_ENV", "dev") == "dev":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.on_event("startup")
def on_startup():
    init_db()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"ok": True}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@app.get("/api/scenarios")
def list_scenarios():
    scenarios = load_all_scenarios()
    result = []
    for s in scenarios.values():
        non_dev = [h for h in s.hypotheses if not h.is_dev]
        dev = [h for h in s.hypotheses if h.is_dev]
        result.append({
            "id": s.config.id,
            "title": s.config.title,
            "hypothesis_count": len(s.hypotheses),
            "hypothesis_sources": {
                "ibm-bob-subagent": sum(1 for h in non_dev if h.source == "ibm-bob-subagent"),
                "dev-placeholder": len(dev),
                "other": sum(1 for h in non_dev if h.source not in ("ibm-bob-subagent",)),
            },
        })
    return result


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    scenarios = load_all_scenarios()
    s = scenarios.get(scenario_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {
        "id": s.config.id,
        "title": s.config.title,
        "repo_path": s.config.repo_path,
        "failing_test": s.config.failing_test,
        "full_suite": s.config.full_suite,
        "test_timeout_seconds": s.config.test_timeout_seconds,
        "bug_report": s.bug_report,
        "metrics": s.metrics,
        "hypotheses": [
            {
                "id": h.id,
                "role": h.role,
                "title": h.title,
                "suspected_file": h.suspected_file,
                "suspected_line": h.suspected_line,
                "reasoning": h.reasoning,
                "evidence": h.evidence,
                "confidence": h.confidence,
                "patch": [p.model_dump() for p in h.patch],
                "source": h.source,
                "generated_at": h.generated_at,
                "is_dev": h.is_dev,
            }
            for h in s.hypotheses
        ],
    }


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

class CreateRunRequest(BaseModel):
    scenario_id: str
    bug_report_text: str


@app.post("/api/runs", status_code=201)
async def create_run(body: CreateRunRequest):
    if active_run_count() >= 2:
        raise HTTPException(status_code=429, detail="Too many concurrent races. Try again shortly.")

    scenarios = load_all_scenarios()
    scenario = scenarios.get(body.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    run_id = str(uuid.uuid4())
    now = time.time()
    insert_run(run_id, body.scenario_id, body.bug_report_text, now)

    # Snapshot hypotheses into DB
    for h in scenario.hypotheses:
        insert_hypothesis(run_id, h.id, json.dumps(h.model_dump()))

    # Fire on the running event loop so subprocess creation works correctly
    asyncio.create_task(run_race(run_id))
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}")
def get_run_state(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    hyp_rows = get_hypotheses(run_id)

    # Parse baseline from verify_output if race still in progress
    baseline_status = None
    baseline_output = None
    raw_verify = run.get("verify_output") or ""
    if raw_verify.startswith("BASELINE:FAIL\n"):
        baseline_status = "fail"
        baseline_output = raw_verify[len("BASELINE:FAIL\n"):]
    elif raw_verify.startswith("SCENARIO BROKEN"):
        baseline_status = "broken"
        baseline_output = raw_verify

    # Compute metrics
    race_duration = None
    if run.get("race_started_at") and run.get("race_finished_at"):
        race_duration = run["race_finished_at"] - run["race_started_at"]
    verify_duration = None
    if run.get("verify_started_at") and run.get("verify_finished_at"):
        verify_duration = run["verify_finished_at"] - run["verify_started_at"]

    scenarios = load_all_scenarios()
    scenario = scenarios.get(run["scenario_id"])
    hyp_meta = {h.id: h for h in scenario.hypotheses} if scenario else {}

    hypotheses_out = []
    for row in hyp_rows:
        meta = hyp_meta.get(row["hypothesis_id"])
        hypotheses_out.append({
            "id": row["hypothesis_id"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "test_output": row["test_output"],
            # enrich with scenario metadata
            "role": meta.role if meta else None,
            "title": meta.title if meta else None,
            "suspected_file": meta.suspected_file if meta else None,
            "suspected_line": meta.suspected_line if meta else None,
            "reasoning": meta.reasoning if meta else None,
            "evidence": meta.evidence if meta else None,
            "confidence": meta.confidence if meta else None,
            "patch": [p.model_dump() for p in meta.patch] if meta else None,
            "source": meta.source if meta else None,
            "is_dev": meta.is_dev if meta else None,
        })

    # Final verify_output (only show when not a baseline marker)
    verify_output = None
    if run.get("verify_status") in ("verified", "verify_failed"):
        verify_output = run.get("verify_output")

    return {
        "run_id": run_id,
        "scenario_id": run["scenario_id"],
        "status": run["status"],
        "created_at": run["created_at"],
        "race_started_at": run["race_started_at"],
        "race_finished_at": run["race_finished_at"],
        "winner_hypothesis_id": run["winner_hypothesis_id"],
        "verify_status": run["verify_status"],
        "verify_started_at": run["verify_started_at"],
        "verify_finished_at": run["verify_finished_at"],
        "verify_output": verify_output,
        "baseline_status": baseline_status,
        "baseline_output": baseline_output,
        "race_duration_seconds": race_duration,
        "verify_duration_seconds": verify_duration,
        "hypotheses": hypotheses_out,
    }


@app.post("/api/runs/{run_id}/apply")
async def apply_winner(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.get("winner_hypothesis_id"):
        raise HTTPException(status_code=400, detail="No winner yet — race must have a passing hypothesis first")
    if run["status"] not in ("race_done",):
        raise HTTPException(status_code=400, detail=f"Cannot apply: run status is '{run['status']}'")

    asyncio.create_task(run_verify(run_id))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Serve built frontend (must be last)
# ---------------------------------------------------------------------------
_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
