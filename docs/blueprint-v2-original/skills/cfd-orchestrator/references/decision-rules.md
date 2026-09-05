# Decision rules

These are project design rules, not universal CFD accuracy thresholds.

## Verification and validation

A solver exit code is process evidence. Residual and conservation checks are numerical-health evidence. Spatial/time studies are discretization evidence. Stable statistics are sampling evidence. Analytical or manufactured solutions support verification; applicable experimental or measured evidence supports physical validation. Cross-code consistency alone does not establish physical validity. Do not substitute one category for another.

Use quantity-specific tolerances with provenance. Near-zero quantities need an absolute scale. Never assume an arbitrary universal percentage establishes engineering adequacy.

Three systematically related meshes can support order and GCI analysis when applicable; test convergence behavior and sampling contamination. Non-asymptotic, noisy, or incomparable studies can be inconclusive. LES/DNS require resolution and sampling considerations, not unconditional steady-style extrapolation.

Reference: [NASA grid convergence](https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html); [Oliver et al., sampling and discretization uncertainty](https://arxiv.org/abs/1311.0828).

## Performance

Fixed-step pilots measure cost, not accuracy. Hold mesh, physics, numerical settings, starting fields, and I/O policy constant when comparing parallel layouts. Use warm-up, repeated measurements, and explicit memory definitions. Reject serial fallback as evidence for an MPI configuration.

Compare transient cost per physical interval and steady cost to the same convergence criterion. Choose among configurations that satisfy the declared scientific checks. Recheck the final combined mesh, timestep, and resource choice.

## Statistics and visualization

Use physical time, appropriate weighting, and correlation-aware uncertainty estimates. Repeated restarted timestamps are not new independent samples. Do not run a conventional equally spaced FFT blindly on irregular data.

Record field definitions, units, references, timestamps, filters, cameras, and color ranges. Keep scripts and source data linked to each figure. A visually pleasing plot cannot override failed evidence.

## State and authorization

The host core decides verdicts; the agent cannot set them. A repair creates a new attempt, and a changed model or numerical configuration invalidates affected evidence. Budget exhaustion with inadequate evidence is not success.

Stop, cancel, or restart only owned jobs through authorized interfaces. Discover capabilities before executing; never assume a proposed API already exists.

## V2 finite-data and lifecycle checks

Observed metrics and thresholds must be finite and semantically comparable. Invalid, stale, or mismatched evidence cannot pass. Keep protocol, tool, business-job, and scientific outcomes separate. A durable job persists beyond client disconnection; an ambiguous launch must be reconciled before retrying.

Task/API compatibility is version-scoped. Read-only tool annotations are not authorization. Bind write access and approvals to the actual revision and scope, and check access again when retrieving jobs or artifacts.
