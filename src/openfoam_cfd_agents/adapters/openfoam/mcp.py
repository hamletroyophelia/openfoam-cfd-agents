"""Thin port adapter for the milsonson/openfoam-mcp execution service."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any


ToolCaller = Callable[[str, dict[str, object]], Awaitable[Any]]


class OpenFoamMcpAdapter:
    """Translate workflow operations to explicit openfoam-mcp tool contracts."""

    def __init__(self, call_tool: ToolCaller) -> None:
        self._call_tool = call_tool

    async def _invoke(self, tool: str, params: dict[str, object]) -> Any:
        return await self._call_tool(tool, {"params": params})

    async def preflight(self, case_path: Path, *, profile: str = "solver") -> Any:
        return await self._invoke(
            "openfoam_preflight_check",
            {"case_path": str(case_path.resolve()), "profile": profile},
        )

    async def validate_case(self, case_path: Path) -> Any:
        return await self._invoke(
            "openfoam_validate_case",
            {"case_path": str(case_path.resolve())},
        )

    async def run(self, case_path: Path, *, processes: int = 1) -> Any:
        tool = "openfoam_run_solver" if processes == 1 else "openfoam_run_parallel"
        params: dict[str, object] = {"case_path": str(case_path.resolve())}
        if processes > 1:
            params["n_processors"] = processes
        return await self._invoke(tool, params)

    async def status(self, case_path: Path) -> Any:
        return await self._invoke(
            "openfoam_get_run_status",
            {"case_path": str(case_path.resolve())},
        )
