"""Render a tiny scene before running an OpenFOAM field pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from paraview import simple
from vtkmodules.vtkCommonCore import vtkVersion


def main(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    simple._DisableFirstRenderCameraReset()
    view = simple.CreateView("RenderView")
    view.ViewSize = [640, 360]
    view.UseColorPaletteForBackground = 0
    view.Background = [0.97, 0.98, 0.99]
    sphere = simple.Sphere(ThetaResolution=64, PhiResolution=64)
    display = simple.Show(sphere, view)
    display.DiffuseColor = [0.05, 0.42, 0.62]
    view.CameraPosition = [0.0, 0.0, 4.0]
    view.CameraFocalPoint = [0.0, 0.0, 0.0]
    simple.Render(view)
    window = view.GetClientSideObject().GetRenderWindow()
    simple.SaveScreenshot(str(output), view, ImageResolution=[640, 360])
    capabilities = window.ReportCapabilities()
    payload = {
        "paraview": str(simple.GetParaViewVersion()).split("-")[0],
        "vtk": vtkVersion.GetVTKVersion(),
        "offscreen": bool(window.GetOffScreenRendering()),
        "capabilities": capabilities,
        "image": str(output.resolve()),
    }
    output.with_suffix(".json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
