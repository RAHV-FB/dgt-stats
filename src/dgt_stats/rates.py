"""Rates with exact Poisson intervals, rate ratios and the travel-weighted driver estimate.

Counts of deaths or involved drivers are treated as Poisson; the exposure (residents, licence
holders, travel-weighted drivers) is treated as known. Intervals are 95 % unless ``alpha`` says otherwise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def poisson_interval(count: float, alpha: float = 0.05) -> tuple[float, float]:
    """Exact (Garwood) confidence interval for a Poisson count."""
    if np.isnan(count):
        return (np.nan, np.nan)
    low = 0.0 if count == 0 else stats.chi2.ppf(alpha / 2, 2 * count) / 2
    high = stats.chi2.ppf(1 - alpha / 2, 2 * (count + 1)) / 2
    return (float(low), float(high))


def rate(
    count: float, exposure: float, per: float = 100_000, alpha: float = 0.05
) -> tuple[float, float, float]:
    """``(rate, low, high)`` per ``per`` units of exposure."""
    if exposure is None or np.isnan(exposure) or exposure <= 0 or np.isnan(count):
        return (np.nan, np.nan, np.nan)
    low, high = poisson_interval(count, alpha)
    scale = per / exposure
    return (count * scale, low * scale, high * scale)


def add_rate(
    frame: pd.DataFrame,
    count: str,
    exposure: str,
    name: str,
    per: float = 100_000,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Add ``name``, ``name_low`` and ``name_high`` columns to a copy of ``frame``."""
    values = [
        rate(c, e, per, alpha)
        for c, e in zip(frame[count].astype(float), frame[exposure].astype(float))
    ]
    out = frame.copy()
    out[name] = [v[0] for v in values]
    out[f"{name}_low"] = [v[1] for v in values]
    out[f"{name}_high"] = [v[2] for v in values]
    return out


def rate_ratio(
    count_1: float,
    exposure_1: float,
    count_2: float,
    exposure_2: float,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Ratio of two Poisson rates with a log-normal interval.

    The bounds are NaN when either count is 0, and the ratio itself is NaN when the reference
    count is, since there is then nothing to divide by.
    """
    if min(exposure_1, exposure_2) <= 0 or np.isnan(count_1) or np.isnan(count_2):
        return (np.nan, np.nan, np.nan)
    if count_2 == 0:
        return (np.nan, np.nan, np.nan)
    ratio = (count_1 / exposure_1) / (count_2 / exposure_2)
    if count_1 == 0:
        return (ratio, np.nan, np.nan)
    z = stats.norm.ppf(1 - alpha / 2)
    se = np.sqrt(1 / count_1 + 1 / count_2)
    return (ratio, ratio * np.exp(-z * se), ratio * np.exp(z * se))


def wilson_interval(share: float, n: float, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for a survey share with ``n`` respondents."""
    if np.isnan(share) or np.isnan(n) or n <= 0:
        return (np.nan, np.nan)
    z = stats.norm.ppf(1 - alpha / 2)
    centre = (share + z**2 / (2 * n)) / (1 + z**2 / n)
    half = z * np.sqrt(share * (1 - share) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return (max(centre - half, 0.0), min(centre + half, 1.0))


def interpolate_share(year: int, waves: pd.DataFrame) -> tuple[float, float, float]:
    """Survey share for ``year``: linear between waves, held flat outside them.

    ``waves`` has columns ``wave``, ``share`` and ``n``. The interval is the Wilson interval of
    the nearest wave, centred on the interpolated value.
    """
    waves = waves.sort_values("wave").reset_index(drop=True)
    years = waves.wave.to_numpy(dtype=float)
    shares = waves.share.to_numpy(dtype=float)
    value = float(np.interp(year, years, shares))
    nearest = waves.iloc[int(np.argmin(np.abs(years - year)))]
    low, high = wilson_interval(float(nearest.share), float(nearest.n))
    return (value, value - (float(nearest.share) - low), value + (high - float(nearest.share)))


def travel_weighted_share(
    year: int,
    waves: pd.DataFrame,
    profile: pd.Series,
    licence_share: pd.Series,
) -> pd.DataFrame:
    """Exploratory ESRA×MOVILIA age-allocation scenario retained for reproducibility.

    This is *not* an observed share of residents who drive and must not be presented as one.
    ``profile`` is historical MOVILIA 2006 car-or-motorcycle trip intensity per resident, where
    drivers and passengers are not separated. The national ESRA share of adults aged 18–74 who
    report driving a car at least a few days a month is allocated across age bands in proportion
    to that profile and capped at each band's licence-holding share. The cap is not redistributed.

    The two inputs therefore measure different objects, cover different age ranges and refer to
    different years. The output is useful only as a sensitivity denominator ("exposure-
    equivalents"), not as a head count, a 2024 age-specific driver share or measured distance
    driven. The function name and columns are retained so historical result tables remain
    reproducible. Columns: ``band, share, share_low, share_high, national_share, capped``.
    """
    national, low, high = interpolate_share(year, waves)
    records = []
    for band, weight in profile.items():
        cap = float(licence_share.get(band, 1.0))
        cap = min(cap, 1.0) if not np.isnan(cap) else 1.0
        share = min(national * weight, cap)
        records.append(
            {
                "band": band,
                "share": share,
                "share_low": min(low * weight, cap),
                "share_high": min(high * weight, cap),
                "national_share": national,
                "capped": national * weight > cap,
            }
        )
    return pd.DataFrame.from_records(records).astype({"band": "string"})
