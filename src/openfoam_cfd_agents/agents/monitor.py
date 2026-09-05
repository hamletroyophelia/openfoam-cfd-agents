"""Deterministic OpenFOAM solver-log monitoring and acceptance evaluation."""

from __future__ import annotations

import re
import math
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from openfoam_cfd_agents.domain import MetricRule, StageResult, evaluate_stage


_NUMBER = r"[-+]?(?:(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|(?i:nan|inf(?:inity)?))"
_TIME_RE = re.compile(rf"^Time\s*=\s*({_NUMBER})\s*s?\s*$", re.MULTILINE)
_RESIDUAL_RE = re.compile(
    rf"Solving for\s+([^,]+),\s*Initial residual\s*=\s*({_NUMBER}),\s*"
    rf"Final residual\s*=\s*({_NUMBER}),\s*No Iterations\s+(\d+)"
)
_COURANT_RE = re.compile(
    rf"^Courant Number\s+mean:\s*({_NUMBER})\s+max:\s*({_NUMBER})", re.MULTILINE
)
_INTERFACE_RE = re.compile(rf"^Interface Courant Number\s+mean:\s*({_NUMBER})\s+max:\s*({_NUMBER})")
_ALPHA_RE = re.compile(rf"Min\(alpha\.water\)\s*=\s*({_NUMBER})\s+Max\(alpha\.water\)\s*=\s*({_NUMBER})")
_CONTINUITY_RE = re.compile(
    rf"time step continuity errors\s*:\s*sum local\s*=\s*({_NUMBER}),\s*"
    rf"global\s*=\s*({_NUMBER}),\s*cumulative\s*=\s*({_NUMBER})"
)
_FATAL_MARKERS = ("FOAM FATAL", "MPI_ABORT", "Segmentation fault", "Floating point exception",
                  "Connection reset by peer", "mca_btl_tcp", "MPI_ERR", "out of memory")


class ResidualSample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    initial: float
    final: float
    iterations: int


class ContinuitySample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    local: float
    global_error: float
    cumulative: float


class SolverLogSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    times: list[float] = Field(default_factory=list)
    residuals: list[ResidualSample] = Field(default_factory=list)
    courant_maxima: list[float] = Field(default_factory=list)
    continuity: list[ContinuitySample] = Field(default_factory=list)
    fatal_errors: list[str] = Field(default_factory=list)
    fatal_error_count: int = 0
    interface_courant_maxima: list[float] = Field(default_factory=list)
    alpha_minima: list[float] = Field(default_factory=list)
    alpha_maxima: list[float] = Field(default_factory=list)
    completed_times: list[float] = Field(default_factory=list)
    completed_residual_maxima: list[float] = Field(default_factory=list)
    nonfinite_samples: int = 0

    @property
    def latest_time(self) -> float | None:
        return self.times[-1] if self.times else None

    @property
    def max_courant(self) -> float | None:
        return max(self.courant_maxima) if self.courant_maxima else None

    @property
    def latest_cumulative_continuity_error(self) -> float | None:
        return self.continuity[-1].cumulative if self.continuity else None


class MonitorThresholds(BaseModel):
    """Numerical gates for a basic Phase 1 run-health decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    max_courant: float = Field(default=1.0, gt=0)
    max_abs_cumulative_continuity_error: float = Field(default=1e-6, gt=0)
    max_final_residual: float = Field(default=1e-3, gt=0)
    min_time_steps: int = Field(default=2, ge=2)
    max_interface_courant: float | None = Field(default=None, gt=0)
    alpha_tolerance: float | None = Field(default=None, ge=0, lt=0.1)


def parse_solver_log(text: str) -> SolverLogSummary:
    """Parse progress and stability signals emitted by Foundation OpenFOAM."""
    return parse_solver_lines(text.splitlines())


def parse_solver_lines(lines: Iterable[str]) -> SolverLogSummary:
    """Consume text incrementally; time headers and completed steps are distinct."""
    data = SolverLogSummary().model_dump()
    current_time = None
    terminal_residuals = {}
    for raw in lines:
        line = raw.strip()
        if any(marker.casefold() in line.casefold() for marker in _FATAL_MARKERS):
            data['fatal_error_count'] += 1
            if len(data['fatal_errors']) < 50:
                data['fatal_errors'].append(line[:1000])
        match = _TIME_RE.match(line)
        if match:
            current_time = float(match.group(1))
            data['times'].append(current_time)
            terminal_residuals = {}
        if line.startswith('ExecutionTime =') and current_time is not None:
            data['completed_times'].append(current_time)
            if terminal_residuals:
                data['completed_residual_maxima'].append(max(terminal_residuals.values()))
            current_time = None
        for regex, key in ((_COURANT_RE, 'courant_maxima'), (_INTERFACE_RE, 'interface_courant_maxima')):
            match = regex.search(line)
            if match:
                data[key].append(float(match.group(2)))
        match = _RESIDUAL_RE.search(line)
        if match:
            data['residuals'].append(ResidualSample(field=match.group(1).strip(), initial=float(match.group(2)),
                                                   final=float(match.group(3)), iterations=int(match.group(4))))
            terminal_residuals[match.group(1).strip()] = float(match.group(3))
        match = _CONTINUITY_RE.search(line)
        if match:
            data['continuity'].append(ContinuitySample(local=float(match.group(1)), global_error=float(match.group(2)),
                                                       cumulative=float(match.group(3))))
        match = _ALPHA_RE.search(line)
        if match:
            data['alpha_minima'].append(float(match.group(1)))
            data['alpha_maxima'].append(float(match.group(2)))
        # Includes initial residuals, Co means and overflowing scientific notation.
        if re.search(r"(?:=|:)\s*[-+]?(?:nan|inf(?:inity)?)\b", line, re.I):
            data['nonfinite_samples'] += 1
        if any(not math.isfinite(float(token)) for token in re.findall(r"[-+]?\d+(?:\.\d*)?[eE][-+]?\d+", line)):
            data['nonfinite_samples'] += 1
    return SolverLogSummary.model_validate(data)


class MonitorAgent:
    """Summarize a run, then delegate pass/fail to deterministic rules."""

    def __init__(self, thresholds: MonitorThresholds | None = None) -> None:
        self.thresholds = thresholds or MonitorThresholds()

    def evaluate_text(self, text: str, *, artifact: str | None = None) -> StageResult:
        summary = parse_solver_log(text)
        return self.evaluate_summary(summary, artifact=artifact)

    def evaluate_summary(self, summary: SolverLogSummary, *, artifact: str | None = None) -> StageResult:
        metrics: dict[str, object] = {
            "time_steps": len(summary.times),
            "completed_time_steps": len(summary.completed_times),
            "time_advances": sum(b > a for a, b in zip(summary.times, summary.times[1:])),
            "time_regressions": sum(b < a for a, b in zip(summary.times, summary.times[1:])),
            "fatal_errors": summary.fatal_error_count,
            "fatal_error_messages": summary.fatal_errors,
            "nonfinite_samples": summary.nonfinite_samples,
            "evidence_kind": "numerical_log_health",
        }
        if summary.latest_time is not None:
            metrics["latest_time"] = summary.latest_time
        if summary.max_courant is not None:
            metrics["max_courant"] = summary.max_courant
        if summary.latest_cumulative_continuity_error is not None:
            metrics["max_abs_cumulative_continuity_error"] = max(
                abs(item.cumulative) for item in summary.continuity
            )
        if summary.completed_residual_maxima:
            metrics["max_final_residual"] = max(summary.completed_residual_maxima)
        metrics['residual_scope'] = 'last_solve_per_field_per_completed_step'

        rules = [
            MetricRule(metric="time_steps", operator=">=", threshold=self.thresholds.min_time_steps),
            MetricRule(metric="completed_time_steps", operator=">=", threshold=self.thresholds.min_time_steps),
            MetricRule(metric="time_advances", operator=">=", threshold=self.thresholds.min_time_steps - 1),
            MetricRule(metric="time_regressions", operator="==", threshold=0),
            MetricRule(metric="nonfinite_samples", operator="==", threshold=0),
            MetricRule(metric="fatal_errors", operator="==", threshold=0),
            MetricRule(metric="max_courant", operator="<=", threshold=self.thresholds.max_courant),
            MetricRule(
                metric="max_abs_cumulative_continuity_error",
                operator="<=",
                threshold=self.thresholds.max_abs_cumulative_continuity_error,
            ),
            MetricRule(
                metric="max_final_residual",
                operator="<=",
                threshold=self.thresholds.max_final_residual,
            ),
        ]
        if self.thresholds.max_interface_courant is not None:
            metrics['max_interface_courant'] = max(summary.interface_courant_maxima, default=None)
            rules.append(MetricRule(metric='max_interface_courant', operator='<=', threshold=self.thresholds.max_interface_courant))
        if self.thresholds.alpha_tolerance is not None:
            metrics['alpha_min'] = min(summary.alpha_minima, default=None)
            metrics['alpha_max'] = max(summary.alpha_maxima, default=None)
            rules.extend([MetricRule(metric='alpha_min', operator='>=', threshold=-self.thresholds.alpha_tolerance),
                          MetricRule(metric='alpha_max', operator='<=', threshold=1 + self.thresholds.alpha_tolerance)])
        return evaluate_stage(
            stage="monitoring",
            metrics=metrics,
            rules=rules,
            artifacts=[artifact] if artifact else [],
        )

    def evaluate_file(self, log_path: Path) -> StageResult:
        with log_path.open(encoding="utf-8", errors="replace") as stream:
            summary = parse_solver_lines(stream)
        return self.evaluate_summary(summary, artifact=str(log_path))
