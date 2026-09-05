import sys

import pytest

from openfoam_cfd_agents.adapters.openfoam.local import CommandSpec, LocalOpenFoamAdapter, RunPlan


def test_default_execution_streams_to_exclusive_log(tmp_path, monkeypatch):
    import openfoam_cfd_agents.adapters.openfoam.local as local
    plan = RunPlan(processes=1, commands=[CommandSpec(argv=['foamRun'], cwd=str(tmp_path))])
    def run(argv, **kwargs):
        assert 'capture_output' not in kwargs
        kwargs['stdout'].write('streamed solver output\n')
        return type('Result', (), {'returncode': 0})()
    monkeypatch.setattr(local.subprocess, 'run', run)
    result = LocalOpenFoamAdapter().execute_plan(plan, log_dir=tmp_path / 'logs')
    assert result.status.value == 'passed'
    assert 'streamed solver output' in (tmp_path / 'logs/01-foamRun.log').read_text()
    with pytest.raises(FileExistsError):
        LocalOpenFoamAdapter().execute_plan(plan, log_dir=tmp_path / 'logs')


def test_absolute_executable_produces_a_log_inside_the_output_directory(tmp_path):
    plan = RunPlan(processes=1, commands=[CommandSpec(argv=[sys.executable, '-c', "print('ok')"], cwd=str(tmp_path))])
    result = LocalOpenFoamAdapter().execute_plan(plan, log_dir=tmp_path / 'logs')
    assert result.status.value == 'passed'
    from pathlib import Path
    assert Path(result.artifacts[0]).parent == tmp_path / 'logs'
