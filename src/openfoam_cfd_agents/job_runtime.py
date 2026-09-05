"""Foreground job payload for a systemd service, never a self-daemonizing solver."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from openfoam_cfd_agents.adapters.openfoam.local import LocalOpenFoamAdapter, RunPlan


class ExecutionSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)

    case_path: str
    revision: str = Field(min_length=1)
    plan: RunPlan
    kind: Literal['openfoam', 'process'] = 'openfoam'
    environment: dict[str, str] = Field(default_factory=dict)
    min_free_bytes: int = Field(default=100_000_000, ge=0)
    max_runtime_seconds: float = Field(default=86400, gt=0)

    @model_validator(mode='after')
    def same_case(self):
        root = Path(self.case_path).resolve()
        if any(Path(command.cwd).resolve() != root for command in self.plan.commands):
            raise ValueError('every command must use the submitted case directory')
        if any('\x00' in value for command in self.plan.commands for value in command.argv):
            raise ValueError('argv contains NUL')
        return self


def assert_no_external_writer(case_path: Path):
    """Check common OpenFOAM writers outside this job before touching case data."""
    writers = {'foamRun', 'mpirun', 'decomposePar', 'reconstructPar', 'blockMesh', 'snappyHexMesh'}
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            argv = (process / 'cmdline').read_bytes().decode(errors='replace').split('\x00')
            if not argv or Path(argv[0]).name not in writers:
                continue
            cwd = (process / 'cwd').resolve(strict=True)
            target = cwd
            if '-case' in argv and argv.index('-case') + 1 < len(argv):
                target = (cwd / argv[argv.index('-case') + 1]).resolve()
            if target == case_path:
                raise RuntimeError(f'external OpenFOAM writer exists: PID {process.name}')
        except (FileNotFoundError, ProcessLookupError):
            continue
        # Permission failures are not evidence that a case is idle.


def execute(spec: ExecutionSpec, directory: Path) -> int:
    import fcntl
    case = Path(spec.case_path).resolve(strict=True)
    with (case / '.cfd-agent.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert_no_external_writer(case)
        if shutil.disk_usage(case).free < spec.min_free_bytes:
            raise RuntimeError('insufficient free bytes on the case filesystem')
        os.environ.update(spec.environment)
        adapter = LocalOpenFoamAdapter()
        if spec.kind == 'openfoam':
            preflight = adapter.preflight(case)
            (directory / 'preflight.json').write_text(preflight.model_dump_json(indent=2), encoding='utf-8')
            if preflight.status.value != 'passed':
                return 2
        result = adapter.execute_plan(spec.plan, log_dir=directory / 'logs')
        (directory / 'execution.json').write_text(result.model_dump_json(indent=2), encoding='utf-8')
        # This is execution status only; no numerical or scientific acceptance is implied.
        return 0 if result.status.value == 'passed' else 1


def main() -> int:
    path = Path(sys.argv[1])
    spec = ExecutionSpec.model_validate_json(path.read_text(encoding='utf-8'))
    try:
        return execute(spec, path.parent)
    except Exception as exc:
        (path.parent / 'runtime-error.json').write_text(
            json.dumps({'type': type(exc).__name__, 'message': str(exc)}), encoding='utf-8')
        raise


if __name__ == '__main__':
    raise SystemExit(main())
