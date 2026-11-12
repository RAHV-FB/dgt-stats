"""Check that the result tables and figures just rebuilt match the committed ones.

On one machine the pipeline reproduces every file byte for byte. Across machines the last digits
of some results move: the fitted models, the survey's distance model and its bootstraps run on
numerical libraries whose kernels depend on the processor. A rebuilt table or caption file
therefore counts as reproduced when its text, with the numbers set aside, is identical to the
committed copy and every number is within one part in a thousand (``RELATIVE``) or ``ABSOLUTE``.
A figure's drawing coordinates come from text measured on the machine that draws it and can move
by a few points, so a figure counts as reproduced when everything it prints (labels, numbers,
titles, legends and the embedded font) is identical. A file that is new, missing or different
beyond that fails.

With ``--rebuilt-after FILE`` the check also fails for every tracked generated file under
``reports/`` (suffix ``.csv``, ``.svg`` or ``.json``; not ``README.md`` or ``.gitkeep``) whose
modification time is older than FILE's: such a file is committed but was not rewritten by the
pipeline, so the comparison above would pass on the committed copy alone. Touch FILE before the
pipeline starts.

Usage (in a git checkout, after the pipeline has rebuilt ``reports/``):
    python scripts/compare_reports.py [--rebuilt-after FILE]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = "reports"
RELATIVE = 1e-3
ABSOLUTE = 1e-6
NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?")
# What an SVG prints: the text between its tags (labels, numbers, titles, the embedded font).
PRINTED = re.compile(r">([^<>]*\S[^<>]*)<")
GENERATED_SUFFIXES = (".csv", ".svg", ".json")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8", check=True
    ).stdout


def _close(a: str, b: str) -> bool:
    if a == b:
        return True
    x, y = float(a), float(b)
    return abs(x - y) <= max(RELATIVE * max(abs(x), abs(y)), ABSOLUTE)


def same_file(committed: str, rebuilt: str, figure: bool) -> bool:
    if committed == rebuilt:
        return True
    if figure:
        return PRINTED.findall(committed) == PRINTED.findall(rebuilt)
    if NUMBER.sub("#", committed) != NUMBER.sub("#", rebuilt):
        return False
    old, new = NUMBER.findall(committed), NUMBER.findall(rebuilt)
    return len(old) == len(new) and all(_close(a, b) for a, b in zip(old, new, strict=True))


def not_rebuilt(paths: set[str], marker: Path) -> list[str]:
    """The generated files among ``paths`` last modified before ``marker`` was."""
    started = marker.stat().st_mtime_ns
    return sorted(
        path
        for path in paths
        if path.endswith(GENERATED_SUFFIXES) and (ROOT / path).stat().st_mtime_ns < started
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--rebuilt-after",
        type=Path,
        metavar="FILE",
        help="fail for every generated file under reports/ last modified before FILE",
    )
    args = parser.parse_args()
    tracked = set(_git("ls-files", REPORTS).split())
    present = {
        str(path.relative_to(ROOT)) for path in (ROOT / REPORTS).rglob("*") if path.is_file()
    }
    problems = [f"rebuilt but not committed: {path}" for path in sorted(present - tracked)]
    problems += [f"committed but no longer built: {path}" for path in sorted(tracked - present)]
    for path in sorted(tracked & present):
        rebuilt = (ROOT / path).read_text("utf-8")
        if not same_file(_git("show", f"HEAD:{path}"), rebuilt, path.endswith(".svg")):
            problems.append(f"differs beyond tolerance: {path}")
    if args.rebuilt_after is not None:
        stale = not_rebuilt(tracked & present, args.rebuilt_after)
        problems += [f"committed but not rebuilt: {path}" for path in stale]
    for problem in problems:
        print(problem)
    print(f"{len(tracked & present)} files compared, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
