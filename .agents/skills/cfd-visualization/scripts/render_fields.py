#!/usr/bin/env pvbatch
"""Render one audited decomposed OpenFOAM time with fixed scientific styling."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--foam-marker', type=Path, required=True,
                        help='Marker in a derived case view; never create it in the source case')
    parser.add_argument('--config-json', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--preview', action='store_true')
    return parser.parse_args()


def select_time(reader, requested):
    reader.UpdatePipelineInformation()
    values = [float(value) for value in reader.TimestepValues or []]
    matching = [value for value in values if math.isclose(value, requested, rel_tol=0, abs_tol=1e-9)]
    if not matching:
        raise ValueError(f'time {requested:g} unavailable; reader exposed {values}')
    return matching[-1], values


def data_range(proxy, association, array, component=0):
    info = proxy.GetDataInformation()
    arrays = info.GetPointDataInformation() if association == 'POINTS' else info.GetCellDataInformation()
    array_info = arrays.GetArrayInformation(array)
    if array_info is None:
        raise ValueError(f'missing {association} array {array}')
    return list(array_info.GetComponentRange(component))


def configure_view(pv, resolution):
    view = pv.CreateView('RenderView')
    view.ViewSize = list(resolution)
    view.UseColorPaletteForBackground = 0
    view.Background = [0.985, 0.989, 0.996]
    view.OrientationAxesVisibility = 0
    view.CenterAxesVisibility = 0
    view.CameraParallelProjection = 1
    return view


def add_title(pv, view, text, font_size):
    source = pv.Text(Text=text)
    display = pv.Show(source, view)
    display.WindowLocation = 'Upper Left Corner'
    display.FontFamily = 'Arial'
    display.FontSize = font_size
    display.Color = [0.063, 0.165, 0.263]
    return source


def add_axis_note(pv, view, font_size, z):
    source = pv.Text(Text=f'x: streamwise    y: cross-stream    sampled plane z={z:g} m')
    display = pv.Show(source, view)
    display.WindowLocation = 'Lower Left Corner'
    display.FontFamily = 'Arial'
    display.FontSize = max(16, font_size - 6)
    display.Color = [0.10, 0.125, 0.165]
    return source


def cylinder(pv, view, body):
    source = pv.Cylinder(Center=body['center'], Radius=body['diameter'] / 2,
                         Height=body['span'], Resolution=240)
    rotated = pv.Transform(Input=source)
    rotated.Transform.Rotate = [90, 0, 0]
    display = pv.Show(rotated, view)
    display.Representation = 'Surface'
    display.ColorArrayName = [None, '']
    display.AmbientColor = [0.035, 0.045, 0.06]
    display.DiffuseColor = [0.035, 0.045, 0.06]
    return [source, rotated]


def scalar_bar(pv, display, view, lut, title, font_size, value_range, *, horizontal=False):
    display.SetScalarBarVisibility(view, True)
    bar = pv.GetScalarBar(lut, view)
    bar.WindowLocation = 'Any Location'
    bar.Orientation = 'Horizontal' if horizontal else 'Vertical'
    bar.Position = [0.05, 0.08] if horizontal else [0.805, 0.19]
    bar.ScalarBarLength = 0.30 if horizontal else 0.62
    bar.ScalarBarThickness = 22 if horizontal else 30
    bar.Title = title
    bar.ComponentTitle = ''
    bar.TitleFontFamily = 'Arial'
    bar.LabelFontFamily = 'Arial'
    bar.TitleFontSize = font_size
    bar.LabelFontSize = max(16, font_size - 4)
    bar.TitleColor = [0.063, 0.165, 0.263]
    bar.LabelColor = [0.063, 0.165, 0.263]
    bar.LabelFormat = '%-#6.2f'
    bar.AutomaticLabelFormat = 0
    bar.UseCustomLabels = 1
    bar.AddRangeLabels = 0
    count = 5 if horizontal else 7
    bar.CustomLabels = [value_range[0] + index * (value_range[1] - value_range[0]) / (count - 1)
                        for index in range(count)]
    bar.DrawAnnotations = 0
    return bar


def plane_camera(view, roi):
    xmin, xmax, ymin, ymax, zmin, zmax = roi
    view.CameraPosition = [(xmin + xmax) / 2, (ymin + ymax) / 2, zmax + 100]
    view.CameraFocalPoint = [(xmin + xmax) / 2, (ymin + ymax) / 2, 0]
    view.CameraViewUp = [0, 1, 0]
    view.CameraParallelScale = (ymax - ymin) / 2


def sampling_plane(pv, roi, z, resolution):
    xmin, xmax, ymin, ymax, _, _ = roi
    plane = pv.Plane(Origin=[xmin, ymin, z], Point1=[xmax, ymin, z], Point2=[xmin, ymax, z])
    plane.XResolution, plane.YResolution = resolution
    return plane


def scalar_slice(pv, source, config, array, component, value_range, title, bar_title, output):
    render = config['render']
    view = configure_view(pv, render['_active_resolution'])
    display = pv.Show(source, view)
    display.Representation = 'Surface'
    color_spec = ('POINTS', array) if component is None else ('POINTS', array, component)
    pv.ColorBy(display, color_spec)
    lut = pv.GetColorTransferFunction(array)
    if component is None:
        lut.RGBPoints = [value_range[0], 0.267, 0.005, 0.329,
                         (value_range[0] + value_range[1]) / 2, 0.128, 0.567, 0.551,
                         value_range[1], 0.993, 0.906, 0.144]
    else:
        limit = max(abs(value_range[0]), abs(value_range[1]))
        lut.RGBPoints = [-limit, 0.230, 0.299, 0.754,
                         0, 0.94, 0.94, 0.94,
                         limit, 0.706, 0.016, 0.150]
    lut.ColorSpace = 'Lab'
    lut.RescaleTransferFunction(*value_range)
    scalar_bar(pv, display, view, lut, bar_title, render['_active_font_size'], value_range)
    pipeline = cylinder(pv, view, config['physics']['body'])
    pipeline += [add_title(pv, view, title, render['_active_font_size'] + 4),
                 add_axis_note(pv, view, render['_active_font_size'], render['slice_origin'][2])]
    plane_camera(view, render['roi'])
    pv.Render(view)
    pv.SaveScreenshot(str(output), view, ImageResolution=render['_active_resolution'], CompressionLevel='5')
    return view, pipeline


def clip_to_roi(pv, source, roi):
    result = source
    definitions = [([roi[0], 0, 0], [1, 0, 0]), ([roi[1], 0, 0], [-1, 0, 0]),
                   ([0, roi[2], 0], [0, 1, 0]), ([0, roi[3], 0], [0, -1, 0]),
                   ([0, 0, roi[4]], [0, 0, 1]), ([0, 0, roi[5]], [0, 0, -1])]
    filters = []
    for origin, normal in definitions:
        clip = pv.Clip(Input=result)
        clip.ClipType = 'Plane'
        clip.ClipType.Origin = origin
        clip.ClipType.Normal = normal
        clip.Invert = 0
        result = clip
        filters.append(clip)
    return result, filters


def render_q(pv, points, config, q_threshold, output):
    render = config['render']
    cropped, clips = clip_to_roi(pv, points, render['roi'])
    surface = pv.Contour(Input=cropped)
    surface.ContourBy = ['POINTS', 'Q']
    surface.Isosurfaces = [q_threshold]
    surface.UpdatePipeline(float(config['case']['selected_time']))
    if surface.GetDataInformation().GetNumberOfCells() == 0:
        raise ValueError('selected Q* threshold produces an empty surface')
    view = configure_view(pv, render['_active_resolution'])
    display = pv.Show(surface, view)
    display.Representation = 'Surface'
    display.Ambient = 0.42
    display.Diffuse = 0.58
    display.Specular = 0.0
    pv.ColorBy(display, ('POINTS', 'Vorticity', 'Z'))
    lut = pv.GetColorTransferFunction('Vorticity')
    low, high = render['vorticity_range']
    limit = max(abs(low), abs(high))
    lut.RGBPoints = [-limit, 0.230, 0.299, 0.754, 0, 0.94, 0.94, 0.94,
                     limit, 0.706, 0.016, 0.150]
    lut.ColorSpace = 'Lab'
    lut.RescaleTransferFunction(low, high)
    scalar_bar(pv, display, view, lut, 'spanwise vorticity omega_z [1/s]',
               render['_active_font_size'], (low, high), horizontal=True)
    pipeline = cylinder(pv, view, config['physics']['body'])
    pipeline += [add_title(pv, view,
        f"{config['case'].get('display_name') or config['case']['id']}\n"
        f"t={float(config['case']['selected_time']):g} s | Q*={render['qstar_threshold']:g}",
        render['_active_font_size'] + 4)]
    view.CameraPosition = render['q_camera_position']
    view.CameraFocalPoint = render['q_camera_focal_point']
    view.CameraViewUp = render['q_camera_view_up']
    view.CameraParallelScale = render['q_camera_parallel_scale']
    pv.Render(view)
    pv.SaveScreenshot(str(output), view, ImageResolution=render['_active_resolution'], CompressionLevel='5')
    return surface, view, clips, pipeline


def main():
    args = arguments()
    started = time.monotonic()
    config = json.loads(args.config_json.read_text(encoding='utf-8'))
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    figures, data, states = output / 'figures', output / 'data', output / 'states'
    for directory in (figures, data, states):
        directory.mkdir()
    config['render']['_active_resolution'] = (config['render']['preview_resolution']
                                               if args.preview else config['render']['resolution'])
    config['render']['_active_font_size'] = max(16, round(
        config['render']['font_size'] * math.sqrt(config['render']['_active_resolution'][0] / 1280)))

    from paraview import simple as pv
    pv._DisableFirstRenderCameraReset()
    reader = pv.OpenFOAMReader(FileName=str(args.foam_marker.resolve(strict=True)))
    reader.CaseType = 'Decomposed Case'
    reader.MeshRegions = ['internalMesh']
    reader.CellArrays = config['case']['required_fields']
    selected, available_times = select_time(reader, float(config['case']['selected_time']))
    reader.UpdatePipeline(selected)
    merged = pv.MergeBlocks(Input=reader)
    merged.MergePoints = 1
    merged.UpdatePipeline(selected)
    input_info = merged.GetDataInformation()
    input_bounds = list(input_info.GetBounds())
    spans = [input_bounds[2 * i + 1] - input_bounds[2 * i] for i in range(3)]
    if sum(span > max(spans) * 1e-8 for span in spans) != 3:
        raise ValueError(f'Q* requires a true 3D mesh; bounds are {input_bounds}')

    gradient = pv.Gradient(Input=merged)
    gradient.ScalarArray = ['CELLS', 'U']
    gradient.ResultArrayName = 'gradU'
    gradient.ComputeVorticity = 1
    gradient.VorticityArrayName = 'Vorticity'
    gradient.ComputeQCriterion = 1
    gradient.QCriterionArrayName = 'Q'
    gradient.UpdatePipeline(selected)

    points = pv.CellDatatoPointData(Input=gradient)
    points.PassCellData = 0
    point_fields = pv.Calculator(Input=points)
    point_fields.AttributeType = 'Point Data'
    point_fields.ResultArrayName = 'Umag'
    point_fields.Function = 'mag(U)'
    point_qstar = pv.Calculator(Input=point_fields)
    point_qstar.AttributeType = 'Point Data'
    point_qstar.ResultArrayName = 'Qstar'
    scale = config['physics']['reference_length'] ** 2 / config['physics']['reference_velocity'] ** 2
    point_qstar.Function = f'Q*{scale:.17g}'
    point_qstar.UpdatePipeline(selected)

    z = config['render']['slice_origin'][2]
    plane = sampling_plane(pv, config['render']['roi'], z,
                           (640, 360) if args.preview else (1600, 900))
    sampled_slice = pv.ResampleWithDataset(SourceDataArrays=point_qstar, DestinationMesh=plane)
    sampled_slice.UpdatePipeline(selected)

    data_plane = sampling_plane(pv, config['render']['roi'], z, config['render']['data_resolution'])
    data_sample = pv.ResampleWithDataset(SourceDataArrays=point_qstar, DestinationMesh=data_plane)
    selected_data = pv.PassArrays(Input=data_sample)
    selected_data.PointDataArrays = ['U', 'Umag', 'Vorticity', 'Q', 'Qstar', 'vtkValidPointMask']
    selected_data.UpdatePipeline(selected)

    resolution_token = 'preview' if args.preview else 'final'
    velocity_file = figures / f'velocity_magnitude_t{selected:g}_{resolution_token}.png'
    vorticity_file = figures / f'vorticity_spanwise_t{selected:g}_{resolution_token}.png'
    q_file = figures / f'qcriterion_qstar{config["render"]["qstar_threshold"]:g}_t{selected:g}_{resolution_token}.png'
    velocity_view, velocity_pipeline = scalar_slice(
        pv, sampled_slice, config, 'Umag', None, config['render']['velocity_range'],
        f"{config['case'].get('display_name') or config['case']['id']}\n"
        f"Velocity magnitude | t={selected:g} s | z={z:g} m",
        '|U| [m/s]', velocity_file)
    vorticity_view, vorticity_pipeline = scalar_slice(
        pv, sampled_slice, config, 'Vorticity', 'Z', config['render']['vorticity_range'],
        f"{config['case'].get('display_name') or config['case']['id']}\n"
        f"Spanwise vorticity | t={selected:g} s | z={z:g} m",
        'omega_z [1/s]', vorticity_file)
    q_threshold = config['render']['qstar_threshold'] / scale
    q_surface, q_view, clips, q_pipeline = render_q(pv, points, config, q_threshold, q_file)

    pv.SaveData(str(data / f'centre_slice_t{selected:g}.csv'), proxy=selected_data, Precision=10)
    state = states / f'{config["case"]["id"]}_t{selected:g}.pvsm'
    pv.SaveState(str(state))
    window = q_view.GetClientSideObject().GetRenderWindow()
    capabilities = window.ReportCapabilities().splitlines()
    summary = {
        'selected_time': selected, 'available_times': available_times,
        'mesh_bounds': input_bounds, 'mesh_dimension': 3,
        'reader_cells': input_info.GetNumberOfCells(),
        'slice_cells': sampled_slice.GetDataInformation().GetNumberOfCells(),
        'q_surface_cells': q_surface.GetDataInformation().GetNumberOfCells(),
        'ranges': {'Umag_actual': data_range(sampled_slice, 'POINTS', 'Umag'),
                   'Vorticity_z_actual': data_range(sampled_slice, 'POINTS', 'Vorticity', 2),
                   'Q_actual': data_range(gradient, 'CELLS', 'Q')},
        'fixed_ranges': {'Umag': config['render']['velocity_range'],
                         'Vorticity_z': config['render']['vorticity_range']},
        'range_exceeded': {}, 'qstar_threshold': config['render']['qstar_threshold'],
        'q_dimensional_threshold': q_threshold,
        'pipeline': {'partition_handling': 'MergeBlocks with coincident-point merging before gradients',
                     'gradient': 'full 3D cell U before interpolation or slicing',
                     'interpolation': ('CellDataToPointData follows the 3D Gradient; field figures and '
                                       'CSV probe those point fields onto a uniform ROI plane'),
                     'slice': {'origin': config['render']['slice_origin'],
                               'normal': config['render']['slice_normal']},
                     'q_roi_clip': config['render']['roi'], 'phase_mask': None,
                     'geometry_simplification': 'analytic cylinder overlay only; no source-field simplification'},
        'resolution': config['render']['_active_resolution'], 'preview': args.preview,
        'data_resolution': config['render']['data_resolution'],
        'outputs': [str(path.relative_to(output)) for path in (velocity_file, vorticity_file, q_file,
                                                               data / f'centre_slice_t{selected:g}.csv', state)],
        'renderer': {'offscreen': bool(window.GetOffScreenRendering()),
                     'capabilities': capabilities[:3]},
        'elapsed_seconds': time.monotonic() - started,
    }
    for key, fixed in summary['fixed_ranges'].items():
        actual = summary['ranges']['Umag_actual' if key == 'Umag' else 'Vorticity_z_actual']
        summary['range_exceeded'][key] = actual[0] < fixed[0] or actual[1] > fixed[1]
    (data / 'render_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
