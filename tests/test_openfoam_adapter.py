from __future__ import annotations

import asyncio
import importlib
from pathlib import Path


def _local_module():
    try:
        return importlib.import_module("openfoam_cfd_agents.adapters.openfoam.local")
    except ModuleNotFoundError as exc:
        raise AssertionError("local OpenFOAM adapter is missing") from exc


def _mcp_module():
    try:
        return importlib.import_module("openfoam_cfd_agents.adapters.openfoam.mcp")
    except ModuleNotFoundError as exc:
        raise AssertionError("openfoam-mcp adapter is missing") from exc


def _make_case(root: Path) -> Path:
    for directory in ("0", "constant", "system"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    for filename in ("controlDict", "fvSchemes", "fvSolution"):
        (root / "system" / filename).write_text("FoamFile {}\n", encoding="utf-8")
    return root


def test_foundation_v14_preflight_checks_case_environment_and_commands(tmp_path: Path) -> None:
    local = _local_module()
    case_path = _make_case(tmp_path / "case with spaces")
    available = {"foamRun", "blockMesh", "checkMesh"}

    result = local.LocalOpenFoamAdapter().preflight(
        case_path,
        environment={"WM_PROJECT_DIR": "/opt/openfoam14", "WM_PROJECT_VERSION": "14"},
        executable_lookup=lambda name: f"/opt/openfoam14/bin/{name}" if name in available else None,
    )

    assert result.status.value == "passed"
    assert result.metrics["version_compatible"] == 1


def test_parallel_plan_uses_argument_lists_and_foamrun_for_v14(tmp_path: Path) -> None:
    local = _local_module()
    case_path = _make_case(tmp_path / "case with spaces").resolve()

    plan = local.LocalOpenFoamAdapter().build_run_plan(case_path, processes=4)

    assert plan.commands[0].argv == ["decomposePar", "-case", str(case_path)]
    assert plan.commands[1].argv == [
        "mpirun",
        "-np",
        "4",
        "foamRun",
        "-parallel",
        "-case",
        str(case_path),
    ]
    assert plan.commands[2].argv[0] == "reconstructPar"


def test_mcp_adapter_maps_workflow_operations_to_openfoam_mcp_tools(tmp_path: Path) -> None:
    mcp = _mcp_module()
    calls: list[tuple[str, dict[str, object]]] = []

    async def call_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
        calls.append((name, arguments))
        return {"status": "ready"}

    adapter = mcp.OpenFoamMcpAdapter(call_tool)
    response = asyncio.run(adapter.preflight(tmp_path, profile="parallel"))

    assert response == {"status": "ready"}
    assert calls == [
        (
            "openfoam_preflight_check",
            {"params": {"case_path": str(tmp_path.resolve()), "profile": "parallel"}},
        )
    ]


def test_execute_plan_stops_on_first_failed_process_and_persists_logs(tmp_path: Path) -> None:
    local = _local_module()
    case_path = _make_case(tmp_path / "case")
    plan = local.LocalOpenFoamAdapter().build_run_plan(case_path, processes=4)
    seen: list[str] = []

    def runner(command):
        seen.append(command.argv[0])
        return_code = 7 if command.argv[0] == "mpirun" else 0
        return local.ProcessResult(
            return_code=return_code,
            stdout=f"ran {command.argv[0]}",
            stderr="parallel failed" if return_code else "",
        )

    result = local.LocalOpenFoamAdapter().execute_plan(
        plan,
        log_dir=tmp_path / "logs",
        runner=runner,
    )

    assert result.status.value == "failed"
    assert seen == ["decomposePar", "mpirun"]
    assert result.metrics["commands_attempted"] == 2
    assert result.metrics["commands_succeeded"] == 1
    assert len(result.artifacts) == 2
    assert "parallel failed" in Path(result.artifacts[1]).read_text(encoding="utf-8")
