"""Age bands shared by every exposure and outcome table.

DGT's driver tables and driver census use 15–17, 18–20, 21–24 and then five-year bands up to
"more than 74"; INE population uses five-year groups; MOVILIA uses six broad bands. Everything is
mapped onto the analysis bands below. A source band is accepted only when it nests inside exactly
one analysis band, so nothing is split silently: a band that straddles two analysis bands raises.
"""

from __future__ import annotations

import re

Band = tuple[int, int | None]

# Analysis bands used for rates: key -> (lowest age, highest age or None for open-ended).
ANALYSIS_BANDS: dict[str, Band] = {
    "15-24": (15, 24),
    "25-34": (25, 34),
    "35-44": (35, 44),
    "45-54": (45, 54),
    "55-64": (55, 64),
    "65-74": (65, 74),
    "75+": (75, None),
}

# The DGT driver bands (census by age and tables 4.1.1 / 4.2 from 15 upwards).
DGT_BANDS: dict[str, Band] = {
    "15-17": (15, 17),
    "18-20": (18, 20),
    "21-24": (21, 24),
    "25-29": (25, 29),
    "30-34": (30, 34),
    "35-39": (35, 39),
    "40-44": (40, 44),
    "45-49": (45, 49),
    "50-54": (50, 54),
    "55-59": (55, 59),
    "60-64": (60, 64),
    "65-69": (65, 69),
    "70-74": (70, 74),
    "75+": (75, None),
}

# Bands for the kilometre-based driver-risk comparison: they nest both DGT's driver bands and
# the owner-age bands of its kilometre release, so numerator and denominator use the same cuts.
# 15-17 exists only in the driver tables (no car licence before 18, and no owner band below 18),
# and is reported but never compared.
EXPOSURE_BANDS: dict[str, Band] = {
    "15-17": (15, 17),
    "18-34": (18, 34),
    "35-54": (35, 54),
    "55-64": (55, 64),
    "65-74": (65, 74),
    "75+": (75, None),
}

# MOVILIA 2006 bands.
MOVILIA_BANDS: dict[str, Band] = {
    "0-14": (0, 14),
    "15-29": (15, 29),
    "30-39": (30, 39),
    "40-49": (40, 49),
    "50-64": (50, 64),
    "65+": (65, None),
}

UNKNOWN = "unknown"

BAND_LABELS: dict[str, str] = {
    "15-24": "15–24",
    "25-34": "25–34",
    "35-44": "35–44",
    "45-54": "45–54",
    "55-64": "55–64",
    "65-69": "65–69",
    "70-74": "70–74",
    "65-74": "65–74",
    "18-34": "18–34",
    "35-54": "35–54",
    "15-17": "15–17",
    "75+": "75 and over",
    "65+": "65 and over",
    UNKNOWN: "Age not recorded",
}

_UNKNOWN_LABELS = {
    "se desconoce",
    "desconocido",
    "desconocida",
    "no especificada",
    "no especifica",
    "no consta",
    "unknown",
}


def _clean(text: object) -> str:
    return " ".join(str(text).replace("\\", " ").split()).lower()


def parse_age_label(text: object) -> Band | None:
    """``(low, high)`` for an age label in any of the source conventions; ``None`` for unknown age.

    ``high`` is ``None`` for open-ended bands. Raises ``ValueError`` for anything unrecognised, so a
    changed label in a future release is caught rather than dropped.
    """
    label = _clean(text)
    if label in _UNKNOWN_LABELS:
        return None
    if label.startswith("todas las edades"):
        return (0, None)
    patterns: tuple[tuple[str, str], ...] = (
        (r"^de (\d+) a (\d+)", "range"),
        (r"^(\d+) a (\d+)", "range"),
        (r"^(\d+) (\d+) años", "range"),  # "0\\14 años" once the backslash is dropped
        (r"^hasta (\d+)", "upto"),
        (r"^de (\d+) o más", "open"),
        (r"^más de (\d+)", "open_after"),
        (r"^(\d+) o más", "open"),
        (r"^(\d+) y más", "open"),
    )
    for pattern, kind in patterns:
        match = re.match(pattern, label)
        if not match:
            continue
        if kind == "range":
            return (int(match.group(1)), int(match.group(2)))
        if kind == "upto":
            return (0, int(match.group(1)))
        if kind == "open":
            return (int(match.group(1)), None)
        return (int(match.group(1)) + 1, None)
    raise ValueError(f"unrecognised age label {text!r}")


def band_for(
    low: int | None, high: int | None, bands: dict[str, Band] = ANALYSIS_BANDS
) -> str | None:
    """Analysis band containing ``[low, high]``; ``UNKNOWN`` for unknown age; ``None`` when the
    interval lies entirely outside the bands (children, in most tables).

    Raises ``ValueError`` when the interval straddles two bands.
    """
    if low is None:
        return UNKNOWN
    overlapping = []
    for key, (band_low, band_high) in bands.items():
        starts_before_end = band_high is None or low <= band_high
        ends_after_start = high is None or high >= band_low
        if starts_before_end and ends_after_start:
            overlapping.append(key)
    if not overlapping:
        return None
    if len(overlapping) > 1:
        raise ValueError(f"age interval {low}-{high} straddles bands {overlapping}")
    key = overlapping[0]
    band_low, band_high = bands[key]
    inside = low >= band_low and (band_high is None or (high is not None and high <= band_high))
    if not inside:
        raise ValueError(f"age interval {low}-{high} is not nested inside band {key}")
    return key


def band_label(key: object) -> str:
    return BAND_LABELS.get(str(key), str(key))
