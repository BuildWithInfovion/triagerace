# TriageRace

> *"When a bug comes in, TriageRace sends four IBM Bob subagents after it, each investigating through a different lens. Every proposed patch is tested live against the real failing test in its own sandbox — then the selected fix is verified against the full suite."*

<!-- hero screenshot: docs/screenshots/race-view.png -->

**Live demo:** https://triagerace.onrender.com  
**Demo video:** _video link here_

> ⚠️ Hosted on Render free tier — the first request after inactivity can take **about 1 minute** while the container wakes up. Open the URL and wait before recording or judging.

---

## The problem

When a bug comes in, developers spend most of their time on **investigation** — reading logs, forming hypotheses, manually tracing code — not on typing the one-line fix. TriageRace compresses the investigation phase to seconds by running all plausible hypotheses in parallel, with the real test suite as the arbiter.

---

## How it works

```
Bug report
    │
    ▼
4 IBM Bob subagents (Agent mode), one per lens
each reads the ticket + code and writes a hypothesis + patch
    │
    ├─ boundary-logic   → hypothesis JSON + patch
    ├─ numeric-precision → hypothesis JSON + patch
    ├─ input-validation  → hypothesis JSON + patch
    └─ order-of-ops     → hypothesis JSON + patch
    │
    ▼
Race engine (backend)
  • baseline: runs the failing test on UNPATCHED code first (must fail — proves the bug is real)
  • copies repo 4×, applies each patch to its own copy
  • runs the real failing pytest in all 4 copies concurrently
  • passing = test exits 0; if several lenses pass (consensus),
    the highest-confidence hypothesis is selected
    │
    ▼
Apply winner
  • winner patch applied to a fresh copy
  • full test suite runs
  • result: ✓ N passed, 0 failed
    │
    ▼
Results panel
  • winning diff shown
  • manual baseline vs assisted time comparison
```

---

## How IBM Bob is used

| Usage | Detail |
|---|---|
| **Agent mode subagents** | 4 Bob subagent tasks, one per debugging lens (boundary logic, numeric precision, input validation, order of operations). Each reads the bug report ticket as a document and the source code, then writes a structured hypothesis JSON file. |
| **Document understanding** | Each subagent reads `scenarios/discount-threshold/bug_report.md` — a realistic support ticket with log excerpts — without being told where the bug is. |
| **Structured output** | Bob writes hypothesis JSON files matching a strict pydantic schema. The race engine loads and validates them. |
| **Codebase co-authoring** | IBM Bob (Agent mode) built the codebase from the build brief (`TriageRace_BOB_BUILD_BRIEF.md`), milestone by milestone. The full session is in `bob_sessions/`. After the Bobcoin budget ran out, Claude Code was used for a final review pass (bug fixes, UI wording, README transparency), as the hackathon FAQ allows. The hypotheses and core architecture are Bob's work. |

Session exports are in `bob_sessions/` (one Markdown export covering the build task and the four subagent tasks). Prompts are in `bob_prompts/subagent_prompts.md`.

---

## Measured results

| | Time | How it was measured |
|---|---|---|
| **Manual baseline** | 4:00 | Stopwatch: read the ticket, find the bug, apply the fix, run pytest |
| **Bob hypothesis generation** | 2:00 | Stopwatch: the 4 subagent tasks, run one after another |
| **Race (4 parallel tests)** | ~1–2 s locally, ~10–15 s on the hosted free tier | Measured live by the app on every run (the free instance has a small CPU share) |
| **Verify (full suite)** | ~1–3 s | Measured live by the app on every run |

The source of truth is `scenarios/discount-threshold/metrics.json`. The app shows `—` for anything not measured, and only shows a speed-up when both sides are real numbers.

---

## Run locally

### Prerequisites

- Python 3.11+
- Node 20+

### PowerShell (Windows)

```powershell
# Backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

```powershell
# Frontend (separate terminal)
cd frontend
npm ci
npm run dev
# opens http://localhost:5173 — proxies /api to port 8000
```

### bash (Linux / macOS / WSL)

```bash
# Backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend (separate terminal)
cd frontend
npm ci
npm run dev
```

### Docker (single container)

```bash
docker build -t triagerace .
docker run -p 8000:8000 triagerace
# open http://localhost:8000
```

### Deploy to Render

1. New → **Web Service** → connect this GitHub repo → Runtime: **Docker**.
2. Health check path: `/api/health`. There's no need to set a port: the container binds to Render's `$PORT`.
3. Optional: set `VITE_REPO_URL` so the results page links to the repo.

---

## Project structure

```
triagerace/
├── backend/
│   ├── app/
│   │   ├── main.py        FastAPI app, all API routes, static serving
│   │   ├── scenarios.py   Scenario + hypothesis loader (pydantic)
│   │   ├── race.py        Patch apply + parallel pytest engine
│   │   └── db.py          SQLite helpers (no ORM)
│   └── tests/             Backend tests
├── frontend/
│   └── src/
│       ├── App.tsx                 View router (Intake → Race → Result)
│       ├── api.ts                  All fetch calls
│       └── components/
│           ├── IntakeView.tsx
│           ├── RaceView.tsx        Live-polling race dashboard
│           ├── HypothesisCard.tsx  Per-hypothesis card with diff + output
│           └── ResultView.tsx      Metrics panel + full suite result
├── sample_repos/shopcart/  Sample Python package with seeded bug
├── scenarios/
│   └── discount-threshold/ Bug report, hypothesis JSONs, metrics
├── bob_prompts/            The 4 subagent role prompts
├── bob_sessions/           Exported IBM Bob session reports
└── Dockerfile              Multi-stage: Node builds frontend, Python serves
```

---

## What the demo run actually shows (transparency)

- **All four lenses converged on the same fix** (`>` → `>=` in `apply_discount`), each with its own reasoning and a different confidence. So the demo shows *consensus*: the app runs every patch against the real failing test, confirms all of them, selects the most confident one (boundary-logic, 0.95), and verifies it against the full suite.
- The sample repo contains a `# SEEDED BUG` comment on the buggy line, and the test's assertion message mentions the comparison operator. Each subagent was also pointed at `TriageRace_BOB_BUILD_BRIEF.md` for the JSON schema, and that brief describes the intended fix. All of these were visible to the subagents (see the read_file calls in `bob_sessions/`), which very likely drove the convergence. The bug report itself doesn't mention the operator, the function or the line.
- The 4 subagent tasks were run one after another, not simultaneously, within the Bobcoin budget.
- `generated_at` values in the hypothesis JSONs were written by Bob itself and aren't reliable wall-clock times.
- The engine and its tests do handle genuinely different bets: `backend/tests/test_backend.py` races a correct fix against a wrong one (tax before discount), and only the correct one passes.

## Limitations & roadmap

- **Hypotheses are pre-generated** by IBM Bob in the IDE; test execution is live. The same architecture extends naturally to live generation via watsonx.ai (see Section 9 of the build brief).
- **Next step:** remove the source hints and give each lens a constraint on what its patch may change (for example, numeric-precision may not touch comparison operators), so the lenses produce competing patches and the suite picks a single winner.
- There is one scenario today. A second one (for example a float-rounding bug in `apply_tax`) would show the approach isn't a one-off.
- The pattern extends to: code review, test generation, release-readiness checks.
- Currently supports one repo layout; multi-repo import is out of scope.

---

## Team

Built for the **IBM Bob 2.0 Hackathon** (lablab.ai, September 2026).

- Sankalp Deshpande

## License

[MIT](LICENSE)
