"""CPU topology checks; Linux CPU ids are never assumed to equal physical cores."""

from __future__ import annotations

import csv
import re
from pydantic import BaseModel, ConfigDict, Field

from openfoam_cfd_agents.domain import MetricRule, StageResult, evaluate_stage


class Cpu(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    cpu: int = Field(ge=0)
    core: int = Field(ge=0)
    socket: int = Field(ge=0)
    node: int = Field(ge=-1)


def parse_cpu_list(text: str) -> list[int]:
    values = []
    for token in text.split(','):
        if not re.fullmatch(r'\d+(?:-\d+)?', token):
            raise ValueError('CPU list must contain integers or ascending ranges')
        bounds = [int(v) for v in token.split('-')]
        start, end = bounds[0], bounds[-1]
        if start > end or end - start > 65536:
            raise ValueError('invalid or oversized CPU range')
        values.extend(range(start, end + 1))
    if len(values) != len(set(values)):
        raise ValueError('duplicate CPU ids')
    return values


def parse_cpu_topology(text: str) -> list[Cpu]:
    rows = csv.reader(line for line in text.splitlines() if line.strip() and not line.startswith('#'))
    cpus = [Cpu(cpu=int(r[0]), core=int(r[1]), socket=int(r[2]), node=int(r[3]) if r[3] else -1) for r in rows]
    if len(cpus) != len({c.cpu for c in cpus}):
        raise ValueError('duplicate CPU topology records')
    return cpus


def validate_cpu_allocation(cpu_ids: list[int], topology: list[Cpu], *,
                            reserved_cpus: list[int] | None = None) -> StageResult:
    cpus = {c.cpu: c for c in topology}
    reserved = reserved_cpus or []
    unknown = [c for c in [*cpu_ids, *reserved] if c not in cpus]
    cores = [(cpus[c].socket, cpus[c].core) for c in cpu_ids if c in cpus]
    occupied = {(cpus[c].socket, cpus[c].core) for c in reserved if c in cpus}
    metrics = {'requested_cpus': cpu_ids, 'reserved_cpus': reserved, 'unknown_cpus': unknown,
               'nonempty': int(bool(cpu_ids)), 'unknown_count': len(unknown),
               'duplicate_or_smt_count': len(cpu_ids) - len(set(cores)),
               'occupied_core_count': len(set(cores) & occupied),
               'topology_unique': int(len(cpus) == len(topology))}
    return evaluate_stage(stage='cpu_allocation', metrics=metrics, rules=[
        MetricRule(metric='nonempty', operator='==', threshold=1),
        MetricRule(metric='topology_unique', operator='==', threshold=1),
        *[MetricRule(metric=k, operator='==', threshold=0) for k in
          ('unknown_count', 'duplicate_or_smt_count', 'occupied_core_count')]])
