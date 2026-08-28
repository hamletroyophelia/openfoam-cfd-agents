from __future__ import annotations

import asyncio
from pathlib import Path

from openfoam_cfd_agents.adapters.openfoam.foam_agent_mcp import FoamAgentMcpAdapter


def test_foam_agent_adapter_preserves_upstream_request_envelopes(tmp_path: Path) -> None:
    """Changing request to params would break Foam-Agent's FastMCP model binding."""

    calls: list[tuple[str, dict[str, object]]] = []

    async def call_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
        calls.append((name, arguments))
        return {"tool": name}

    adapter = FoamAgentMcpAdapter(call_tool)
    plan = {
        "case_name": "cavity",
        "case_solver": "icoFoam",
        "case_domain": "incompressible",
        "case_category": "laminar",
        "subtasks": [{"file": "controlDict", "folder": "system"}],
    }
    case_dir = (tmp_path / "cavity").resolve()

    async def exercise() -> None:
        await adapter.plan("Lid-driven cavity at Re=1000")
        await adapter.generate_case(plan, user_requirement="Lid-driven cavity at Re=1000")
        await adapter.run(case_dir, timeout=600)
        await adapter.review(case_dir, ["FOAM FATAL ERROR"], "Lid-driven cavity at Re=1000")
        await adapter.apply_fixes(
            case_dir,
            ["FOAM FATAL ERROR"],
            "Correct the pressure boundary condition.",
            "Lid-driven cavity at Re=1000",
        )
        await adapter.visualize(
            case_dir,
            quantity="velocity",
            visualization_type="pyvista",
        )

    asyncio.run(exercise())

    assert calls == [
        (
            "plan",
            {"request": {"user_requirement": "Lid-driven cavity at Re=1000"}},
        ),
        (
            "input_writer",
            {
                "request": {
                    "case_name": "cavity",
                    "subtasks": [{"file": "controlDict", "folder": "system"}],
                    "user_requirement": "Lid-driven cavity at Re=1000",
                    "case_solver": "icoFoam",
                    "case_domain": "incompressible",
                    "case_category": "laminar",
                }
            },
        ),
        (
            "run",
            {"request": {"case_dir": str(case_dir), "timeout": 600}},
        ),
        (
            "review",
            {
                "request": {
                    "case_dir": str(case_dir),
                    "errors": ["FOAM FATAL ERROR"],
                    "user_requirement": "Lid-driven cavity at Re=1000",
                }
            },
        ),
        (
            "apply_fixes",
            {
                "request": {
                    "case_dir": str(case_dir),
                    "error_logs": ["FOAM FATAL ERROR"],
                    "review_analysis": "Correct the pressure boundary condition.",
                    "user_requirement": "Lid-driven cavity at Re=1000",
                }
            },
        ),
        (
            "visualization",
            {
                "request": {
                    "case_dir": str(case_dir),
                    "quantity": "velocity",
                    "visualization_type": "pyvista",
                }
            },
        ),
    ]


def test_foam_agent_adapter_rejects_incomplete_planner_output() -> None:
    """Passing an incomplete plan downstream would produce a malformed case request."""

    async def call_tool(_name: str, _arguments: dict[str, object]) -> dict[str, object]:
        raise AssertionError("the MCP tool must not be called for an invalid plan")

    adapter = FoamAgentMcpAdapter(call_tool)

    async def exercise() -> None:
        await adapter.generate_case(
            {"case_name": "missing-metadata"},
            user_requirement="Create a complete case",
        )

    try:
        asyncio.run(exercise())
    except ValueError as exc:
        assert "case_solver" in str(exc)
    else:
        raise AssertionError("incomplete planner output was accepted")
