# CFD Agents Blueprint V2 — reliability and evidence

**Updated:** 2026-09-05  
**Target:** [hamletroyophelia/openfoam-cfd-agents](https://github.com/hamletroyophelia/openfoam-cfd-agents)  
**Status:** integrated design and implementation handoff, **not a software release**.

The user-provided WeChat report could not be read. This package does not summarize or attribute claims to that report. V2 instead builds on the previous blueprint, the connected repository's README/domain source, and accessible primary documentation.

## What changed

Keep one authoritative workflow controller. Prioritize finite-metric gates, capability evidence, durable jobs, physical/data semantics, evidence invalidation, authorization, and negative tests before adding more agents or user interfaces.

The existing CFD lifecycle remains intact: physics/numerics and BC/IC, mesh generation and verification, timestep/domain studies, resource benchmarking, production monitoring, statistical analysis, physical validation, ParaView/CSV delivery, and reporting. VibeFlow and third-party MCP providers remain optional.

## Contents

| Document | Purpose |
| --- | --- |
| [完整系统设计 V2](docs/SYSTEM_DESIGN.zh-CN.md) | Integrated lifecycle and architecture |
| [本次改动](docs/CHANGELOG_V2.md) | What changed relative to the previous blueprint |
| [源码风险核验](docs/SOURCE_REVIEW.md) | Non-finite metric comparison issue and limits of the review |
| [开发交接](docs/IMPLEMENTATION_HANDOFF.md) | Incremental changes for the coding agent |
| [24 项验收用例](docs/ACCEPTANCE_TESTS.md) | Contract, fault-injection, safety and scientific negative tests |
| [V2 来源与边界](docs/SOURCES_V2.md) | Accessible primary sources and unread report status |
| [原上游调研](docs/UPSTREAM_REVIEW.md) | Prior research, retaining its original review date |
| [配置契约示例](config/reliability-policy.example.yaml) | Proposed policy; not a supported current CLI configuration |
| [Orchestrator skill](skills/cfd-orchestrator/SKILL.md) | Original instructions; no solver or backend bundled |

## Verification performed for this package

Read the connected repository's README and domain.py. Demonstrated relevant floating-point comparisons independently. Checked the package's text links, YAML/JSON readability, file hashes and ZIP integrity. These checks are not OpenFOAM, MCP, MPI or ParaView integration tests.

No remote repository was modified, no issue or PR was opened, no production case was changed, and no solver was run. The source review is not a completed bug fix. Inspect the current checkout and run its tests before implementing the handoff.

The package contains original design/instruction text, configuration proposals and a synthetic arithmetic probe; it does not bundle third-party code, solver binaries, private data or credentials. Preserve the repository's licensing and verify upstream licenses before source reuse.
