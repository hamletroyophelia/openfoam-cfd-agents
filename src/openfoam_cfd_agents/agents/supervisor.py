"""Workflow orchestration with explicit gates, approvals, and failure stops."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from openfoam_cfd_agents.domain import MetricRule, StageResult, StageStatus, evaluate_stage


StageRunner = Callable[[], StageResult]
ApprovalCallback = Callable[[StageResult], bool]


@dataclass(frozen=True, slots=True)
class StageTask:
    name: str
    execute: StageRunner
    requires_approval: bool = False


class WorkflowManifest(BaseModel):
    """Auditable state for one supervisor run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    status: StageStatus
    stages: list[StageResult] = Field(default_factory=list)
    stopped_after: str | None = None

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)


class SupervisorAgent:
    """Run ordered tasks and stop whenever a deterministic gate disallows progress."""

    def run(
        self,
        tasks: Sequence[StageTask],
        *,
        run_id: str | None = None,
        approve: ApprovalCallback | None = None,
    ) -> WorkflowManifest:
        manifest = WorkflowManifest(
            run_id=run_id or uuid4().hex,
            status=StageStatus.RUNNING,
        )
        for task in tasks:
            try:
                result = task.execute()
            except Exception as exc:
                result = evaluate_stage(
                    stage=task.name,
                    metrics={"stage_exception": 1, "exception_type": type(exc).__name__},
                    rules=[MetricRule(metric="stage_exception", operator="==", threshold=0)],
                )
            if result.stage != task.name:
                raise ValueError(
                    f"stage task '{task.name}' returned result for '{result.stage}'"
                )
            manifest.stages.append(result)

            if result.status is not StageStatus.PASSED:
                manifest.status = StageStatus.FAILED
                manifest.stopped_after = task.name
                return manifest

            if task.requires_approval:
                if approve is None:
                    manifest.status = StageStatus.APPROVAL_REQUIRED
                    manifest.stopped_after = task.name
                    return manifest
                if not approve(result):
                    manifest.status = StageStatus.BLOCKED
                    manifest.stopped_after = task.name
                    return manifest

        manifest.status = StageStatus.PASSED
        return manifest
