import json

from typer.testing import CliRunner

from openfoam_cfd_agents.cli import app
from test_reliability_gates import log_step


def test_live_cli_waits_for_progress_and_keeps_transport_error_sticky(tmp_path, monkeypatch):
    import openfoam_cfd_agents.reliability.cli as live
    monkeypatch.setattr(live, 'linux_process_identity', lambda _: 'boot:10:100')
    clock = [10]
    monkeypatch.setattr(live.time, 'time', lambda: clock[0])
    log = tmp_path / 'solver.log'
    state = tmp_path / 'state.json'
    log.write_text(log_step() + log_step('0.2'))
    args = ['live-monitor', str(log), '--pid', '10', '--job-id', 'test', '--state', str(state)]
    runner = CliRunner()
    assert runner.invoke(app, args).exit_code == 2
    clock[0] = 20
    log.write_text(log_step() + log_step('0.2') + log_step('0.3'))
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    clock[0] = 30
    log.write_text(log.read_text() + 'Connection reset by peer (104)\n')
    assert runner.invoke(app, args).exit_code == 2
    clock[0] = 40
    log.write_text(log_step() + log_step('0.5'))
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert json.loads(result.output)['metrics']['error_seen'] == 1


def test_pid_reuse_and_job_reuse_leave_previous_state_untouched(tmp_path, monkeypatch):
    import openfoam_cfd_agents.reliability.cli as live
    monkeypatch.setattr(live, 'linux_process_identity', lambda _: 'boot:10:100')
    log = tmp_path / 'solver.log'
    state = tmp_path / 'state.json'
    log.write_text(log_step() + log_step('0.2'))
    args = ['live-monitor', str(log), '--pid', '10', '--job-id', 'test', '--state', str(state)]
    runner = CliRunner()
    assert runner.invoke(app, args).exit_code == 2
    saved = state.read_bytes()
    monkeypatch.setattr(live, 'linux_process_identity', lambda _: 'boot:10:999')
    assert runner.invoke(app, args).exit_code == 2
    assert state.read_bytes() == saved


def test_supervisor_rejects_claimed_pass_with_no_checks():
    from openfoam_cfd_agents.agents.supervisor import SupervisorAgent, StageTask
    from openfoam_cfd_agents.domain import StageResult
    manifest = SupervisorAgent().run([StageTask('fake', lambda: StageResult(stage='fake', status='passed'))])
    assert manifest.status.value == 'failed'


def test_checkpoint_cli_reports_failure_as_json(tmp_path):
    result = CliRunner().invoke(app, ['checkpoint', str(tmp_path), '--processes', '2', '--fields', 'U,p'])
    assert result.exit_code == 2
    assert json.loads(result.output)['status'] == 'failed'
