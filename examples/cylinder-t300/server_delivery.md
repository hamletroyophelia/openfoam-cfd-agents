# Server paper-layout delivery

Server output root:

`/data/post/cylinder_Re100_LES_WALE_Lz4D_v14force_20260902/paper-layout-20260906-r1`

The directory is independent of the original OpenFOAM case. It contains the exact-stride 321x181 centre-plane table, resolved visualization configuration, reusable script, preview PNGs, final PNGs, logs, summaries and checksums.

The final server command used one low-priority process and one numerical-library thread:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 19 ionice -c 3 /srv/cfd/apps/bin/pvpython \
  scripts/paper_fields.py \
  --csv inputs/centre_plane_321x181.csv \
  --config-json inputs/viz.resolved.json \
  --output-dir final
```

This layout pass did not read or alter the running sphere case, the completed cylinder source case, OpenFOAM, MPI or system Python.
