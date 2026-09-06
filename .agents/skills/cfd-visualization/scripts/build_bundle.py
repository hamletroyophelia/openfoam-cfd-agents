#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description='Build a deterministic CFD visualization manifest and gallery')
    parser.add_argument('root', type=Path)
    parser.add_argument('metadata', type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    metadata = json.loads(args.metadata.read_text(encoding='utf-8'))
    artifacts = []
    for relative in metadata.pop('artifact_paths'):
        path = (root / relative).resolve(strict=True)
        if root not in path.parents:
            raise ValueError(f'artifact escapes bundle: {relative}')
        artifacts.append({'path': relative.replace('\\', '/'), 'bytes': path.stat().st_size,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {**metadata, 'artifacts': artifacts}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

    cards = []
    for item in manifest['gallery']:
        cards.append('<article><a href="../{0}"><img src="../{0}" alt="{1}"></a>'
                     '<h2>{2}</h2><p>{3}</p></article>'.format(
                         html.escape(item['path'], quote=True), html.escape(item['alt'], quote=True),
                         html.escape(item['name']), html.escape(item['caption'])))
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>{0}</title><style>
:root{{--ink:#16202a;--navy:#102a43;--cyan:#22a6b3;--paper:#fbfcfe;--line:#cdd5df}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 Arial,sans-serif}}
header,main{{width:min(1500px,94vw);margin:auto}}header{{padding:40px 0 20px;border-bottom:3px solid var(--cyan)}}
main{{padding:30px 0 60px;display:grid;gap:28px}}article{{background:white;border:1px solid var(--line);padding:18px}}
img{{display:block;width:100%;height:auto}}h1,h2{{color:var(--navy)}}h2{{margin-bottom:4px}}p{{margin-top:0}}</style>
</head><body><header><h1>{0}</h1><p>One complete time step with fixed scales. Read manifest.json and qa_report.md before citing results.</p></header>
<main>{1}</main></body></html>'''.format(html.escape(manifest['title']), ''.join(cards))
    gallery = root / 'gallery' / 'index.html'
    gallery.parent.mkdir(exist_ok=True)
    gallery.write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()
