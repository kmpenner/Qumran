#!/usr/bin/env python3
"""Keep original/dss.txt and original/scroll/*.txt in step, in both directions.

``dss.txt`` is one file holding every scroll: a siglum on its own line, the
scroll's lines beneath it, then blank lines before the next siglum. The
per-scroll files hold the same content split apart. Both are committed, so an
edit can arrive on either side.

Directions:

  from-dss   rewrite the per-scroll files from dss.txt
  to-dss     splice the per-scroll files back into dss.txt
  check      report drift, change nothing (exit 1 if any)

``to-dss`` is a splice, not a regeneration: only the byte ranges belonging to
changed scrolls are replaced, so blocks nobody touched keep their exact
original bytes. Regenerating the whole file would rewrite the separators and
bury a one-line edit in thousands of lines of whitespace churn.

Usage:
    python3 sync_dss.py check
    python3 sync_dss.py from-dss [--only 1QS,CD]
    python3 sync_dss.py to-dss   [--only 1QS,CD]
"""

from __future__ import annotations

import argparse
import os
import re
import sys

DSS = "English Translation/original/dss.txt"
SCROLL_DIR = "English Translation/original/scroll"
DEFAULT_SEPARATOR = "\n" * 10


class Block:
    __slots__ = ("name", "body", "body_start", "body_end")

    def __init__(self, name: str, body: str, body_start: int, body_end: int):
        self.name, self.body = name, body
        self.body_start, self.body_end = body_start, body_end


def parse_dss(text: str) -> list[Block]:
    """Split dss.txt into blocks, recording where each body sits in the file.

    A siglum is a non-blank line that follows a blank one (or starts the file).
    Everything up to the next blank line is that scroll's body.
    """
    blocks: list[Block] = []
    pos = 0
    expecting_name = True
    name: str | None = None
    body_start = 0

    for match in re.finditer(r"[^\n]*\n?", text):
        line, start, end = match.group(0), match.start(), match.end()
        if start >= len(text):
            break
        stripped = line.strip().lstrip("﻿")

        if not stripped:
            if name is not None:
                blocks.append(Block(name, text[body_start:pos], body_start, pos))
                name = None
            expecting_name = True
        elif expecting_name:
            name = stripped
            body_start = end
            expecting_name = False
        pos = end

    if name is not None:
        blocks.append(Block(name, text[body_start:len(text)], body_start, len(text)))
    return blocks


def read_dss(path: str) -> tuple[str, list[Block]]:
    text = open(path, encoding="utf-8").read()
    return text, parse_dss(text)


def scroll_path(name: str) -> str:
    return os.path.join(SCROLL_DIR, f"{name.replace('/', '_')}.txt")


def from_dss(only: set[str] | None) -> list[str]:
    _, blocks = read_dss(DSS)
    os.makedirs(SCROLL_DIR, exist_ok=True)
    changed: list[str] = []
    for block in blocks:
        if only and block.name not in only:
            continue
        path = scroll_path(block.name)
        current = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if current != block.body:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(block.body)
            changed.append(block.name)
    return changed


def to_dss(only: set[str] | None) -> list[str]:
    text, blocks = read_dss(DSS)
    by_name = {b.name: b for b in blocks}

    edits: list[tuple[int, int, str]] = []
    changed: list[str] = []

    for block in blocks:
        if only and block.name not in only:
            continue
        path = scroll_path(block.name)
        if not os.path.exists(path):
            continue
        body = open(path, encoding="utf-8").read()
        if body != block.body:
            edits.append((block.body_start, block.body_end, body))
            changed.append(block.name)

    # Apply back-to-front so earlier offsets stay valid.
    out = text
    for start, end, body in sorted(edits, key=lambda e: -e[0]):
        out = out[:start] + body + out[end:]

    # Scrolls that exist only as files get appended.
    for name in sorted(
        n for n in scroll_names() if n not in by_name and (not only or n in only)
    ):
        body = open(scroll_path(name), encoding="utf-8").read()
        if not out.endswith("\n"):
            out += "\n"
        out += DEFAULT_SEPARATOR + name + "\n" + body
        changed.append(name)

    if out != text:
        with open(DSS, "w", encoding="utf-8") as fh:
            fh.write(out)
    return changed


def scroll_names() -> list[str]:
    if not os.path.isdir(SCROLL_DIR):
        return []
    return [f[:-4] for f in os.listdir(SCROLL_DIR) if f.endswith(".txt")]


def check() -> list[str]:
    _, blocks = read_dss(DSS)
    by_name = {b.name: b.body for b in blocks}
    files = set(scroll_names())
    problems: list[str] = []

    for name in sorted(set(by_name) - files):
        problems.append(f"{name}: in dss.txt, no file in scroll/")
    for name in sorted(files - set(by_name)):
        problems.append(f"{name}: file in scroll/, not in dss.txt")
    for name in sorted(set(by_name) & files):
        if open(scroll_path(name), encoding="utf-8").read() != by_name[name]:
            problems.append(f"{name}: content differs")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("direction", choices=["check", "from-dss", "to-dss"])
    ap.add_argument("--only", default="", help="comma-separated sigla to limit to")
    args = ap.parse_args()

    if not os.path.exists(DSS):
        print(f"error: {DSS} not found", file=sys.stderr)
        return 2

    only = {s.strip() for s in args.only.split(",") if s.strip()} or None

    if args.direction == "check":
        problems = check()
        print(f"{len(problems)} discrepancy(ies) between dss.txt and scroll/.")
        for line in problems[:60]:
            print("  ", line)
        if len(problems) > 60:
            print(f"   …and {len(problems) - 60} more")
        return 1 if problems else 0

    changed = from_dss(only) if args.direction == "from-dss" else to_dss(only)
    target = "scroll/" if args.direction == "from-dss" else "dss.txt"
    print(f"{args.direction}: updated {len(changed)} scroll(s) in {target}.")
    for name in changed[:60]:
        print("  ", name)
    if len(changed) > 60:
        print(f"   …and {len(changed) - 60} more")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(
                f"## Sync ({args.direction})\n\n{len(changed)} scroll(s) updated.\n"
            )
            if changed:
                fh.write("\n" + ", ".join(f"`{c}`" for c in changed[:80]) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
