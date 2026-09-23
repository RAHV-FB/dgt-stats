"""Speed, alcohol, distraction and other concurrent factors: what DGT's factor tables can support.

DGT's speed report (``io_reports``) publishes, for Spain without Cataluña and País Vasco and for
2014–2023, the injury crashes in which the police recorded each of five *concurrent factors*
(inappropriate speed, distraction, alcohol, drugs, illegal manoeuvres), and for speed alone the
deaths in those crashes by road type. Two uses follow, each with its own limit.

**Speed as a severity factor.** The deaths per 100 injury crashes in which speed was recorded are
set against the same ratio for the crashes in which it was not, within the same scope. The scope's
totals come from the report's own series and, by road type, from the crash microdata restricted to
the same provinces; the microdata reproduce the report's totals exactly (``validate``). Comparing
within road type matters because speed-related crashes concentrate on conventional interurban
roads, where every crash is more often fatal. The ratio is an association: a factor that is
recorded after the fact is more likely to be investigated, and so recorded, when someone has died,
which would inflate it; unrecorded speed in the comparison group would deflate it. Neither
direction can be measured from these tables, so the page reports the ratio as what it is.

**Other factors across years.** A factor's share of injury crashes can only be compared between
years that recorded it the same way. ``factor_consistency`` flags every year-to-year change in a
factor's share larger than ``BREAK_RATIO`` (a 25 % jump or fall in a single year, which no road
behaviour produces across 20,000–50,000 crashes) as a recording break, and treats a change it
cannot test (fewer than ``MIN_CRASHES`` crashes in either year) as a break too.
``comparable_windows`` lists the runs of years between breaks, within which a change in share can
be read as a change in what the police recorded, not in how they recorded it.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from dgt_stats import io_reports, rates
from dgt_stats.paths import PROCESSED_DATA_DIR

PROCESSED_CRASHES = PROCESSED_DATA_DIR / "accidentes.parquet"

# Provinces outside the speed report's scope: Barcelona, Girona, Lleida, Tarragona (Cataluña) and
# Araba/Álava, Gipuzkoa, Bizkaia (País Vasco), by INE code.
EXCLUDED_PROVINCES = frozenset({8, 17, 25, 43, 1, 20, 48})
REPORT_ROAD_TYPES = {
    "Autopista": "motorway",
    "Autovía": "dual_carriageway",
    "Resto de vías interurbanas": "other_interurban",
    "Vías urbanas": "urban",
}
ROAD_TYPE_LABELS = {
    "motorway": "Motorways",
    "dual_carriageway": "Dual carriageways",
    "other_interurban": "Other interurban roads",
    "urban": "Urban streets",
    "interurban": "All interurban roads",
    "all": "All roads",
}
FACTOR_LABELS = {
    "Conducción distraída o desatenta": "Distraction or inattention",
    "Velocidad inadecuada": "Inappropriate speed",
    "Maniobras antirreglamentarias*": "Illegal manoeuvres",
    "Alcohol": "Alcohol",
    "Drogas": "Drugs",
}
ZONE_LABELS = {"all": "All roads", "interurban": "Interurban roads", "urban": "Urban streets"}
# A single-year change in a factor's share beyond this ratio (either way) is a recording break.
BREAK_RATIO = 1.25
# Below this many crashes in either year the change is too noisy for the rule to apply.
MIN_CRASHES = 200


def report_road_type(zone: pd.Series, tipo_via: pd.Series) -> pd.Series:
    """The report's four road types from the microdata's zone and road-type code."""
    code = pd.to_numeric(tipo_via, errors="coerce").fillna(0).to_numpy()
    urban = (zone == "urban").fillna(False).to_numpy(dtype=bool)
    interurban = np.where(
        np.isin(code, [1, 2]),
        "motorway",
        np.where(code == 3, "dual_carriageway", "other_interurban"),
    )
    return pd.Series(np.where(urban, "urban", interurban), index=zone.index, dtype="string")


@cache
def scoped_microdata_totals() -> pd.DataFrame:
    """Injury crashes and 30-day deaths per year and report road type, in the report's scope."""
    crashes = pd.read_parquet(
        PROCESSED_CRASHES,
        columns=["ANYO", "COD_PROVINCIA", "zone", "TIPO_VIA", "n_deaths"],
    )
    province = pd.to_numeric(crashes.COD_PROVINCIA, errors="coerce")
    crashes = crashes[~province.isin(EXCLUDED_PROVINCES)].copy()
    crashes["road_type"] = report_road_type(crashes.zone, crashes.TIPO_VIA)
    out = (
        crashes.groupby(["ANYO", "road_type"])
        .agg(crashes=("ANYO", "size"), deaths=("n_deaths", "sum"))
        .reset_index()
        .rename(columns={"ANYO": "year"})
    )
    return out.astype({"year": "int16", "road_type": "string"})


def _report() -> pd.DataFrame:
    return io_reports.read_report()


def report_totals() -> pd.DataFrame:
    """The report's own totals: injury crashes and deaths per year and zone (Tables 1–3)."""
    report = _report()
    series = report[report.breakdown == "series"]
    names = {"Siniestros con víctimas": "crashes", "Personas fallecidas": "deaths"}
    series = series[series.category.isin(names)]
    out = series.assign(
        metric=series.category.map(names), year=series.column.astype(int)
    ).pivot_table(index=["year", "zone"], columns="metric", values="value", aggfunc="first")
    return out.reset_index().astype({"year": "int16", "zone": "string"})


def speed_crashes() -> pd.DataFrame:
    """Crashes and deaths with inappropriate speed recorded, per year and report road type."""
    report = _report()
    rows = report[(report.breakdown == "road_type") & report.metric.isin(["crashes", "deaths"])]
    rows = rows[rows.category.isin(REPORT_ROAD_TYPES)]
    out = rows.assign(
        road_type=rows.category.map(REPORT_ROAD_TYPES), year=rows.column.astype(int)
    ).pivot_table(index=["year", "road_type"], columns="metric", values="value", aggfunc="first")
    out = out.reset_index().rename(columns={"crashes": "speed_crashes", "deaths": "speed_deaths"})
    return out.astype({"year": "int16", "road_type": "string"})


def _severity_row(year, road_type, speed_c, speed_d, total_c, total_d, source) -> dict:
    other_c, other_d = total_c - speed_c, total_d - speed_d
    speed_rate, speed_low, speed_high = rates.rate(speed_d, speed_c, per=100)
    other_rate, other_low, other_high = rates.rate(other_d, other_c, per=100)
    ratio, low, high = rates.rate_ratio(speed_d, speed_c, other_d, other_c)
    return {
        "year": year,
        "road_type": road_type,
        "road_type_label": ROAD_TYPE_LABELS[road_type],
        "totals_source": source,
        "speed_crashes": speed_c,
        "speed_deaths": speed_d,
        "other_crashes": other_c,
        "other_deaths": other_d,
        "share_of_crashes": speed_c / total_c,
        "share_of_deaths": speed_d / total_d if total_d else np.nan,
        "speed_deaths_per_100": speed_rate,
        "speed_low": speed_low,
        "speed_high": speed_high,
        "other_deaths_per_100": other_rate,
        "other_low": other_low,
        "other_high": other_high,
        "rate_ratio": ratio,
        "ratio_low": low,
        "ratio_high": high,
    }


def speed_severity() -> pd.DataFrame:
    """Deaths per 100 injury crashes with and without recorded speed, by year and road type.

    Zone rows (all roads, all interurban, urban) use the report's own totals and cover 2014–2023;
    rows by interurban road type use the microdata totals of the same scope and cover 2016–2023.
    """
    speed = speed_crashes()
    totals = report_totals().set_index(["year", "zone"])
    micro = scoped_microdata_totals().set_index(["year", "road_type"])
    records = []
    for year, group in speed.groupby("year"):
        year = int(year)
        by_type = group.set_index("road_type")
        interurban = by_type.loc[["motorway", "dual_carriageway", "other_interurban"]].sum()
        zone_speed = {
            "all": by_type[["speed_crashes", "speed_deaths"]].sum(),
            "interurban": interurban,
            "urban": by_type.loc["urban"],
        }
        for zone, values in zone_speed.items():
            total = totals.loc[(year, zone)]
            records.append(
                _severity_row(
                    year,
                    zone,
                    float(values.speed_crashes),
                    float(values.speed_deaths),
                    float(total.crashes),
                    float(total.deaths),
                    "report",
                )
            )
        for road_type in ("motorway", "dual_carriageway", "other_interurban"):
            if (year, road_type) not in micro.index:
                continue
            total = micro.loc[(year, road_type)]
            row = by_type.loc[road_type]
            records.append(
                _severity_row(
                    year,
                    road_type,
                    float(row.speed_crashes),
                    float(row.speed_deaths),
                    float(total.crashes),
                    float(total.deaths),
                    "microdata",
                )
            )
    return pd.DataFrame.from_records(records)


def speed_severity_pooled() -> pd.DataFrame:
    """The 2016–2023 ratio pooled by road type, then adjusted for road type and year.

    The pooled rows sum the eight years. The adjusted row is the speed coefficient of a
    quasi-Poisson model of deaths with the number of crashes as exposure, and road type and year
    as factors: the ratio with the concentration of speed crashes on deadlier roads taken out.
    """
    table = speed_severity()
    detail = table[
        table.road_type.isin(["motorway", "dual_carriageway", "other_interurban", "urban"])
    ]
    detail = detail[detail.year >= 2016]
    records = []
    for road_type, group in detail.groupby("road_type", sort=False):
        sums = group[["speed_crashes", "speed_deaths", "other_crashes", "other_deaths"]].sum()
        total_c = sums.speed_crashes + sums.other_crashes
        total_d = sums.speed_deaths + sums.other_deaths
        row = _severity_row(
            "2016-2023",
            road_type,
            sums.speed_crashes,
            sums.speed_deaths,
            total_c,
            total_d,
            "pooled",
        )
        records.append(row)
    long = pd.concat(
        [
            detail[["year", "road_type", "speed_crashes", "speed_deaths"]]
            .rename(columns={"speed_crashes": "crashes", "speed_deaths": "deaths"})
            .assign(speed=1),
            detail[["year", "road_type", "other_crashes", "other_deaths"]]
            .rename(columns={"other_crashes": "crashes", "other_deaths": "deaths"})
            .assign(speed=0),
        ],
        ignore_index=True,
    )
    long = long.astype({"crashes": float, "deaths": float, "road_type": str})
    result = smf.glm(
        "deaths ~ speed + C(road_type) + C(year)",
        data=long,
        family=sm.families.Poisson(),
        offset=np.log(long.crashes),
    ).fit(scale="X2")
    coefficient, se = float(result.params["speed"]), float(result.bse["speed"])
    crude = records_crude(detail)
    records.append(
        {
            "year": "2016-2023",
            "road_type": "adjusted",
            "road_type_label": "All roads, adjusted for road type and year",
            "totals_source": "model",
            "rate_ratio": float(np.exp(coefficient)),
            "ratio_low": float(np.exp(coefficient - 1.96 * se)),
            "ratio_high": float(np.exp(coefficient + 1.96 * se)),
            "crude_ratio": crude,
            "dispersion": float(result.scale),
        }
    )
    return pd.DataFrame.from_records(records)


def records_crude(detail: pd.DataFrame) -> float:
    """The unadjusted 2016–2023 ratio over all four road types, for comparison with the model."""
    sums = detail[["speed_crashes", "speed_deaths", "other_crashes", "other_deaths"]].sum()
    return float(
        (sums.speed_deaths / sums.speed_crashes) / (sums.other_deaths / sums.other_crashes)
    )


# --------------------------------------------------------------------------- other factors


def factor_shares() -> pd.DataFrame:
    """Injury crashes with each concurrent factor recorded, and their share, per year and zone."""
    report = _report()
    rows = report[(report.breakdown == "factors") & (report.metric == "crashes")]
    rows = rows.assign(year=rows.column.astype(int), factor=rows.category.map(FACTOR_LABELS))
    if rows.factor.isna().any():
        unknown = sorted(rows.loc[rows.factor.isna(), "category"].unique())
        raise ValueError(f"speed report: unexpected factor labels {unknown}")
    totals = report_totals().set_index(["year", "zone"]).crashes
    out = rows[["year", "zone", "factor", "value"]].rename(columns={"value": "crashes"})
    out["all_crashes"] = [totals.loc[(y, z)] for y, z in zip(out.year, out.zone)]
    out["share"] = out.crashes / out.all_crashes
    out["zone_label"] = out.zone.map(ZONE_LABELS)
    out = out.sort_values(["zone", "factor", "year"]).reset_index(drop=True)
    return out.astype({"year": "int16", "zone": "string", "factor": "string"})


def factor_consistency(
    break_ratio: float = BREAK_RATIO, min_crashes: int = MIN_CRASHES
) -> pd.DataFrame:
    """Every year-to-year change in each factor's share, and whether it is a recording break."""
    shares = factor_shares()
    records = []
    for (zone, factor), group in shares.groupby(["zone", "factor"], sort=False):
        group = group.sort_values("year")
        previous = None
        for row in group.itertuples(index=False):
            if previous is not None:
                ratio = row.share / previous.share if previous.share else np.nan
                small = min(row.crashes, previous.crashes) < min_crashes
                jump = bool(ratio > break_ratio or ratio < 1 / break_ratio)
                # A change that cannot be tested is not shown to be comparable either.
                is_break = small or jump
                records.append(
                    {
                        "zone": zone,
                        "zone_label": ZONE_LABELS[zone],
                        "factor": factor,
                        "from_year": int(previous.year),
                        "to_year": int(row.year),
                        "share_from": previous.share,
                        "share_to": row.share,
                        "share_ratio": ratio,
                        "too_few": small,
                        "jump": jump and not small,
                        "is_break": is_break,
                    }
                )
            previous = row
    return pd.DataFrame.from_records(records)


def comparable_windows(
    break_ratio: float = BREAK_RATIO, min_crashes: int = MIN_CRASHES
) -> pd.DataFrame:
    """Runs of consecutive years with no recording break, per factor and zone.

    A single-year run whose count is below ``min_crashes`` is marked ``too_few``: it is too small
    to test against its neighbours and is not compared with anything.
    """
    shares = factor_shares().set_index(["zone", "factor", "year"])
    changes = factor_consistency(break_ratio, min_crashes)
    records = []
    for (zone, factor), group in changes.groupby(["zone", "factor"], sort=False):
        group = group.sort_values("to_year")
        start = int(group.from_year.iloc[0])
        breaks = [int(row.to_year) for row in group.itertuples() if row.is_break]
        edges = [start, *breaks, int(group.to_year.iloc[-1]) + 1]
        for first, next_start in zip(edges, edges[1:]):
            last = next_start - 1
            years = range(first, last + 1)
            counts = [float(shares.loc[(zone, factor, y), "crashes"]) for y in years]
            first_share = float(shares.loc[(zone, factor, first), "share"])
            last_share = float(shares.loc[(zone, factor, last), "share"])
            records.append(
                {
                    "zone": zone,
                    "zone_label": ZONE_LABELS[zone],
                    "factor": factor,
                    "first_year": first,
                    "last_year": last,
                    "n_years": last - first + 1,
                    "too_few": min(counts) < min_crashes,
                    "share_first": first_share,
                    "share_last": last_share,
                    "change_in_share": last_share / first_share - 1 if first_share else np.nan,
                }
            )
    return pd.DataFrame.from_records(records)


def factor_shares_segmented(
    break_ratio: float = BREAK_RATIO, min_crashes: int = MIN_CRASHES
) -> pd.DataFrame:
    """``factor_shares`` with the comparable window each year belongs to (``segment``, from 0)."""
    shares = factor_shares()
    windows = comparable_windows(break_ratio, min_crashes)
    segments = []
    for row in shares.itertuples(index=False):
        match = windows[
            (windows.zone == row.zone)
            & (windows.factor == row.factor)
            & (windows.first_year <= row.year)
            & (windows.last_year >= row.year)
        ]
        segments.append(int(match.index[0]) if len(match) else -1)
    out = shares.assign(segment=segments)
    out["segment"] = out.groupby(["zone", "factor"]).segment.rank(method="dense").astype(int) - 1
    return out
