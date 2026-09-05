"""Local Foundation OpenFOAM v14 execution planning and preflight checks."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from openfoam_cfd_agents.domain import MetricRule, StageResult, evaluate_stage
from openfoam_cfd_agents.reliability.checkpoints import inspect_checkpoint


class CommandSpec(BaseModel):
    """One shell-free process invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    argv: list[str] = Field(min_length=1)
    cwd: str


class RunPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: str = "openfoam"
    version: str = "foundation-14"
    processes: int = Field(ge=1)
    commands: list[CommandSpec] = Field(min_length=1)
    restart_time: str | None = None
    required_fields: list[str] = Field(default_factory=list)
    required_control_dict: dict[str, str] = Field(default_factory=dict)
    shared_memory_mpi: bool = False


class ProcessResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    return_code: int
    stdout: str = ""
    stderr: str = ""


class SubprocessCommandRunner:
    """Execute one command without a shell and capture UTF-8 logs."""

    def __init__(self, *, timeout_seconds: float | None = None) -> None:
        self.timeout_seconds = timeout_seconds

    def __call__(self, command: CommandSpec) -> ProcessResult:
        completed = subprocess.run(
            command.argv,
            cwd=command.cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout_seconds,
        )
        return ProcessResult(
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class LocalOpenFoamAdapter:
    """Build v14 commands and prove the local runtime is ready before execution."""

    required_case_paths = (
        Path("0"),
        Path("constant"),
        Path("system"),
        Path("system/controlDict"),
        Path("system/fvSchemes"),
        Path("system/fvSolution"),
    )
    required_commands = ("foamRun", "blockMesh", "checkMesh")

    def __init__(self, *, application: str = "foamRun") -> None:
        if application != 'foamRun':
            raise ValueError('Foundation v14 adapter requires foamRun')
        self.application = application

    def preflight(
        self,
        case_path: Path,
        *,
        environment: Mapping[str, str] | None = None,
        executable_lookup: Callable[[str], str | None] = shutil.which,
    ) -> StageResult:
        case_path = case_path.resolve()
        env = os.environ if environment is None else environment
        missing_paths = [
            str(relative)
            for relative in self.required_case_paths
            if not (case_path / relative).exists()
        ]
        missing_commands = [
            command for command in self.required_commands if executable_lookup(command) is None
        ]
        version = env.get("WM_PROJECT_VERSION", "")
        version_compatible = version.strip() == '14'
        metrics: dict[str, object] = {
            "required_paths_present": int(not missing_paths),
            "environment_loaded": int(bool(env.get("WM_PROJECT_DIR"))),
            "version_compatible": int(version_compatible),
            "commands_available": int(not missing_commands),
            "detected_version": version,
            "missing_paths": missing_paths,
            "missing_commands": missing_commands,
        }
        return evaluate_stage(
            stage="openfoam_preflight",
            metrics=metrics,
            rules=[
                MetricRule(metric="required_paths_present", operator="==", threshold=1),
                MetricRule(metric="environment_loaded", operator="==", threshold=1),
                MetricRule(metric="version_compatible", operator="==", threshold=1),
                MetricRule(metric="commands_available", operator="==", threshold=1),
            ],
        )

    def build_run_plan(self, case_path: Path, *, processes: int = 1,
                       restart_time: str | None = None, required_fields: list[str] | None = None,
                       checkpoint_min_age: float = 30, shared_memory_mpi: bool = False) -> RunPlan:
        if processes < 1:
            raise ValueError("processes must be at least one")
        case_path = case_path.resolve()
        cwd = str(case_path)
        if shared_memory_mpi and processes == 1:
            raise ValueError('shared-memory MPI requires parallel execution')
        control = {}
        if restart_time is not None:
            checkpoint = inspect_checkpoint(case_path, processes=processes,
                                            required_fields=required_fields or [], time_name=restart_time,
                                            min_age_seconds=checkpoint_min_age)
            if checkpoint.status.value != 'passed':
                raise ValueError('checkpoint rejected: ' + checkpoint.model_dump_json())
            control = {'startFrom': 'startTime', 'startTime': restart_time}
        elif any(re.fullmatch(r'processors?\d+(?:_.*)?', p.name) for p in case_path.iterdir()):
            raise ValueError('existing decomposition: select a verified restart or a fresh case directory')
        if processes == 1:
            commands = [CommandSpec(argv=[self.application, "-case", cwd], cwd=cwd)]
        else:
            transport = ['--host', f'localhost:{processes}', '--mca', 'pml', 'ob1', '--mca', 'btl', 'self,vader'] if shared_memory_mpi else []
            commands = [
                CommandSpec(argv=["decomposePar", "-case", cwd], cwd=cwd),
                CommandSpec(
                    argv=[
                        "mpirun",
                        *transport,
                        "-np",
                        str(processes),
                        self.application,
                        "-parallel",
                        "-case",
                        cwd,
                    ],
                    cwd=cwd,
                ),
                CommandSpec(
                    argv=["reconstructPar", "-case", cwd, "-latestTime"],
                    cwd=cwd,
                ),
            ]
            if restart_time is not None:
                commands = commands[1:]
        return RunPlan(processes=processes, commands=commands, restart_time=restart_time,
                       required_fields=required_fields or [], required_control_dict=control,
                       shared_memory_mpi=shared_memory_mpi)

    def execute_plan(
        self,
        plan: RunPlan,
        *,
        log_dir: Path,
        runner: Callable[[CommandSpec], ProcessResult] | None = None,
    ) -> StageResult:
        """Execute commands in order, stopping at the first non-zero return code."""

        case_path = Path(plan.commands[0].cwd)
        if plan.restart_time is not None:
            checkpoint = inspect_checkpoint(case_path, processes=plan.processes,
                                            required_fields=plan.required_fields, time_name=plan.restart_time)
            if checkpoint.status.value != 'passed':
                raise ValueError('checkpoint changed or remains too recent; recheck stopped writers')
            text = (case_path / 'system/controlDict').read_text(encoding='utf-8')
            text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
            if '#' in text or '$' in text:
                raise ValueError('restart execution requires explicit control entries; expanded/dynamic dictionaries need review')
            for key, expected in plan.required_control_dict.items():
                values = re.findall(r'\b' + re.escape(key) + r'\s+([^;{}]+);', text)
                if len(values) != 1:
                    raise ValueError(f'controlDict requires exactly one explicit {key}')
                value = values[0].strip()
                equal = value == expected if key != 'startTime' else float(value) == float(expected)
                if not equal:
                    raise ValueError(f'controlDict {key} must be {expected} before restart')
        if plan.shared_memory_mpi:
            version = subprocess.run(['mpirun', '--version'], check=True, capture_output=True, text=True).stdout
            if not re.search(r'Open MPI\)?\s+4\.', version):
                raise ValueError('self,vader transport profile requires Open MPI 4.x on one host')
        log_dir.mkdir(parents=True, exist_ok=True)
        if any(log_dir.iterdir()):
            raise FileExistsError('log directory is not empty; use a new directory for every attempt')
        artifacts: list[str] = []
        attempted = 0
        succeeded = 0
        last_return_code = 0
        for index, command in enumerate(plan.commands, start=1):
            attempted += 1
            log_path = (log_dir / f"{index:02d}-{Path(command.argv[0]).name}.log").resolve()
            try:
                if runner is not None:
                    process = runner(command)
                else:
                    with log_path.open('x', encoding='utf-8') as log:
                        log.write(f'argv: {json.dumps(command.argv, ensure_ascii=False)}\n')
                        log.flush()
                        completed = subprocess.run(command.argv, cwd=command.cwd, check=False,
                                                   stdout=log, stderr=subprocess.STDOUT)
                        log.write(f'\nreturn_code: {completed.returncode}\n')
                    process = ProcessResult(return_code=completed.returncode)
            except Exception as exc:
                process = ProcessResult(
                    return_code=1,
                    stderr=f"{type(exc).__name__}: {exc}",
                )
            last_return_code = process.return_code
            with log_path.open('a' if runner is None and log_path.exists() else 'x', encoding='utf-8') as log:
                log.write("\n".join([
                    f"argv: {json.dumps(command.argv, ensure_ascii=False)}",
                    f"return_code: {process.return_code}",
                    "stdout:", process.stdout, "stderr:", process.stderr,
                ]))
            artifacts.append(str(log_path))
            if process.return_code != 0:
                break
            succeeded += 1

        metrics = {
            "commands_planned": len(plan.commands),
            "commands_attempted": attempted,
            "commands_succeeded": succeeded,
            "last_return_code": last_return_code,
            "all_commands_succeeded": int(succeeded == len(plan.commands)),
            "processes": plan.processes,
        }
        return evaluate_stage(
            stage="openfoam_execution",
            metrics=metrics,
            rules=[
                MetricRule(metric="all_commands_succeeded", operator="==", threshold=1),
                MetricRule(metric="last_return_code", operator="==", threshold=0),
            ],
            artifacts=artifacts,
        )
