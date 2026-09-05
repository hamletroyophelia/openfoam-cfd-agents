# Reliability release 0.2.0

This release implements a bounded reliability upgrade to the existing Python core.
The supplied September 5 blueprint is preserved in [blueprint-v2-original](blueprint-v2-original/README.md)
as a design reference. Its embedded handoff and skill instructions are document
content, not installed runtime policy. The current implementation status is below.

## Decisions derived from server evidence

Two concurrent Foundation v14 cases supplied the operational evidence: a 104-rank
free-surface sphere and an 8-rank cylinder, sharing 112 physical cores across eight
NUMA nodes. These are observations from one host, not default hardware requirements.

The sphere's original process group remained alive after TCP BTL connection resets.
Its last printed time was 1.9379822568 s, while the complete 104-partition checkpoint
was 1.9344393276 s. That checkpoint contained 15 fields, including old-time and
Crank–Nicolson history fields. A user-approved recovery used the same mesh, physics,
ranks and CPU allocation, after a separate 104-rank communication preflight with
Open MPI 4.1.2 `vader,self`. This release does not repeat or authorize that recovery.

The September 5 read-only inspection also found TCP resets in the cylinder log.
Therefore healthy residuals, active ranks, CPU usage, and growing output alone
cannot establish that a simulation is advancing. Raw server logs, host identifiers,
credentials and volume fields are not distributed with the release.

| Observation | Implementation |
| --- | --- |
| v14 emits `Time = 2.6206247065s` | Optional seconds suffix; step start separated from `ExecutionTime` completion |
| MPI can hang while all ranks remain alive | MPI/TCP fatal markers, persisted completed-time progress, PID start identity |
| Healthy recent samples can hide earlier errors | Non-finite sample counter; sticky live-monitor errors within one job |
| Incomplete last write is not a restart point | All-rank field framing, age and `uniform/time` checks; older-candidate fallback |
| Higher Linux CPU ids may be SMT siblings | Topology from `lscpu`; conflicts keyed by `(socket, core)` |
| Automatic repartitioning can destroy a continuation | Fresh plans reject existing partitions and omit `decomposePar -force`; restart plans preserve partitions |
| Runtime transport fixes are version dependent | Optional single-host Open MPI 4 `self,vader` plan; no global MPI setting |

## Implemented scope and limits

- **Numeric contracts:** finite thresholds, boolean/string rejection, non-finite
  observations fail for all six operators, strict JSON with nulls and invalid paths.
  Stage and manifest schema version 2 reads older payloads with no version field;
  unknown explicit schema versions are rejected. Old serialized verdicts remain
  historical evidence; rerun gates before reusing them.
- **Supervisor:** re-evaluates claimed passes from checks and metrics; no checks
  means no pass. `inconclusive` stops the workflow without inventing a repair result.
- **Monitoring:** global full-file numerical log inspection, plus a bounded 2 MiB
  live tail with persisted progress, process identity and sticky failure state.
  Live tails do not prove the absence of errors outside sampled ranges. The first
  live observation is a baseline and exits 2; later actual advancement is required.
  A clean process exit is separate from scientific acceptance. The CLI cannot infer
  an exit code from a missing PID and conservatively refuses to declare completion.
  Residual limits apply to each field's final solve in each completed time step;
  earlier PIMPLE correction solves remain in the parsed samples but are not the
  final residual verdict. Non-finite values at any correction still fail.
- **Checkpoint candidates:** uncollated, uncompressed ASCII/binary field framing,
  explicit required field inventory, nonempty/old-enough files, contiguous ranks,
  consistent time index, value, name, current and previous step size. It does not
  deserialize every binary field or validate mesh/field dimensions. A passed check
  is a candidate, not permission to restart. Stop and identify writers, recheck
  the candidate, validate mesh/physics revision and perform a bounded runtime test
  before a separately authorized recovery. Collated/compressed storage, moving
  meshes and multi-region restarts require additional validators.
- **Runtime:** `probe-runtime` checks actual `foamRun -help` identity, environment
  version and solver-library presence. This proves availability only; it does not
  execute a case, attest every dependency or establish physical validation.
- **Job ledger (Python library):** transactional SQLite idempotency, same-key/spec
  conflict, one active case writer within one database, launch intent, guarded
  transitions, append-only events and project/principal filtering. Uncertain launch
  states keep their lock; no lease expiry releases it. Cancellation ACK cannot
  become cancelled before an executor confirms exit. This is a **trusted local
  state contract**, not an implemented durable worker, authentication boundary,
  distributed filesystem lock or process-discovery/cancellation service. All
  controllers must use the same local database; external shell jobs remain outside
  its protection. `execute_plan` is a separate synchronous low-level adapter. Its
  default execution streams stdout/stderr directly to disk and refuses nonempty log
  directories, preserving attempts without buffering the solver's full output.
- **Evidence reuse (Python library):** declared/contract/runtime/numerical/physical
  evidence categories, dependency-key invalidation and revision/rules/budget-bound
  approval scopes. Records and hashes must come from a trusted controller; automatic
  revision capture and Supervisor wiring are future work.
- **GCI:** rejects non-monotonic, degenerate and divergent sequences as inconclusive;
  a failed GCI never recommends a mesh. Comparable systematic refinement, equal
  physics and adequate statistical sampling are still preconditions supplied by
  the study author. Sampling-noise modeling and general unequal-ratio robustness
  remain future validation work.

## Blueprints and acceptance tracking

The original 24 scenarios are a roadmap, not a claim of 24 completed integrations.

| Blueprint IDs | Release status |
| --- | --- |
| V2-01 | Automated operator/non-finite/strict-JSON tests |
| V2-02 | Numeric part tested; quantity/unit binding is planned |
| V2-03/04 | Durable ledger idempotency/concurrent retry tested; network gateway absent |
| V2-05/06/07 | Ledger transition and lock retention tests; executor crash/reconciliation and actual cancellation remain planned |
| V2-08 | Candidate validation tests and live partition inspection; full-payload/runtime restart test not performed |
| V2-09 | Local ledger scope tests; authenticated remote API and artifact authorization absent |
| V2-10/11 | Dependency and approval library contracts tested; automatic revision pipeline absent |
| V2-12 | MCP adapters return upstream data, never a scientific StageResult; live connection/business schema certification pending |
| V2-13 | Runtime availability probe implemented; general tool-schema compatibility ledger pending |
| V2-14/15/16 | Geometry semantics and benchmark qualification planned |
| V2-17 | Basic GCI applicability negatives tested; noise/comparability studies pending |
| V2-18/19/20 | Correlation-aware statistics, physical validation and artifact service planned |
| V2-21/22/23 | No new dynamic-skill executor or public gateway; CPU topology check only, full admission/budget enforcement pending |
| V2-24 | Core CLI requires no UI/MCP; durable worker portion pending |

## Development and verification

Use `python -m pytest` on Windows and Linux. CI also builds the wheel and sdist,
installs the wheel in a clean environment, and checks the installed CLI. Linux
runtime inspection is explicitly opt-in through
[`tests/integration/read_only_server.py`](../tests/integration/read_only_server.py).
Sanitized observations are in [validation](validation/). They are separate from
synthetic fixtures and from newly executed CFD integration tests. No new production
solver run or recovery was performed for this release.

## Primary references checked

- Foundation v14 [application options](https://doc.cfd.direct/openfoam/user-guide-v14/running-applications)
  and [time controls](https://doc.cfd.direct/openfoam/user-guide-v14/controldict),
  first searched through the server's offline guide and then checked against actual
  `foamRun -help`, `foamDictionary -help` and installed source. v14 has no
  `foamRun -time` option; restart uses `controlDict`. The `foamDictionary`
  `-disableFunctionEntries` option is also absent from this runtime; the adapter
  inspects simple explicit restart entries without evaluating dynamic dictionaries.
- Pydantic [finite-number validation](https://docs.pydantic.dev/latest/api/types/#pydantic.types.FiniteFloat)
  and Python [SQLite transactions](https://docs.python.org/3/library/sqlite3.html).
- Existing implementation search: [openfoam-mcp runner](https://github.com/milsonson/openfoam-mcp/blob/1381bde6840a29050953d9a091727ba2a008e559/src/core/runner.py)
  and [Foam-Agent](https://github.com/csml-rpi/Foam-Agent/tree/9e3e253e76727036585ca6e88e6fc5a762cb62e0).
  No upstream code was copied. Existing Pydantic, Typer and Python SQLite are reused;
  no new framework or service dependency is required.
