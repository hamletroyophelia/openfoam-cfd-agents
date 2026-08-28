# Upstream source study

This document records the source revisions inspected before defining the integration boundary. It distinguishes reusable architecture from upstream behavior that must not be inherited as a scientific conclusion.

## Revisions reviewed

| Project | Revision | Reviewed areas |
| --- | --- | --- |
| [csml-rpi/Foam-Agent](https://github.com/csml-rpi/Foam-Agent/tree/9e3e253e76727036585ca6e88e6fc5a762cb62e0) | `9e3e253e76727036585ca6e88e6fc5a762cb62e0` | LangGraph state and routing, nodes, services, FastMCP server, `/foam` skill, configuration, and MCP integration tests |
| [milsonson/openfoam-mcp](https://github.com/milsonson/openfoam-mcp/tree/1381bde6840a29050953d9a091727ba2a008e559) | `1381bde6840a29050953d9a091727ba2a008e559` | all 23 tool registrations, input models, case/stability/workflow tools, runner, parallel execution, validator, path controls, artifacts/events, and regression tests |

The review was performed on 2026-08-28. Future upstream changes require a fresh contract review before adapter behavior is changed.

## Foam-Agent findings

### Architecture worth retaining

- The graph separates planning, optional meshing, input writing, local or HPC execution, review, rewriting, and visualization.
- Shared state carries case metadata, generated files, errors, review analysis, rewrite plans, routing choices, HPC job data, and termination reasons.
- Routing decisions are cached in state, avoiding repeated LLM decisions that could send the same run down different branches.
- Input generation supports a dependency-aware sequential mode and a faster parallel mode without cross-file context. This is an explicit accuracy/cost tradeoff.
- Execution errors feed a bounded review-and-rewrite loop. The main configuration allows up to 25 iterations; the MCP example and `/foam` workflow use a five-attempt budget.
- Blocking generation work is moved to worker threads while progress is bridged back to the asynchronous MCP context.
- Planning, generation, review, and repair are exposed as composable MCP tools instead of one inseparable application.

### Verified MCP contract

Foam-Agent's FastMCP functions bind a model named `request`, and its own integration test calls each tool with a nested `request` object. The sequence is:

```text
plan
-> input_writer
-> run
-> review (only when errors exist)
-> apply_fixes
-> run again, within a fixed attempt budget
-> visualization (only after execution succeeds)
```

`FoamAgentMcpAdapter` implements that exact envelope and validates the planner fields required by `input_writer` before making a remote call.

### Boundaries not inherited

- The default and primarily validated target is Foundation OpenFOAM v10. ESI conversion is documented as best effort. Neither path establishes Foundation v14 compatibility.
- The run response treats an empty error list as success. That proves only that the recognized execution errors were absent.
- Reviewer reference lookup currently supplies a default `simpleFoam` solver in one path, so reviewer advice cannot be assumed to carry correct solver metadata.
- RAG loading enables dangerous FAISS deserialization. This project will not copy that trust setting into its core.
- Automatic rewriting is LLM-driven. Every rewrite must be followed by fresh deterministic checks; a reviewer statement is never a gate result.

## openfoam-mcp findings

### Architecture worth retaining

- Tool metadata distinguishes read-only, destructive, idempotent, and open-world behavior.
- Writable case paths use an allowlist. Relative dictionary and artifact paths are resolved inside a trusted root. Writes use atomic replacement where corruption would be costly.
- Solver names and dictionary values are validated against command injection and structural injection.
- Preflight has scenario-specific profiles and structured `ready`, `degraded`, and `blocked` outcomes.
- Ambiguous natural-language classification returns `needs_input` and prevents case creation.
- Execution results preserve error, warning, skipped, and degraded states instead of collapsing them to a Boolean.
- Parallel dependency or runtime failures may fall back to serial execution, while recording `execution_mode`, `fallback_reason`, and a workflow warning.
- End-to-end jobs persist a versioned manifest, progress events, KPI and quality summaries, case bundles, artifact URLs, and bounded MCP responses.
- The test suite covers path traversal, symlink and command injection, atomic writes, mesh and boundary consistency, parallel degradation, malformed logs, preflight semantics, response truncation, and artifact persistence.

### Verified MCP contract

openfoam-mcp's FastMCP functions bind a model named `params`; `OpenFoamMcpAdapter` therefore sends `{"params": ...}`. The adapter exposes granular calls so the Supervisor can place deterministic gates between tool operations.

### Boundaries not inherited

- `completed` and `completed_with_warnings` are delivery states, not proof of discretization independence, statistical convergence, or physical validity.
- Automatic stability fixes change case dictionaries. They must be treated as an auditable repair action and followed by preflight and numerical checks.
- Serial fallback preserves deliverability but invalidates a requested parallel benchmark. It must not satisfy an HPC selection stage.
- The natural-language one-click workflow is useful for execution, but it cannot replace explicit scientific approval stages.

## Decisions applied here

| Upstream lesson | Implementation in OpenFOAM CFD Agents |
| --- | --- |
| Separate reasoning from execution | Separate Foam-Agent and openfoam-mcp adapters |
| Preserve real MCP model envelopes | `request` for Foam-Agent; `params` for openfoam-mcp, covered by tests |
| Bound automatic correction | `StageTask.max_attempts` and an optional repair callback |
| Re-evaluate after every repair | Each attempt calls the stage again and appends a new immutable result |
| Stop ambiguous or failed work | Supervisor advances only after a deterministic `passed` result |
| Preserve degraded execution facts | Adapters return upstream payloads as evidence; gates decide whether they are acceptable |
| Keep artifacts auditable | Attempts, logs, metrics, checks, and artifacts remain in the workflow manifest |

The resulting design uses Foam-Agent as a reasoning source and openfoam-mcp as an execution source, with this project's deterministic control plane as the only authority for progression.
