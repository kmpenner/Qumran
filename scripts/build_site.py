#!/usr/bin/env python3
"""Build a static reading edition and concordance from the TEI.

Produces, under --out:

    index.html            scroll list with per-scroll figures
    search.html           client-side concordance search
    concordance.json      surface form -> occurrences
    scroll/<siglum>.html  the reading edition, one page per scroll

Rendering conventions follow print editions of the scrolls: reconstructed text
in half-brackets, uncertain letters dotted, lacunae as a centred ellipsis.
Everything is inline - no external requests - so the pages work offline and
from a file:// URL.

Usage:
    python3 build_site.py [--tei DIR] [--stats FILE] [--out DIR]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections import defaultdict
from xml.etree import ElementTree as ET

TEI = "{http://www.tei-c.org/ns/1.0}"

CSS = """
:root{--bg:#fbfaf7;--fg:#1c1a17;--muted:#6b645c;--rule:#ddd6cc;--accent:#7a5c3e;--sup:#8a6a44}
@media(prefers-color-scheme:dark){:root{--bg:#16150f;--fg:#ece7dd;--muted:#9b9287;--rule:#3a352c;--accent:#c9a97e;--sup:#c9a97e}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.6 "Iowan Old Style",Palatino,Georgia,serif}
header{border-bottom:1px solid var(--rule);padding:1.2rem 1.5rem}
header a{color:var(--muted);text-decoration:none;font-size:.85rem}
h1{margin:.2rem 0;font-size:1.5rem;letter-spacing:.01em}
main{max-width:56rem;margin:0 auto;padding:1.5rem}
.meta{color:var(--muted);font-size:.85rem;margin-bottom:1.5rem}
.col{margin:2rem 0}
.col h2{font-size:.8rem;text-transform:uppercase;letter-spacing:.12em;
  color:var(--muted);font-weight:600;border-bottom:1px solid var(--rule);padding-bottom:.3rem}
.ln{display:flex;gap:.9rem;align-items:baseline;padding:.15rem 0}
.ln .n{flex:0 0 2.6rem;text-align:right;color:var(--muted);
  font:400 .75rem/1.6 ui-monospace,SFMono-Regular,Menlo,monospace}
/* min-width:0 is load-bearing: a flex item defaults to min-width:auto and so
   refuses to shrink below its content, which pushes long unbroken Hebrew runs
   off the right edge and leaves short lines stranded outside the viewport. */
.heb{direction:rtl;text-align:right;flex:1 1 auto;min-width:0;
  overflow-wrap:anywhere;font-size:1.35rem;line-height:2;
  font-family:"SBL Hebrew","Ezra SIL","Times New Roman",serif}
.sup{color:var(--sup)}
.sup::before{content:"⌈"}.sup::after{content:"⌉"}
.unc{border-bottom:1px dotted currentColor}
.unc.low{opacity:.65}
.gap{color:var(--muted);padding:0 .15em}
del{text-decoration:line-through;opacity:.55}
ins,.add{vertical-align:super;font-size:.75em;color:var(--accent);text-decoration:none}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;padding:.35rem .6rem;border-bottom:1px solid var(--rule)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
a{color:var(--accent)}
input[type=search]{width:100%;padding:.6rem .8rem;font-size:1rem;
  border:1px solid var(--rule);border-radius:.3rem;background:var(--bg);color:var(--fg)}
.hit{padding:.4rem 0;border-bottom:1px solid var(--rule)}
.hit .ref{color:var(--muted);font-size:.8rem;font-family:ui-monospace,monospace}
"""


def render(node: ET.Element, parts: list[str]) -> None:
    """Walk a TEI element, appending HTML."""
    for child in node:
        tag = child.tag.replace(TEI, "")
        if tag == "lb":
            parts.append(f'\x00{child.get("n", "")}\x00')
        elif tag == "gap":
            q = child.get("quantity")
            title = child.get("reason", "lost")
            if q:
                title += f", {q} characters"
            parts.append(f'<span class="gap" title="{html.escape(title,quote=True)}">…</span>')
        elif tag == "supplied":
            inner: list[str] = []
            if child.text:
                inner.append(html.escape(child.text))
            render(child, inner)
            parts.append(f'<span class="sup">{"".join(inner)}</span>')
        elif tag == "unclear":
            cls = "unc low" if child.get("cert") == "low" else "unc"
            parts.append(f'<span class="{cls}">{html.escape(child.text or "")}</span>')
        elif tag == "del":
            parts.append(f"<del>{html.escape(child.text or '')}</del>")
        elif tag == "add":
            parts.append(f'<span class="add">{html.escape(child.text or "")}</span>')
        elif tag == "corr":
            parts.append(f"<ins>{html.escape(child.text or '')}</ins>")
        else:
            if child.text:
                parts.append(html.escape(child.text))
            render(child, parts)
        if child.tail:
            parts.append(html.escape(child.tail))


def page(title: str, body: str, home: bool = False) -> str:
    back = "" if home else '<a href="../index.html">← all scrolls</a>'
    return (
        "<!doctype html><html lang='he'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>"
        f"<header>{back}<h1>{html.escape(title)}</h1></header><main>{body}</main>"
        "</body></html>"
    )


def build_scroll_page(path: str, concordance: dict[str, list[str]]) -> tuple[str, str, int]:
    tree = ET.parse(path)
    siglum = os.path.splitext(os.path.basename(path))[0]
    out: list[str] = []
    lines = 0

    for div in tree.getroot().iter(f"{TEI}div"):
        column = div.get("n", "")
        parts: list[str] = []
        if div.text:
            parts.append(html.escape(div.text))
        render(div, parts)
        chunk = "".join(parts)

        rendered: list[str] = []
        for piece in re.split(r"\x00(.*?)\x00", chunk)[1:]:
            rendered.append(piece)
        pairs = list(zip(rendered[0::2], rendered[1::2]))

        out.append(f'<section class="col"><h2>Column {html.escape(column)}</h2>')
        for line_no, content in pairs:
            lines += 1
            out.append(
                f'<div class="ln"><span class="n">{html.escape(line_no)}</span>'
                f'<span class="heb">{content}</span></div>'
            )
            plain = re.sub(r"<[^>]+>", "", content).replace("…", " ")
            for word in plain.split():
                word = word.strip(".,;:!?()")
                if word:
                    concordance.setdefault(word, []).append(
                        f"{siglum} {column}:{line_no}"
                    )
        out.append("</section>")

    return siglum, page(siglum, "".join(out)), lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tei", default="tei")
    ap.add_argument("--stats", default="derived/corpus-stats.json")
    ap.add_argument("--out", default="site")
    args = ap.parse_args()

    if not os.path.isdir(args.tei):
        print(f"error: no TEI at {args.tei}; run build_tei.py first", file=sys.stderr)
        return 2

    os.makedirs(os.path.join(args.out, "scroll"), exist_ok=True)
    stats = {}
    if os.path.exists(args.stats):
        stats = json.load(open(args.stats, encoding="utf-8")).get("scrolls", {})

    concordance: dict[str, list[str]] = {}
    built: list[tuple[str, int]] = []

    for name in sorted(os.listdir(args.tei)):
        if not name.endswith(".xml"):
            continue
        siglum, markup, lines = build_scroll_page(
            os.path.join(args.tei, name), concordance
        )
        with open(os.path.join(args.out, "scroll", f"{siglum}.html"), "w",
                  encoding="utf-8") as fh:
            fh.write(markup)
        built.append((siglum, lines))

    # Index
    rows = []
    for siglum, lines in sorted(built):
        s = stats.get(siglum, {})
        words = s.get("words", "")
        recon = (f"{100*s['reconstructed']/s['words']:.0f}%"
                 if s.get("words") else "—")
        rows.append(
            f'<tr><td><a href="scroll/{html.escape(siglum)}.html">{html.escape(siglum)}</a></td>'
            f'<td class="n">{lines}</td><td class="n">{words}</td><td class="n">{recon}</td></tr>'
        )
    index_body = (
        f'<p class="meta">{len(built)} scrolls · '
        f'<a href="search.html">search the concordance</a></p>'
        '<table><thead><tr><th>Scroll</th><th class="n">Lines</th>'
        '<th class="n">Words</th><th class="n">Reconstructed</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page("Qumran transcriptions", index_body, home=True))

    # Concordance: keep it to forms attested more than once to hold the size down
    trimmed = {w: refs[:60] for w, refs in concordance.items()}
    with open(os.path.join(args.out, "concordance.json"), "w", encoding="utf-8") as fh:
        json.dump(trimmed, fh, ensure_ascii=False, separators=(",", ":"))

    search_body = (
        '<p class="meta">Type a Hebrew form. Matching is by prefix; '
        'reconstructed and uncertain letters are included.</p>'
        '<input type="search" id="q" placeholder="למשל: אמת" autofocus>'
        '<div id="out"></div>'
        '<script>'
        'let D=null;'
        'fetch("concordance.json").then(r=>r.json()).then(d=>{D=d;go()});'
        'const q=document.getElementById("q"),o=document.getElementById("out");'
        'function go(){if(!D)return;const v=q.value.trim();o.innerHTML="";'
        'if(!v){o.innerHTML=\'<p class="meta">\'+Object.keys(D).length+\' distinct forms.</p>\';return}'
        'const keys=Object.keys(D).filter(k=>k.startsWith(v)).slice(0,60);'
        'if(!keys.length){o.innerHTML=\'<p class="meta">No match.</p>\';return}'
        'o.innerHTML=keys.map(k=>\'<div class="hit"><span class="heb">\'+k+\'</span> \'+'
        '\'<span class="ref">\'+D[k].length+\'×: \'+D[k].slice(0,12).join(" · ")+\'</span></div>\').join("")}'
        'q.addEventListener("input",go);'
        '</script>'
    )
    with open(os.path.join(args.out, "search.html"), "w", encoding="utf-8") as fh:
        fh.write(page("Concordance", search_body, home=True))

    size = sum(os.path.getsize(os.path.join(dp, f))
               for dp, _, fs in os.walk(args.out) for f in fs)
    msg = (f"Built {len(built)} scroll pages, "
           f"{len(concordance):,} distinct forms, {size/1e6:.1f} MB")
    print(msg)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## Reading edition\n\n{msg}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
