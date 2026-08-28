"""Deterministic OpenFOAM solver-log monitoring and acceptance evaluation."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from openfoam_cfd_agents.domain import MetricRule, StageResult, evaluate_stage


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_TIME_RE = re.compile(rf"^Time\s*=\s*({_NUMBER})\s*$", re.MULTILINE)
_RESIDUAL_RE = re.compile(
    rf"Solving for\s+([^,]+),\s*Initial residual\s*=\s*({_NUMBER}),\s*"
    rf"Final residual\s*=\s*({_NUMBER}),\s*No Iterations\s+(\d+)"
)
_COURANT_RE = re.compile(
    rf"Courant Number\s+mean:\s*({_NUMBER})\s+max:\s*({_NUMBER})"
)
_CONTINUITY_RE = re.compile(
    rf"time step continuity errors\s*:\s*sum local\s*=\s*({_NUMBER}),\s*"
    rf"global\s*=\s*({_NUMBER}),\s*cumulative\s*=\s*({_NUMBER})"
)
_FATAL_MARKERS = ("FOAM FATAL", "MPI_ABORT", "Segmentation fault")


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

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_courant: float = Field(default=1.0, gt=0)
    max_abs_cumulative_continuity_error: float = Field(default=1e-6, gt=0)
    max_final_residual: float = Field(default=1e-3, gt=0)
    min_time_steps: int = Field(default=1, ge=1)


def parse_solver_log(text: str) -> SolverLogSummary:
    """Parse progress and stability signals emitted by Foundation OpenFOAM."""

    residuals = [
        ResidualSample(
            field=match.group(1).strip(),
            initial=float(match.group(2)),
            final=float(match.group(3)),
            iterations=int(match.group(4)),
        )
        for match in _RESIDUAL_RE.finditer(text)
    ]
    continuity = [
        ContinuitySample(
            local=float(match.group(1)),
            global_error=float(match.group(2)),
            cumulative=float(match.group(3)),
        )
        for match in _CONTINUITY_RE.finditer(text)
    ]
    fatal_errors = [
        line.strip()
        for line in text.splitlines()
        if any(marker.casefold() in line.casefold() for marker in _FATAL_MARKERS)
    ]
    return SolverLogSummary(
        times=[float(value) for value in _TIME_RE.findall(text)],
        residuals=residuals,
        courant_maxima=[float(match.group(2)) for match in _COURANT_RE.finditer(text)],
        continuity=continuity,
        fatal_errors=fatal_errors,
    )


class MonitorAgent:
    """Summarize a run, then delegate pass/fail to deterministic rules."""

    def __init__(self, thresholds: MonitorThresholds | None = None) -> None:
        self.thresholds = thresholds or MonitorThresholds()

    def evaluate_text(self, text: str, *, artifact: str | None = None) -> StageResult:
        summary = parse_solver_log(text)
        metrics: dict[str, object] = {
            "time_steps": len(summary.times),
            "fatal_errors": len(summary.fatal_errors),
            "fatal_error_messages": summary.fatal_errors,
        }
        if summary.latest_time is not None:
            metrics["latest_time"] = summary.latest_time
        if summary.max_courant is not None:
            metrics["max_courant"] = summary.max_courant
        if summary.latest_cumulative_continuity_error is not None:
            metrics["max_abs_cumulative_continuity_error"] = max(
                abs(item.cumulative) for item in summary.continuity
            )
        if summary.residuals:
            metrics["max_final_residual"] = max(item.final for item in summary.residuals)

        rules = [
            MetricRule(metric="time_steps", operator=">=", threshold=self.thresholds.min_time_steps),
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
        return evaluate_stage(
            stage="monitoring",
            metrics=metrics,
            rules=rules,
            artifacts=[artifact] if artifact else [],
        )

    def evaluate_file(self, log_path: Path) -> StageResult:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        return self.evaluate_text(text, artifact=str(log_path))
