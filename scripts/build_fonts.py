"""Subset the site's two open fonts: a web font for the pages and static fonts for the charts.

The web fonts, the sans in two styles, go to ``src/dgt_stats/site/fonts`` and the site build copies
them. The charts' fonts, two static weights of the serif, go to ``src/dgt_stats/fonts``: matplotlib
lays chart text out with them, and each chart embeds the glyphs it uses, so it reads the same on
every system. Not part of
the pipeline: the subsets are committed. Run it again only to change the character set or update
a font. It needs ``fonttools`` with Brotli for
WOFF2 output, and the source fonts from the google/fonts repository (SIL Open Font License):

- ``ofl/nunitosans/NunitoSans[YTLC,opsz,wdth,wght].ttf`` and its italic: the stand-in for Avenir
  Next on systems that do not have it (Avenir Next ships with macOS and iOS only);
- ``ofl/stixtwotext/STIXTwoText[wght].ttf``: the serif of the charts.

Usage:
    python scripts/build_fonts.py <directory holding the source fonts>
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "dgt_stats" / "site" / "fonts"
CHART_TARGET = ROOT / "src" / "dgt_stats" / "fonts"

# Latin with Spanish and Catalan letters, and the punctuation and signs the pages use.
UNICODES = (
    "U+0020-007E,U+00A0-00FF,U+0131,U+0152-0153,U+0160-0161,U+0178,U+017D-017E,U+02C6,U+02DA,"
    "U+02DC,U+2009-200A,U+2010-2014,U+2018-201E,U+2022,U+2026,U+2030,U+2032-2033,U+2039-203A,"
    "U+2044,U+20AC,U+2122,U+2212,U+2215,U+2248,U+2260,U+2264-2265"
)
FEATURES = [
    "kern",
    "liga",
    "calt",
    "lnum",
    "onum",
    "tnum",
    "pnum",
    "frac",
    "sups",
    "subs",
    "case",
    "smcp",
    "c2sc",
    "ccmp",
    "locl",
    "mark",
    "mkmk",
]

# Source file, output file, and the axis limits kept in the subset.
FONTS = (
    (
        "NunitoSans[YTLC,opsz,wdth,wght].ttf",
        "NunitoSans.woff2",
        {"wght": (300, 800), "wdth": 100, "opsz": 12, "YTLC": 500},
    ),
    (
        "NunitoSans-Italic[YTLC,opsz,wdth,wght].ttf",
        "NunitoSans-Italic.woff2",
        {"wght": (300, 800), "wdth": 100, "opsz": 12, "YTLC": 500},
    ),
)


# The charts' serif: the text weight and the weight of their few headings.
CHART_FONTS = (
    ("STIXTwoText[wght].ttf", "STIXTwoText-Regular.ttf", 400),
    ("STIXTwoText[wght].ttf", "STIXTwoText-SemiBold.ttf", 600),
)


def _limited(path: Path, limits: dict) -> TTFont:
    """The font with its axes limited (or pinned), reloaded so the subsetter sees plain tables."""
    buffer = io.BytesIO()
    instancer.instantiateVariableFont(TTFont(path), limits, updateFontNames=True).save(buffer)
    buffer.seek(0)
    return TTFont(buffer)


def build(source: Path) -> list[Path]:
    TARGET.mkdir(parents=True, exist_ok=True)
    written = []
    for name, output, limits in FONTS:
        font = _limited(source / name, limits)
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = FEATURES
        options.name_IDs = ["*"]
        options.notdef_outline = True
        subsetter = subset.Subsetter(options)
        subsetter.populate(unicodes=subset.parse_unicodes(UNICODES))
        subsetter.subset(font)
        path = TARGET / output
        subset.save_font(font, str(path), options)
        written.append(path)
    CHART_TARGET.mkdir(parents=True, exist_ok=True)
    for name, output, weight in CHART_FONTS:
        font = _limited(source / name, {"wght": weight})
        options = subset.Options()
        options.layout_features = ["kern", "liga", "lnum", "tnum"]
        options.name_IDs = ["*"]
        options.notdef_outline = True
        subsetter = subset.Subsetter(options)
        subsetter.populate(unicodes=subset.parse_unicodes(UNICODES))
        subsetter.subset(font)
        path = CHART_TARGET / output
        subset.save_font(font, str(path), options)
        written.append(path)
    return written


if __name__ == "__main__":
    for path in build(Path(sys.argv[1])):
        print(path.relative_to(ROOT), path.stat().st_size)
