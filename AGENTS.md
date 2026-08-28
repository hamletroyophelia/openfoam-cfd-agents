# Project working agreements

- Target Foundation OpenFOAM v14. Treat other forks and versions as separate adapters.
- Use `foamRun` and the solver module declared in `system/controlDict` for v14 cases.
- Never let an LLM or Agent set a stage to `passed`; calculate the status from explicit checks.
- Preserve raw inputs, logs, normalized metrics, acceptance checks, and generated artifacts.
- A successful process exit proves execution only. Physical and numerical credibility require separate verification stages.
- Add a failing test before changing behavior. Keep command execution shell-free and paths as argument-list elements.
- Do not introduce an OpenFOAM function object until it is verified against the actual v14 runtime or source.
- Keep integrations behind ports/adapters so Foam-Agent, openfoam-mcp, local processes, and future schedulers remain replaceable.
