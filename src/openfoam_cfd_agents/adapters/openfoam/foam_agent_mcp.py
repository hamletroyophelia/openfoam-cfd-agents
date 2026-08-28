"""Port adapter for the csml-rpi/Foam-Agent MCP service."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from openfoam_cfd_agents.adapters.openfoam.mcp import ToolCaller


class FoamAgentMcpAdapter:
    """Map planning and repair operations to Foam-Agent's MCP contracts."""

    _plan_fields = (
        "case_name",
        "subtasks",
        "case_solver",
        "case_domain",
        "case_category",
    )

    def __init__(self, call_tool: ToolCaller) -> None:
        self._call_tool = call_tool

    async def _invoke(self, tool: str, request: dict[str, object]) -> Any:
        return await self._call_tool(tool, {"request": request})

    async def plan(self, user_requirement: str) -> Any:
        return await self._invoke("plan", {"user_requirement": user_requirement})

    async def generate_case(
        self,
        plan: Mapping[str, Any],
        *,
        user_requirement: str,
    ) -> Any:
        missing = [field for field in self._plan_fields if field not in plan]
        if missing:
            raise ValueError(
                "planner output is missing required fields: " + ", ".join(missing)
            )
        return await self._invoke(
            "input_writer",
            {
                "case_name": plan["case_name"],
                "subtasks": plan["subtasks"],
                "user_requirement": user_requirement,
                "case_solver": plan["case_solver"],
                "case_domain": plan["case_domain"],
                "case_category": plan["case_category"],
            },
        )

    async def run(self, case_dir: Path, *, timeout: int = 3600) -> Any:
        return await self._invoke(
            "run",
            {"case_dir": str(case_dir.resolve()), "timeout": timeout},
        )

    async def review(
        self,
        case_dir: Path,
        errors: Sequence[str],
        user_requirement: str,
    ) -> Any:
        return await self._invoke(
            "review",
            {
                "case_dir": str(case_dir.resolve()),
                "errors": list(errors),
                "user_requirement": user_requirement,
            },
        )

    async def apply_fixes(
        self,
        case_dir: Path,
        error_logs: Sequence[str],
        review_analysis: str,
        user_requirement: str,
    ) -> Any:
        return await self._invoke(
            "apply_fixes",
            {
                "case_dir": str(case_dir.resolve()),
                "error_logs": list(error_logs),
                "review_analysis": review_analysis,
                "user_requirement": user_requirement,
            },
        )

    async def visualize(
        self,
        case_dir: Path,
        *,
        quantity: str = "velocity",
        visualization_type: str = "pyvista",
    ) -> Any:
        return await self._invoke(
            "visualization",
            {
                "case_dir": str(case_dir.resolve()),
                "quantity": quantity,
                "visualization_type": visualization_type,
            },
        )
