# Agent contracts

These agents are workflow roles, not numerical judges. The current Python implementations live in `src/openfoam_cfd_agents/agents/`.

## Supervisor Agent

- Input: ordered `StageTask` objects, approval policy, and run identifier.
- Output: `WorkflowManifest`.
- Contract: accepts only `StageResult` outputs; stops on a failed gate; exposes `approval_required`; may run a bounded repair callback before repeating the same deterministic gate.
- Audit rule: every failed and successful attempt remains in the manifest with its attempt number. A repair callback cannot change a failed result into a pass; it can only change external state before the stage is evaluated again.

## Monitor Agent

- Input: a Foundation OpenFOAM solver log and explicit limits.
- Output: a `monitoring` stage result plus the original log artifact.
- Contract: parser code produces the metrics. Fatal errors, insufficient progress, excessive Courant number, continuity error, or residuals stop the workflow.

## Verification Agent

- Input: cell counts and the same quantity of interest from three systematically refined meshes.
- Output: observed order, Richardson extrapolation, GCI, recommended level, and stage status.
- Contract: rejects duplicate grid sizes, zero differences, and non-computable sequences; acceptance limits come from configuration.

## Report Agent

- Input: a persisted `WorkflowManifest`.
- Output: Markdown.
- Contract: presents evidence without deciding status again and never describes successful execution as a credible result.

## Planned agents

Physics, Case Builder, Mesh, HPC, Statistics, Postprocess, and an independent Reviewer will be added only after their deterministic tools and acceptance contracts exist.
