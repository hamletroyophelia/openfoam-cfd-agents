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
        version_compatible = bool(re.search(r"(?:^|\D)14(?:$|\D)", version))
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

    def build_run_plan(self, case_path: Path, *, processes: int = 1) -> RunPlan:
        if processes < 1:
            raise ValueError("processes must be at least one")
        case_path = case_path.resolve()
        cwd = str(case_path)
        if processes == 1:
            commands = [CommandSpec(argv=[self.application, "-case", cwd], cwd=cwd)]
        else:
            commands = [
                CommandSpec(argv=["decomposePar", "-case", cwd, "-force"], cwd=cwd),
                CommandSpec(
                    argv=[
                        "mpirun",
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
        return RunPlan(processes=processes, commands=commands)

    def execute_plan(
        self,
        plan: RunPlan,
        *,
        log_dir: Path,
        runner: Callable[[CommandSpec], ProcessResult] | None = None,
    ) -> StageResult:
        """Execute commands in order, stopping at the first non-zero return code."""

        run_command = runner or SubprocessCommandRunner()
        log_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[str] = []
        attempted = 0
        succeeded = 0
        last_return_code = 0
        for index, command in enumerate(plan.commands, start=1):
            attempted += 1
            try:
                process = run_command(command)
            except Exception as exc:
                process = ProcessResult(
                    return_code=1,
                    stderr=f"{type(exc).__name__}: {exc}",
                )
            last_return_code = process.return_code
            log_path = (log_dir / f"{index:02d}-{command.argv[0]}.log").resolve()
            log_path.write_text(
                "\n".join(
                    [
                        f"argv: {json.dumps(command.argv, ensure_ascii=False)}",
                        f"return_code: {process.return_code}",
                        "stdout:",
                        process.stdout,
                        "stderr:",
                        process.stderr,
                    ]
                ),
                encoding="utf-8",
            )
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
