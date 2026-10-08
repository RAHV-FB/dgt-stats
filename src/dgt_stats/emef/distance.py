"""Road kilometres from the banded straight-line distance of EMEF trips.

From 2021 the public trip files give the straight-line (orthodromic) origin-destination distance
in seven bands: under 0.5 km, 0.5–2, 2–5, 5–10, 10–50, 50–100 and over 100 km. Two steps turn a
band into road kilometres.

**Where in its band a trip lies.** A fixed midpoint would put every 10–50 km trip at 30 km. The
trip's duration says more: a 15-minute trip in that band is near 10 km, a 50-minute one much
further. The straight-line distance is modelled as log-normal given the trip's duration and
context,

    log d = x'b + e,   e ~ N(0, s^2),   log s = g0 + g1 log(duration),

and fitted by maximum likelihood with each trip contributing the probability of its observed band
(interval censoring), so the model never contradicts a band. A trip's expected distance is then
the mean of the fitted distribution truncated to its band, which uses the band and the duration
together; the open band over 100 km gets the same treatment, so its mean is set by the durations
of those trips and not by an arbitrary cap. ``x`` holds the log duration and its square, whether
the trip stays in one municipality, whether it leaves the survey area, whether it starts or ends in
Barcelona city, the respondent's age group and the year (trips before 2021, which have no band,
are given the 2021 level). One model is fitted per mode group (walking, cycling, public transport,
driving), because speed differs by mode.

**From straight line to road.** The EMEF 2021 distance report (Institut Metròpoli for the ATM,
October 2022, Table 1) computed, for every trip with coordinates, both the straight-line distance
and the road distance from Google's Distance Matrix API: driving trips averaged 8.9 km in a
straight line and 12.9 km by road, a ratio of 1.45 (walking 1.32, cycling 1.41, public transport
1.50, all trips 1.44). These ratios are applied to the expected straight-line distances. They are
ratios of means for 2021 trips; the ratio for any one trip is unknown, so the sensitivity analysis
varies the driving ratio. Because a common factor multiplies every age group's kilometres alike,
it changes absolute rates per kilometre but not the ratio of one age group's rate to another's.

:func:`validate_against_report` reproduces the report's mean straight-line distances by mode and
its daily road distance per mobile person by age, the only published benchmarks for the method.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import optimize, stats

from dgt_stats.emef import variables as v

# EMEF 2021 distance report, Table 1: road (Google) over straight-line mean distance by mode.
ROAD_RATIO: dict[str, float] = {
    "walking": 1.4 / 1.0,
    "cycling": 4.5 / 3.2,
    "driving": 12.9 / 8.9,
    "transit": 10.3 / 6.9,
}
# The same table's mean straight-line distance (km) by mode group, and the overall mean.
REPORT_STRAIGHT_LINE_KM: dict[str, float] = {
    "walking": 1.0,
    "cycling": 3.2,
    "driving": 8.9,
    "transit": 6.9,
    "all": 4.7,
}
# Its daily road distance per mobile person (km, Google distance), by the survey's three age
# groups and overall (section 4.1, text and table).
REPORT_DAILY_ROAD_KM: dict[str, float] = {"16-29": 29.7, "30-64": 29.2, "65+": 14.7, "all": 26.5}

# The report's mode groups (Table 1 note): "Driving" is car, motorcycle, moped, lorry, van, other
# private vehicles, works bus, school bus, coach and taxi; "Transit" is bus, metro, tram, FGC,
# Rodalies, regional rail and other public transport; "Cycling" is bicycle and other non-motorised
# means. Built from the first-stage codes of each year's dictionary.
MODE_GROUP_CODES: dict[str, tuple[int, ...]] = {
    "walking": (1,),
    "cycling": (17, 18, 19),
    "transit": (5, 6, 7, 8, 9, 10, 23, 24),
    "driving": (2, 3, 4, 11, 12, 13, 14, 15, 16, 20, 21, 22, 25),
}
TRANSIT_PRIORITY = MODE_GROUP_CODES["transit"]


def mode_group(trips: pd.DataFrame) -> pd.Series:
    """The report's main-mode group for 2021–2024 trips: public transport first, then driving.

    The survey's main mode gives public transport priority over private vehicles and motorised
    over non-motorised means; the same order is applied across the three recorded stages.
    """
    stages = trips[["mode1", "mode2", "mode3"]]
    has = {name: stages.isin(codes).any(axis=1) for name, codes in MODE_GROUP_CODES.items()}
    out = pd.Series("walking", index=trips.index, dtype="object")
    out[has["cycling"]] = "cycling"
    out[has["driving"]] = "driving"
    out[has["transit"]] = "transit"
    out[stages.isin([v.MISSING_MODE]).any(axis=1) & ~(has["driving"] | has["transit"])] = "unknown"
    return out.astype("string")


@dataclass(frozen=True)
class IntervalModel:
    """A fitted interval-censored log-normal model of straight-line distance."""

    columns: tuple[str, ...]
    beta: np.ndarray
    gamma: np.ndarray
    n: int
    log_likelihood: float

    def location_scale(self, trips: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        x = design(trips, self.columns)
        log_duration = _log_duration(trips)
        return x @ self.beta, np.exp(self.gamma[0] + self.gamma[1] * log_duration)

    def expected_km(
        self,
        trips: pd.DataFrame,
        use_band: bool = True,
        max_speed_kmh: float | None = None,
        road_ratio: float = 1.0,
    ) -> np.ndarray:
        """Mean straight-line distance (km) of each trip, within its band when it has one.

        With ``max_speed_kmh``, a trip's straight-line distance is also bounded above by the
        distance its duration allows at that door-to-door road speed (``duration x speed /
        road_ratio``); where the bound falls below the band's lower edge, the lower edge is used.
        """
        mu, sigma = self.location_scale(trips)
        if use_band:
            low, high = _band_limits(trips.distance_band)
        else:
            low = np.zeros(len(trips))
            high = np.full(len(trips), np.inf)
        if max_speed_kmh is not None:
            duration = trips.duration_min.astype(float).to_numpy()
            reachable = np.where(
                np.isnan(duration), np.inf, duration / 60 * max_speed_kmh / road_ratio
            )
            high = np.minimum(high, reachable)
        known = ~np.isnan(low)
        out = np.exp(mu + sigma**2 / 2)
        inside = known & (high > low)
        out[inside] = truncated_lognormal_mean(mu[inside], sigma[inside], low[inside], high[inside])
        squeezed = known & (high <= low)
        out[squeezed] = low[squeezed]
        return out


def _log_duration(trips: pd.DataFrame) -> np.ndarray:
    # A duration of 0 or missing is treated as one minute / the median of the trip's band.
    duration = trips.duration_min.astype(float).to_numpy()
    duration = np.where(np.isnan(duration), np.nanmedian(duration), duration)
    return np.log(np.clip(duration, 1.0, 600.0))


def _band_limits(bands: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    low = np.full(len(bands), np.nan)
    high = np.full(len(bands), np.nan)
    codes = bands.astype("Int64").to_numpy(dtype=float, na_value=np.nan)
    for code, (a, b) in v.DISTANCE_BANDS.items():
        mask = codes == code
        low[mask], high[mask] = a, b
    return low, high


def design(trips: pd.DataFrame, columns: tuple[str, ...] | None = None) -> np.ndarray:
    """The covariates ``x``: duration, flow type, Barcelona ends, age group, year."""
    log_duration = _log_duration(trips)
    frame = pd.DataFrame(
        {
            "intercept": 1.0,
            "log_duration": log_duration,
            "log_duration_sq": log_duration**2,
            "same_municipality": trips.same_municipality.fillna(False).astype(float).to_numpy(),
            "leaves_survey_area": ((trips.origin_zone == 6) | (trips.destination_zone == 6))
            .astype(float)
            .to_numpy(),
            "barcelona_end": ((trips.origin_zone == 1) | (trips.destination_zone == 1))
            .astype(float)
            .to_numpy(),
        },
        index=trips.index,
    )
    for group in ("30-44", "45-64", "65+"):
        frame[f"age_{group}"] = (trips.age_group == group).astype(float).to_numpy()
    for year in range(v.DISTANCE_FROM + 1, max(v.YEARS) + 1):
        frame[f"year_{year}"] = (trips.year == year).astype(float).to_numpy()
    if columns is not None:
        frame = frame.reindex(columns=list(columns), fill_value=0.0)
    return frame.to_numpy(dtype=float)


def design_columns(trips: pd.DataFrame) -> tuple[str, ...]:
    base = ("intercept", "log_duration", "log_duration_sq", "same_municipality")
    extra = ["leaves_survey_area", "barcelona_end"]
    extra += [f"age_{g}" for g in ("30-44", "45-64", "65+")]
    extra += [f"year_{y}" for y in range(v.DISTANCE_FROM + 1, max(v.YEARS) + 1)]
    return base + tuple(extra)


def truncated_lognormal_mean(
    mu: np.ndarray, sigma: np.ndarray, low: np.ndarray, high: np.ndarray
) -> np.ndarray:
    """E[d | low <= d < high] for log d ~ N(mu, sigma^2); ``high`` may be infinite."""
    log_low = np.where(low > 0, np.log(np.maximum(low, 1e-12)), -np.inf)
    log_high = np.where(np.isinf(high), np.inf, np.log(np.maximum(high, 1e-12)))
    a = (log_low - mu) / sigma
    b = (log_high - mu) / sigma
    # Work in log space: both numerator and denominator are differences of normal tails.
    numerator = _log_diff_cdf(a - sigma, b - sigma)
    denominator = _log_diff_cdf(a, b)
    mean = np.exp(mu + sigma**2 / 2 + numerator - denominator)
    # Guard against numerical failure far in a tail: fall back to the band's geometric middle.
    fallback = np.where(np.isinf(high), low * 1.25, np.sqrt(np.maximum(low, 0.05) * high))
    bad = ~np.isfinite(mean) | (mean < low) | (mean > high)
    return np.where(bad, fallback, mean)


def _log_diff_cdf(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """log(Phi(b) - Phi(a)) computed stably on whichever side of zero the interval lies."""
    upper = a > 0
    out = np.empty_like(a, dtype=float)
    # Right of zero, use survival functions: Phi(b) - Phi(a) = S(a) - S(b).
    sa, sb = stats.norm.logsf(a[upper]), stats.norm.logsf(b[upper])
    out[upper] = sa + np.log1p(-np.exp(np.minimum(sb - sa, 0.0)))
    ca, cb = stats.norm.logcdf(a[~upper]), stats.norm.logcdf(b[~upper])
    out[~upper] = cb + np.log1p(-np.exp(np.minimum(ca - cb, 0.0)))
    return out


def fit(trips: pd.DataFrame, columns: tuple[str, ...] | None = None) -> IntervalModel:
    """Maximum-likelihood fit on trips with a known band (unweighted: a model of the trip)."""
    trips = trips[trips.distance_band.notna()]
    columns = columns or design_columns(trips)
    x = design(trips, columns)
    log_duration = _log_duration(trips)
    low, high = _band_limits(trips.distance_band)
    log_low = np.where(low > 0, np.log(np.maximum(low, 1e-12)), -np.inf)
    log_high = np.where(np.isinf(high), np.inf, np.log(high))
    k = x.shape[1]
    # Start from least squares on the log band midpoints.
    middle = np.where(
        np.isinf(log_high),
        log_low + 0.25,
        (np.where(np.isinf(log_low), np.log(0.25), log_low) + log_high) / 2,
    )
    start_beta = np.linalg.lstsq(x, middle, rcond=None)[0]
    start = np.concatenate([start_beta, [np.log(0.5), 0.0]])

    def negative_log_likelihood(theta: np.ndarray) -> float:
        beta, gamma = theta[:k], theta[k:]
        mu = x @ beta
        sigma = np.exp(gamma[0] + gamma[1] * log_duration)
        return -float(np.sum(_log_diff_cdf((log_low - mu) / sigma, (log_high - mu) / sigma)))

    result = optimize.minimize(
        negative_log_likelihood, start, method="L-BFGS-B", options={"maxiter": 2000}
    )
    if not result.success:
        raise RuntimeError(f"distance model did not converge: {result.message}")
    return IntervalModel(
        columns=tuple(columns),
        beta=result.x[:k],
        gamma=result.x[k:],
        n=len(trips),
        log_likelihood=-float(result.fun),
    )


def validate_against_report() -> pd.DataFrame:
    """The model's 2021 means beside the EMEF 2021 distance report's: mean straight-line distance
    of a trip by mode group, and daily road distance per mobile person by age group."""
    from dgt_stats.emef import ingest

    trips = ingest.trips()
    measured = trips[trips.year >= v.DISTANCE_FROM].copy()
    measured["group"] = mode_group(measured)
    year = measured[(measured.year == 2021) & measured.distance_band.notna()].copy()
    year["km_straight"] = np.nan
    for group in ROAD_RATIO:
        model = fit(measured[measured.group == group])
        part = year[year.group == group]
        year.loc[part.index, "km_straight"] = model.expected_km(part)
    year = year[year.km_straight.notna()]
    year["km_road"] = year.km_straight * year.group.map(ROAD_RATIO)
    rows = []
    for group in (*ROAD_RATIO, "all"):
        part = year if group == "all" else year[year.group == group]
        rows.append(
            {
                "measure": f"mean straight-line km per trip: {group}",
                "report": REPORT_STRAIGHT_LINE_KM[group],
                "model": float(np.average(part.km_straight, weights=part.weight)),
                "trips": len(part),
            }
        )
    daily = year.groupby("person_id").agg(
        km=("km_road", "sum"), weight=("weight", "first"), age=("age3", "first")
    )
    for age in ("16-29", "30-64", "65+", "all"):
        part = daily if age == "all" else daily[daily.age == age]
        rows.append(
            {
                "measure": f"daily road km per mobile person: {age}",
                "report": REPORT_DAILY_ROAD_KM[age],
                "model": float(np.average(part.km, weights=part.weight)),
                "trips": int(len(part)),
            }
        )
    out = pd.DataFrame(rows)
    out["relative_difference"] = out.model / out.report - 1
    return out.rename(columns={"trips": "n"})
