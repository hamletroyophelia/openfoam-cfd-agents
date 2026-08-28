"""Markdown reporting from persisted machine results."""

from __future__ import annotations

from pathlib import Path

from openfoam_cfd_agents.agents.supervisor import WorkflowManifest


class ReportAgent:
    """Present workflow evidence without changing any stage decision."""

    def render_markdown(self, manifest: WorkflowManifest) -> str:
        lines = [
            f"# CFD Workflow Report: {manifest.run_id}",
            "",
            f"Overall status: **{manifest.status.value}**",
            "",
            "## Stage summary",
            "",
            "| Stage | Status | Artifacts |",
            "| --- | --- | --- |",
        ]
        for stage in manifest.stages:
            artifacts = "<br>".join(stage.artifacts) if stage.artifacts else "-"
            lines.append(f"| {stage.stage} | {stage.status.value} | {artifacts} |")

        for stage in manifest.stages:
            lines.extend(["", f"## {stage.stage}", "", stage.message or "-"])
            if stage.metrics:
                lines.extend(["", "### Metrics", "", "| Metric | Value |", "| --- | ---: |"])
                for name, value in stage.metrics.items():
                    lines.append(f"| {name} | `{value}` |")
            if stage.checks:
                lines.extend(["", "### Acceptance checks", ""])
                lines.extend(
                    f"- [{'x' if check.passed else ' '}] {check.message}"
                    for check in stage.checks
                )
        lines.append("")
        return "\n".join(lines)

    def write_markdown(self, manifest: WorkflowManifest, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render_markdown(manifest), encoding="utf-8")
        return path
