import json
from dataclasses import replace

import pytest

from openfoam_cfd_agents.jobs import JobLedger


class FakeBackend:
    def __init__(self):
        from openfoam_cfd_agents.worker import ProcessObservation
        self.observation = ProcessObservation('missing')
        self.launches = 0
        self.cancellations = 0
        self.launch_error = False

    def observe(self, job):
        return self.observation

    def launch(self, job):
        from openfoam_cfd_agents.worker import ProcessObservation
        self.launches += 1
        self.observation = ProcessObservation('running', 'invocation-a')
        if self.launch_error:
            raise TimeoutError('ACK lost after launch')

    def cancel(self, job, identity):
        from openfoam_cfd_agents.worker import ProcessObservation
        assert identity == self.observation.identity
        self.cancellations += 1
        return ProcessObservation('exited', identity, 130)


def setup_job(tmp_path):
    ledger = JobLedger(tmp_path / 'jobs.sqlite')
    job = ledger.submit('alice', 'cfd', 'key', {'case_path': str(tmp_path / 'case'), 'revision': 'v1'})
    backend = FakeBackend()
    return ledger, job, backend


def test_restart_reconciles_launch_without_duplicate_process(tmp_path):
    from openfoam_cfd_agents.worker import WorkerAgent
    ledger, job, backend = setup_job(tmp_path)
    backend.launch_error = True
    WorkerAgent(ledger, backend, 'alice', 'cfd').tick()
    assert ledger.get('alice', 'cfd', job['job_id'])['status'] == 'reconciliation_required'
    WorkerAgent(ledger, backend, 'alice', 'cfd').tick()
    assert ledger.get('alice', 'cfd', job['job_id'])['status'] == 'running'
    assert backend.launches == 1


def test_success_and_failure_use_verified_exit_code(tmp_path):
    from openfoam_cfd_agents.worker import WorkerAgent
    ledger, job, backend = setup_job(tmp_path)
    worker = WorkerAgent(ledger, backend, 'alice', 'cfd')
    worker.tick()
    backend.observation = replace(backend.observation, state='exited', exit_code=0)
    worker.tick()
    assert ledger.get('alice', 'cfd', job['job_id'])['status'] == 'completed'
    assert ledger.list_active('alice', 'cfd') == []


def test_identity_change_keeps_lock_and_never_signals_foreign_job(tmp_path):
    from openfoam_cfd_agents.worker import WorkerAgent
    ledger, job, backend = setup_job(tmp_path)
    worker = WorkerAgent(ledger, backend, 'alice', 'cfd')
    worker.tick()
    ledger.request_cancel('alice', 'cfd', job['job_id'])
    backend.observation = replace(backend.observation, identity='foreign')
    worker.tick()
    assert backend.cancellations == 0
    assert ledger.get('alice', 'cfd', job['job_id'])['status'] == 'cancel_requested'
    with pytest.raises(ValueError, match='writer'):
        ledger.submit('alice', 'cfd', 'key2', json.loads(job['spec']))


def test_queued_cancel_never_launches_and_running_cancel_checks_exit(tmp_path):
    from openfoam_cfd_agents.worker import WorkerAgent
    ledger, job, backend = setup_job(tmp_path)
    worker = WorkerAgent(ledger, backend, 'alice', 'cfd')
    worker.tick()
    ledger.request_cancel('alice', 'cfd', job['job_id'])
    worker.tick()
    assert ledger.get('alice', 'cfd', job['job_id'])['status'] == 'cancelled'
    job2 = ledger.submit('alice', 'cfd', 'key2', json.loads(job['spec']))
    ledger.request_cancel('alice', 'cfd', job2['job_id'])
    worker.tick()
    assert backend.launches == 1


def test_missing_unit_after_interrupted_launch_is_not_retried(tmp_path):
    from openfoam_cfd_agents.worker import WorkerAgent
    ledger, job, backend = setup_job(tmp_path)
    ledger.transition('alice', 'cfd', job['job_id'], expected='queued', status='launching')
    WorkerAgent(ledger, backend, 'alice', 'cfd').tick()
    assert backend.launches == 0
    assert ledger.get('alice', 'cfd', job['job_id'])['status'] == 'reconciliation_required'


def test_nonzero_exit_fails_and_scope_is_respected(tmp_path):
    from openfoam_cfd_agents.worker import WorkerAgent
    ledger, job, backend = setup_job(tmp_path)
    WorkerAgent(ledger, backend, 'bob', 'cfd').tick()
    assert backend.launches == 0
    worker = WorkerAgent(ledger, backend, 'alice', 'cfd')
    worker.tick()
    backend.observation = replace(backend.observation, state='exited', exit_code=9)
    worker.tick()
    assert ledger.get('alice', 'cfd', job['job_id'])['status'] == 'failed'


def test_cancel_ack_without_exit_keeps_pending_and_case_lock(tmp_path):
    from openfoam_cfd_agents.worker import WorkerAgent, ProcessObservation
    ledger, job, backend = setup_job(tmp_path)
    worker = WorkerAgent(ledger, backend, 'alice', 'cfd')
    worker.tick()
    ledger.request_cancel('alice', 'cfd', job['job_id'])
    backend.cancel = lambda job, identity: ProcessObservation('unknown', identity)
    worker.tick()
    assert ledger.get('alice', 'cfd', job['job_id'])['status'] == 'cancel_requested'
    with pytest.raises(ValueError, match='writer'):
        ledger.submit('alice', 'cfd', 'key2', json.loads(job['spec']))


def test_linux_worker_lock_excludes_second_controller(tmp_path):
    import os
    if os.name != 'posix':
        pytest.skip('Linux flock integration')
    from openfoam_cfd_agents.worker import worker_lock
    with worker_lock(tmp_path / 'jobs.sqlite'):
        with pytest.raises(RuntimeError, match='another worker'):
            with worker_lock(tmp_path / 'jobs.sqlite'):
                pytest.fail('second worker acquired lock')
