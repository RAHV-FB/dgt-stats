"""Where the regional microdata meet the national layer: only at a shared aggregation level.

No crash in one source is matched to a crash in another. Catalonia's file has no identifier,
Barcelona's identifier exists only in Barcelona's tables, and the DGT microdata's identifier only
in the DGT file; date, place or casualty matching would be a guess and is forbidden by the data
contract. Two comparisons are legitimate because both sides share a real key:

1. **Catalonia against the DGT microdata, by province and year.** Key: the four Catalan
   demarcations, which are the provinces with INE codes 08, 17, 25 and 43, and the calendar
   year (2016-2023, the years both cover). Unit before: one crash in each source. Unit after: one
   province-year with two counts side by side. The definitions are not shown to be equal (the
   Catalan file does not state its death window; DGT publishes deaths within 24 hours and within
   30 days), so the comparison reports both DGT windows and is a reconciliation, not a merge.
2. **Catalonia per resident, by province and year.** Key: province code and year; denominator:
   INE residents on 1 July of the year (``io_population``, table 56947). Unit after: province-year. This is
   a rate per resident of the province, not a risk per trip or kilometre; it says nothing about
   who travelled where.

Barcelona 2025 has no counterpart: the DGT microdata end in 2024, INE's table is by province
rather than municipality, and Catalonia's file ends in 2023.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import io_population
from dgt_stats.microdata import catalonia
from dgt_stats.paths import DGT_PROCESSED_CRASHES, TABLES_DIR

PROVINCES = catalonia.DEMARCATION_PROVINCE_CODE


def dgt_catalan_counts() -> pd.DataFrame:
    columns = [
        "ANYO",
        "COD_PROVINCIA",
        "TOTAL_MU24H",
        "TOTAL_HG24H",
        "TOTAL_MU30DF",
        "TOTAL_HG30DF",
    ]
    dgt = pd.read_parquet(DGT_PROCESSED_CRASHES, columns=columns)
    dgt = dgt[pd.to_numeric(dgt.COD_PROVINCIA, errors="coerce").isin(PROVINCES.values())].copy()
    for column in columns[2:]:
        dgt[column] = pd.to_numeric(dgt[column], errors="coerce").fillna(0)
    dgt["province_code"] = pd.to_numeric(dgt.COD_PROVINCIA).astype(int)
    dgt["fatal_30d"] = dgt.TOTAL_MU30DF > 0
    dgt["fatal_or_serious_30d"] = (dgt.TOTAL_MU30DF + dgt.TOTAL_HG30DF) > 0
    dgt["fatal_24h"] = dgt.TOTAL_MU24H > 0
    dgt["fatal_or_serious_24h"] = (dgt.TOTAL_MU24H + dgt.TOTAL_HG24H) > 0
    return (
        dgt.groupby(["ANYO", "province_code"])[
            ["fatal_30d", "fatal_or_serious_30d", "fatal_24h", "fatal_or_serious_24h"]
        ]
        .sum()
        .astype(int)
        .add_prefix("dgt_crashes_")
        .reset_index()
        .rename(columns={"ANYO": "year"})
    )


def catalonia_vs_dgt() -> pd.DataFrame:
    cat = catalonia.read()
    counts = (
        cat.groupby(["year", "province_code", "demarcation"])
        .agg(cat_crashes_fatal_or_serious=("fatal", "size"), cat_crashes_fatal=("fatal", "sum"))
        .reset_index()
    )
    dgt = dgt_catalan_counts()
    years = sorted(set(counts.year) & set(dgt.year))
    merged = counts[counts.year.isin(years)].merge(
        dgt, on=["year", "province_code"], how="inner", validate="one_to_one"
    )
    merged["ratio_fatal_or_serious_30d"] = (
        merged.cat_crashes_fatal_or_serious / merged.dgt_crashes_fatal_or_serious_30d
    )
    merged["ratio_fatal_30d"] = merged.cat_crashes_fatal / merged.dgt_crashes_fatal_30d
    merged["ratio_fatal_24h"] = merged.cat_crashes_fatal / merged.dgt_crashes_fatal_24h
    return merged


# Annual rates divide by the mid-year population, as every national per-resident rate does.
RESIDENTS_REFERENCE = "1 July"


def catalonia_per_resident() -> pd.DataFrame:
    cat = catalonia.read()
    counts = (
        cat.groupby(["year", "province_code", "demarcation"])
        .agg(
            crashes_fatal_or_serious=("fatal", "size"),
            crashes_fatal=("fatal", "sum"),
            deaths=("n_deaths", "sum"),
        )
        .reset_index()
    )
    population = io_population.read_population()
    population = population[
        population.all_ages
        & population.sex.eq("total")
        & population.reference.eq(RESIDENTS_REFERENCE)
    ].copy()
    population["province_code"] = pd.to_numeric(population.province_code, errors="coerce")
    population = population[population.province_code.isin(PROVINCES.values())]
    population = population[["year", "province_code", "population"]].astype(
        {"year": int, "province_code": int}
    )
    out = counts.merge(population, on=["year", "province_code"], how="inner", validate="one_to_one")
    for column in ("crashes_fatal_or_serious", "crashes_fatal", "deaths"):
        out[f"{column}_per_100k_residents"] = out[column] / out.population * 1e5
    return out


def write() -> dict[str, pd.DataFrame]:
    tables = {
        "cat_vs_dgt_province_year": catalonia_vs_dgt(),
        "cat_per_resident_province_year": catalonia_per_resident(),
    }
    for name, frame in tables.items():
        frame.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.6g")
    return tables
