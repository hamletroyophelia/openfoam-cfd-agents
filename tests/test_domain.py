from __future__ import annotations

import importlib


def _domain():
    try:
        return importlib.import_module("openfoam_cfd_agents.domain")
    except ModuleNotFoundError as exc:
        raise AssertionError("domain gate implementation is missing") from exc


def test_metric_rules_determine_passed_status_instead_of_agent_text() -> None:
    domain = _domain()

    result = domain.evaluate_stage(
        stage="mesh_verification",
        metrics={"gci": 0.018, "observed_order": 1.92},
        rules=[
            domain.MetricRule(metric="gci", operator="<=", threshold=0.02),
            domain.MetricRule(metric="observed_order", operator=">=", threshold=1.8),
        ],
        artifacts=["mesh-study.csv"],
    )

    assert result.status is domain.StageStatus.PASSED
    assert [check.passed for check in result.checks] == [True, True]
    assert result.model_dump(mode="json")["status"] == "passed"


def test_one_failed_rule_fails_the_entire_stage() -> None:
    domain = _domain()

    result = domain.evaluate_stage(
        stage="monitoring",
        metrics={"max_courant": 1.4, "fatal_errors": 0},
        rules=[
            domain.MetricRule(metric="max_courant", operator="<=", threshold=1.0),
            domain.MetricRule(metric="fatal_errors", operator="==", threshold=0),
        ],
    )

    assert result.status is domain.StageStatus.FAILED
    assert result.checks[0].passed is False


def test_missing_metric_is_a_failed_check_not_an_exception() -> None:
    domain = _domain()

    result = domain.evaluate_stage(
        stage="monitoring",
        metrics={},
        rules=[domain.MetricRule(metric="max_courant", operator="<=", threshold=1.0)],
    )

    assert result.status is domain.StageStatus.FAILED
    assert result.checks[0].observed is None
    assert "missing" in result.checks[0].message.lower()
