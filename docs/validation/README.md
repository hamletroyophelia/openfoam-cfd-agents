# Release validation

## 0.3.0 — 2026-09-05

[server-worker-v030.json](server-worker-v030.json) records the installed wheel's
five real systemd lifecycle checks, the resident worker and two read-only observers,
and the separately authorized cylinder recovery. Windows: **104 passed, 1 Linux-only
test skipped**. Linux: **105 passed**. Production processes remain in their existing
tmux sessions; they were not migrated to the worker. Both observers passed after
actual completed-time advancement. These facts do not establish final CFD validity.

The record below is the preserved **0.2.0 historical snapshot**, taken before that
recovery. Its strict demonstration alpha gate was not the sphere's production policy.

## 0.2.0 — 2026-09-05

### Automated tests

- Windows, Python 3.12.10: **89 passed**.
- Linux isolated scratch environment, Python 3.12.14: **89 passed**.
- Windows dependencies: Pydantic 2.13.4, Typer 0.27.1, PyYAML 6.0.3, pytest 9.1.1.
- Linux dependencies: Pydantic 2.13.5, Typer 0.27.2, PyYAML 6.0.3, pytest 9.1.1.

The test suite includes operator/non-finite cross-products, schema compatibility,
PIMPLE terminal residuals, MPI errors, completed-time progress, PID reuse, field
framing, incomplete checkpoints, time-scheme field names containing commas,
physical-core collisions, concurrent SQLite submissions, guarded transitions and
evidence dependency invalidation. These are synthetic/contract tests, not CFD solves.

### Live read-only inspection

Actual runtime: Foundation OpenFOAM 14, build `14-7b05503f98a8`, Open MPI 4.1.2.
The validation code and Python dependencies ran in a separate scratch environment.
No production dictionaries, fields, monitors or processes were changed.

| Check | Sphere | Cylinder |
| --- | --- | --- |
| Runtime module availability | Passed, incompressibleVoF | Passed, incompressibleFluid |
| Actual CPU affinity | Exactly 104 requested physical CPUs | Exactly 8 complementary physical CPUs |
| Checkpoint candidate | 1.9344393276 s, all 104 ranks, all 15 explicit fields | 290 s, 8 ranks, U/p/nut |
| Completed physical time | Advanced from 2.6438823222 to 2.6440537542 s | Stayed at 290.94 s; last started time 290.95 s |
| Numerical/communication verdict | **Failed** strict example alpha threshold | **Failed** TCP reset markers |

The sphere's sampled `alpha_max=1.0000023` exceeds the explicit demonstration gate
`1.000002`. The initial expectation that it would pass was rejected by the program.
That first report is retained in [sphere-initial-expectation.json](sphere-initial-expectation.json).
The follow-up records a negative acceptance expectation, with the **same threshold**,
in [sphere-inspection.json](sphere-inspection.json). This is not a finding that the
production case violates its own approved physical tolerance: this release test's
example threshold has not been substituted for the case's scientific policy.

[cylinder-inspection.json](cylinder-inspection.json) records ten TCP reset lines in
the sampled tail and no completed-time advancement despite eight live ranks.
The first progress observation is a baseline, so its `progress_status=failed` is
expected for both cases. The second sphere observation passes the progress gate;
the cylinder does not. These observations validate detection, not target-time
completion, restart safety, statistical convergence or physical validity.

Full field contents, host/PID identifiers and raw logs are excluded. The files
contain selected measurements and machine checks; inspect their timestamps before
using them as historical evidence. GitHub Actions supplies the release's additional
Windows/Linux and Python 3.11/3.12 test/build/clean-wheel-install checks.
