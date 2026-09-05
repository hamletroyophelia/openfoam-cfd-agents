# Changelog

## 0.3.0 — 2026-09-05

- Connect the SQLite ledger to a Linux systemd `WorkerAgent` with persistent
  launch intents, invocation reconciliation and cancellation after verified group exit.
- Add trusted-local `jobs submit/status/cancel/worker` commands, bounded runtime,
  case-file locking, existing-writer checks and preserved execution artifacts.
- Add real-service integration tests for worker death, interrupted launch, nonzero
  exit and descendant cancellation; provide a resident-controller service template.
- Distinguish the exact healthy OpenFOAM sigFpe banner from actual exceptions.
- Declare `localhost:N` MPI slots for the Open MPI 4 single-host transport profile.
- Document the separately authorized cylinder checkpoint recovery, retained sphere
  process, and boundaries between process control and scientific acceptance.

## 0.2.0 — 2026-09-05

- Fail closed for NaN/Inf and invalid numeric thresholds; persist invalid locations in strict JSON.
- Read Foundation v14 unit-suffixed time, separate completed steps and interface Courant numbers,
  and detect communication/runtime errors even when numerical values look healthy.
- Add read-only live progress, PID identity, sticky failure state, checkpoint candidate selection,
  runtime capability probing and physical-core conflict checks.
- Preserve restart decomposition; remove forced decomposition from fresh plans; make the
  single-host Open MPI 4 shared-memory transport profile an explicit option.
- Stream default solver output to disk and preserve each attempt in a fresh log directory.
- Add a transactional local job ledger and dependency/approval contracts as Python library APIs.
- Reject inapplicable GCI sequences and withhold mesh recommendations on failure.
- Re-evaluate claimed stage passes in the Supervisor. Add `inconclusive` and schema version 2
  with support for older payloads that omit the version.
- Include Chinese documentation, immutable blueprint reference, acceptance coverage, CI and
  separately labeled server inspection evidence.

This remains an early release. Durable process execution/reconciliation, authenticated MCP/API,
full scientific studies, statistics and production recovery automation are not implemented.
