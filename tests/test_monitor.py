from __future__ import annotations

import importlib


GOOD_LOG = """
Time = 0.1
smoothSolver:  Solving for Ux, Initial residual = 0.01, Final residual = 1e-06, No Iterations 2
smoothSolver:  Solving for p, Initial residual = 0.02, Final residual = 2e-06, No Iterations 2
Courant Number mean: 0.03 max: 0.8
time step continuity errors : sum local = 1e-08, global = -2e-09, cumulative = 3e-08
ExecutionTime = 1 s  ClockTime = 1 s

Time = 0.2
smoothSolver:  Solving for Ux, Initial residual = 0.005, Final residual = 5e-07, No Iterations 1
Courant Number mean: 0.04 max: 0.6
time step continuity errors : sum local = 8e-09, global = -1e-09, cumulative = 2e-08
ExecutionTime = 2 s  ClockTime = 2 s
"""


def _monitor_module():
    try:
        return importlib.import_module("openfoam_cfd_agents.agents.monitor")
    except ModuleNotFoundError as exc:
        raise AssertionError("OpenFOAM v14 monitor implementation is missing") from exc


def test_parser_extracts_v14_progress_residuals_and_conservation_metrics() -> None:
    monitor = _monitor_module()

    summary = monitor.parse_solver_log(GOOD_LOG)

    assert summary.times == [0.1, 0.2]
    assert summary.latest_time == 0.2
    assert summary.max_courant == 0.8
    assert summary.latest_cumulative_continuity_error == 2e-08
    assert [sample.field for sample in summary.residuals] == ["Ux", "p", "Ux"]
    assert summary.fatal_errors == []


def test_monitor_agent_passes_only_when_all_numeric_gates_pass() -> None:
    monitor = _monitor_module()
    agent = monitor.MonitorAgent(
        monitor.MonitorThresholds(
            max_courant=1.0,
            max_abs_cumulative_continuity_error=1e-6,
            max_final_residual=1e-4,
            min_time_steps=2,
        )
    )

    result = agent.evaluate_text(GOOD_LOG)

    assert result.status.value == "passed"
    assert result.metrics["latest_time"] == 0.2
    assert result.metrics["fatal_errors"] == 0


def test_fatal_error_forces_failed_status_even_when_numeric_values_are_small() -> None:
    monitor = _monitor_module()
    text = GOOD_LOG + "\nFOAM FATAL ERROR: Unknown function type fieldMinMax\n"

    result = monitor.MonitorAgent().evaluate_text(text)

    assert result.status.value == "failed"
    assert result.metrics["fatal_errors"] == 1
    assert "fieldMinMax" in result.metrics["fatal_error_messages"][0]


def test_sigfpe_startup_banner_is_healthy_but_real_exception_is_fatal():
    monitor = _monitor_module()
    banner = 'sigFpe : Enabling floating point exception trapping (FOAM_SIGFPE).\n'
    assert monitor.MonitorAgent().evaluate_text(banner + GOOD_LOG).status.value == 'passed'
    for failure in ('Floating point exception (core dumped)', '[rank 1] Signal: Floating point exception (8)',
                    banner.strip() + ' FOAM FATAL ERROR: broken'):
        assert monitor.parse_solver_log(failure).fatal_error_count == 1
