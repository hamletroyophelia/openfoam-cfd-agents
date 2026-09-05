"""Opt-in Linux/OpenFOAM inspection; creates only the explicit output file.

No solver launch, dictionary modification, signals, mesh reads or field hashes.
Invoke under an environment with the package and Foundation v14 loaded.
"""

import argparse
import json
import platform
import subprocess
import time
from pathlib import Path

from openfoam_cfd_agents import __version__
from openfoam_cfd_agents.agents.monitor import MonitorAgent, MonitorThresholds, parse_solver_log
from openfoam_cfd_agents.reliability.checkpoints import inspect_checkpoint, parse_field_list
from openfoam_cfd_agents.reliability.live import read_log_tail
from openfoam_cfd_agents.reliability.progress import observe_progress
from openfoam_cfd_agents.reliability.resources import parse_cpu_list, parse_cpu_topology, validate_cpu_allocation
from openfoam_cfd_agents.reliability.runtime import probe_runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--solver-module', required=True)
    parser.add_argument('--processes', type=int, required=True)
    parser.add_argument('--cpus', required=True)
    parser.add_argument('--reserved-cpus', default='')
    parser.add_argument('--checkpoint')
    parser.add_argument('--fields', required=True)
    parser.add_argument('--vof', action='store_true')
    parser.add_argument('--expect-health', choices=['passed', 'failed'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.case.resolve()
    runtime = probe_runtime(args.solver_module)
    topology = parse_cpu_topology(subprocess.run(['lscpu', '-p=CPU,CORE,SOCKET,NODE'],
                                                capture_output=True, text=True, check=True).stdout)
    allocation = validate_cpu_allocation(parse_cpu_list(args.cpus), topology,
                                          reserved_cpus=parse_cpu_list(args.reserved_cpus) if args.reserved_cpus else [])
    fields = parse_field_list(args.fields)
    checkpoint = inspect_checkpoint(root, processes=args.processes, required_fields=fields,
                                    time_name=args.checkpoint)
    thresholds = MonitorThresholds(max_courant=0.9 if args.vof else 1,
                                   max_interface_courant=0.55 if args.vof else None,
                                   alpha_tolerance=2e-6 if args.vof else None)
    observations = []
    state = None
    for index in range(2):
        if index:
            time.sleep(12)
        text, offset = read_log_tail(root / 'log.solver')
        summary = parse_solver_log(text)
        numerical = MonitorAgent(thresholds).evaluate_summary(summary)
        bindings = []
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if (proc / 'comm').read_text().strip() != 'foamRun' or (proc / 'cwd').resolve() != root:
                    continue
                line = next(l for l in (proc / 'status').read_text().splitlines() if l.startswith('Cpus_allowed_list:'))
                bindings.append(parse_cpu_list(line.split(':', 1)[1].strip()))
            except (OSError, StopIteration):
                continue
        progress, state = observe_progress(state, job_id=args.label, latest_completed_time=summary.completed_times[-1]
                                           if summary.completed_times else None, now=time.time(),
                                           process_alive=len(bindings) == args.processes)
        observations.append({'latest_started_time': summary.latest_time,
                             'latest_completed_time': state.latest_completed_time, 'log_offset': offset,
                             'numerical_status': numerical.status.value, 'fatal_count': summary.fatal_error_count,
                             'failed_numerical_checks': [c.model_dump(mode='json') for c in numerical.checks if not c.passed],
                             'nonfinite_count': summary.nonfinite_samples, 'max_courant': summary.max_courant,
                             'rank_count': len(bindings),
                             'affinity_exact': sorted(bindings) == [[c] for c in sorted(parse_cpu_list(args.cpus))],
                             'progress_status': progress.status.value})
    actual = 'passed' if numerical.status.value == 'passed' and progress.status.value == 'passed' else 'failed'
    evidence = {'package_version': __version__, 'python': platform.python_version(), 'platform': platform.system(),
                'case_label': args.label, 'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'evidence_kind': 'live_read_only_inspection', 'solver_launched': False,
                'monitor_thresholds': thresholds.model_dump(mode='json'),
                'runtime': runtime.model_dump(mode='json'), 'allocation': allocation.model_dump(mode='json'),
                'checkpoint': {'status': checkpoint.status.value, 'selected_time': checkpoint.metrics['selected_time'],
                               'required_field_count': len(fields), 'processes': args.processes,
                               'rejection_count': len(checkpoint.metrics['rejected_candidates'])},
                'observations': observations, 'expected_health': args.expect_health, 'actual_health': actual,
                'expectation_met': actual == args.expect_health}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(evidence, indent=2))
    return 0 if (evidence['expectation_met'] and runtime.status.value == 'passed'
                 and allocation.status.value == 'passed' and checkpoint.status.value == 'passed'
                 and all(o['affinity_exact'] for o in observations)) else 2


if __name__ == '__main__':
    raise SystemExit(main())
