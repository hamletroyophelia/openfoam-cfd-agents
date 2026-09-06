# Changelog

## 0.5.1 — 2026-09-06

- Add an executable animation-cadence gate with nondimensional time windows, target spacing, frequency resolution, frames-per-period and Nyquist evidence.
- Require at least 20 real saved fields per shortest period of interest and prohibit interpolated or duplicated frames from being presented as resolved CFD motion.
- Classify the cylinder's seven available converged fields as a coarse temporal comparison because `delta_t*=5` provides only about 1.18 frames per exploratory shedding period.

## 0.5.0 — 2026-09-06

- Make numerical nondimensionalization mandatory for every plotted quantity with defensible reference scales.
- Add explicit schema-v2 reference symbols and fixed ranges for velocity and vorticity stars.
- Plot force-history time as `t*=t U_ref/L_ref`, while retaining dimensional raw samples and statistics provenance.
- Correct the cylinder paper sample so spanwise vorticity values are multiplied by `L_ref/U_ref` before rendering.

## 0.4.1 — 2026-09-06

- Add journal-style 2D field plots with `x/D`, `y/D` axes, in-panel labels and adjacent fixed-range colour bars.
- Replace the cylinder sample's main velocity and vorticity images with visually reviewed 3223-pixel server renders.
- Distinguish the published 41,014-point unstructured slice from the separate 321x181 exact-stride paper plane.

## 0.4.0 — 2026-09-06

- Add a reusable, case-read-only CFD visualization workflow with strict decomposed-time audits and explicit resource limits.
- Render fixed-scale velocity, signed vorticity and full-3D Q* figures through ParaView pvbatch, with a portable state and compact raw slice extract.
- Merge force-history branches without silent duplicate replacement and plot the full raw history plus an explicit, unsmoothed statistics window.
- Publish the real cylinder t=300 sample as 3200x1800 PNGs, SVG/PDF curves, a static gallery, manifest and visual QA report.
- Add `.agents/skills/cfd-visualization` with templates, publication style, renderer, bundle builder and integrity validator.

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
