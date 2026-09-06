#!/usr/bin/env python3
"""Render publication-style 2D scalar fields from an audited plane CSV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle


def latex_symbol(symbol):
    return {'D': 'D', 'L_ref': r'L_{ref}', 'U_inf': r'U_\infty',
            'U_ref': r'U_{ref}'}.get(symbol, symbol)


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--config-json', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--preview', action='store_true')
    return parser.parse_args()


def load_plane(path: Path):
    data = np.genfromtxt(path, delimiter=',', names=True, encoding='utf-8')
    names = set(data.dtype.names or ())
    aliases = {
        'x': 'x' if 'x' in names else 'Points0',
        'y': 'y' if 'y' in names else 'Points1',
        'speed': 'Umag',
        'vorticity': 'Vorticity_z' if 'Vorticity_z' in names else 'Vorticity2',
    }
    missing = [name for name in aliases.values() if name not in names]
    if missing:
        raise ValueError(f'CSV lacks required columns: {missing}')
    order = np.lexsort((data[aliases['x']], data[aliases['y']]))
    x, y = data[aliases['x']][order], data[aliases['y']][order]
    unique_x, unique_y = np.unique(x), np.unique(y)
    shape = (unique_y.size, unique_x.size)
    if unique_x.size * unique_y.size != x.size:
        raise ValueError('plane CSV is not a complete rectilinear grid')
    return unique_x, unique_y, {
        'speed': data[aliases['speed']][order].reshape(shape),
        'vorticity': data[aliases['vorticity']][order].reshape(shape),
    }


def plot_field(x, y, values, config, *, key, title, symbol, panel, output, preview):
    reference_length = config['physics']['reference_length']
    center = config['physics']['body']['center']
    diameter = config['physics']['body']['diameter']
    render = config['render']
    limits = render[key]
    cmap = 'viridis' if key == 'velocity_star_range' else 'coolwarm'
    extend = 'neither' if values.min() >= limits[0] and values.max() <= limits[1] else 'both'
    dpi = 100 if preview else 200
    with plt.rc_context({
        'font.family': 'DejaVu Serif', 'font.size': 12 if preview else 15,
        'axes.linewidth': 0.9, 'xtick.direction': 'in', 'ytick.direction': 'in',
        'xtick.top': True, 'ytick.right': True, 'xtick.major.size': 5, 'ytick.major.size': 5,
    }):
        figure_size = (12.0, 6.75) if preview else (16.0, 9.0)
        fig, axis = plt.subplots(figsize=figure_size, constrained_layout=True)
        image = axis.pcolormesh(x / reference_length, y / reference_length, values, shading='auto',
                                cmap=cmap, vmin=limits[0], vmax=limits[1], rasterized=True)
        axis.add_patch(Circle((center[0] / reference_length, center[1] / reference_length),
                              diameter / (2 * reference_length),
                              facecolor='#111820', edgecolor='white', linewidth=0.8, zorder=5))
        axis.set_aspect('equal', adjustable='box')
        coordinate_denominator = latex_symbol(
            config['physics'].get('reference_length_symbol', 'L_ref'))
        velocity_symbol = latex_symbol(
            config['physics'].get('reference_velocity_symbol', 'U_ref'))
        axis.set_xlabel(fr'$x/{coordinate_denominator}$', labelpad=2)
        axis.set_ylabel(fr'$y/{coordinate_denominator}$', labelpad=2)
        axis.text(0.015, 0.975, f'({panel})  {title}', transform=axis.transAxes,
                  ha='left', va='top', color='white', fontweight='bold',
                  bbox={'facecolor': '#102A43', 'edgecolor': 'none', 'alpha': 0.88, 'pad': 4})
        axis.annotate(fr'${velocity_symbol}$', xy=(0.12, 0.88), xytext=(0.025, 0.88),
                      xycoords='axes fraction', textcoords='axes fraction',
                      arrowprops={'arrowstyle': '->', 'lw': 1.2}, ha='center', va='center')
        bar = fig.colorbar(image, ax=axis, pad=0.015, fraction=0.035, aspect=28, extend=extend)
        bar.set_label(symbol, labelpad=5)
        bar.ax.tick_params(direction='in', pad=3)
        fig.savefig(output, dpi=dpi, bbox_inches='tight', facecolor='white')
        plt.close(fig)


def main():
    args = arguments()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.config_json.read_text(encoding='utf-8'))
    x, y, fields = load_plane(args.csv)
    length = config['physics']['reference_length']
    velocity = config['physics']['reference_velocity']
    length_symbol = latex_symbol(config['physics'].get('reference_length_symbol', 'L_ref'))
    velocity_symbol = latex_symbol(config['physics'].get('reference_velocity_symbol', 'U_ref'))
    fields['speed'] = fields['speed'] / velocity
    fields['vorticity'] = fields['vorticity'] * length / velocity
    suffix = 'preview' if args.preview else 'final'
    speed = output / f'velocity_magnitude_t300_paper_{suffix}.png'
    vort = output / f'vorticity_spanwise_t300_paper_{suffix}.png'
    plot_field(x, y, fields['speed'], config, key='velocity_star_range',
               title='Velocity magnitude', symbol=fr'$|\mathbf{{U}}|/{velocity_symbol}$', panel='a',
               output=speed, preview=args.preview)
    plot_field(x, y, fields['vorticity'], config, key='vorticity_star_range',
               title='Spanwise vorticity',
               symbol=fr'$\omega_z {length_symbol}/{velocity_symbol}$', panel='b',
               output=vort, preview=args.preview)
    summary = {
        'input': str(args.csv.resolve()), 'outputs': [speed.name, vort.name],
        'nondimensionalization': {
            'coordinates': 'x* = x/L_ref, y* = y/L_ref',
            'velocity': '|U|* = |U|/U_ref',
            'vorticity': 'omega* = omega L_ref/U_ref',
            'reference_length': length, 'reference_velocity': velocity,
        }, 'colorbar_pad_fraction': 0.015,
        'interpolation': 'none beyond pcolormesh display of the audited rectilinear probe',
        'smoothing': None, 'actual_ranges': {
            'speed_star': [float(np.nanmin(fields['speed'])), float(np.nanmax(fields['speed']))],
            'vorticity_star': [float(np.nanmin(fields['vorticity'])), float(np.nanmax(fields['vorticity']))],
        }, 'fixed_ranges': {'speed_star': config['render']['velocity_star_range'],
                            'vorticity_star': config['render']['vorticity_star_range']},
        'preview': args.preview,
    }
    (output / 'paper_layout_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
