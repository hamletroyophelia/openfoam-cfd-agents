#!/usr/bin/env python3
"""Render publication-style 2D scalar fields from an audited plane CSV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle


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
    diameter = config['physics']['body']['diameter']
    center = config['physics']['body']['center']
    render = config['render']
    limits = render[key]
    cmap = 'viridis' if key == 'velocity_range' else 'coolwarm'
    extend = 'neither' if values.min() >= limits[0] and values.max() <= limits[1] else 'both'
    dpi = 100 if preview else 200
    with plt.rc_context({
        'font.family': 'DejaVu Serif', 'font.size': 12 if preview else 15,
        'axes.linewidth': 0.9, 'xtick.direction': 'in', 'ytick.direction': 'in',
        'xtick.top': True, 'ytick.right': True, 'xtick.major.size': 5, 'ytick.major.size': 5,
    }):
        figure_size = (12.0, 6.75) if preview else (16.0, 9.0)
        fig, axis = plt.subplots(figsize=figure_size, constrained_layout=True)
        image = axis.pcolormesh(x / diameter, y / diameter, values, shading='auto',
                                cmap=cmap, vmin=limits[0], vmax=limits[1], rasterized=True)
        axis.add_patch(Circle((center[0] / diameter, center[1] / diameter), 0.5,
                              facecolor='#111820', edgecolor='white', linewidth=0.8, zorder=5))
        axis.set_aspect('equal', adjustable='box')
        axis.set_xlabel(r'$x/D$', labelpad=2)
        axis.set_ylabel(r'$y/D$', labelpad=2)
        axis.text(0.015, 0.975, f'({panel})  {title}', transform=axis.transAxes,
                  ha='left', va='top', color='white', fontweight='bold',
                  bbox={'facecolor': '#102A43', 'edgecolor': 'none', 'alpha': 0.88, 'pad': 4})
        axis.annotate(r'$U_\infty$', xy=(-2.1, 2.55), xytext=(-2.85, 2.55),
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
    suffix = 'preview' if args.preview else 'final'
    speed = output / f'velocity_magnitude_t300_paper_{suffix}.png'
    vort = output / f'vorticity_spanwise_t300_paper_{suffix}.png'
    plot_field(x, y, fields['speed'], config, key='velocity_range',
               title='Velocity magnitude', symbol=r'$|\mathbf{U}|/U_\infty$', panel='a',
               output=speed, preview=args.preview)
    plot_field(x, y, fields['vorticity'], config, key='vorticity_range',
               title='Spanwise vorticity', symbol=r'$\omega_z D/U_\infty$', panel='b',
               output=vort, preview=args.preview)
    summary = {
        'input': str(args.csv.resolve()), 'outputs': [speed.name, vort.name],
        'coordinates': 'x/D and y/D', 'colorbar_pad_fraction': 0.015,
        'interpolation': 'none beyond pcolormesh display of the audited rectilinear probe',
        'smoothing': None, 'actual_ranges': {
            'speed': [float(np.nanmin(fields['speed'])), float(np.nanmax(fields['speed']))],
            'vorticity': [float(np.nanmin(fields['vorticity'])), float(np.nanmax(fields['vorticity']))],
        }, 'fixed_ranges': {'speed': config['render']['velocity_range'],
                            'vorticity': config['render']['vorticity_range']},
        'preview': args.preview,
    }
    (output / 'paper_layout_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
