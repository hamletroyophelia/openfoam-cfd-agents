from __future__ import annotations

import importlib
import json
from pathlib import Path

from typer.testing import CliRunner

GOOD_LOG = """
Time = 0.1
smoothSolver: Solving for Ux, Initial residual = 0.01, Final residual = 1e-06, No Iterations 2
Courant Number mean: 0.03 max: 0.8
time step continuity errors : sum local = 1e-08, global = -2e-09, cumulative = 3e-08
ExecutionTime = 1 s ClockTime = 1 s
"""


def _app():
    try:
        return importlib.import_module("openfoam_cfd_agents.cli").app
    except ModuleNotFoundError as exc:
        raise AssertionError("workflow CLI implementation is missing") from exc


def test_monitor_command_writes_the_machine_readable_stage_result(tmp_path: Path) -> None:
    log_path = tmp_path / "log.foamRun"
    result_path = tmp_path / "monitor.json"
    log_path.write_text(GOOD_LOG + GOOD_LOG.replace('0.1', '0.2'), encoding="utf-8")

    result = CliRunner().invoke(
        _app(),
        ["monitor", str(log_path), "--output", str(result_path)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "monitoring"
    assert payload["status"] == "passed"


def test_plan_run_keeps_a_case_path_with_spaces_as_one_argument(tmp_path: Path) -> None:
    case_path = tmp_path / "case with spaces"
    case_path.mkdir()
    output = tmp_path / "plan.json"

    result = CliRunner().invoke(
        _app(),
        ["plan-run", str(case_path), "--processes", "2", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["commands"][1]["argv"][-1] == str(case_path.resolve())
