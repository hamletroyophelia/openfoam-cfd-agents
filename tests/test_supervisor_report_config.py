from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from openfoam_cfd_agents.domain import MetricRule, StageStatus, evaluate_stage


def _module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"{name} implementation is missing") from exc


def _result(stage: str, observed: float, threshold: float = 1.0):
    return evaluate_stage(
        stage=stage,
        metrics={"value": observed},
        rules=[MetricRule(metric="value", operator="<=", threshold=threshold)],
        artifacts=[f"{stage}.json"],
    )


def test_supervisor_stops_after_failed_gate_and_never_runs_downstream_stage() -> None:
    supervisor = _module("openfoam_cfd_agents.agents.supervisor")
    executed: list[str] = []

    def first():
        executed.append("mesh")
        return _result("mesh", observed=2.0)

    def second():
        executed.append("run")
        return _result("run", observed=0.0)

    manifest = supervisor.SupervisorAgent().run(
        [supervisor.StageTask("mesh", first), supervisor.StageTask("run", second)],
        run_id="gate-failure",
    )

    assert manifest.status is StageStatus.FAILED
    assert executed == ["mesh"]
    assert [item.stage for item in manifest.stages] == ["mesh"]


def test_manual_approval_is_an_explicit_workflow_state() -> None:
    supervisor = _module("openfoam_cfd_agents.agents.supervisor")
    manifest = supervisor.SupervisorAgent().run(
        [supervisor.StageTask("physics", lambda: _result("physics", 0.0), requires_approval=True)],
        run_id="manual-gate",
    )

    assert manifest.status is StageStatus.APPROVAL_REQUIRED
    assert manifest.stopped_after == "physics"


def test_repairable_stage_retries_until_deterministic_gate_passes() -> None:
    """Removing the retry loop must leave this stage failed after attempt one."""

    supervisor = _module("openfoam_cfd_agents.agents.supervisor")
    observations = iter([2.0, 1.5, 0.5])
    repairs: list[tuple[int, StageStatus]] = []

    def execute():
        return _result("case_execution", observed=next(observations))

    def repair(result, failed_attempt: int) -> None:
        repairs.append((failed_attempt, result.status))

    manifest = supervisor.SupervisorAgent().run(
        [
            supervisor.StageTask(
                "case_execution",
                execute,
                repair=repair,
                max_attempts=3,
            )
        ],
        run_id="repair-success",
    )

    assert manifest.status is StageStatus.PASSED
    assert [result.status for result in manifest.stages] == [
        StageStatus.FAILED,
        StageStatus.FAILED,
        StageStatus.PASSED,
    ]
    assert [result.metrics["attempt"] for result in manifest.stages] == [1, 2, 3]
    assert repairs == [(1, StageStatus.FAILED), (2, StageStatus.FAILED)]


def test_repairable_stage_stops_after_attempt_budget_is_exhausted() -> None:
    """Increasing attempts implicitly or running downstream would hide a failed gate."""

    supervisor = _module("openfoam_cfd_agents.agents.supervisor")
    executed: list[str] = []
    repairs: list[int] = []

    def execute_failed():
        executed.append("case_execution")
        return _result("case_execution", observed=2.0)

    def repair(_result, failed_attempt: int) -> None:
        repairs.append(failed_attempt)

    def downstream():
        executed.append("verification")
        return _result("verification", observed=0.0)

    manifest = supervisor.SupervisorAgent().run(
        [
            supervisor.StageTask(
                "case_execution",
                execute_failed,
                repair=repair,
                max_attempts=2,
            ),
            supervisor.StageTask("verification", downstream),
        ],
        run_id="repair-exhausted",
    )

    assert manifest.status is StageStatus.FAILED
    assert manifest.stopped_after == "case_execution"
    assert executed == ["case_execution", "case_execution"]
    assert repairs == [1]
    assert [result.metrics["attempt"] for result in manifest.stages] == [1, 2]


def test_stage_task_rejects_an_invalid_attempt_budget() -> None:
    """Allowing zero attempts would silently skip a required workflow stage."""

    supervisor = _module("openfoam_cfd_agents.agents.supervisor")

    with pytest.raises(ValueError, match="max_attempts"):
        supervisor.StageTask("mesh", lambda: _result("mesh", 0.0), max_attempts=0)

    with pytest.raises(ValueError, match="repair callback"):
        supervisor.StageTask("mesh", lambda: _result("mesh", 0.0), max_attempts=2)


def test_repair_exception_becomes_an_auditable_failed_stage() -> None:
    """Letting a repair exception escape would leave no terminal manifest state."""

    supervisor = _module("openfoam_cfd_agents.agents.supervisor")

    def repair(_result, _failed_attempt: int) -> None:
        raise RuntimeError("rewrite service unavailable")

    manifest = supervisor.SupervisorAgent().run(
        [
            supervisor.StageTask(
                "case_execution",
                lambda: _result("case_execution", observed=2.0),
                repair=repair,
                max_attempts=3,
            )
        ],
        run_id="repair-exception",
    )

    assert manifest.status is StageStatus.FAILED
    assert manifest.stopped_after == "case_execution"
    assert len(manifest.stages) == 1
    assert manifest.stages[0].metrics["repair_exception_type"] == "RuntimeError"
    assert "rewrite service unavailable" in manifest.stages[0].message


def test_report_renders_machine_results_without_redeciding_status() -> None:
    supervisor = _module("openfoam_cfd_agents.agents.supervisor")
    report = _module("openfoam_cfd_agents.agents.report")
    manifest = supervisor.WorkflowManifest(
        run_id="report-001",
        status=StageStatus.FAILED,
        stages=[_result("monitoring", observed=1.2)],
        stopped_after="monitoring",
    )

    markdown = report.ReportAgent().render_markdown(manifest)

    assert "# CFD Workflow Report: report-001" in markdown
    assert "| monitoring | failed |" in markdown
    assert "monitoring.json" in markdown
    assert "does not satisfy" in markdown


def test_yaml_config_accepts_the_foundation_v14_mvp_shape(tmp_path: Path) -> None:
    config_module = _module("openfoam_cfd_agents.config")
    path = tmp_path / "workflow.yaml"
    path.write_text(
        """
solver:
  platform: openfoam
  version: foundation-14
  application: foamRun
physics:
  flow_type: incompressible
  transient: true
  turbulence_model: auto
  multiphase_model: none
verification:
  mesh_levels: [coarse, medium, fine]
  timestep_levels: [large, medium, small]
  domain_independence: false
  gci_analysis: true
  gci_limit: 0.02
hpc:
  process_counts: [1, 2, 4]
  benchmark_steps: 100
  test_smt: false
  test_decomposition_methods: true
monitoring:
  residuals: true
  courant_number: true
  conservation_errors: true
  force_coefficients: false
  automatic_stop: true
  max_courant: 1.0
postprocessing:
  formats: [csv, png]
  fields: [velocity, pressure]
  vortex_methods: [Q]
report:
  formats: [markdown, html]
""".strip(),
        encoding="utf-8",
    )

    config = config_module.load_config(path)

    assert config.solver.version == "foundation-14"
    assert config.solver.application == "foamRun"
    assert config.verification.gci_limit == pytest.approx(0.02)
    assert config.monitoring.max_courant == pytest.approx(1.0)
