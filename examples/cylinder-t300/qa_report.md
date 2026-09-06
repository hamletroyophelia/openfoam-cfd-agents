# QA report

## Data and resource checks

- Selected completed time: 300 s.
- Partition check: expected 8, present 8, read 8. Post-processing used 1 process and 1 thread.
- Required fields `U`, `p`, and `nut` and time metadata matched in every partition. The audited copy was older than the safety interval before reading.
- Mesh bounds are `[-20, 30] x [-20, 20] x [-4, 4]` m with 2,944,000 cells, so the Q computation is genuinely three-dimensional.
- Offscreen smoke rendering passed with ParaView 5.12.1, VTK 9.3 and Intel Iris Xe OpenGL 4.5. OSMesa was unnecessary.
- Preview peak working set was 2.13 GiB. The first measured 3200x1800 final render used 5.45 GiB, under the explicit 12 GiB budget.

## Visual iterations

1. The inherited field sample used a long identifier that clipped titles and colour-bar units. Its Q view was difficult to read. Short labels, a fixed ROI, an orthographic camera and explicit scalar-bar positions corrected this.
2. The first new preview failed during Q update because selected time was passed as a string. Converting at the pvbatch boundary corrected the error.
3. Early 3200px output allowed ParaView to generate too many tick labels. Supported custom labels and square-root font scaling corrected the overlap.
4. Velocity and vorticity images show angular transitions near mesh-resolution changes. They persisted after merging coincident partition points, sampling at z=0 and z=0.05 m, and comparing point and cell probes. They are not missing-partition seams. No smoothing was used to conceal them.
5. Final PNGs were opened and checked at full output and reduced display size. Titles, body outline, scalar bars and axis notes are readable. The Q view hides the domain exterior and partition boundaries and does not mistake a two-dimensional slice for a three-dimensional gradient.
6. The server paper-layout pass replaced canvas-edge annotations with real `x/D`, `y/D` axes, inward ticks, compact in-panel labels and colour bars separated from the axes by 0.015 of the figure width. Server previews and 3223-pixel final PNGs were both opened and checked.
7. The earlier public CSV was correctly identified as a 41,014-point unstructured slice. It remains available under that name. Paper figures use a separate 321x181 rectilinear table made by retaining every second coordinate from the audited 641x361 probe, with no interpolation or smoothing during reduction.

## Scientific warnings

- Velocity remains inside its fixed `[0, 1.5]` m/s scale. Spanwise vorticity reaches about `[-6.90, 7.21]` 1/s and therefore saturates the fixed `[-1, 1]` 1/s comparison scale.
- Q* is `Q L_ref^2 / U_ref^2` with `L_ref=2 m`, `U_ref=1 m/s`; `Q*=0.2` is `Q=0.05 1/s^2`.
- `centre_slice_unstructured_t300.csv` is the original unstructured slice. `centre_plane_paper_t300.csv` is the exact-stride rectilinear paper table. Q itself was computed from the full three-dimensional cell velocity gradient before point interpolation.
- Cd restart segments are merged with explicit precedence at 290 s. Startup impulses at 0.01 and 0.02 s remain in the overview. The 240–300 s panel is raw and unsmoothed.
- The Cd effective sample size is about 28.9. No confidence interval is reported. No spectrum is claimed in this phase.
