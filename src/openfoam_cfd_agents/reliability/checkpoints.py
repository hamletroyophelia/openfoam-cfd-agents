"""Conservative checkpoint inspection without loading or hashing volume fields."""

from __future__ import annotations

import math
import json
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openfoam_cfd_agents.domain import MetricRule, StageResult, evaluate_stage


def parse_field_list(text: str) -> list[str]:
    """JSON arrays preserve commas in OpenFOAM time-scheme field names."""
    fields = json.loads(text) if text.lstrip().startswith('[') else text.split(',')
    if not isinstance(fields, list) or not fields or not all(isinstance(f, str) and _plain_name(f) for f in fields):
        raise ValueError('fields must be a JSON string array or comma-separated simple names')
    return fields


def _time_value(name: str) -> Decimal | None:
    if not re.fullmatch(r'[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', name):
        return None
    try:
        value = Decimal(name)
        return value if value.is_finite() and value >= 0 else None
    except InvalidOperation:
        return None


def _plain_name(name: str) -> bool:
    return bool(name and name not in {'.', '..'} and not any(c in name for c in '/\\\x00'))


def _read_state(path: Path, time_name: str) -> tuple[str, ...]:
    if path.stat().st_size > 65536:
        raise ValueError('uniform/time is unexpectedly large')
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    values = {}
    for key in ('value', 'name', 'index', 'deltaT', 'deltaT0'):
        matches = re.findall(rf'\b{key}\s+([^;]+);', text)
        if len(matches) != 1:
            raise ValueError(f'uniform/time requires one {key}')
        values[key] = matches[0].strip().strip('"')
    numeric = {k: Decimal(values[k]) for k in ('value', 'index', 'deltaT', 'deltaT0')}
    if not all(v.is_finite() for v in numeric.values()):
        raise ValueError('non-finite uniform/time state')
    if values['name'] != time_name or not math.isclose(float(numeric['value']), float(time_name), rel_tol=1e-10, abs_tol=1e-12):
        raise ValueError('uniform/time value/name does not match checkpoint directory')
    if numeric['index'] < 0 or numeric['index'] != numeric['index'].to_integral() or min(numeric['deltaT'], numeric['deltaT0']) <= 0:
        raise ValueError('invalid time index or step size')
    return tuple(str(numeric[k].normalize()) for k in ('value', 'index', 'deltaT', 'deltaT0'))


def _check_field(path: Path, name: str) -> None:
    with path.open('rb') as stream:
        header = stream.read(8192).decode('utf-8', errors='replace')
        stream.seek(max(0, path.stat().st_size - 256))
        ending = stream.read()
    if 'FoamFile' not in header or not re.search(r'\bobject\s+"?' + re.escape(name) + r'"?\s*;', header):
        raise ValueError(f'{name}: missing/mismatched OpenFOAM field header')
    if not re.search(rb'//\s*\*{10,}\s*//\s*$', ending):
        raise ValueError(f'{name}: missing OpenFOAM end marker (possibly truncated)')


def _inspect_candidate(root: Path, ranks: list[Path], name: str, fields: list[str], now: float, min_age: float) -> None:
    reference = None
    for rank in ranks:
        checkpoint = rank / name
        if checkpoint.is_symlink():
            raise ValueError('checkpoint directory is a symlink')
        for relative in [*fields, 'uniform/time']:
            f = checkpoint / relative
            if not f.resolve().is_relative_to(root) or f.is_symlink():
                raise ValueError('checkpoint path escapes case or is a symlink')
            stat = f.stat()
            if not f.is_file() or stat.st_size == 0 or now - stat.st_mtime < min_age:
                raise ValueError(f'{rank.name}/{name}/{relative}: empty, non-file, or too recent')
            if relative != 'uniform/time':
                _check_field(f, relative)
        state = _read_state(checkpoint / 'uniform/time', name)
        if reference is not None and state != reference:
            raise ValueError(f'{rank.name}: uniform/time differs across partitions')
        reference = state


def inspect_checkpoint(case_path: Path, *, processes: int, required_fields: list[str],
                       time_name: str | None = None, min_age_seconds: float = 30,
                       now: float | None = None) -> StageResult:
    """Select an uncompressed, uncollated checkpoint candidate; never authorize restart.

    Checks headers, end markers, nonempty required fields and consistent time state.
    This deliberately does not claim full binary payload or scientific validation.
    The caller must stop writers and recheck before any restart.
    """
    if isinstance(processes, bool) or processes < 1 or not required_fields:
        raise ValueError('positive processes and explicit required fields are required')
    if not all(_plain_name(f) for f in required_fields) or len(set(required_fields)) != len(required_fields):
        raise ValueError('required fields must be unique simple filenames')
    if time_name is not None and _time_value(time_name) is None:
        raise ValueError('checkpoint time must be a nonnegative finite directory name')
    if not math.isfinite(min_age_seconds) or min_age_seconds < 0:
        raise ValueError('minimum checkpoint age must be finite and nonnegative')
    if now is not None and not math.isfinite(now):
        raise ValueError('inspection clock must be finite')
    root = case_path.resolve(strict=True)
    ranks = [root / f'processor{i}' for i in range(processes)] if processes > 1 else [root]
    found = {p.name for p in root.iterdir() if re.fullmatch(r'processor\d+', p.name)}
    expected = {p.name for p in ranks} if processes > 1 else set()
    rejected = []
    selected = None
    collated = any(re.fullmatch(r'processors\d+(?:_.*)?', p.name) for p in root.iterdir())
    if collated or found != expected or any(not p.is_dir() or p.is_symlink() for p in ranks):
        rejected.append({'time': None, 'reason': 'decomposition does not match requested ranks'})
    else:
        candidates = [time_name] if time_name else sorted(
            {p.name for rank in ranks for p in rank.iterdir() if p.is_dir() and _time_value(p.name) is not None},
            key=lambda n: (_time_value(n), n), reverse=True)
        for candidate in candidates:
            try:
                _inspect_candidate(root, ranks, candidate, required_fields,
                                   time.time() if now is None else now, min_age_seconds)
                selected = candidate
                break
            except (OSError, ValueError, InvalidOperation) as exc:
                rejected.append({'time': candidate, 'reason': str(exc)})
    return evaluate_stage(stage='checkpoint_inspection', metrics={
        'candidate_available': int(selected is not None), 'selected_time': selected,
        'processes': processes, 'required_fields': required_fields, 'rejected_candidates': rejected,
        'evidence_kind': 'field_framing_and_time_metadata', 'requires_stopped_writer_recheck': True,
    }, rules=[MetricRule(metric='candidate_available', operator='==', threshold=1)])
