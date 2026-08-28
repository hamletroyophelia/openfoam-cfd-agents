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
