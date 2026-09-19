"""INE resident population by province, five-year age group and sex (table 56947 extract)."""

from __future__ import annotations

from functools import cache

import pandas as pd

from dgt_stats import agebands
from dgt_stats.paths import POPULATION_PATH

NATIONAL_CODE = "ES"
SEX_LABELS = {"Hombres": "male", "Mujeres": "female", "Total": "total"}
ALL_AGES = "Todas las edades"
ROUNDING_TOLERANCE = 10


@cache
def read_population() -> pd.DataFrame:
    """The extract as a tidy frame, one row per province × age group × sex × reference date × year.

    ``province_code`` is the two-digit INE code, or ``"ES"`` for the national total. ``age_low`` and
    ``age_high`` are parsed from the group label (``age_high`` is NA for "90 y más" and for the
    all-ages row, which is flagged by ``all_ages``).
    """
    raw = pd.read_csv(POPULATION_PATH, dtype={"province": "string", "age_group": "string"})
    codes = raw.province.str.extract(r"^(\d{2}) ")[0]
    names = raw.province.str.replace(r"^\d{2} ", "", regex=True)
    parsed = [agebands.parse_age_label(label) for label in raw.age_group]
    out = pd.DataFrame(
        {
            "province_code": codes.fillna(NATIONAL_CODE).astype("string"),
            "province": names.where(codes.notna(), "Spain").astype("string"),
            "age_group": raw.age_group,
            "age_low": pd.array(
                [None if item is None else item[0] for item in parsed], dtype="Int16"
            ),
            "age_high": pd.array(
                [None if item is None else item[1] for item in parsed], dtype="Int16"
            ),
            "all_ages": (raw.age_group == ALL_AGES).to_numpy(),
            "sex": raw.sex.map(SEX_LABELS).astype("string"),
            "reference": raw.reference.astype("string"),
            "year": raw.year.astype("int16"),
            "population": raw.population.astype("int64"),
        }
    )
    if out.sex.isna().any():
        raise ValueError("population: unexpected sex label")
    keys = ["province_code", "sex", "reference", "year"]
    groups = out[~out.all_ages].groupby(keys).population.sum()
    totals = out[out.all_ages].set_index(keys).population
    # INE publishes rounded estimates: the groups differ from the all-ages row by a few persons.
    mismatch = (groups - totals).abs()
    if (mismatch > ROUNDING_TOLERANCE).any():
        raise ValueError("population: five-year groups do not sum to the all-ages row")
    return out


def _select(year: int, reference: str, sex: str, province_code: str | None) -> pd.DataFrame:
    frame = read_population()
    mask = (frame.year == year) & (frame.reference == reference) & (frame.sex == sex)
    if province_code is not None:
        mask &= frame.province_code == province_code
    selected = frame[mask]
    if selected.empty:
        raise ValueError(f"population: no rows for {year} {reference} {sex} {province_code}")
    return selected


def population(
    year: int,
    reference: str = "1 July",
    sex: str = "total",
    province_code: str = NATIONAL_CODE,
) -> pd.DataFrame:
    """Five-year age groups for one place, date and sex: ``age_group, age_low, age_high, population``."""
    rows = _select(year, reference, sex, province_code)
    rows = rows[~rows.all_ages].sort_values("age_low")
    return rows[["age_group", "age_low", "age_high", "population"]].reset_index(drop=True)


def population_by_band(
    year: int,
    bands: dict[str, agebands.Band] = agebands.ANALYSIS_BANDS,
    reference: str = "1 July",
    sex: str = "total",
    province_code: str = NATIONAL_CODE,
) -> pd.DataFrame:
    """Residents per analysis band (``band, population``); groups outside the bands are dropped."""
    groups = population(year, reference, sex, province_code)
    keys = [
        agebands.band_for(int(low), None if pd.isna(high) else int(high), bands)
        for low, high in zip(groups.age_low, groups.age_high)
    ]
    groups = groups.assign(band=pd.Series(keys, dtype="string")).dropna(subset=["band"])
    out = groups.groupby("band", sort=False).population.sum().reindex(list(bands)).reset_index()
    return out.astype({"band": "string", "population": "int64"})


def population_by_province(
    year: int, reference: str = "1 July", sex: str = "total", ages: str = "all"
) -> pd.DataFrame:
    """Residents per province (``province_code, province, population``), plus the national row.

    ``ages`` is ``"all"`` or an analysis-band key such as ``"65-74"`` / ``"75+"``.
    """
    rows = _select(year, reference, sex, None)
    if ages == "all":
        rows = rows[rows.all_ages]
        out = rows[["province_code", "province", "population"]]
    else:
        band_low, band_high = agebands.ANALYSIS_BANDS[ages]
        rows = rows[~rows.all_ages & (rows.age_low >= band_low)]
        if band_high is not None:
            rows = rows[rows.age_high <= band_high]
        out = rows.groupby(["province_code", "province"], sort=True).population.sum().reset_index()
    return out.sort_values("province_code").reset_index(drop=True)
