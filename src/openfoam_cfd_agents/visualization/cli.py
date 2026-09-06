from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .config import load_visualization_config
from .inventory import inspect_decomposed_time

app = typer.Typer(no_args_is_help=True, help='Audit, prepare and plot reproducible CFD visualizations.')


@app.command('prepare')
def prepare(config: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
            output: Annotated[Path, typer.Option()]):
    """Validate viz.yaml and write JSON for a dependency-minimal pvbatch script."""
    value = load_visualization_config(config)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(value.model_dump_json(indent=2), encoding='utf-8')
    typer.echo(str(output))


@app.command('audit')
def audit(case: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
          config: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
          output: Annotated[Path, typer.Option()],
          safety_age_seconds: Annotated[float, typer.Option(min=0)] = 30):
    result = inspect_decomposed_time(case, load_visualization_config(config),
                                     safety_age_seconds=safety_age_seconds)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    typer.echo(str(output))


@app.command('plot-cd')
def plot_cd(config: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
            segments: Annotated[Path, typer.Argument(exists=True, dir_okay=False,
                help='JSON list of {path,start_inclusive,stop_exclusive}')],
            output_dir: Annotated[Path, typer.Option()],
            style: Annotated[Path | None, typer.Option()] = None):
    from .plotting import plot_cd_history
    rules = json.loads(segments.read_text(encoding='utf-8'))
    parsed = [(Path(item['path']), item.get('start_inclusive'), item.get('stop_exclusive')) for item in rules]
    result = plot_cd_history(load_visualization_config(config), parsed, output_dir, style=style)
    typer.echo(json.dumps(result, indent=2))
