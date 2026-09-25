# TriageRace

> *"When a bug comes in, TriageRace fires four IBM Bob subagents at once, each betting on a different root cause. The real test suite decides who's right, live — then the winning fix is verified against the full suite."*

<!-- hero screenshot: docs/screenshots/race-view.png -->

**Live demo:** _deploy URL here_  
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
4 parallel IBM Bob subagents (Agent mode)
each reads the ticket + code through a different lens
    │
    ├─ boundary-logic   → hypothesis JSON + patch
    ├─ numeric-precision → hypothesis JSON + patch
    ├─ input-validation  → hypothesis JSON + patch
    └─ order-of-ops     → hypothesis JSON + patch
    │
    ▼
Race engine (backend)
  • copies repo 4×, applies each patch to its own copy
  • runs the real failing pytest in all 4 copies concurrently
  • winner = first copy whose test exits 0
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
| **Agent mode subagents** | 4 subagents run in parallel, one per debugging lens (boundary logic, numeric precision, input validation, order of operations). Each reads the bug report ticket as a document and the source code, then writes a structured hypothesis JSON file. |
| **Document understanding** | Each subagent reads `scenarios/discount-threshold/bug_report.md` — a realistic support ticket with log excerpts — without being told where the bug is. |
| **Structured output** | Bob writes hypothesis JSON files matching a strict pydantic schema. The race engine loads and validates them. |
| **Codebase co-authoring** | IBM Bob (Agent mode) was used to build this entire codebase. |

Session exports are in `bob_sessions/`. Prompts are in `bob_prompts/subagent_prompts.md`.

---

## Measured results

| | Time | Note |
|---|---|---|
| **Manual baseline** | — | Not yet measured |
| **Bob hypothesis generation** | — | From exported session |
| **Race (4 parallel tests)** | ~1–2 s | Measured live |
| **Verify (full suite)** | ~1–2 s | Measured live |
| **Total assisted** | — | Sum of above |
| **Speed-up** | — | Only shown when both sides are real numbers |

_Fill in `scenarios/discount-threshold/metrics.json` after measuring._

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

## Limitations & roadmap

- **Hypotheses are pre-generated** by IBM Bob in the IDE (offline). The same architecture extends naturally to live generation via watsonx.ai (see Section 9 of the build brief).
- The pattern extends to: code review, test generation, release-readiness checks.
- Currently supports one repo layout; multi-repo import is out of scope.

---

## Team

Built for the **IBM Bob 2.0 Hackathon** (lablab.ai, September 2025).

## License

MIT
