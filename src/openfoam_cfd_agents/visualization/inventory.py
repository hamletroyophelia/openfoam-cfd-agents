from __future__ import annotations

import re
import time
from pathlib import Path

from .config import VisualizationConfig


_PROCESSOR = re.compile(r'^processor(\d+)$')


def _time_metadata(path: Path) -> tuple[float, str]:
    text = path.read_text(encoding='utf-8', errors='replace')
    value = re.search(r'\bvalue\s+([^;]+);', text)
    name = re.search(r'\bname\s+"([^"]+)"\s*;', text)
    if not value or not name:
        raise ValueError(f'incomplete OpenFOAM time metadata: {path}')
    return float(value.group(1)), name.group(1)


def inspect_decomposed_time(case_path: Path, config: VisualizationConfig | dict,
                            *, safety_age_seconds: float = 30) -> dict:
    cfg = config if isinstance(config, VisualizationConfig) else VisualizationConfig.model_validate(config)
    root = case_path.resolve(strict=True)
    numbered = []
    for path in root.iterdir():
        match = _PROCESSOR.fullmatch(path.name)
        if match and path.is_dir():
            numbered.append((int(match.group(1)), path))
    numbered.sort()
    actual = [rank for rank, _ in numbered]
    expected = list(range(cfg.case.expected_partitions))
    if actual != expected:
        raise ValueError(f'processor inventory mismatch: expected {expected}, found {actual}')
    now = time.time()
    selected = cfg.case.selected_time
    metadata = []
    oldest_age = float('inf')
    for rank, processor in numbered:
        directory = processor / selected
        required = [directory / field for field in cfg.case.required_fields]
        time_file = directory / 'uniform/time'
        missing = [str(path.relative_to(root)) for path in [*required, time_file] if not path.is_file()]
        if missing:
            raise ValueError(f'partition {rank} missing selected-time inputs: {missing}')
        ages = [now - path.stat().st_mtime for path in [*required, time_file]]
        oldest_age = min(oldest_age, *ages)
        if min(ages) < safety_age_seconds:
            raise ValueError(f'partition {rank} selected time may still be written')
        value, name = _time_metadata(time_file)
        if name != selected or not abs(value - float(selected)) <= 1e-9 * max(1, abs(value)):
            raise ValueError(f'partition {rank} mixes time metadata: value={value}, name={name}')
        metadata.append({'rank': rank, 'time_value': value, 'time_name': name,
                         'fields': list(cfg.case.required_fields)})
    return {'status': 'passed', 'case_path': str(root), 'selected_time': selected,
            'expected_partitions': cfg.case.expected_partitions, 'actual_partitions': len(numbered),
            'read_partitions': len(metadata), 'postprocess_processes': cfg.resources.processes,
            'required_fields': list(cfg.case.required_fields), 'minimum_input_age_seconds': oldest_age,
            'partitions': metadata}
