import json
import math

import pytest
from pydantic import ValidationError

from openfoam_cfd_agents.domain import MetricRule, StageResult, evaluate_stage
from openfoam_cfd_agents.agents.monitor import MonitorAgent, MonitorThresholds, parse_solver_log
from openfoam_cfd_agents.agents.verification import MeshStudyPoint, VerificationAgent


@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize('operator', ['<', '<=', '>', '>=', '==', '!='])
def test_nonfinite_observations_fail_and_remain_strict_json(value, operator):
    result = evaluate_stage(stage='test', metrics={'q': value, 'nested': [value]},
                            rules=[MetricRule(metric='q', operator=operator, threshold=0)])
    assert result.status.value == 'failed'
    assert result.checks[0].observed is None
    assert 'finite' in result.checks[0].message
    assert result.invalid_metric_paths
    json.dumps(result.model_dump(mode='json'), allow_nan=False)
    assert StageResult.model_validate_json(result.model_dump_json()).invalid_metric_paths


@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf, True, '0.1'])
def test_invalid_threshold_is_rejected(value):
    with pytest.raises(ValidationError):
        MetricRule(metric='q', operator='!=', threshold=value)


def test_old_stage_result_is_readable_as_v2():
    old = {'stage': 'old', 'status': 'failed', 'metrics': {}, 'checks': []}
    assert StageResult.model_validate(old).schema_version == 2


def log_step(time='0.1', co='0.8', residual='1e-8'):
    return f'''Courant Number mean: 0.01 max: {co}
Interface Courant Number mean: 0.001 max: 0.3
Time = {time}s
smoothSolver: Solving for U, Initial residual = 0.01, Final residual = {residual}, No Iterations 2
Phase-1 volume fraction = 0.66 Min(alpha.water) = -1e-30 Max(alpha.water) = 1.000001
time step continuity errors : sum local = 1e-9, global = -1e-10, cumulative = 2e-8
ExecutionTime = 1 s ClockTime = 1 s
'''


def test_v14_units_and_interface_co_are_separate():
    summary = parse_solver_log(log_step() + log_step('0.2'))
    assert summary.times == [0.1, 0.2]
    assert summary.courant_maxima == [0.8, 0.8]
    assert summary.interface_courant_maxima == [0.3, 0.3]
    assert summary.completed_times == [0.1, 0.2]


@pytest.mark.parametrize('marker', ['Connection reset by peer (104)', 'mca_btl_tcp_recv_blocking',
                                    'Floating point exception', 'MPI_ABORT'])
def test_transport_and_runtime_errors_override_good_numerics(marker):
    result = MonitorAgent().evaluate_text(log_step() + log_step('0.2') + marker)
    assert result.status.value == 'failed'


@pytest.mark.parametrize('bad', ['nan', '-nan', '+Inf', '1e999'])
def test_monitor_cannot_hide_nonfinite_samples_behind_good_samples(bad):
    result = MonitorAgent().evaluate_text(log_step(co=bad) + log_step('0.2'))
    assert result.status.value == 'failed'
    assert result.metrics['nonfinite_samples'] > 0


def test_repeated_time_is_not_progress_and_last_started_step_is_not_complete():
    result = MonitorAgent().evaluate_text(log_step() * 3)
    assert result.status.value == 'failed'
    summary = parse_solver_log(log_step() + 'Time = 0.2s\n')
    assert summary.completed_times == [0.1]


def test_vof_thresholds_are_explicit_and_missing_phase_data_fails():
    thresholds = MonitorThresholds(max_interface_courant=0.55, alpha_tolerance=2e-6)
    assert MonitorAgent(thresholds).evaluate_text(log_step() + log_step('0.2')).status.value == 'passed'
    result = MonitorAgent(thresholds).evaluate_text((log_step() + log_step('0.2')).replace('1.000001', '1.1'))
    assert result.status.value == 'failed'


@pytest.mark.parametrize('values', [[1, 1.1, 1.05], [1, 1, 1], [1, 1.2, 1.3]])
def test_inapplicable_gci_is_inconclusive_and_has_no_recommendation(values):
    points = [MeshStudyPoint(label=label, cells=cells, value=value)
              for label, cells, value in zip(['fine', 'medium', 'coarse'], [8000, 1000, 125], values)]
    result = VerificationAgent().evaluate_mesh_study(points)
    assert result.status.value == 'inconclusive'
    assert 'recommended_level' not in result.metrics


def test_failed_gci_does_not_recommend_a_mesh():
    points = [MeshStudyPoint(label=str(c), cells=c, value=v)
              for c, v in [(8000, 1.0), (1000, 1.04), (125, 1.12)]]
    result = VerificationAgent(gci_limit=0.001).evaluate_mesh_study(points)
    assert result.status.value == 'failed'
    assert 'recommended_level' not in result.metrics


def test_residual_gate_uses_last_field_solve_in_each_completed_step():
    inner = 'GAMG: Solving for U, Initial residual = 0.4, Final residual = 0.1, No Iterations 1\n'
    good = (log_step() + log_step('0.2')).replace('smoothSolver:', inner + 'smoothSolver:')
    assert MonitorAgent().evaluate_text(good).status.value == 'passed'
    bad = good.replace('Final residual = 1e-8', 'Final residual = 0.1')
    assert MonitorAgent().evaluate_text(bad).status.value == 'failed'
