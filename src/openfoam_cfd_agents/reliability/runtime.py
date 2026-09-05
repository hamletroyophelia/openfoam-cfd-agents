"""Probe the actual Foundation runtime without running a solver or case code."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from openfoam_cfd_agents.domain import MetricRule, StageResult, evaluate_stage


def probe_runtime(solver_module: str) -> StageResult:
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', solver_module):
        raise ValueError('solver module must be a simple identifier')
    executable = shutil.which('foamRun')
    help_text = ''
    error = ''
    if executable:
        try:
            response = subprocess.run([executable, '-help'], check=True, capture_output=True,
                                      text=True, encoding='utf-8', errors='replace', timeout=15)
            help_text = response.stdout + response.stderr
        except (OSError, subprocess.SubprocessError) as exc:
            error = type(exc).__name__
    library_root = os.environ.get('FOAM_LIBBIN')
    library_present = bool(library_root and (Path(library_root) / f'lib{solver_module}Solver.so').is_file())
    metrics = {'foundation_v14_help': int('OpenFOAM-14' in help_text and 'openfoam.org' in help_text),
               'version_environment': int(os.environ.get('WM_PROJECT_VERSION') == '14'),
               'module_library_present': int(library_present), 'solver_module': solver_module,
               'error': error, 'evidence_kind': 'runtime_availability_only'}
    return evaluate_stage(stage='runtime_capability', metrics=metrics, rules=[
        MetricRule(metric=k, operator='==', threshold=1) for k in
        ('foundation_v14_help', 'version_environment', 'module_library_present')])
