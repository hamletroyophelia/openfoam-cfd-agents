"""Trusted local worker commands; these do not provide remote authentication."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer

from openfoam_cfd_agents.adapters.openfoam.local import RunPlan
from openfoam_cfd_agents.job_runtime import ExecutionSpec
from openfoam_cfd_agents.jobs import JobLedger
from openfoam_cfd_agents.systemd_backend import SystemdUserBackend
from openfoam_cfd_agents.worker import WorkerAgent, serve

app = typer.Typer(no_args_is_help=True, help='Trusted local job submission and Linux systemd worker.')
Database = Annotated[Path, typer.Option('--db', help='One local SQLite database for all case writers')]
Principal = Annotated[str, typer.Option()]
Project = Annotated[str, typer.Option()]


@app.command('submit')
def submit(plan_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
           db: Database, revision: Annotated[str, typer.Option()], key: Annotated[str, typer.Option()],
           principal: Principal = 'local', project: Project = 'default',
           max_runtime_seconds: Annotated[float, typer.Option(min=1)] = 86400,
           min_free_bytes: Annotated[int, typer.Option(min=0)] = 100_000_000):
    """Persist an OpenFOAM run plan; the separately running worker executes it.

    Source OpenFOAM before submission. Environment snapshots contain only runtime
    variables, not the caller's general environment or credentials.
    """
    plan = RunPlan.model_validate_json(plan_file.read_text(encoding='utf-8'))
    environment = {k: v for k, v in os.environ.items()
                   if k in ('PATH', 'LD_LIBRARY_PATH') or k.startswith(('FOAM_', 'WM_'))}
    spec = ExecutionSpec(case_path=str(Path(plan.commands[0].cwd).resolve()), revision=revision,
                         plan=plan, environment=environment, max_runtime_seconds=max_runtime_seconds,
                         min_free_bytes=min_free_bytes)
    row = JobLedger(db).submit(principal, project, key, spec.model_dump(mode='json'))
    typer.echo(json.dumps({k: row[k] for k in ('job_id', 'status', 'digest')}, indent=2))


@app.command('status')
def status(job_id: str, db: Database, principal: Principal = 'local', project: Project = 'default'):
    ledger = JobLedger(db)
    row = ledger.get(principal, project, job_id)
    row.pop('spec')  # Do not echo environment snapshots in routine status output.
    typer.echo(json.dumps({'job': row, 'events': ledger.events(principal, project, job_id)}, indent=2))


@app.command('cancel')
def cancel(job_id: str, db: Database, principal: Principal = 'local', project: Project = 'default'):
    row = JobLedger(db).request_cancel(principal, project, job_id)
    typer.echo(json.dumps({k: row[k] for k in ('job_id', 'status')}, indent=2))


@app.command('worker')
def worker(db: Database, spool: Annotated[Path, typer.Option()],
           principal: Principal = 'local', project: Project = 'default',
           interval: Annotated[float, typer.Option(min=0.1, max=3600)] = 5,
           once: Annotated[bool, typer.Option()] = False):
    if os.name != 'posix' or not Path('/proc').is_dir():
        raise typer.BadParameter('worker execution requires Linux systemd user services and cgroup v2')
    serve(WorkerAgent(JobLedger(db), SystemdUserBackend(spool), principal, project), interval=interval, once=once)
