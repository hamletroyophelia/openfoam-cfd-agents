"""Deterministic durable worker; the process backend owns process lifetimes."""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from openfoam_cfd_agents.jobs import JobLedger

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessObservation:
    state: Literal['missing', 'running', 'exited', 'unknown']
    identity: str | None = None
    exit_code: int | None = None


class ProcessBackend(Protocol):
    def launch(self, job: dict) -> None: ...
    def observe(self, job: dict) -> ProcessObservation: ...
    def cancel(self, job: dict, identity: str) -> ProcessObservation: ...


class WorkerAgent:
    def __init__(self, ledger: JobLedger, backend: ProcessBackend, principal: str, project: str):
        self.ledger, self.backend = ledger, backend
        self.principal, self.project = principal, project

    def _move(self, job, status, **evidence):
        return self.ledger.transition(self.principal, self.project, job['job_id'],
                                      expected=job['status'], status=status, **evidence)

    def _uncertain(self, job):
        # Preserve a pending cancellation: it must not become running after a retry.
        if job['status'] not in ('reconciliation_required', 'cancel_requested'):
            self._move(job, 'reconciliation_required')

    def _reconcile(self, job):
        observation = self.backend.observe(job)
        if observation.state in ('missing', 'unknown') or not observation.identity:
            self._uncertain(job)
            return
        if job['process_identity'] and job['process_identity'] != observation.identity:
            self._uncertain(job)
            return  # Never signal a replacement invocation.
        if job['status'] == 'cancel_requested':
            if observation.state == 'running':
                observation = self.backend.cancel(job, observation.identity)
            if observation.state == 'exited' and observation.exit_code is not None:
                self._move(job, 'cancelled', process_identity=observation.identity,
                           exit_confirmed=True, exit_code=observation.exit_code)
            return
        if job['status'] != 'running':
            job = self._move(job, 'running', process_identity=observation.identity)
        if observation.state == 'exited' and observation.exit_code is not None:
            self._move(job, 'completed' if observation.exit_code == 0 else 'failed',
                       exit_confirmed=True, exit_code=observation.exit_code)

    def tick(self) -> list[dict]:
        for job in self.ledger.list_active(self.principal, self.project):
            try:
                if job['status'] == 'queued':
                    # Commit intent before the first external side effect. An interrupted
                    # launching state is reconciled, never automatically launched again.
                    job = self._move(job, 'launching')
                    self.backend.launch(job)
                self._reconcile(job)
            except Exception:
                LOG.exception('job %s needs reconciliation', job['job_id'])
                current = self.ledger.get(self.principal, self.project, job['job_id'])
                if current['status'] in ('launching', 'running'):
                    self._uncertain(current)
        return self.ledger.list_active(self.principal, self.project)


@contextmanager
def worker_lock(database: Path):
    """One local Linux controller per database, including across CLI invocations."""
    import fcntl
    with database.with_suffix(database.suffix + '.worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('another worker owns this database') from exc
        yield


def serve(worker: WorkerAgent, *, interval: float = 5, once: bool = False):
    if not 0 < interval <= 3600:
        raise ValueError('interval must be positive and at most 3600 seconds')
    with worker_lock(worker.ledger.path):
        previous = None
        while True:
            active = worker.tick()
            status = json.dumps({'active_jobs': [{k: row[k] for k in ('job_id', 'status')} for row in active]})
            if status != previous:
                print(status, flush=True)
                previous = status
            if once:
                return
            time.sleep(interval)
