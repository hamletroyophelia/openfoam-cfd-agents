"""Opt-in Linux/systemd lifecycle test, using only disposable Python processes.

Run: python tests/integration/systemd_worker.py /absolute/empty/evidence-directory
This does not start OpenFOAM, modify production cases, or run in the pytest suite.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

from openfoam_cfd_agents.jobs import JobLedger
from openfoam_cfd_agents.systemd_backend import SystemdUserBackend
from openfoam_cfd_agents.worker import WorkerAgent
from openfoam_cfd_agents.reliability.live import linux_process_identity


def wait_for(predicate, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError('timed out waiting for test condition')


def main(root):
    root.mkdir(parents=True, exist_ok=False)
    ledger = JobLedger(root / 'jobs.sqlite')
    backend = SystemdUserBackend(root / 'spool')
    worker = WorkerAgent(ledger, backend, 'integration', 'processes')
    jobs = []
    results = {}

    def submit(name, code, max_runtime_seconds=60):
        case = root / (name + ' case with spaces')
        case.mkdir()
        spec = {'case_path': str(case), 'revision': 'integration-v1', 'kind': 'process',
                'max_runtime_seconds': max_runtime_seconds, 'min_free_bytes': 0,
                'plan': {'processes': 1, 'commands': [{'argv': [sys.executable, '-c', code], 'cwd': str(case)}]}}
        row = ledger.submit('integration', 'processes', name, spec)
        jobs.append(row)
        return row

    def get(row):
        return ledger.get('integration', 'processes', row['job_id'])

    def terminal(row):
        worker.tick()
        return get(row) if get(row)['status'] in ('completed', 'failed', 'cancelled') else None

    try:
        row = submit('survival', 'import time; from pathlib import Path; Path("started").write_text("yes"); time.sleep(5)')
        command = [sys.executable, '-m', 'openfoam_cfd_agents.cli', 'jobs', 'worker', '--db', str(ledger.path),
                   '--spool', str(backend.spool), '--principal', 'integration', '--project', 'processes', '--interval', '0.2']
        controller = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            wait_for(lambda: get(row)['status'] == 'running' and (Path(row['case_path']) / 'started').exists())
            identity = get(row)['process_identity']
            controller.terminate()
            controller.wait(timeout=5)
            assert backend.observe(row).state == 'running'
            worker.tick()  # New controller reconciles the surviving job.
            assert get(row)['process_identity'] == identity
            result = wait_for(lambda: terminal(row))
            assert result['status'] == 'completed'
            assert sum(e['status'] == 'launching' for e in ledger.events('integration', 'processes', row['job_id'])) == 1
            results['worker_restart_survival'] = True
        finally:
            if controller.poll() is None:
                controller.terminate()
                controller.wait(timeout=5)

        row = submit('failure', 'raise SystemExit(7)')
        result = wait_for(lambda: terminal(row))
        assert result['status'] == 'failed'
        execution = json.loads((backend.spool / row['job_id'] / 'execution.json').read_text())
        assert execution['metrics']['last_return_code'] == 7
        results['nonzero_exit'] = True

        row = submit('interrupted-launch', 'import time; time.sleep(2)')
        ledger.transition('integration', 'processes', row['job_id'], expected='queued', status='launching')
        backend.launch(row)  # Model a crash after external launch but before recording identity.
        assert get(row)['process_identity'] is None
        result = wait_for(lambda: terminal(row))
        assert result['status'] == 'completed'
        assert sum(e['status'] == 'launching' for e in ledger.events('integration', 'processes', row['job_id'])) == 1
        results['interrupted_launch_reconciled'] = True

        row = submit('cancel', 'import subprocess,sys,time; from pathlib import Path; '
                     'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(45)"]); '
                     'Path("child.pid").write_text(str(p.pid)); time.sleep(45)')
        worker.tick()
        pidfile = Path(row['case_path']) / 'child.pid'
        wait_for(pidfile.exists)
        child = int(pidfile.read_text())
        assert linux_process_identity(child)
        ledger.request_cancel('integration', 'processes', row['job_id'])
        result = wait_for(lambda: terminal(row))
        assert result['status'] == 'cancelled'
        assert linux_process_identity(child) is None
        results['cancel_descendants'] = True

        row = submit('timeout', 'import time; time.sleep(45)', max_runtime_seconds=2)
        result = wait_for(lambda: terminal(row))
        assert result['status'] == 'failed'
        results['runtime_budget_enforced'] = True
        results['jobs'] = [{k: get(row)[k] for k in ('job_id', 'status', 'process_identity')} for row in jobs]
        (root / 'result.json').write_text(json.dumps(results, indent=2))
        print(json.dumps(results, indent=2))
    finally:
        for row in jobs:
            # These units belong only to this disposable test's UUIDs.
            subprocess.run(['systemctl', '--user', 'stop', backend.unit(row)], capture_output=True)
            subprocess.run(['systemctl', '--user', 'reset-failed', backend.unit(row)], capture_output=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
