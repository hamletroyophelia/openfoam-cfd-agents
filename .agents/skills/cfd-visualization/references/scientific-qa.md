# Scientific visualization QA

- Confirm `L_ref` and `U_ref` against case dictionaries or documented case setup.
- Check that coordinates, time, velocity, vorticity, Q, frequency, and geometric depths are transformed numerically before plotting.
- Check that fixed colour limits are expressed in the transformed quantity and shared across comparison cases.
- Confirm dimensional raw columns remain available and the manifest records each formula and reference value.
- Treat pressure and spectra as special cases: verify dimensions, reference pressure, density convention, and spectral Jacobian before conversion.
- Verify that saved-field `delta_t*` meets the configured target and provides at least 20 real frames per shortest period of interest.
- Distinguish physical field cadence from playback FPS; list every source time and reject interpolation or duplicated frames presented as resolved motion.

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
