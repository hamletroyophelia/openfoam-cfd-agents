"""Machine-readable workflow contracts and deterministic acceptance gates."""

from __future__ import annotations

import operator as comparison
import math
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StageStatus(StrEnum):
    """Lifecycle states persisted by the supervisor."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    APPROVAL_REQUIRED = "approval_required"
    INCONCLUSIVE = "inconclusive"


class MetricRule(BaseModel):
    """A deterministic comparison applied to one named metric."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, strict=True)

    metric: str = Field(min_length=1)
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    threshold: float | int

    @field_validator("threshold", mode="before")
    @classmethod
    def finite_threshold(cls, value: Any) -> Any:
        if not is_finite_number(value):
            raise ValueError("threshold must be a finite number, not a boolean or string")
        return value


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

    schema_version: Literal[2] = 2
    stage: str = Field(min_length=1)
    status: StageStatus
    metrics: dict[str, Any] = Field(default_factory=dict)
    checks: list[AcceptanceCheck] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    message: str = ""
    invalid_metric_paths: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_metrics(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        metrics, paths = json_safe_metrics(data.get("metrics", {}))
        return {**data, "metrics": metrics,
                "invalid_metric_paths": list(dict.fromkeys([*data.get("invalid_metric_paths", []), *paths]))}


def is_finite_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and (isinstance(value, int) or math.isfinite(value)))


def json_safe_metrics(value: Any, path: str = "metrics") -> tuple[Any, list[str]]:
    """Preserve invalid-data locations while producing strict JSON-compatible numbers."""
    if isinstance(value, float) and not math.isfinite(value):
        return None, [path]
    if isinstance(value, dict):
        pairs = {key: json_safe_metrics(item, f"{path}.{key}") for key, item in value.items()}
        return {key: item[0] for key, item in pairs.items()}, [p for item in pairs.values() for p in item[1]]
    if isinstance(value, (list, tuple)):
        pairs = [json_safe_metrics(item, f"{path}[{i}]") for i, item in enumerate(value)]
        return [item[0] for item in pairs], [p for item in pairs for p in item[1]]
    return value, []


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
    if isinstance(observed, float) and not math.isfinite(observed):
        return AcceptanceCheck(metric=rule.metric, operator=rule.operator,
                               threshold=rule.threshold, observed=None, passed=False,
                               message=f"Metric '{rule.metric}' is non-finite and cannot be accepted.")
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
    _, invalid_paths = json_safe_metrics(metrics)
    status = (
        StageStatus.PASSED
        if checks and all(check.passed for check in checks) and not invalid_paths
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
