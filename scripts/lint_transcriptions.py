#!/usr/bin/env python3
"""Check the scroll transcriptions for structural errors.

Every line must read ``<siglum> <column>:<line><padding><content>``, which is
what ``txt_to_s_xml.py`` assumes. That script only ``print``s on a line it
cannot parse and carries on, so malformed input turns into silently missing
XML. This fails the build instead.

Checks, most to least severe:

  * unparseable line        - the converter would drop it
  * unbalanced [ ]          - brackets carry reconstruction semantics, so an
                              unclosed one corrupts every downstream TEI tag
  * siglum/filename mismatch - a line attributed to the wrong scroll
  * unexpected characters   - anything outside Hebrew, the markup alphabet and
                              ASCII digits/punctuation

Usage:
    python3 lint_transcriptions.py [DIR] [--quiet]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from collections import Counter

LINE_RE = re.compile(r"^(?P<siglum>\S+) (?P<column>[^:\s]+):(?P<line>\S+)(?:\s+(?P<content>.*))?$")

# The markup alphabet, taken from a census of the corpus rather than guessed.
# Anything outside this set is a stray character - a Latin letter from a bad
# paste, a smart quote from a word processor - and is worth failing on.
#
#   -        gap dash                    [ ]   reconstruction
#   U+05AF   possible letter (circle)    U+0307 probable letter (dot above)
#   U+25CC   unreadable letter           〚 〛  scribal erasure
#   ^        supralinear insertion       { }   scribal deletion
#   ( )      editorial addition          < >   editorial correction
#   ⸱        word separator              ־     maqaf
ALLOWED_EXTRA = set(
    " \t"
    "-[]().{}<>^?!+"
    "0123456789"
    "◌"        # ◌ unreadable letter
    "〚〛"  # 〚 〛 erasure
    " "        # thin space
    "⸱"        # ⸱ word separator middle dot
)


def allowed(ch: str) -> bool:
    if "֐" <= ch <= "׿":      # Hebrew block, incl. points and marks
        return True
    if ch in ALLOWED_EXTRA:
        return True
    return unicodedata.combining(ch) != 0


def lint_file(path: str) -> list[tuple[int, str, str]]:
    """Return a list of (line_number, code, detail)."""
    problems: list[tuple[int, str, str]] = []
    expected_siglum = os.path.splitext(os.path.basename(path))[0]

    with open(path, encoding="utf-8") as fh:
        for n, raw in enumerate(fh, 1):
            text = raw.rstrip("\n").rstrip("\r")
            if not text.strip():
                continue

            m = LINE_RE.match(text)
            if not m:
                problems.append((n, "unparseable", text[:60]))
                continue

            content = m.group("content") or ""

            if content.count("[") != content.count("]"):
                problems.append((
                    n, "unbalanced-brackets",
                    f"{content.count('[')} open, {content.count(']')} close: {content[:50]}",
                ))

            if m.group("siglum") != expected_siglum:
                problems.append((
                    n, "siglum-mismatch",
                    f"line says {m.group('siglum')!r}, file is {expected_siglum!r}",
                ))

            bad = {ch for ch in content if not allowed(ch)}
            if bad:
                names = ", ".join(
                    f"U+{ord(c):04X} {unicodedata.name(c, '?')}" for c in sorted(bad)
                )
                problems.append((n, "unexpected-character", names))

    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", nargs="?", default="original/scroll")
    ap.add_argument("--quiet", action="store_true", help="only print failures")
    args = ap.parse_args()

    if not os.path.isdir(args.directory):
        print(f"error: no such directory: {args.directory}", file=sys.stderr)
        return 2

    files = sorted(f for f in os.listdir(args.directory) if f.endswith(".txt"))
    counts: Counter[str] = Counter()
    lines_out: list[str] = []

    for name in files:
        for n, code, detail in lint_file(os.path.join(args.directory, name)):
            counts[code] += 1
            lines_out.append(f"{name}:{n}: {code}: {detail}")

    total = sum(counts.values())
    header = f"Linted {len(files)} transcription file(s): {total} problem(s)."
    print(header)
    if counts:
        for code, n in counts.most_common():
            print(f"  {code}: {n}")
        print()
        for line in lines_out:
            print(line)
    elif not args.quiet:
        print("No problems found.")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## Transcription lint\n\n{header}\n\n")
            if counts:
                fh.write("| Problem | Count |\n| --- | ---: |\n")
                for code, n in counts.most_common():
                    fh.write(f"| {code} | {n} |\n")
                fh.write("\n```\n" + "\n".join(lines_out[:200]) + "\n```\n")
            else:
                fh.write("No problems found.\n")

    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
