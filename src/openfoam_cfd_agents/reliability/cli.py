"""Additional CLI commands. Monitoring and inspection never modify a case."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated

import typer

from openfoam_cfd_agents.agents.monitor import MonitorAgent, MonitorThresholds, parse_solver_log
from openfoam_cfd_agents.domain import MetricRule, StageStatus, evaluate_stage
from .checkpoints import inspect_checkpoint, parse_field_list
from .live import linux_process_identity, read_log_tail
from .progress import ProgressState, observe_progress
from .resources import parse_cpu_list, parse_cpu_topology, validate_cpu_allocation
from .runtime import probe_runtime


def _emit(result, output: Path | None = None):
    text = result.model_dump_json(indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding='utf-8')
    else:
        typer.echo(text)
    if result.status is not StageStatus.PASSED:
        raise typer.Exit(2)


def checkpoint(case_path: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
               processes: Annotated[int, typer.Option(min=1)],
               fields: Annotated[str, typer.Option(help='JSON array or comma-separated fields; use JSON for names containing commas')],
               time_name: Annotated[str | None, typer.Option('--time')] = None,
               min_age_seconds: Annotated[float, typer.Option(min=0)] = 30,
               output: Annotated[Path | None, typer.Option()] = None):
    """Inspect checkpoint candidates across all partitions without changing files."""
    _emit(inspect_checkpoint(case_path, processes=processes, required_fields=parse_field_list(fields),
                             time_name=time_name, min_age_seconds=min_age_seconds), output)


def audit_cpus(topology: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
               cpus: Annotated[str, typer.Option()], reserved: Annotated[str, typer.Option()] = '',
               output: Annotated[Path | None, typer.Option()] = None):
    """Check physical-core conflicts using saved `lscpu -p=CPU,CORE,SOCKET,NODE` output."""
    _emit(validate_cpu_allocation(parse_cpu_list(cpus), parse_cpu_topology(topology.read_text()),
                                  reserved_cpus=parse_cpu_list(reserved) if reserved else []), output)


def live_monitor(log_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
                 pid: Annotated[int, typer.Option(min=1)], job_id: Annotated[str, typer.Option()],
                 state: Annotated[Path, typer.Option(help='Private persisted state file for this job')],
                 stall_seconds: Annotated[float, typer.Option(min=1)] = 300,
                 target_time: Annotated[float | None, typer.Option()] = None,
                 max_courant: Annotated[float, typer.Option()] = 1,
                 max_interface_courant: Annotated[float | None, typer.Option()] = None,
                 alpha_tolerance: Annotated[float | None, typer.Option()] = None,
                 max_continuity_error: Annotated[float, typer.Option()] = 1e-6,
                 max_final_residual: Annotated[float, typer.Option()] = 1e-3,
                 output: Annotated[Path | None, typer.Option()] = None):
    """Sample numerical health and completed-time progress; run repeatedly from a timer.

    The first observation establishes a baseline and returns exit 2. A later
    advancing observation is required. Error evidence is sticky within a job.
    """
    paths = [log_path.resolve(), state.resolve(), *([output.resolve()] if output else [])]
    if len(paths) != len(set(paths)):
        raise typer.BadParameter('log, state and output must be distinct files')
    identity = linux_process_identity(pid)
    previous = json.loads(state.read_text(encoding='utf-8')) if state.exists() else None
    resolved_log = str(log_path.resolve())
    if previous and (previous['log_path'] != resolved_log or previous['pid'] != pid):
        raise typer.BadParameter('state belongs to another log/PID; use a new job and state file')
    if previous and identity is not None and previous['process_identity'] != identity:
        raise typer.BadParameter('process identity changed; reconcile restart and use a new job/state')
    text, offset = read_log_tail(log_path)
    summary = parse_solver_log(text)
    thresholds = MonitorThresholds(max_courant=max_courant, max_interface_courant=max_interface_courant,
                                   alpha_tolerance=alpha_tolerance,
                                   max_abs_cumulative_continuity_error=max_continuity_error,
                                   max_final_residual=max_final_residual)
    numerical = MonitorAgent(thresholds).evaluate_summary(summary)
    progress, updated = observe_progress(
        ProgressState.model_validate(previous['progress']) if previous else None,
        job_id=job_id, latest_completed_time=summary.completed_times[-1] if summary.completed_times else None,
        now=time.time(), process_alive=identity is not None, stall_seconds=stall_seconds, target_time=target_time)
    error_seen = bool(summary.fatal_error_count or summary.nonfinite_samples or (previous and previous['error_seen']))
    size = log_path.stat().st_size
    truncated = bool(previous and size < previous['log_size'])
    saved = {'progress': updated.model_dump(), 'process_identity': identity or (previous or {}).get('process_identity'),
             'log_path': resolved_log, 'pid': pid, 'log_size': size, 'error_seen': error_seen or truncated}
    state.parent.mkdir(parents=True, exist_ok=True)
    temporary = state.with_suffix(state.suffix + '.tmp')
    temporary.write_text(json.dumps(saved, allow_nan=False), encoding='utf-8')
    temporary.replace(state)
    metrics = {'numerical_health': int(numerical.status is StageStatus.PASSED),
               'time_health': int(progress.status is StageStatus.PASSED), 'error_seen': int(saved['error_seen']),
               'progress': progress.metrics, 'numerical': numerical.metrics,
               'log_offset': offset, 'evidence_scope': 'bounded_tail_plus_persisted_observations'}
    result = evaluate_stage(stage='live_monitoring', metrics=metrics, rules=[
        MetricRule(metric='numerical_health', operator='==', threshold=1),
        MetricRule(metric='time_health', operator='==', threshold=1),
        MetricRule(metric='error_seen', operator='==', threshold=0)])
    _emit(result, output)


def register(app: typer.Typer) -> None:
    app.command('checkpoint')(checkpoint)
    app.command('audit-cpus')(audit_cpus)
    app.command('live-monitor')(live_monitor)
    app.command('probe-runtime')(runtime_command)


def runtime_command(solver_module: Annotated[str, typer.Option()],
                    output: Annotated[Path | None, typer.Option()] = None):
    """Verify foamRun's actual v14 identity and a solver library without solving."""
    _emit(probe_runtime(solver_module), output)
