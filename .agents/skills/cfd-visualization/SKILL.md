---
name: cfd-visualization
description: This skill should be used when the user asks to "plot OpenFOAM results", "make publication CFD figures", "nondimensionalize flow fields", "render Q criterion", or "analyze force coefficients" without modifying the solver case.
---

# CFD visualization

Treat the source case as read-only. Put copied inputs, temporary readers, caches, states, figures, and extracted tables in a separate output root. Never stop or reconfigure a solver to make post-processing convenient.

## Audit before rendering

1. Read the case dictionaries and mesh metadata. Establish axes, gravity, reference scales, body geometry, fields, and dimension from evidence rather than names.
2. Select one completed time. Require the requested fields and matching time metadata in every contiguous `processorN` directory. Reject recent files that may still be changing.
3. Record `actual_partitions`, `read_partitions`, and `postprocess_processes` separately. Reading all partitions with one pvbatch process is valid; reading a subset is not a full-domain result.
4. Copy only the audited time and constant mesh into a derived case view. Create the `.foam` marker there.
5. Run a small offscreen scene with `tests/integration/paraview_offscreen_smoke.py`. Record the ParaView, VTK, OpenGL and offscreen results. Use OSMesa only when the host has no working graphics backend and an OSMesa build has passed this smoke test.

Use `cfd-workflow visualize audit` and `prepare` for the first two machine checks. Start with one process and one thread. Measure a preview before approving a final render.

## Render and analyze

Copy [viz.template.yaml](assets/viz.template.yaml) and replace every physical value with reviewed case evidence. Keep fixed ranges, ROI, camera, output size, Q* threshold, phase mask status, and resource budget in this file.

## Nondimensionalization contract

Nondimensionalize every plotted physical quantity for which the audited case supplies a defensible reference scale. Apply the transform to the numerical data before plotting; changing only the axis or colour-bar label is invalid. Use the same reviewed `L_ref` and `U_ref` throughout one comparison set:

- coordinates: `x* = x/L_ref`, including body geometry and display limits;
- time: `t* = t U_ref/L_ref`;
- velocity: `U* = U/U_ref`;
- vorticity and strain rate: `omega* = omega L_ref/U_ref`;
- Q criterion: `Q* = Q L_ref^2/U_ref^2`, computed from the full three-dimensional velocity gradient;
- frequency: `St = f L_ref/U_ref`;
- displacement, wave elevation, depth and submergence: divide by `L_ref`;
- force and moment coefficients: retain them as already nondimensional and record their definitions.

For pressure, first inspect the OpenFOAM dimensions and solver convention. Convert physical pressure with density where required, or kinematic pressure without adding density, and record the exact `C_p` formula and reference pressure. Apply the corresponding spectral-density Jacobian when changing a frequency axis; never relabel a dimensional spectrum as nondimensional.

Store the reference values, symbols, units, source dictionaries, formulas, and transformed fixed ranges in `viz.yaml` and `manifest.json`. Retain dimensional source columns in extracted CSV files and add explicitly named nondimensional columns. If a reference is absent or physically ambiguous, keep that quantity dimensional and add a warning instead of inventing a scale.

Run [render_fields.py](scripts/render_fields.py) with pvbatch. Compute the velocity gradient on the complete three-dimensional velocity field before slicing or point interpolation. Skip Q when all three mesh spans are not physical. Record any sampling, interpolation, clipping, masking, or geometry overlay.

Merge force segments with explicit half-open intervals. Fail on time regressions, non-finite values, and conflicting duplicate times. Plot the full raw history and an unsmoothed statistics-window panel. Use time integration for nonuniform samples. Withhold confidence intervals when time correlation leaves too few effective observations.

Apply [cfd-publication.mplstyle](assets/cfd-publication.mplstyle) to Matplotlib outputs. Save curve figures as PNG, SVG, and PDF. Keep previews separate from final 3200-pixel field figures.

Use [paper_fields.py](scripts/paper_fields.py) when a reviewed plane CSV needs journal-style nondimensional axes, compact in-panel labels, and a colour bar immediately beside the axes. This step must apply the configured reference scales to the numerical arrays, retain the configured nondimensional fixed ranges, and must not smooth the extracted field.

## Inspect and publish

Open every PNG and inspect composition, type, scalar bars, occlusion, aliasing, saturation, body outline, partition artifacts, and physical labels. Modify the pipeline and render again when a defect is visible. Record failed iterations and the correction in `qa_report.md`; never infer visual acceptance from exit status.

Build `manifest.json` and the static gallery with [build_bundle.py](scripts/build_bundle.py). Verify hashes, image dimensions, and required artifacts with [validate_bundle.py](scripts/validate_bundle.py). Follow [scientific-qa.md](references/scientific-qa.md) when reviewing a new case.

Do not batch time steps or make an animation until the single-time bundle passes data, resource, and visual review. Never auto-rescale frames within a comparison set.
