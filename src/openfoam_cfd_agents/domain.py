"""Machine-readable workflow contracts and deterministic acceptance gates."""

from __future__ import annotations

import operator as comparison
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StageStatus(StrEnum):
    """Lifecycle states persisted by the supervisor."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    APPROVAL_REQUIRED = "approval_required"


class MetricRule(BaseModel):
    """A deterministic comparison applied to one named metric."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str = Field(min_length=1)
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    threshold: float | int


class AcceptanceCheck(BaseModel):
    """The auditable outcome of evaluating one acceptance rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str
    operator: str
    threshold: float | int
    observed: float | int | None
    passed: bool
    message: str


class StageResult(BaseModel):
    """Canonical output emitted by every workflow stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: str = Field(min_length=1)
    status: StageStatus
    metrics: dict[str, Any] = Field(default_factory=dict)
    checks: list[AcceptanceCheck] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    message: str = ""


_OPERATORS = {
    "<": comparison.lt,
    "<=": comparison.le,
    ">": comparison.gt,
    ">=": comparison.ge,
    "==": comparison.eq,
    "!=": comparison.ne,
}


def _evaluate_rule(metrics: dict[str, Any], rule: MetricRule) -> AcceptanceCheck:
    observed = metrics.get(rule.metric)
    if not isinstance(observed, (int, float)) or isinstance(observed, bool):
        return AcceptanceCheck(
            metric=rule.metric,
            operator=rule.operator,
            threshold=rule.threshold,
            observed=None,
            passed=False,
            message=f"Metric '{rule.metric}' is missing or non-numeric.",
        )

    passed = bool(_OPERATORS[rule.operator](observed, rule.threshold))
    relation = "satisfies" if passed else "does not satisfy"
    return AcceptanceCheck(
        metric=rule.metric,
        operator=rule.operator,
        threshold=rule.threshold,
        observed=observed,
        passed=passed,
        message=(
            f"Observed {rule.metric}={observed} {relation} "
            f"{rule.operator} {rule.threshold}."
        ),
    )


def evaluate_stage(
    *,
    stage: str,
    metrics: dict[str, Any],
    rules: list[MetricRule],
    artifacts: list[str] | None = None,
) -> StageResult:
    """Evaluate all rules and derive status without relying on agent prose."""

    checks = [_evaluate_rule(metrics, rule) for rule in rules]
    status = (
        StageStatus.PASSED
        if checks and all(check.passed for check in checks)
        else StageStatus.FAILED
    )
    message = (
        "All acceptance checks passed."
        if status is StageStatus.PASSED
        else "One or more acceptance checks failed."
    )
    return StageResult(
        stage=stage,
        status=status,
        metrics=metrics,
        checks=checks,
        artifacts=artifacts or [],
        message=message,
    )
