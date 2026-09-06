# Cylinder t=300 visualization bundle

This is the first reusable visualization sample for a completed Foundation OpenFOAM v14 case. It reads all eight decomposed partitions with one pvbatch process. The source case remained read-only; the selected time and mesh were copied into a separate local case view before rendering.

Open [the static gallery](gallery/index.html), then read [manifest.json](manifest.json) and [qa_report.md](qa_report.md). The 41,014-point unstructured slice, the 321x181 exact-stride paper plane, and the merged force history are separate files in `data/`. The force figure is provided as PNG, SVG, and PDF. Preview and final field figures are separate.

The main figures use paper-style `x/D`, `y/D` axes, compact in-panel labels and colour bars immediately beside the axes. Values are transformed before plotting: `|U|*=|U|/U_ref`, `omega_z*=omega_z D/U_ref`, and the force-history axis is `t*=t U_ref/D`. The dimensional source columns remain in `data/`. No field values are smoothed.

For video, validate real saved-field cadence with `cfd-workflow visualize plan-animation`. The available converged fields at `t=240,250,...,300` have `delta_t*=5`; with the exploratory `St=0.169`, this is only about 1.18 frames per period. These fields may be shown as a coarse multi-time comparison, not as resolved continuous motion.

Re-run the workflow with the repository skill at `.agents/skills/cfd-visualization/SKILL.md`. Prepare the JSON consumed by pvbatch with:

```powershell
cfd-workflow visualize audit D:\derived-case-view .\viz.yaml --output .\case-audit.json --safety-age-seconds 120
cfd-workflow visualize prepare .\viz.yaml --output .\viz.resolved.json
pvbatch --force-offscreen-rendering ..\..\.agents\skills\cfd-visualization\scripts\render_fields.py --foam-marker D:\derived-case-view\cylinder.foam --config-json .\viz.resolved.json --output-dir D:\postprocessing\preview --preview
python ..\..\.agents\skills\cfd-visualization\scripts\paper_fields.py --csv .\data\centre_plane_paper_t300.csv --config-json .\viz.resolved.json --output-dir D:\postprocessing\paper-final
```

The PVSM uses `cylinder.foam` as a portable placeholder. Relink it to the `.foam` marker inside the derived case view when loading the state.
