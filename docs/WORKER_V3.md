# 0.3.0 durable execution worker

The local SQLite ledger now drives an executable `WorkerAgent`. Linux systemd
user services own job processes and their descendants. CLI or worker termination
does not terminate those independent services. The existing deterministic
monitor, verification and report agents keep their separate responsibilities.

## Lifecycle and evidence

1. `jobs submit` validates an OpenFOAM plan, snapshots its runtime environment and
   persists the spec and idempotency key. It does not start the solver.
2. The worker obtains a Linux file lock for its database and commits `launching`
   before calling `systemd-run`. Unit names contain the persisted job UUID.
3. A unit description binds the job UUID and spec digest. Its systemd InvocationID
   identifies the particular execution. Interrupted launches are rediscovered;
   missing or conflicting evidence retains the case reservation and never retries
   the launch automatically.
4. Each foreground runtime checks for existing OpenFOAM writers, obtains a
   cooperative case-directory lock, checks space on the actual case filesystem,
   and runs the plan through the existing adapter. OpenFOAM preflight and restart
   checkpoint checks precede execution. Raw command logs remain on disk.
5. `completed` requires a verified zero service exit and an empty cgroup. This
   means execution completed; numerical health and scientific validity are
   separate stages. A nonzero command is retained in `execution.json` and fails
   the job. No LLM chooses these statuses.
6. Cancellation is persisted first. The backend checks invocation identity again,
   stops the service's entire control group, confirms exit and saves a cancellation
   receipt before releasing the database reservation. An ACK alone is insufficient.

Systemd `Type=exec`, `RemainAfterExit=yes`, `KillMode=control-group` and `Restart=no`
are used for payloads. The controller itself may use `Restart=on-failure`.
See the [systemd service documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
and [process termination documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html).
Implementation was checked against the installed systemd 249 manuals and tested
on that runtime; no newer `--expand-environment` option is required.

## Running it

Python 3.11+, Linux, a usable systemd user manager and cgroup v2 are required for
execution. Windows supports submission/inspection and deterministic unit tests,
but cannot run this backend. Use a persistent, private directory on local storage,
not a network-mounted SQLite database. One database and one controller cover all
case writers on a host; a worker serves its configured principal/project scope.

```bash
umask 077
mkdir -p "$HOME/.local/state/cfd-agents"
source /opt/openfoam14/etc/bashrc

# Review the plan, case state, resource allocation and revision before submission.
cfd-workflow plan-run /absolute/case --processes 4 --output /absolute/plan.json
cfd-workflow jobs submit /absolute/plan.json \
  --db "$HOME/.local/state/cfd-agents/jobs.sqlite" \
  --revision case-revision-1 --key case-revision-1-attempt-1

cfd-workflow jobs worker --db "$HOME/.local/state/cfd-agents/jobs.sqlite" \
  --spool "$HOME/.local/state/cfd-agents/spool"

cfd-workflow jobs status JOB_ID --db "$HOME/.local/state/cfd-agents/jobs.sqlite"
cfd-workflow jobs cancel JOB_ID --db "$HOME/.local/state/cfd-agents/jobs.sqlite"
```

Use `--once` for one reconciliation pass. The [example service](../deploy/systemd/cfd-agents-worker.service)
keeps the controller resident. Install the package into the example's venv path,
or edit `ExecStart` to match your installation before enabling it. The submission
environment retains only PATH, LD_LIBRARY_PATH, FOAM_* and WM_* variables. It
does not copy SSH credentials or unrelated environment variables. Specs and logs
are private local artifacts. For a restart, `plan-run --restart-time ... --fields ...`
checks the candidate; explicitly prepare the control dictionary before submission.

## Boundaries

- This is a trusted local controller, not an authenticated HTTP/MCP service. Its
  Python API accepts executable plans; do not expose it directly to untrusted input.
- `revision` is a caller-provided immutable label. Its correspondence to the actual
  mesh and physics is not automatically proven. The spec digest is not a full case
  content hash, and evidence/approval-scope objects are not wired into submission.
- CPU/NUMA admission, host-wide quotas and multi-node scheduling remain separate.
  Run the existing CPU audit and allocate resources before submission. The default
  free-space floor is only a launch floor; set an appropriate explicit budget.
- The `/proc` check detects current common OpenFOAM writers. The cooperative case
  lock excludes other copies of this runtime, but external scripts must use the
  same coordination protocol to eliminate races with independent launches.
- The worker does not adopt pre-existing tmux solvers for cancellation, infer a
  checkpoint, change a dictionary, or restart a failed CFD job automatically.
- If the host/user manager loses the transient unit, or a crash occurs after stop
  but before a cancellation receipt is persisted, missing evidence keeps the job
  reserved. An operator must establish that all writers exited before using the
  ledger's explicit transition API. There is no force-unlock CLI.
- Successful/failed units retain evidence until operators stop/reset those exact
  units. No automatic history purge is performed.
- Systemd 249 payload paths containing `%`, `$`, or newlines are rejected because
  they have expansion semantics. Spaces are tested and supported.

## Tests and server recovery

Unit tests cover lost launch ACKs, interrupted intents, identity mismatch, scope,
exit codes, cancellation ACKs, exclusive worker locking, CLI idempotency, and
cgroup exit evidence. Opt-in real-service tests use disposable Python processes:

```bash
python tests/integration/systemd_worker.py /absolute/new/evidence-directory
```

The server test kills the controller while a payload is running, reconnects through
the ledger, models launch before identity persistence, preserves nonzero exit
evidence, cancels a process with a descendant, and enforces a runtime budget. It
never starts an OpenFOAM solve.

The separately authorized production recovery resumed the cylinder from 290 s
after all eight previous ranks exited. Six checkpoint fields (`U`, `U_0`, `nut`,
`p`, `phi`, `phi_0`) and matching per-rank time metadata were checked. An MPI ring
and allreduce probe passed with `--host localhost:8 --mca pml ob1 --mca btl self,vader`.
The original failure log and control dictionary were preserved. The sphere kept
its existing process and 104-core allocation. Neither production solver was
migrated to the new worker. Their new Agent checks are read-only.

Recovery exposed two corrected defects: OpenFOAM's exact `sigFpe` startup banner
is no longer classified as a fatal exception, and the single-host MPI plan now
declares `localhost:N` slots. Actual FPE failures and TCP faults still fail gates.
The sanitized [validation record](validation/server-worker-v030.json) distinguishes
worker process-control evidence from production numerical observations.
