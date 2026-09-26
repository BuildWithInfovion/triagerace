"""
SQLite helpers — no ORM, plain sqlite3.

Tables
------
runs(id, scenario_id, bug_report_text, status, created_at,
     race_started_at, race_finished_at, winner_hypothesis_id,
     verify_status, verify_started_at, verify_finished_at, verify_output)

hypotheses(run_id, hypothesis_id, payload_json, status,
           started_at, finished_at, test_output)

Run status flow:   created → racing → race_done → verifying → verified | verify_failed
Hyp status flow:   queued → patching → testing → passed | failed | patch_failed | timeout | error
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

_DEFAULT_DB = "./triagerace.db"


def _db_path() -> str:
    return os.getenv("TRIAGERACE_DB", _DEFAULT_DB)


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    con = sqlite3.connect(_db_path(), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    """Create tables if they don't exist."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id                   TEXT PRIMARY KEY,
                scenario_id          TEXT NOT NULL,
                bug_report_text      TEXT NOT NULL,
                status               TEXT NOT NULL,
                created_at           REAL NOT NULL,
                race_started_at      REAL,
                race_finished_at     REAL,
                winner_hypothesis_id TEXT,
                verify_status        TEXT,
                verify_started_at    REAL,
                verify_finished_at   REAL,
                verify_output        TEXT
            );
            CREATE TABLE IF NOT EXISTS hypotheses (
                run_id          TEXT NOT NULL,
                hypothesis_id   TEXT NOT NULL,
                payload_json    TEXT NOT NULL,
                status          TEXT NOT NULL,
                started_at      REAL,
                finished_at     REAL,
                test_output     TEXT,
                PRIMARY KEY (run_id, hypothesis_id)
            );
        """)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def insert_run(run_id: str, scenario_id: str, bug_report_text: str, created_at: float) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO runs (id, scenario_id, bug_report_text, status, created_at) "
            "VALUES (?, ?, ?, 'created', ?)",
            (run_id, scenario_id, bug_report_text, created_at),
        )


def update_run(run_id: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as con:
        con.execute(f"UPDATE runs SET {cols} WHERE id = ?", (*fields.values(), run_id))


def get_run(run_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def list_runs(limit: int = 50) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]




# ---------------------------------------------------------------------------
# Hypotheses
# ---------------------------------------------------------------------------

def insert_hypothesis(run_id: str, hypothesis_id: str, payload_json: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO hypotheses (run_id, hypothesis_id, payload_json, status) "
            "VALUES (?, ?, ?, 'queued')",
            (run_id, hypothesis_id, payload_json),
        )


def update_hypothesis(run_id: str, hypothesis_id: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as con:
        con.execute(
            f"UPDATE hypotheses SET {cols} WHERE run_id = ? AND hypothesis_id = ?",
            (*fields.values(), run_id, hypothesis_id),
        )


def get_hypotheses(run_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM hypotheses WHERE run_id = ? ORDER BY hypothesis_id",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
