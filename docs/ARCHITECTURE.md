# Architecture

## Stable core

`openfoam_cfd_agents.domain` is the stable core. Execution platforms, LLMs, schedulers, and visualization systems remain outside it. They may produce evidence through adapters, but only core rules derive workflow status.

## Stage flow

1. The Supervisor invokes a stage task.
2. An agent, adapter, or deterministic tool creates raw artifacts and normalized metrics.
3. `MetricRule` compares metrics with explicit thresholds.
4. `evaluate_stage` derives `passed` or `failed` from all checks.
5. A failed repairable stage may invoke its repair callback and repeat, up to `max_attempts`.
6. Every attempt remains in the manifest. Exhaustion stops downstream work.
7. A passed stage advances only when its approval policy also permits it.
8. The Report Agent renders the manifest without changing any decision.

The repair callback changes files or execution state; it never mutates a `StageResult`. A fresh stage execution must prove that the repair worked.

## Integration layers

### Foam-Agent reasoning layer

`FoamAgentMcpAdapter` exposes the source-verified Foam-Agent sequence:

| Operation | MCP tool | Envelope |
| --- | --- | --- |
| plan | `plan` | `request` |
| generate case | `input_writer` | `request` |
| run | `run` | `request` |
| review errors | `review` | `request` |
| apply fixes | `apply_fixes` | `request` |
| visualize | `visualization` | `request` |

Planning, generated dictionaries, and LLM-authored repairs must pass Foundation v14 adaptation, preflight, execution, and independent stage gates. Foam-Agent's default Foundation v10 references are not treated as v14 evidence.

### openfoam-mcp execution layer

`OpenFoamMcpAdapter` currently maps:

| Operation | MCP tool | Envelope |
| --- | --- | --- |
| preflight | `openfoam_preflight_check` | `params` |
| validate case | `openfoam_validate_case` | `params` |
| serial run | `openfoam_run_solver` | `params` |
| parallel run | `openfoam_run_parallel` | `params` |
| status | `openfoam_get_run_status` | `params` |

Both adapters accept an injected asynchronous `call_tool(name, arguments)` function and therefore do not depend on a specific MCP client SDK. The caller owns connection management, authentication, transport timeouts, and transport retries.

openfoam-mcp may report `ready`, `degraded`, `blocked`, `completed_with_warnings`, or a serial fallback. These are valuable execution facts, not scientific acceptance decisions. Automatic stability fixes and fallback execution must be recorded and then checked again by the relevant stage gate.

## Foundation OpenFOAM v14 profile

- Platform: Foundation OpenFOAM.
- Version: 14.
- Single-region application: `foamRun`.
- Serial: `foamRun -case <path>`.
- Parallel: `decomposePar` -> `mpirun -np N foamRun -parallel` -> `reconstructPar`.
- Commands use argument arrays, never concatenated shell strings.
- Preflight checks the case structure, environment variables, version, and required executables.

Function objects such as `fieldMinMax` do not enter default templates until their availability and syntax are verified in the target v14 installation, source, or an actual case.

## Trust model

```text
process exited
< numerical run healthy
< discretization verified
< statistics converged
< physical validation passed
```

Passing a lower layer cannot replace a higher-layer check.
