#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


def png_size(path: Path) -> tuple[int, int]:
    with path.open('rb') as stream:
        if stream.read(8) != b'\x89PNG\r\n\x1a\n':
            raise ValueError(f'not a PNG: {path}')
        length = struct.unpack('>I', stream.read(4))[0]
        if stream.read(4) != b'IHDR' or length < 8:
            raise ValueError(f'missing PNG IHDR: {path}')
        return struct.unpack('>II', stream.read(8))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    for item in manifest['artifacts']:
        path = (root / item['path']).resolve(strict=True)
        if path.stat().st_size != item['bytes']:
            raise ValueError(f'size mismatch: {item["path"]}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f'hash mismatch: {item["path"]}')
    expected_pngs = manifest['acceptance'].get('final_png_dimensions')
    if expected_pngs is None:
        expected_pngs = {relative: manifest['render']['resolution']
                         for relative in manifest['acceptance']['final_pngs']}
    for relative, expected in expected_pngs.items():
        if png_size(root / relative) != tuple(expected):
            raise ValueError(f'wrong final PNG dimensions: {relative}')
    print(f'validated {len(manifest["artifacts"])} artifacts')


if __name__ == '__main__':
    main()
