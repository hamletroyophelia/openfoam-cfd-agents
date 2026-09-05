import json
import subprocess
from pathlib import Path

import pytest


def job(tmp_path):
    return {'job_id': 'a' * 32, 'digest': 'b' * 64, 'case_path': str(tmp_path),
            'spec': json.dumps({'case_path': str(tmp_path), 'revision': 'v1',
                               'plan': {'processes': 1, 'commands': [{'argv': ['foamRun'], 'cwd': str(tmp_path)}]}})}


def test_backend_retains_exit_evidence_and_uses_shell_free_argv(tmp_path):
    from openfoam_cfd_agents.systemd_backend import SystemdUserBackend
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, '', '')
    backend = SystemdUserBackend(tmp_path / 'spool', run=run)
    backend.launch(job(tmp_path))
    argv = calls[-1]
    assert '--property=RemainAfterExit=yes' in argv
    assert '--property=KillMode=control-group' in argv
    assert '--property=Restart=no' in argv
    assert '--property=Type=exec' in argv
    assert '-m' in argv and 'openfoam_cfd_agents.job_runtime' in argv
    assert not any('bash' in arg for arg in argv)


def test_exit_requires_same_invocation_and_empty_cgroup(tmp_path):
    from openfoam_cfd_agents.systemd_backend import SystemdUserBackend
    row = job(tmp_path)
    output = ('LoadState=loaded\nActiveState=active\nSubState=exited\nInvocationID=abc\n'
              'ExecMainCode=1\nExecMainStatus=0\nControlGroup=/unit\n'
              f'Description=cfd-job:{row["job_id"]}:{row["digest"]}\n')
    def run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, output, '')
    cgroup = tmp_path / 'cgroup' / 'unit'
    cgroup.mkdir(parents=True)
    (tmp_path / 'cgroup' / 'cgroup.controllers').write_text('cpu memory')
    (cgroup / 'cgroup.procs').write_text('123\n')
    backend = SystemdUserBackend(tmp_path / 'spool', run=run, cgroup_root=tmp_path / 'cgroup')
    assert backend.observe(row).state == 'unknown'
    (cgroup / 'cgroup.procs').write_text('')
    assert backend.observe(row).exit_code == 0
    output = output.replace('InvocationID=abc', 'InvocationID=def')
    assert backend.observe(row).identity.endswith(':def')
    output = output.replace(row['digest'], 'wrong-digest')
    assert backend.observe(row).state == 'unknown'


def test_missing_cgroup_v2_mount_is_not_exit_evidence(tmp_path):
    from openfoam_cfd_agents.systemd_backend import SystemdUserBackend
    backend = SystemdUserBackend(tmp_path / 'spool', cgroup_root=tmp_path / 'not-mounted')
    assert not backend._empty_group('/unit')


def test_spec_rejects_cross_case_commands_and_nonfinite_budget(tmp_path):
    from openfoam_cfd_agents.job_runtime import ExecutionSpec
    raw = json.loads(job(tmp_path)['spec'])
    raw['plan']['commands'][0]['cwd'] = str(tmp_path / 'other')
    with pytest.raises(ValueError, match='case'):
        ExecutionSpec.model_validate(raw)
    raw = json.loads(job(tmp_path)['spec'])
    raw['max_runtime_seconds'] = float('nan')
    with pytest.raises(ValueError):
        ExecutionSpec.model_validate(raw)


def test_launch_cannot_overwrite_previous_attempt_files(tmp_path):
    from openfoam_cfd_agents.systemd_backend import SystemdUserBackend
    backend = SystemdUserBackend(tmp_path / 'spool', run=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, '', ''))
    backend.launch(job(tmp_path))
    with pytest.raises(FileExistsError):
        backend.launch(job(tmp_path))
