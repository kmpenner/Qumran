#!/usr/bin/env python3
"""Convert scroll transcriptions to TEI P5.

Goes straight from the ``.txt`` transcription to TEI rather than through the
intermediate ``<s>`` XML, so the reconstruction markup survives into the output
instead of being flattened into a text node first.

Markup mapping, from the corpus character census:

    [word]      -> <supplied reason="lost">word</supplied>
    [ -- ]      -> <gap reason="lost" extent="unknown"/>
    --          -> <gap reason="lost" extent="unknown"/>
    ẋ (U+0307)  -> <unclear cert="high">x</unclear>
    x֯ (U+05AF)  -> <unclear cert="low">x</unclear>
    ◌◌◌         -> <gap reason="illegible" unit="character" quantity="3"/>
    〚word〛     -> <del rend="erasure">word</del>
    {word}      -> <del rend="dots">word</del>
    ^word^      -> <add place="above">word</add>
    <word>      -> <corr>word</corr>
    (word)      -> <supplied reason="omitted">word</supplied>

Usage:
    python3 build_tei.py [--src DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from xml.etree import ElementTree as ET

TEI_NS = "http://www.tei-c.org/ns/1.0"

LINE_RE = re.compile(r"^(?P<siglum>\S+) (?P<column>[^:\s]+):(?P<line>\S+)(?:\s+(?P<content>.*))?$")

DOT_ABOVE = "̇"
CIRCLE = "֯"
UNREADABLE = "◌"
# Hebrew consonants only: the certainty and bracket patterns must never reach
# into XML tags that earlier substitutions have already inserted.
HEB = "[\u05D0-\u05EA]"
NOTAG = "[^<>]"


def encode_inline(text: str) -> str:
    """Turn one line of transcription into a TEI fragment (as a string)."""
    out = html.escape(text, quote=False)

    # Runs of unreadable-letter placeholders, before anything else consumes them.
    out = re.sub(
        f"{UNREADABLE}+",
        lambda m: f'<gap reason="illegible" unit="character" quantity="{len(m.group(0))}"/>',
        out,
    )

    # Certainty marks: a Hebrew consonant followed by a dot above or a circle.
    # Consecutive marked characters collapse into one <unclear>. The base class
    # must be Hebrew letters, not ".", or the pattern reaches into the tags
    # already inserted above and splits them.
    out = re.sub(
        f"((?:{HEB}{DOT_ABOVE})+)",
        lambda m: f'<unclear cert="high">{m.group(1).replace(DOT_ABOVE, "")}</unclear>',
        out,
    )
    out = re.sub(
        f"((?:{HEB}{CIRCLE})+)",
        lambda m: f'<unclear cert="low">{m.group(1).replace(CIRCLE, "")}</unclear>',
        out,
    )

    # Lacunae. The bracketed forms first, so "[ -- ]" does not become
    # <supplied> wrapped around a <gap>.
    out = re.sub(r"\[\s*--\s*\]", '<gap reason="lost" extent="unknown"/>', out)
    out = re.sub(
        rf"\[\s*--\s*({NOTAG}*?)\]",
        r'<gap reason="lost" extent="unknown"/><supplied reason="lost">\1</supplied>',
        out,
    )
    out = re.sub(
        rf"\[({NOTAG}*?)\s*--\s*\]",
        r'<supplied reason="lost">\1</supplied><gap reason="lost" extent="unknown"/>',
        out,
    )
    out = re.sub(rf"\[({NOTAG}*?)\]", r'<supplied reason="lost">\1</supplied>', out)
    out = re.sub(r"--", '<gap reason="lost" extent="unknown"/>', out)

    # Scribal interventions.
    out = re.sub(rf"〚({NOTAG}*?)〛", r'<del rend="erasure">\1</del>', out)
    out = re.sub(rf"\{{({NOTAG}*?)\}}", r'<del rend="dots">\1</del>', out)
    out = re.sub(rf"\^({NOTAG}*?)\^", r'<add place="above">\1</add>', out)
    out = re.sub(rf"&lt;({NOTAG}*?)&gt;", r"<corr>\1</corr>", out)
    out = re.sub(rf"\(({NOTAG}*?)\)", r'<supplied reason="omitted">\1</supplied>', out)

    return out


def build_scroll(path: str) -> str | None:
    siglum = os.path.splitext(os.path.basename(path))[0]
    columns: list[tuple[str, list[tuple[str, str]]]] = []
    current: str | None = None

    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            text = raw.rstrip("\n")
            if not text.strip():
                continue
            m = LINE_RE.match(text)
            if not m:
                continue
            column = m.group("column")
            if column != current:
                columns.append((column, []))
                current = column
            columns[-1][1].append((m.group("line"), m.group("content") or ""))

    if not columns:
        return None

    body = []
    for column, lines in columns:
        body.append(f'<div type="column" n="{html.escape(column, quote=True)}">')
        for line_no, content in lines:
            body.append(
                f'<lb n="{html.escape(line_no, quote=True)}"/>{encode_inline(content)}'
            )
        body.append("</div>")

    title = html.escape(siglum, quote=False)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<TEI xmlns="{TEI_NS}">\n'
        "  <teiHeader>\n"
        "    <fileDesc>\n"
        f"      <titleStmt><title>{title}</title></titleStmt>\n"
        "      <publicationStmt><p>Generated from the transcription by "
        "build_tei.py.</p></publicationStmt>\n"
        f"      <sourceDesc><p>Transcription of {title}.</p></sourceDesc>\n"
        "    </fileDesc>\n"
        "  </teiHeader>\n"
        "  <text>\n    <body>\n      "
        + "\n      ".join(body)
        + "\n    </body>\n  </text>\n</TEI>\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="original/scroll")
    ap.add_argument("--out", default="tei")
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        print(f"error: no such directory: {args.src}", file=sys.stderr)
        return 2

    os.makedirs(args.out, exist_ok=True)
    written = failed = 0
    problems: list[str] = []

    for name in sorted(os.listdir(args.src)):
        if not name.endswith(".txt"):
            continue
        xml = build_scroll(os.path.join(args.src, name))
        if xml is None:
            continue
        target = os.path.join(args.out, name[:-4] + ".xml")
        try:
            ET.fromstring(xml)                      # must be well-formed
        except ET.ParseError as exc:
            failed += 1
            problems.append(f"{name}: {exc}")
            continue
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(xml)
        written += 1

    print(f"Wrote {written} TEI file(s); {failed} failed to parse.")
    for line in problems[:40]:
        print("  ", line)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## TEI build\n\n{written} written, {failed} failed.\n")
            if problems:
                fh.write("\n```\n" + "\n".join(problems[:40]) + "\n```\n")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
