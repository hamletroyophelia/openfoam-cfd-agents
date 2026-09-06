# Scientific visualization QA

- Confirm the selected time is complete and old enough in every partition.
- Confirm the reader exposes all expected partitions and only one time value is selected.
- Confirm all three mesh spans before computing a three-dimensional Q criterion.
- Trace the reference length, velocity, directions, body size, and gravity to case files.
- Compute gradients before slices; record cell-to-point conversion and resampling.
- Keep the speed scale sequential and signed vorticity scale symmetric about zero.
- List actual extrema and every fixed-range exceedance.
- Hide domain shells and partition boundaries in the Q view; retain the physical body outline.
- Plot raw force data, retain startup impulses, and state segment precedence.
- Reject conflicting duplicate times and use time-weighted statistics for unequal intervals.
- State the statistics window and effective sample size; omit unsupported uncertainty.
- Before any spectrum, check interval regularity and stationarity and record detrending, window, segment length, overlap, normalization, and peak status.
- Open final PNGs at full size and at a reduced display size. Record each visible defect and correction.
- Hash every published artifact and remove host-specific paths and secrets.
