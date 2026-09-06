from __future__ import annotations

import math
from collections.abc import Sequence

from .config import VisualizationConfig


def assess_animation_times(config: VisualizationConfig,
                           available_dimensional_times: Sequence[float]) -> dict:
    animation = config.animation
    if not animation.enabled:
        raise ValueError('animation is disabled in viz.yaml')
    if len(available_dimensional_times) != len(set(available_dimensional_times)):
        raise ValueError('available times contain duplicates')
    if any(not math.isfinite(value) for value in available_dimensional_times):
        raise ValueError('available times contain non-finite values')
    if any(right <= left for left, right in
           zip(available_dimensional_times, available_dimensional_times[1:])):
        raise ValueError('available times must be strictly increasing in source order')

    scale = config.physics.reference_velocity / config.physics.reference_length
    times_star = [value * scale for value in available_dimensional_times]
    start, stop = animation.window_star or (0.0, 0.0)
    selected = [value for value in times_star if start <= value <= stop]
    if len(selected) < 2:
        raise ValueError('animation window contains fewer than two saved times')
    gaps = [right - left for left, right in zip(selected, selected[1:])]
    maximum_gap = max(gaps)
    minimum_gap = min(gaps)
    uniform = math.isclose(maximum_gap, minimum_gap, rel_tol=1e-6, abs_tol=1e-12)

    limits: list[tuple[str, float]] = []
    if animation.target_delta_time_star is not None:
        limits.append(('configured target', animation.target_delta_time_star))
    frames_per_period = None
    if animation.reference_strouhal is not None:
        period_star = 1.0 / animation.reference_strouhal
        frequency_limit = period_star / animation.minimum_frames_per_period
        limits.append(('frames per period', frequency_limit))
        frames_per_period = period_star / maximum_gap
    allowed_gap = min(value for _, value in limits)
    covers_window = (math.isclose(selected[0], start, rel_tol=0, abs_tol=1e-9)
                     and math.isclose(selected[-1], stop, rel_tol=0, abs_tol=1e-9))
    passed = maximum_gap <= allowed_gap * (1 + 1e-9) and covers_window
    return {
        'continuous_animation_allowed': passed,
        'classification': 'continuous_animation' if passed else 'coarse_temporal_comparison_only',
        'source_times_dimensional': list(available_dimensional_times),
        'selected_times_star': selected,
        'window_star': [start, stop],
        'frame_count': len(selected),
        'covers_configured_window': covers_window,
        'delta_time_star': {'minimum': minimum_gap, 'maximum': maximum_gap, 'uniform': uniform},
        'allowed_maximum_delta_time_star': allowed_gap,
        'reference_strouhal': animation.reference_strouhal,
        'minimum_frames_per_period': animation.minimum_frames_per_period,
        'actual_frames_per_period_using_max_gap': frames_per_period,
        'nyquist_strouhal_using_max_gap': 1.0 / (2.0 * maximum_gap),
        'output_fps': animation.output_fps,
        'interpolation': animation.interpolation,
        'warning': (None if passed else
                    'saved fields are too sparse or do not cover the configured window; '
                    'do not interpolate or duplicate frames'),
    }
