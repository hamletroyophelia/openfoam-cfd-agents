from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .config import VisualizationConfig
from .forces import COLUMNS, merge_force_segments, time_weighted_statistics


def plot_cd_history(config: VisualizationConfig,
                    segments: list[tuple[Path, float | None, float | None]],
                    output_dir: Path, *, style: Path | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    data_dir, figure_dir = output_dir / 'data', output_dir / 'figures'
    data_dir.mkdir()
    figure_dir.mkdir()
    series = merge_force_segments(segments)
    time_scale = config.physics.reference_velocity / config.physics.reference_length
    time_star = series['time'] * time_scale
    start, stop = config.statistics.window
    selected = (series['time'] >= start) & (series['time'] <= stop)
    if np.count_nonzero(selected) < 4:
        raise ValueError('statistics window has fewer than four force samples')
    statistics = time_weighted_statistics(series['time'][selected], series['Cd'][selected],
                                          confidence_level=config.statistics.confidence_level)
    with (data_dir / 'force_coefficients.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow((*COLUMNS, 'source'))
        writer.writerows(zip(*(series[name] for name in COLUMNS), series['source']))

    context = plt.style.context(str(style)) if style else plt.style.context('default')
    with context:
        fig, (overview, window) = plt.subplots(
            2, 1, figsize=(16, 9), constrained_layout=True,
            gridspec_kw={'height_ratios': [1, 2]}, sharex=False)
        label = config.case.display_name or config.case.id
        start_star, stop_star = start * time_scale, stop * time_scale
        overview.plot(time_star, series['Cd'], color='#0F5B90', linewidth=1.0,
                      label=r'raw $C_d$ (all samples)')
        overview.axvspan(start_star, stop_star, color='#22A6B3', alpha=0.14,
                        label=fr'statistics window $t^*\in[{start_star:g}, {stop_star:g}]$')
        overview.set(xlabel=r'$t^*=tU_{ref}/L_{ref}$', ylabel=r'$C_d$',
                     title=f'{label}: complete raw history, including startup impulses')
        overview.legend(loc='upper right')
        window.plot(time_star[selected], series['Cd'][selected], color='#0F5B90',
                    linewidth=1.15, label=r'raw $C_d$ in statistics window')
        window.axhline(statistics['mean'], color='#BF573A', linewidth=1.4, linestyle='--',
                       label=fr'time-weighted mean = {statistics["mean"]:.5f}')
        window.set(xlabel=r'$t^*=tU_{ref}/L_{ref}$', ylabel=r'$C_d$',
                   title='Unsmoothed statistics window')
        window.legend(loc='best')
        for axis in (overview, window):
            axis.margins(x=0)
        for suffix in ('png', 'svg', 'pdf'):
            fig.savefig(figure_dir / f'cd_history.{suffix}', dpi=200 if suffix == 'png' else None)
        plt.close(fig)
    summary = {
        'quantity': 'Cd', 'transform': 'Cd is already dimensionless; raw samples retained',
        'horizontal_axis': {
            'quantity': 't_star', 'formula': 't* = t U_ref / L_ref',
            'reference_length': config.physics.reference_length,
            'reference_velocity': config.physics.reference_velocity,
            'statistics_window_dimensional': [start, stop],
            'statistics_window_nondimensional': [start * time_scale, stop * time_scale],
        },
        'merge_rules': [{'path': str(path.resolve()), 'start_inclusive': start_value,
                         'stop_exclusive': stop_value}
                        for path, start_value, stop_value in segments],
        'total_samples': int(series['time'].size), 'missing_values': 0,
        'time_regressions_after_merge': int(np.count_nonzero(np.diff(series['time']) <= 0)),
        'raw_extrema': {
            'minimum': float(np.min(series['Cd'])),
            'minimum_time': float(series['time'][np.argmin(series['Cd'])]),
            'maximum': float(np.max(series['Cd'])),
            'maximum_time': float(series['time'][np.argmax(series['Cd'])]),
            'handling': 'retained in the overview; no clipping or smoothing',
        },
        'statistics': statistics,
        'outputs': ['figures/cd_history.png', 'figures/cd_history.svg',
                    'figures/cd_history.pdf', 'data/force_coefficients.csv'],
    }
    (output_dir / 'force_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary
