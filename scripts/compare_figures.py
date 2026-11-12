"""Check that the figures just drawn match the committed ones.

The result tables are compared byte for byte; the figures cannot be. A chart's coordinates come
out of floating-point layout arithmetic whose last digits differ between machines, and each clip
path's id is a hash of those coordinates. A figure therefore counts as reproduced when its text is
identical and every number in it lies within ``TOLERANCE`` points of the committed figure's, once
the hashed ids are set aside. A figure that is new, missing or different beyond that fails.

Usage (in a git checkout, after ``python scripts/analyse.py figures``):
    python scripts/compare_figures.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURES = "reports/figures"
# A tenth of a point (1/720 inch): far below what a reader can see, far above machine noise.
TOLERANCE = 0.1
NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?")
HASHED_ID = re.compile(r"\bp[0-9a-f]{10}\b")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8", check=True
    ).stdout


def same_figure(committed: str, drawn: str) -> bool:
    committed, drawn = HASHED_ID.sub("p", committed), HASHED_ID.sub("p", drawn)
    if NUMBER.sub("#", committed) != NUMBER.sub("#", drawn):
        return False
    old, new = NUMBER.findall(committed), NUMBER.findall(drawn)
    # Equal text first: the embedded font data holds digit runs such as "9e999" that are not
    # numbers and would read as infinite.
    return len(old) == len(new) and all(
        a == b or abs(float(a) - float(b)) <= TOLERANCE for a, b in zip(old, new, strict=True)
    )


def main() -> int:
    tracked = set(_git("ls-files", f"{FIGURES}/*.svg").split())
    drawn = {
        str(path.relative_to(ROOT)) for path in (ROOT / FIGURES).rglob("*.svg") if path.is_file()
    }
    problems = [f"drawn but not committed: {path}" for path in sorted(drawn - tracked)]
    problems += [f"committed but no longer drawn: {path}" for path in sorted(tracked - drawn)]
    for path in sorted(tracked & drawn):
        if not same_figure(_git("show", f"HEAD:{path}"), (ROOT / path).read_text("utf-8")):
            problems.append(f"differs beyond {TOLERANCE} pt: {path}")
    for problem in problems:
        print(problem)
    print(f"{len(tracked & drawn)} figures compared, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
