---
name: cfd-visualization
description: Use when an OpenFOAM case needs auditable ParaView field rendering, force-history analysis, fixed scientific styling, or a reproducible visualization bundle without modifying the solver case.
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

Run [render_fields.py](scripts/render_fields.py) with pvbatch. Compute the velocity gradient on the complete three-dimensional velocity field before slicing or point interpolation. Skip Q when all three mesh spans are not physical. Record any sampling, interpolation, clipping, masking, or geometry overlay.

Merge force segments with explicit half-open intervals. Fail on time regressions, non-finite values, and conflicting duplicate times. Plot the full raw history and an unsmoothed statistics-window panel. Use time integration for nonuniform samples. Withhold confidence intervals when time correlation leaves too few effective observations.

Apply [cfd-publication.mplstyle](assets/cfd-publication.mplstyle) to Matplotlib outputs. Save curve figures as PNG, SVG, and PDF. Keep previews separate from final 3200-pixel field figures.

## Inspect and publish

Open every PNG and inspect composition, type, scalar bars, occlusion, aliasing, saturation, body outline, partition artifacts, and physical labels. Modify the pipeline and render again when a defect is visible. Record failed iterations and the correction in `qa_report.md`; never infer visual acceptance from exit status.

Build `manifest.json` and the static gallery with [build_bundle.py](scripts/build_bundle.py). Verify hashes, image dimensions, and required artifacts with [validate_bundle.py](scripts/validate_bundle.py). Follow [scientific-qa.md](references/scientific-qa.md) when reviewing a new case.

Do not batch time steps or make an animation until the single-time bundle passes data, resource, and visual review. Never auto-rescale frames within a comparison set.
