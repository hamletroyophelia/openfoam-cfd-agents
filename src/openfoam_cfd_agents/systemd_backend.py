"""Linux systemd user services keep process ownership across worker restarts."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from openfoam_cfd_agents.job_runtime import ExecutionSpec
from openfoam_cfd_agents.worker import ProcessObservation

PROPERTIES = ('LoadState', 'ActiveState', 'SubState', 'InvocationID', 'ExecMainCode',
              'ExecMainStatus', 'ControlGroup', 'Description', 'Result')


class SystemdUserBackend:
    def __init__(self, spool: Path, *, run=subprocess.run, cgroup_root=Path('/sys/fs/cgroup')):
        self.spool, self.run, self.cgroup_root = spool.resolve(), run, cgroup_root
        self.spool.mkdir(parents=True, exist_ok=True, mode=0o700)

    @staticmethod
    def unit(job):
        if not re.fullmatch(r'[0-9a-f]{32}', job['job_id']):
            raise ValueError('invalid job id')
        return f'cfd-job-{job["job_id"]}.service'

    @staticmethod
    def description(job):
        return f'cfd-job:{job["job_id"]}:{job["digest"]}'

    def _call(self, argv, *, check=True, timeout=15):
        return self.run(argv, check=check, capture_output=True, text=True, timeout=timeout)

    def launch(self, job):
        spec = ExecutionSpec.model_validate_json(job['spec'])
        unit = self.unit(job)
        directory = self.spool / job['job_id']
        # systemd 249 expands these characters in unit properties/ExecStart.
        # Refuse ambiguous paths instead of depending on a newer expand switch.
        if any(char in str(path) for path in (directory, spec.case_path, sys.executable) for char in '%$\n\r'):
            raise ValueError('systemd payload paths cannot contain %, $, or newlines')
        directory.mkdir(mode=0o700)
        path = directory / 'spec.json'
        with path.open('x', encoding='utf-8') as stream:
            stream.write(spec.model_dump_json(indent=2))
        argv = ['systemd-run', '--user', f'--unit={unit}', f'--description={self.description(job)}',
                '--property=Type=exec', '--property=RemainAfterExit=yes', '--property=Restart=no',
                '--property=KillMode=control-group', '--property=KillSignal=SIGINT',
                '--property=TimeoutStopSec=30', f'--property=RuntimeMaxSec={spec.max_runtime_seconds}',
                f'--property=WorkingDirectory={spec.case_path}',
                f'--property=StandardOutput=append:{directory / "service.log"}',
                '--property=StandardError=inherit', '--', sys.executable, '-m',
                'openfoam_cfd_agents.job_runtime', str(path)]
        result = self._call(argv)
        (directory / 'launch.json').write_text(json.dumps({'unit': unit, 'stdout': result.stdout,
                                                         'stderr': result.stderr}), encoding='utf-8')

    def _properties(self, job):
        result = self._call(['systemctl', '--user', 'show', self.unit(job),
                             '--property=' + ','.join(PROPERTIES)], check=False)
        props = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        if result.returncode and props.get('LoadState') != 'not-found':
            raise RuntimeError('cannot query systemd: ' + result.stderr.strip())
        return props

    def _empty_group(self, group: str) -> bool:
        if not group:
            return True  # systemd reports no cgroup for a fully stopped service.
        root = self.cgroup_root.resolve()
        if not (root / 'cgroup.controllers').is_file():
            return False
        path = (root / group.lstrip('/')).resolve()
        if path == root or root not in path.parents:
            return False
        if not path.exists():
            return True
        files = [path / 'cgroup.procs', *path.glob('**/cgroup.procs')]
        try:
            return all(not file.read_text().strip() for file in files)
        except OSError:
            return False

    def observe(self, job):
        props = self._properties(job)
        if props.get('LoadState') == 'not-found':
            receipt = self.spool / job['job_id'] / 'cancel-exit.json'
            if receipt.exists():
                proof = json.loads(receipt.read_text(encoding='utf-8'))
                if proof['description'] == self.description(job):
                    return ProcessObservation('exited', proof['identity'], proof['exit_code'])
            return ProcessObservation('missing')
        if props.get('Description') != self.description(job) or not props.get('InvocationID'):
            return ProcessObservation('unknown')
        identity = self.unit(job) + ':' + props['InvocationID']
        state, substate = props.get('ActiveState'), props.get('SubState')
        if state in ('activating', 'active') and substate not in ('exited', 'dead', 'failed'):
            return ProcessObservation('running', identity)
        if (state in ('inactive', 'failed') or substate == 'exited') and self._empty_group(props.get('ControlGroup', '')):
            code = int(props.get('ExecMainCode', '0'))
            status = int(props.get('ExecMainStatus', '0'))
            if code:
                exit_code = status if code == 1 else 128 + status
                if props.get('Result') not in (None, '', 'success') and exit_code == 0:
                    exit_code = 1
                return ProcessObservation('exited', identity, exit_code)
        return ProcessObservation('unknown', identity)

    def cancel(self, job, identity):
        before = self.observe(job)
        if before.identity != identity or before.state != 'running':
            return ProcessObservation('unknown', before.identity)
        props = self._properties(job)
        if self.unit(job) + ':' + props.get('InvocationID', '') != identity:
            return ProcessObservation('unknown')
        self._call(['systemctl', '--user', 'stop', self.unit(job)], timeout=45)
        after = self._properties(job)
        same_or_gone = after.get('LoadState') == 'not-found' or (
            after.get('ActiveState') in ('inactive', 'failed') and
            after.get('InvocationID', '') in ('', props['InvocationID']))
        if not same_or_gone or not self._empty_group(props.get('ControlGroup', '')):
            return ProcessObservation('unknown', identity)
        # Persist the synchronous stop receipt before the ledger releases its lock.
        proof = {'description': self.description(job), 'identity': identity, 'exit_code': 130}
        receipt = self.spool / job['job_id'] / 'cancel-exit.json'
        temporary = receipt.with_suffix('.tmp')
        temporary.write_text(json.dumps(proof), encoding='utf-8')
        temporary.replace(receipt)
        return ProcessObservation('exited', identity, 130)
