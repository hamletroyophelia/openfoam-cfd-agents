from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from scipy import stats as scipy_stats


COLUMNS = ('time', 'Cm', 'Cd', 'Cl', 'Cl_f', 'Cl_r')


def read_force_coefficients(path: Path) -> dict[str, np.ndarray]:
    rows = []
    for number, raw in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        values = line.split()
        if len(values) < len(COLUMNS):
            raise ValueError(f'{path}:{number}: expected six force-coefficient columns')
        row = tuple(float(value) for value in values[:len(COLUMNS)])
        if not all(math.isfinite(value) for value in row):
            raise ValueError(f'{path}:{number}: non-finite force value')
        rows.append(row)
    if not rows:
        raise ValueError(f'no force rows: {path}')
    data = np.asarray(rows, dtype=float)
    delta = np.diff(data[:, 0])
    if np.any(delta < 0):
        raise ValueError(f'time regression in {path}')
    for index in np.flatnonzero(delta == 0):
        if not np.array_equal(data[index], data[index + 1]):
            raise ValueError(f'conflicting duplicate time {data[index, 0]} in {path}')
    keep = np.concatenate(([True], delta > 0))
    return {name: data[keep, column] for column, name in enumerate(COLUMNS)}


def merge_force_segments(segments: list[tuple[Path, float | None, float | None]]) -> dict[str, np.ndarray]:
    combined = []
    for path, start, stop in segments:
        resolved = path.resolve(strict=True)
        values = read_force_coefficients(resolved)
        mask = np.ones(values['time'].size, dtype=bool)
        if start is not None:
            mask &= values['time'] >= start
        if stop is not None:
            mask &= values['time'] < stop
        for index in np.flatnonzero(mask):
            combined.append((values['time'][index], *(values[name][index] for name in COLUMNS[1:]), str(resolved)))
    combined.sort(key=lambda row: row[0])
    if not combined:
        raise ValueError('merge rules selected no force samples')
    deduplicated = []
    for row in combined:
        if deduplicated and row[0] == deduplicated[-1][0]:
            if row[1:-1] != deduplicated[-1][1:-1]:
                raise ValueError(f'conflicting duplicate time {row[0]} across force segments')
            continue
        deduplicated.append(row)
    array = np.asarray([row[:-1] for row in deduplicated], dtype=float)
    return {**{name: array[:, index] for index, name in enumerate(COLUMNS)},
            'source': np.asarray([row[-1] for row in deduplicated], dtype=str)}


def _effective_sample_size(values: np.ndarray) -> tuple[float, float]:
    centered = values - np.mean(values)
    variance = float(np.dot(centered, centered))
    if variance == 0 or values.size < 4:
        return float(values.size), 0.0
    correlation = np.correlate(centered, centered, mode='full')[values.size - 1:] / variance
    positive_sum = 0.0
    for lag in range(1, correlation.size):
        if correlation[lag] <= 0:
            break
        positive_sum += float(correlation[lag])
    tau_samples = 1 + 2 * positive_sum
    return max(1.0, values.size / tau_samples), tau_samples


def time_weighted_statistics(time_values: np.ndarray, values: np.ndarray,
                             *, confidence_level: float) -> dict:
    if time_values.size != values.size or time_values.size < 2:
        raise ValueError('statistics require matching arrays with at least two rows')
    steps = np.diff(time_values)
    if np.any(steps <= 0) or not np.all(np.isfinite(values)):
        raise ValueError('statistics require finite values and strictly increasing time')
    duration = float(time_values[-1] - time_values[0])
    mean = float(np.trapezoid(values, time_values) / duration)
    variance = float(np.trapezoid((values - mean) ** 2, time_values) / duration)
    uniform = bool(np.allclose(steps, np.median(steps), rtol=1e-6, atol=1e-12))
    effective, tau_samples = _effective_sample_size(values) if uniform else (0.0, float('nan'))
    interval = None
    warning = 'insufficient independent samples for a defensible confidence interval'
    # A short autocorrelation estimate can be optimistic for a periodic wake.
    # Require at least fifty effective observations before reporting an interval.
    if uniform and effective >= 50 and values.size >= 40:
        sem = math.sqrt(variance / effective)
        critical = float(scipy_stats.t.ppf((1 + confidence_level) / 2, max(1, effective - 1)))
        interval = [mean - critical * sem, mean + critical * sem]
        warning = None
    return {'mean': mean, 'standard_deviation': math.sqrt(variance),
            'time_start': float(time_values[0]), 'time_end': float(time_values[-1]),
            'duration': duration, 'confidence_level': confidence_level,
            'confidence_interval': interval, 'effective_sample_size': effective or None,
            'integrated_autocorrelation_samples': tau_samples if math.isfinite(tau_samples) else None,
            'uncertainty_warning': warning,
            'sampling': {'count': int(time_values.size), 'uniform': uniform,
                         'minimum_interval': float(np.min(steps)), 'maximum_interval': float(np.max(steps)),
                         'median_interval': float(np.median(steps))}}
