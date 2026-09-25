"""
Scenario and hypothesis loading with pydantic validation.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator

log = logging.getLogger(__name__)

# Root of the whole project (one level above backend/)
_PROJECT_ROOT = Path(__file__).parent.parent.parent


class PatchEdit(BaseModel):
    file: str
    find: str
    replace: str


class Hypothesis(BaseModel):
    id: str
    role: str
    title: str
    suspected_file: str
    suspected_line: int
    reasoning: str
    evidence: list[str]
    confidence: float
    patch: list[PatchEdit]
    source: str
    generated_at: str

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0 and 1")
        return v

    @property
    def is_dev(self) -> bool:
        return self.source == "dev-placeholder"


class ScenarioConfig(BaseModel):
    id: str
    title: str
    repo_path: str
    bug_report_file: str
    failing_test: str
    full_suite: str
    hypotheses_dir: str
    test_timeout_seconds: int


class LoadedScenario:
    def __init__(
        self,
        config: ScenarioConfig,
        bug_report: str,
        hypotheses: list[Hypothesis],
        metrics: dict,
        scenario_dir: Path,
    ):
        self.config = config
        self.bug_report = bug_report
        self.hypotheses = hypotheses
        self.metrics = metrics
        self.scenario_dir = scenario_dir

    @property
    def repo_abs(self) -> Path:
        return (_PROJECT_ROOT / self.config.repo_path).resolve()


def _load_hypotheses(hypotheses_dir: Path) -> list[Hypothesis]:
    """
    Load all hypothesis JSON files from a directory.
    - Skips _dev_* files if any non-dev file exists.
    - Invalid files are logged and skipped (never crash).
    """
    all_files = sorted(hypotheses_dir.glob("*.json"))
    non_dev = [f for f in all_files if not f.name.startswith("_dev_")]
    dev = [f for f in all_files if f.name.startswith("_dev_")]

    files_to_load = non_dev if non_dev else dev

    hypotheses: list[Hypothesis] = []
    for path in files_to_load:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            h = Hypothesis.model_validate(data)
            hypotheses.append(h)
        except Exception as exc:
            log.warning("Skipping invalid hypothesis file %s: %s", path.name, exc)

    return hypotheses


def load_scenario(scenario_dir: Path) -> Optional[LoadedScenario]:
    """Load and validate a single scenario directory. Returns None on failure."""
    config_path = scenario_dir / "scenario.json"
    if not config_path.exists():
        log.warning("No scenario.json in %s", scenario_dir)
        return None

    try:
        config = ScenarioConfig.model_validate(
            json.loads(config_path.read_text(encoding="utf-8"))
        )
    except Exception as exc:
        log.warning("Invalid scenario.json in %s: %s", scenario_dir, exc)
        return None

    bug_report_path = scenario_dir / config.bug_report_file
    bug_report = bug_report_path.read_text(encoding="utf-8") if bug_report_path.exists() else ""

    hypotheses_dir = scenario_dir / config.hypotheses_dir
    hypotheses = _load_hypotheses(hypotheses_dir) if hypotheses_dir.exists() else []

    metrics_path = scenario_dir / "metrics.json"
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    except Exception:
        metrics = {}

    return LoadedScenario(
        config=config,
        bug_report=bug_report,
        hypotheses=hypotheses,
        metrics=metrics,
        scenario_dir=scenario_dir,
    )


def load_all_scenarios() -> dict[str, LoadedScenario]:
    """Load every scenario folder under <project_root>/scenarios/."""
    scenarios_root = _PROJECT_ROOT / "scenarios"
    result: dict[str, LoadedScenario] = {}
    if not scenarios_root.exists():
        return result
    for entry in sorted(scenarios_root.iterdir()):
        if entry.is_dir():
            scenario = load_scenario(entry)
            if scenario:
                result[scenario.config.id] = scenario
    return result
