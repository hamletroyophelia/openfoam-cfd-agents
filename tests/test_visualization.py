from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


def config_payload():
    return {
        'schema_version': 2,
        'case': {'id': 'cylinder', 'selected_time': '300', 'expected_partitions': 2,
                 'required_fields': ['U', 'p'], 'format': 'decomposed'},
        'physics': {'reference_length': 2.0, 'reference_velocity': 1.0,
                    'streamwise': [1, 0, 0], 'cross_stream': [0, 1, 0],
                    'spanwise': [0, 0, 1], 'gravity': None,
                    'body': {'kind': 'cylinder', 'center': [0, 0, 0],
                             'diameter': 2.0, 'span': 8.0}},
        'render': {'slice_origin': [0, 0, 0], 'slice_normal': [0, 0, 1],
                   'roi': [-6, 18, -6.75, 6.75, -4, 4],
                   'resolution': [3200, 1800], 'preview_resolution': [1280, 720],
                   'velocity_star_range': [0, 1.5], 'vorticity_star_range': [-2, 2],
                   'qstar_threshold': 0.2},
        'statistics': {'window': [240, 300], 'confidence_level': 0.95},
        'resources': {'processes': 1, 'threads': 1, 'memory_gib': 12},
    }


def make_partition(root: Path, rank: int, time_name='300', *, age=60):
    directory = root / f'processor{rank}' / time_name
    (directory / 'uniform').mkdir(parents=True)
    (root / f'processor{rank}' / 'constant/polyMesh').mkdir(parents=True)
    for name in ('U', 'p'):
        (directory / name).write_text('FoamFile {}\n// ************************************************************************* //\n')
    (directory / 'uniform/time').write_text(
        f'value {time_name}; name "{time_name}"; index 30000; deltaT 0.01; deltaT0 0.01;')
    timestamp = time.time() - age
    for path in directory.rglob('*'):
        if path.is_file():
            path.touch()
            import os
            os.utime(path, (timestamp, timestamp))


def test_config_rejects_guessed_or_nonorthogonal_axes():
    from openfoam_cfd_agents.visualization.config import VisualizationConfig
    payload = config_payload()
    payload['physics']['cross_stream'] = [1, 0, 0]
    with pytest.raises(ValueError, match='orthonormal'):
        VisualizationConfig.model_validate(payload)
    payload = config_payload()
    payload['render']['velocity_star_range'] = [1, 0]
    with pytest.raises(ValueError):
        VisualizationConfig.model_validate(payload)


def test_inventory_distinguishes_reader_processes_from_all_partitions(tmp_path):
    from openfoam_cfd_agents.visualization.inventory import inspect_decomposed_time
    for rank in range(2):
        make_partition(tmp_path, rank)
    result = inspect_decomposed_time(tmp_path, config_payload(), safety_age_seconds=30)
    assert result['actual_partitions'] == 2
    assert result['read_partitions'] == 2
    assert result['postprocess_processes'] == 1
    assert result['selected_time'] == '300'
    assert result['status'] == 'passed'


@pytest.mark.parametrize('defect', ['missing_partition', 'mixed_time', 'active_write', 'missing_field'])
def test_inventory_never_accepts_partial_or_mutating_time(tmp_path, defect):
    from openfoam_cfd_agents.visualization.inventory import inspect_decomposed_time
    make_partition(tmp_path, 0)
    make_partition(tmp_path, 1)
    if defect == 'missing_partition':
        (tmp_path / 'processor1').rename(tmp_path / 'processor2')
    elif defect == 'mixed_time':
        (tmp_path / 'processor1/300/uniform/time').write_text(
            'value 299; name "300"; index 30000; deltaT 0.01; deltaT0 0.01;')
    elif defect == 'active_write':
        (tmp_path / 'processor1/300/U').touch()
    else:
        (tmp_path / 'processor1/300/U').unlink()
    with pytest.raises(ValueError):
        inspect_decomposed_time(tmp_path, config_payload(), safety_age_seconds=30)


def write_force(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('# Time Cm Cd Cl Cl(f) Cl(r)\n' + ''.join(
        f'{t} 0 {cd} {cl} 0 0\n' for t, cd, cl in rows))


def test_force_merge_rejects_conflicting_duplicates_and_records_branch(tmp_path):
    from openfoam_cfd_agents.visualization.forces import merge_force_segments
    old, recovery = tmp_path / 'old.dat', tmp_path / 'recovery.dat'
    write_force(old, [(0, 1, 0), (1, 2, 0), (1, 3, 0)])
    write_force(recovery, [(1, 4, 0), (2, 5, 0)])
    with pytest.raises(ValueError, match='conflicting duplicate'):
        merge_force_segments([(old, None, 1), (recovery, 1, None)])
    write_force(old, [(0, 1, 0), (1, 2, 0)])
    merged = merge_force_segments([(old, None, 1), (recovery, 1, None)])
    assert merged['time'].tolist() == [0, 1, 2]
    assert merged['Cd'].tolist() == [1, 4, 5]
    assert merged['source'].tolist() == [str(old.resolve()), str(recovery.resolve()), str(recovery.resolve())]


def test_time_weighted_statistics_do_not_invent_confidence_interval():
    import numpy as np
    from openfoam_cfd_agents.visualization.forces import time_weighted_statistics
    time_values = np.array([0.0, 1.0, 3.0])
    values = np.array([0.0, 2.0, 2.0])
    stats = time_weighted_statistics(time_values, values, confidence_level=0.95)
    assert stats['mean'] == pytest.approx(5 / 3)
    assert stats['sampling']['uniform'] is False
    assert stats['confidence_interval'] is None
    assert 'insufficient' in stats['uncertainty_warning']


def test_periodic_short_window_does_not_get_optimistic_interval():
    import numpy as np
    from openfoam_cfd_agents.visualization.forces import time_weighted_statistics
    time_values = np.arange(6001) * 0.01
    values = np.sin(2 * np.pi * 0.17 * time_values)
    stats = time_weighted_statistics(time_values, values, confidence_level=0.95)
    assert stats['effective_sample_size'] < 50
    assert stats['confidence_interval'] is None
