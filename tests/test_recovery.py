from pathlib import Path

import pytest


def make_checkpoint(root: Path, time: str, ranks: int = 2):
    for rank in range(ranks):
        p = root / f'processor{rank}' / time
        (p / 'uniform').mkdir(parents=True)
        (p / 'uniform/time').write_text(f'value {time}; name "{time}"; index 10; deltaT 0.01; deltaT0 0.01;', encoding='utf-8')
        for field in ['U', 'p']:
            (p / field).write_text(f'FoamFile {{ format ascii; class volScalarField; object {field}; }}\ninternalField uniform 0;\n// ************************************************************************* //\n', encoding='utf-8')
    return root


def test_checkpoint_falls_back_when_latest_partition_field_missing(tmp_path):
    from openfoam_cfd_agents.reliability.checkpoints import inspect_checkpoint
    make_checkpoint(tmp_path, '1.0')
    make_checkpoint(tmp_path, '2.0')
    (tmp_path / 'processor1/2.0/U').unlink()
    result = inspect_checkpoint(tmp_path, processes=2, required_fields=['U', 'p'], min_age_seconds=0)
    assert result.status.value == 'passed'
    assert result.metrics['selected_time'] == '1.0'
    assert result.metrics['rejected_candidates'][0]['time'] == '2.0'


@pytest.mark.parametrize('defect', ['missing_rank', 'extra_rank', 'time_mismatch', 'empty_field', 'truncated_field'])
def test_invalid_checkpoint_cannot_be_accepted(tmp_path, defect):
    from openfoam_cfd_agents.reliability.checkpoints import inspect_checkpoint
    make_checkpoint(tmp_path, '1.0')
    if defect == 'missing_rank':
        (tmp_path / 'processor1').rename(tmp_path / 'missing1')
    elif defect == 'extra_rank':
        (tmp_path / 'processor2').mkdir()
    elif defect == 'time_mismatch':
        (tmp_path / 'processor1/1.0/uniform/time').write_text('value 2; name "1.0"; index 10; deltaT 0.01; deltaT0 0.01;')
    else:
        (tmp_path / 'processor1/1.0/U').write_text('' if defect == 'empty_field' else 'FoamFile { object U; }')
    assert inspect_checkpoint(tmp_path, processes=2, required_fields=['U', 'p'], min_age_seconds=0).status.value == 'failed'


def test_fresh_plan_never_overwrites_decomposition(tmp_path):
    from openfoam_cfd_agents.adapters.openfoam.local import LocalOpenFoamAdapter
    (tmp_path / 'processor0').mkdir()
    with pytest.raises(ValueError, match='decomposition'):
        LocalOpenFoamAdapter().build_run_plan(tmp_path, processes=2)


def test_resume_plan_preserves_decomposition_and_uses_exact_checkpoint(tmp_path):
    from openfoam_cfd_agents.adapters.openfoam.local import LocalOpenFoamAdapter
    make_checkpoint(tmp_path, '1.0')
    plan = LocalOpenFoamAdapter().build_run_plan(tmp_path, processes=2, restart_time='1.0',
                                               required_fields=['U', 'p'], checkpoint_min_age=0)
    assert len(plan.commands) == 2
    assert plan.commands[0].argv[0] == 'mpirun'
    assert '-time' not in plan.commands[0].argv  # foamRun does not provide a restart -time option.
    assert plan.restart_time == '1.0'
    assert 'startTime' in plan.required_control_dict
    assert 'decomposePar' not in [c.argv[0] for c in plan.commands]


def test_physical_core_overlap_includes_smt_siblings():
    from openfoam_cfd_agents.reliability.resources import validate_cpu_allocation, parse_cpu_topology
    topology = parse_cpu_topology('# CPU,Core,Socket,Node\n0,0,0,0\n1,1,0,0\n2,0,0,0\n3,1,0,0\n')
    assert validate_cpu_allocation([0], topology, reserved_cpus=[2]).status.value == 'failed'
    assert validate_cpu_allocation([0, 2], topology).status.value == 'failed'
    assert validate_cpu_allocation([0, 1], topology).status.value == 'passed'


def test_alive_process_with_unchanged_time_is_stalled_even_if_log_grows():
    from openfoam_cfd_agents.reliability.progress import ProgressState, observe_progress
    state = ProgressState(job_id='job1', latest_completed_time=1, last_advance_at=10, observed_at=10)
    result, new = observe_progress(state, job_id='job1', latest_completed_time=1,
                                  now=100, process_alive=True, stall_seconds=30)
    assert result.status.value == 'failed'
    assert new.last_advance_at == 10


def test_new_job_cannot_inherit_previous_job_progress():
    from openfoam_cfd_agents.reliability.progress import ProgressState, observe_progress
    state = ProgressState(job_id='job1', latest_completed_time=1, last_advance_at=10, observed_at=10)
    with pytest.raises(ValueError, match='job'):
        observe_progress(state, job_id='job2', latest_completed_time=2, now=100, process_alive=True)


def test_field_inventory_preserves_time_scheme_commas():
    from openfoam_cfd_agents.reliability.checkpoints import parse_field_list
    assert parse_field_list('["U", "CrankNicolson:ddt0(rho,U)"]') == ['U', 'CrankNicolson:ddt0(rho,U)']
