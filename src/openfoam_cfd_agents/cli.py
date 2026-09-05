"""Command-line entry points for deterministic workflow tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from openfoam_cfd_agents.adapters.openfoam.local import LocalOpenFoamAdapter
from openfoam_cfd_agents.agents.monitor import MonitorAgent, MonitorThresholds
from openfoam_cfd_agents.agents.report import ReportAgent
from openfoam_cfd_agents.agents.supervisor import WorkflowManifest
from openfoam_cfd_agents.agents.verification import MeshStudyPoint, VerificationAgent
from openfoam_cfd_agents.config import load_config
from openfoam_cfd_agents.domain import StageStatus
from openfoam_cfd_agents.reliability.cli import register
from openfoam_cfd_agents.reliability.checkpoints import parse_field_list
from openfoam_cfd_agents.job_cli import app as job_app


app = typer.Typer(
    name="cfd-workflow",
    help="Auditable Foundation OpenFOAM v14 workflow utilities.",
    no_args_is_help=True,
)
register(app)
app.add_typer(job_app, name='jobs')


def _write_json(payload: object, output: Path | None) -> None:
    text = (
        payload.model_dump_json(indent=2)
        if hasattr(payload, "model_dump_json")
        else json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    )
    if output is None:
        typer.echo(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    typer.echo(str(output))


@app.command("validate-config")
def validate_config_command(
    config: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Validate YAML and print its normalized representation."""

    typer.echo(load_config(config).model_dump_json(indent=2))


@app.command()
def monitor(
    log_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    max_courant: Annotated[float, typer.Option()] = 1.0,
    max_continuity_error: Annotated[float, typer.Option()] = 1e-6,
    max_final_residual: Annotated[float, typer.Option()] = 1e-3,
    min_time_steps: Annotated[int, typer.Option(min=2)] = 2,
    max_interface_courant: Annotated[float | None, typer.Option()] = None,
    alpha_tolerance: Annotated[float | None, typer.Option()] = None,
) -> None:
    """Parse a solver log and apply deterministic run-health gates."""

    thresholds = MonitorThresholds(
        max_courant=max_courant,
        max_abs_cumulative_continuity_error=max_continuity_error,
        max_final_residual=max_final_residual,
        min_time_steps=min_time_steps,
        max_interface_courant=max_interface_courant,
        alpha_tolerance=alpha_tolerance,
    )
    result = MonitorAgent(thresholds).evaluate_file(log_path.resolve())
    _write_json(result, output)
    if result.status is not StageStatus.PASSED:
        raise typer.Exit(code=2)


@app.command("verify-mesh")
def verify_mesh(
    study: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Calculate Richardson extrapolation and GCI from a three-level YAML study."""

    raw = yaml.safe_load(study.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("points"), list):
        raise typer.BadParameter("study YAML must contain a 'points' list")
    points = [MeshStudyPoint.model_validate(item) for item in raw["points"]]
    result = VerificationAgent(gci_limit=float(raw.get("gci_limit", 0.02))).evaluate_mesh_study(
        points,
        dimension=int(raw.get("dimension", 3)),
        artifact=str(study.resolve()),
    )
    _write_json(result, output)
    if result.status is not StageStatus.PASSED:
        raise typer.Exit(code=2)


@app.command("plan-run")
def plan_run(
    case_path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    processes: Annotated[int, typer.Option(min=1)] = 1,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    restart_time: Annotated[str | None, typer.Option()] = None,
    fields: Annotated[str, typer.Option(help='Required checkpoint fields for a restart')] = '',
    shared_memory_mpi: Annotated[bool, typer.Option(help='Single-host Open MPI 4.x self,vader transport')] = False,
) -> None:
    """Create a shell-free serial or MPI command plan without executing it."""

    plan = LocalOpenFoamAdapter().build_run_plan(case_path, processes=processes, restart_time=restart_time,
                                                required_fields=parse_field_list(fields) if fields else [],
                                                shared_memory_mpi=shared_memory_mpi)
    _write_json(plan, output)


@app.command("render-report")
def render_report(
    manifest_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")],
) -> None:
    """Render a Markdown report from a persisted workflow manifest."""

    manifest = WorkflowManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    ReportAgent().write_markdown(manifest, output)
    typer.echo(str(output))


if __name__ == "__main__":
    app()
