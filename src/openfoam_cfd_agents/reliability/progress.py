"""Persisted wall-clock progress observations, independent of process liveness."""

from __future__ import annotations

import math
from pydantic import BaseModel, ConfigDict, Field

from openfoam_cfd_agents.domain import MetricRule, StageResult, evaluate_stage


class ProgressState(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    job_id: str = Field(min_length=1)
    latest_completed_time: float | None = None
    last_advance_at: float
    observed_at: float
    advance_count: int = Field(default=0, ge=0)


def observe_progress(previous: ProgressState | None, *, job_id: str,
                     latest_completed_time: float | None, now: float, process_alive: bool,
                     stall_seconds: float = 300, target_time: float | None = None,
                     process_exit_code: int | None = None) -> tuple[StageResult, ProgressState]:
    if not math.isfinite(now) or not math.isfinite(stall_seconds) or stall_seconds <= 0:
        raise ValueError('finite clock and positive stall window required')
    if target_time is not None and not math.isfinite(target_time):
        raise ValueError('target time must be finite')
    if previous and (previous.job_id != job_id or now < previous.observed_at):
        raise ValueError('job identity mismatch or wall clock regressed; reconcile before continuing')
    finite = latest_completed_time is not None and math.isfinite(latest_completed_time)
    old_time = previous.latest_completed_time if previous else None
    advancing = finite and previous is not None and (old_time is None or latest_completed_time > old_time)
    regressed = previous is not None and old_time is not None and (not finite or latest_completed_time < old_time)
    last_advance = now if previous is None or advancing else previous.last_advance_at
    reached = finite and target_time is not None and latest_completed_time >= target_time
    clean_exit = reached and not process_alive and process_exit_code == 0
    state = ProgressState(job_id=job_id, latest_completed_time=latest_completed_time if finite else None,
                          last_advance_at=last_advance, observed_at=now,
                          advance_count=(previous.advance_count if previous else 0) + int(advancing))
    metrics = {'process_alive': process_alive, 'target_reached': bool(reached), 'clean_target_exit': bool(clean_exit),
               'latest_completed_time': state.latest_completed_time, 'seconds_since_advance': now - last_advance,
               'progress_observed': int(state.advance_count > 0 or clean_exit),
               'regressed': int(regressed), 'within_stall_window': int(now - last_advance < stall_seconds or clean_exit),
               'execution_viable': int(process_alive or clean_exit), 'finite_time': int(finite)}
    result = evaluate_stage(stage='live_progress', metrics=metrics, rules=[
        *[MetricRule(metric=k, operator='==', threshold=1) for k in
          ('progress_observed', 'within_stall_window', 'execution_viable', 'finite_time')],
        MetricRule(metric='regressed', operator='==', threshold=0)])
    return result, state
