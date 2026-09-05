"""Bounded log sampling and Linux process identity for read-only observations."""

from __future__ import annotations

from pathlib import Path


def read_log_tail(path: Path, *, max_bytes: int = 2 * 1024 * 1024) -> tuple[str, int]:
    if max_bytes < 1024:
        raise ValueError('log sample must be at least 1024 bytes')
    with path.open('rb') as stream:
        size = stream.seek(0, 2)
        offset = max(0, size - max_bytes)
        stream.seek(offset)
        if offset:
            stream.readline()  # omit a partial first record
            offset = stream.tell()
        return stream.read(max_bytes).decode('utf-8', errors='replace'), offset


def linux_process_identity(pid: int, *, proc_root: Path = Path('/proc')) -> str | None:
    if pid <= 0:
        raise ValueError('PID must be positive')
    if not proc_root.is_dir():
        raise ValueError('process identity inspection requires Linux /proc')
    try:
        stat = (proc_root / str(pid) / 'stat').read_text()
        fields = stat.rsplit(')', 1)[1].split()
        if fields[0] in {'Z', 'X'}:
            return None
        boot = (proc_root / 'sys/kernel/random/boot_id').read_text().strip()
        return f'{boot}:{pid}:{fields[19]}'
    except (FileNotFoundError, ProcessLookupError):
        return None
