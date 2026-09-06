from __future__ import annotations

import html
from pathlib import Path


def write_gallery(output: Path, *, title: str, entries: list[dict]) -> None:
    cards = []
    for item in entries:
        cards.append(
            '<article><a href="{href}"><img src="{href}" alt="{alt}"></a>'
            '<div><h2>{name}</h2><p>{caption}</p></div></article>'.format(
                href=html.escape(item['path'], quote=True), alt=html.escape(item['alt'], quote=True),
                name=html.escape(item['name']), caption=html.escape(item['caption'])))
    document = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title}</title><style>
:root{{--ink:#16202a;--navy:#102a43;--cyan:#22a6b3;--paper:#fbfcfe;--line:#cdd5df}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 Arial,sans-serif}}
header,main{{width:min(1500px,94vw);margin:auto}}header{{padding:42px 0 20px;border-bottom:3px solid var(--cyan)}}
h1{{margin:0;color:var(--navy);font-size:clamp(30px,4vw,52px)}}header p{{max-width:78ch}}
main{{padding:30px 0 60px;display:grid;gap:28px}}article{{background:white;border:1px solid var(--line)}}
article img{{display:block;width:100%;height:auto}}article div{{padding:18px 22px}}h2{{margin:0 0 7px;color:var(--navy)}}p{{margin:0}}
</style></head><body><header><h1>{title}</h1><p>Fixed scales and a single completed time step. Open an image for the full-resolution file. Read manifest.json and qa_report.md before reusing a scientific claim.</p></header><main>{cards}</main></body></html>'''.format(
        title=html.escape(title), cards=''.join(cards))
    output.write_text(document, encoding='utf-8')
