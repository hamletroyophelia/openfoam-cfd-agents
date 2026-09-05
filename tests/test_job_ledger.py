import concurrent.futures

import pytest


def spec(tmp_path, revision='revision-a'):
    return {'case_path': str(tmp_path / 'case'), 'revision': revision, 'processes': 2}


def test_idempotency_is_durable_and_spec_conflicts_are_rejected(tmp_path):
    from openfoam_cfd_agents.jobs import JobLedger
    db = tmp_path / 'jobs.sqlite'
    first = JobLedger(db).submit('alice', 'project', 'key', spec(tmp_path))
    assert JobLedger(db).submit('alice', 'project', 'key', spec(tmp_path)) == first
    with pytest.raises(ValueError, match='idempotency'):
        JobLedger(db).submit('alice', 'project', 'key', spec(tmp_path, 'changed'))


def test_concurrent_submission_starts_one_case_writer(tmp_path):
    from openfoam_cfd_agents.jobs import JobLedger
    db = tmp_path / 'jobs.sqlite'
    JobLedger(db)
    def submit(_):
        return JobLedger(db).submit('alice', 'p', 'key', spec(tmp_path))['job_id']
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        assert len(set(pool.map(submit, range(8)))) == 1


def test_launch_ambiguity_keeps_case_lock_and_cancel_ack_is_not_exit(tmp_path):
    from openfoam_cfd_agents.jobs import JobLedger
    ledger = JobLedger(tmp_path / 'jobs.sqlite')
    job = ledger.submit('alice', 'p', 'key', spec(tmp_path))
    jid = job['job_id']
    ledger.transition('alice', 'p', jid, expected='queued', status='launching')
    ledger.transition('alice', 'p', jid, expected='launching', status='reconciliation_required')
    with pytest.raises(ValueError, match='writer'):
        ledger.submit('bob', 'different-project', 'key2', spec(tmp_path, 'revision-b'))
    ledger.transition('alice', 'p', jid, expected='reconciliation_required', status='cancel_requested')
    with pytest.raises(ValueError, match='exit'):
        ledger.transition('alice', 'p', jid, expected='cancel_requested', status='cancelled')
    ledger.transition('alice', 'p', jid, expected='cancel_requested', status='cancelled', exit_confirmed=True)
    assert ledger.submit('alice', 'p', 'next', spec(tmp_path))['job_id'] != jid


def test_scope_and_compare_and_swap_cannot_be_bypassed(tmp_path):
    from openfoam_cfd_agents.jobs import JobLedger
    ledger = JobLedger(tmp_path / 'jobs.sqlite')
    jid = ledger.submit('alice', 'p', 'key', spec(tmp_path))['job_id']
    with pytest.raises(PermissionError):
        ledger.get('bob', 'p', jid)
    with pytest.raises(ValueError, match='state'):
        ledger.transition('alice', 'p', jid, expected='running', status='completed', exit_confirmed=True)


def test_provenance_invalidation_tracks_actual_dependency_keys():
    from openfoam_cfd_agents.reliability.evidence import EvidenceRecord, reusable_evidence
    record = EvidenceRecord(kind='numerical', dependencies={'mesh': 'm1', 'physics': 'p1'},
                            artifacts=['checks.json'])
    assert reusable_evidence(record, {'mesh': 'm1', 'physics': 'p1', 'camera': 'new'})
    assert not reusable_evidence(record, {'mesh': 'm1', 'physics': 'changed'})
    assert not reusable_evidence(record, {'mesh': 'm1'})
