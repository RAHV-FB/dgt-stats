"""Reconciliation checks between the interim layer and the published DGT totals.

Each check returns :class:`Result` rows. ``run_all`` writes them to ``reports/tables/validation.csv``
together with a per-year missingness profile of the crash microdata.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from dgt_stats import codes, io_exposure, io_microdata, io_tables, vehicles
from dgt_stats.paths import MICRODATA_YEARS, TABLES_DIR

log = logging.getLogger(__name__)

VALIDATION_PATH = TABLES_DIR / "validation.csv"
MISSINGNESS_PATH = TABLES_DIR / "missingness_by_year.csv"

CENSUS_TOLERANCE = 0.005
CENSUS_AGE_TOLERANCE = 0.02
VEHICLE_TABLE_TOLERANCE = 0.001

VICTIM_COLUMNS = {
    "deaths_30d": "TOTAL_MU30DF",
    "hospitalised_30d": "TOTAL_HG30DF",
    "non_hospitalised_30d": "TOTAL_HL30DF",
    "victims_30d": "TOTAL_VICTIMAS_30DF",
}


@dataclass
class Result:
    check: str
    year: int | None
    unit: str
    expected: float | None
    actual: float | None
    passed: bool
    note: str = ""


def _normalise_province(name: str) -> str:
    """'Balears, Illes' (dictionary) and 'Balears (Illes)' (tables) become the same key."""
    text = " ".join(str(name).split())
    if ", " in text:
        head, tail = text.split(", ", 1)
        text = f"{head} ({tail})"
    return text.lower()


def _province_names(frame: pd.DataFrame) -> pd.Series:
    labels = codes.labels_for("COD_PROVINCIA")
    return frame["COD_PROVINCIA"].astype("Int64").astype(str).map(labels).map(_normalise_province)


# --------------------------------------------------------------------------- checks


def check_row_counts(crashes: pd.DataFrame, annual: pd.DataFrame) -> list[Result]:
    """Check 1: rows per year equal the yearbook crash totals."""
    expected = annual[(annual.metric == "crashes") & (annual.zone == "all")].set_index("year").value
    actual = crashes.groupby("ANYO").size()
    return [
        Result(
            "row_count",
            int(year),
            "crashes",
            float(expected.loc[year]),
            float(actual.get(year, 0)),
            expected.loc[year] == actual.get(year, 0),
            "" if year in actual.index else "year missing from interim layer",
        )
        for year in MICRODATA_YEARS
    ]


def check_victim_totals(
    crashes: pd.DataFrame, annual: pd.DataFrame, monthly: pd.DataFrame
) -> list[Result]:
    """Check 2: 30-day victim sums per year equal the yearbook; 24-hour deaths equal the 24 h series."""
    results: list[Result] = []
    sums = crashes.groupby("ANYO")[list(VICTIM_COLUMNS.values())].sum()
    sums = sums.reindex(list(MICRODATA_YEARS), fill_value=0)
    for metric, column in VICTIM_COLUMNS.items():
        expected = (
            annual[(annual.metric == metric) & (annual.zone == "all")].set_index("year").value
        )
        for year, actual in sums[column].items():
            results.append(
                Result(
                    "victim_total",
                    int(year),
                    metric,
                    float(expected.loc[year]),
                    float(actual),
                    expected.loc[year] == actual,
                )
            )
    deaths_24h = (
        monthly[(monthly.metric == "deaths_24h") & (monthly.zone == "all")]
        .groupby("year")
        .annual_total.first()
    )
    actual_24h = (
        crashes.groupby("ANYO")["TOTAL_MU24H"].sum().reindex(list(MICRODATA_YEARS), fill_value=0)
    )
    for year, actual in actual_24h.items():
        results.append(
            Result(
                "victim_total",
                int(year),
                "deaths_24h",
                float(deaths_24h.loc[year]),
                float(actual),
                deaths_24h.loc[year] == actual,
            )
        )
    return results


def check_tables_2024(
    crashes: pd.DataFrame, province_table: pd.DataFrame, month_table: pd.DataFrame
) -> list[Result]:
    """Check 3: 2024 province and month totals equal TABLA 1.1 and TABLA 3.1."""
    results: list[Result] = []
    year = crashes[crashes.ANYO == 2024].copy()
    year["province"] = _province_names(year)

    table = province_table[(~province_table.is_total) & (province_table.zone == "all")]
    for metric, column in (("crashes", None), ("deaths_30d", "TOTAL_MU30DF")):
        expected = table[table.metric == metric].assign(
            key=lambda d: d.province.map(_normalise_province)
        )
        expected = expected.set_index("key").value
        actual = (
            year.groupby("province").size()
            if column is None
            else year.groupby("province")[column].sum()
        )
        for province, value in expected.items():
            got = actual.get(province)
            results.append(
                Result(
                    "table_1_1_province",
                    2024,
                    f"{metric}:{province}",
                    float(value),
                    None if got is None else float(got),
                    got is not None and value == got,
                )
            )

    table = month_table[(~month_table.is_total) & (month_table.zone == "all")]
    for metric, column in (("crashes", None), ("deaths_30d", "TOTAL_MU30DF")):
        expected = table[table.metric == metric].set_index("month").value
        actual = year.groupby("MES").size() if column is None else year.groupby("MES")[column].sum()
        for month, value in expected.items():
            got = actual.get(month)
            results.append(
                Result(
                    "table_3_1_month",
                    2024,
                    f"{metric}:{int(month):02d}",
                    float(value),
                    None if got is None else float(got),
                    got is not None and value == got,
                )
            )
    return results


def check_unique_keys(crashes: pd.DataFrame) -> list[Result]:
    """Check 4: (ANYO, ID_ACCIDENTE) is unique."""
    duplicates = crashes.duplicated(["ANYO", "ID_ACCIDENTE"]).groupby(crashes.ANYO).sum()
    return [
        Result("unique_key", int(year), "duplicate_rows", 0.0, float(n), n == 0)
        for year, n in duplicates.items()
    ]


def check_code_domains(crashes: pd.DataFrame) -> list[Result]:
    """Check 5: every non-empty value of each coded column is in the dictionary or a missing marker."""
    results: list[Result] = []
    for column in codes.CATEGORICAL_COLUMNS:
        allowed = codes.allowed_codes(column)
        observed = crashes[column].dropna().unique()
        unexpected = sorted({key for key in map(codes._code_key, observed) if key not in allowed})
        results.append(
            Result(
                "code_domain",
                None,
                column,
                0.0,
                float(len(unexpected)),
                not unexpected,
                "" if not unexpected else "unexpected codes: " + ", ".join(unexpected),
            )
        )
    return results


def check_census(census: pd.DataFrame, province_table: pd.DataFrame) -> list[Result]:
    """Check 6: the 2025 census extract agrees with the published province table."""
    results: list[Result] = []
    labels = codes.labels_for("COD_PROVINCIA")
    extract = census[census.census_year == 2025].copy()
    extract["province"] = (
        extract.province_code.astype(int).astype(str).map(labels).map(_normalise_province)
    )
    actual = extract.groupby("province").n_drivers.sum()
    table = province_table.copy()
    table["key"] = table.province.map(_normalise_province)

    total_expected = float(table[table.is_total].total.iloc[0])
    total_actual = float(extract.n_drivers.sum())
    results.append(
        Result(
            "census_2025",
            2025,
            "drivers:total",
            total_expected,
            total_actual,
            abs(total_actual - total_expected) <= CENSUS_TOLERANCE * total_expected,
            f"difference {total_actual - total_expected:+.0f}",
        )
    )
    for _, row in table[~table.is_total].iterrows():
        got = actual.get(row.key)
        expected = float(row.total)
        results.append(
            Result(
                "census_2025",
                2025,
                f"drivers:{row.key}",
                expected,
                None if got is None else float(got),
                got is not None and abs(got - expected) <= CENSUS_TOLERANCE * expected,
                "" if got is None else f"difference {got - expected:+.0f}",
            )
        )
    return results


def check_driver_tables(driver_victims: pd.DataFrame, road_users: pd.DataFrame) -> list[Result]:
    """Check 7: driver deaths in tables 4.1.1 equal the yearbook series of driver deaths, by zone."""
    results: list[Result] = []
    deaths = driver_victims[driver_victims.is_total & (driver_victims.severity == "deaths_30d")]
    actual = deaths.groupby(["year", "zone"]).value.sum()
    expected = (
        road_users[
            (road_users.population == "drivers")
            & (road_users.severity == "deaths_30d")
            & road_users.is_total
        ]
        .set_index(["year", "zone"])
        .value
    )
    for year in sorted(deaths.year.unique()):
        for zone in ("interurban", "urban", "all"):
            got = (
                float(actual.get((year, "interurban"), 0) + actual.get((year, "urban"), 0))
                if zone == "all"
                else float(actual.get((year, zone), 0))
            )
            want = expected.get((year, zone))
            results.append(
                Result(
                    "driver_deaths",
                    int(year),
                    f"driver_deaths:{zone}",
                    None if want is None else float(want),
                    got,
                    want is not None and float(want) == got,
                )
            )
    return results


def check_census_age(census_tables: pd.DataFrame, census_text: pd.DataFrame) -> list[Result]:
    """Check 8: the 2023 census text file agrees with the 2023 published age table per band."""
    results: list[Result] = []
    year = 2023
    tables = census_tables[(census_tables.census_year == year) & (census_tables.sex == "total")]
    text = census_text[census_text.census_year == year].groupby("band").n_drivers.sum()
    for row in tables.itertuples():
        got = text.get(row.band)
        expected = float(row.n_drivers)
        tolerance = CENSUS_AGE_TOLERANCE * expected if row.band != "unknown" else float("inf")
        results.append(
            Result(
                "census_age_2023",
                year,
                f"drivers:{row.band}",
                expected,
                None if got is None else float(got),
                got is not None and abs(got - expected) <= tolerance,
                "" if got is None else f"difference {got - expected:+.0f}",
            )
        )
    return results


# --------------------------------------------------------------------------- missingness


PROFILE_COLUMNS = codes.CATEGORICAL_COLUMNS + (
    "COD_MUNICIPIO",
    "CARRETERA",
    "KM",
    "CARRETERA_CRUCE",
)


def missingness_profile(crashes: pd.DataFrame) -> pd.DataFrame:
    """Share of empty / 999 / 998 / explicit-unknown values per year and column."""
    records = []
    for year, group in crashes.groupby("ANYO"):
        n = len(group)
        for column in PROFILE_COLUMNS:
            series = group[column]
            if column in codes.CATEGORICAL_COLUMNS:
                state = codes.status(column, series)
                counts = state.value_counts()
                records.append(
                    {
                        "year": int(year),
                        "column": column,
                        "rows": n,
                        "share_empty": counts.get("empty", 0) / n,
                        "share_not_specified": counts.get("not_specified", 0) / n,
                        "share_not_applicable": counts.get("not_applicable", 0) / n,
                        "share_unknown": counts.get("unknown", 0) / n,
                    }
                )
            else:
                records.append(
                    {
                        "year": int(year),
                        "column": column,
                        "rows": n,
                        "share_empty": series.isna().mean(),
                        "share_not_specified": 0.0,
                        "share_not_applicable": 0.0,
                        "share_unknown": 0.0,
                    }
                )
    out = pd.DataFrame.from_records(records)
    out["share_observed"] = 1 - out[
        ["share_empty", "share_not_specified", "share_not_applicable", "share_unknown"]
    ].sum(axis=1)
    return out.round(4)


def check_vehicle_tables(
    crashes: pd.DataFrame, units: pd.DataFrame, victims: pd.DataFrame
) -> list[Result]:
    """Checks 9 and 10: the yearbook vehicle tables against the microdata, 2020–2024.

    TABLA 2.3 vehicles involved (its total less pedestrians) must be within 0.1 % of the microdata
    ``TOTAL_VEHICULOS`` sum (2024 is published with a 66-vehicle gap). TABLA 2.2 deaths by means of
    transport, summed over drivers, passengers and pedestrians and over both zones, must equal the
    microdata ``TOT_*_MU30DF`` columns exactly for every vehicle group.
    """
    results: list[Result] = []
    pedestrian_units = vehicles.VEHICLE_GROUPS["pedestrian"]["units"]
    for year in sorted(units.year.unique()):
        year_crashes = crashes[crashes.ANYO == year]
        block = units[(units.year == year) & (units.zone == "all") & (units.metric == "crashes")]
        expected = float(block[block.is_total].value.sum()) - float(
            block[block.unit_type.isin(pedestrian_units)].value.sum()
        )
        actual = float(year_crashes["TOTAL_VEHICULOS"].sum())
        results.append(
            Result(
                "table_2_3_vehicles",
                int(year),
                "vehicles",
                expected,
                actual,
                abs(actual - expected) <= VEHICLE_TABLE_TOLERANCE * expected,
                f"tolerance {VEHICLE_TABLE_TOLERANCE:.1%}",
            )
        )
    deaths = victims[
        (victims.metric == "deaths_30d") & (victims.role == "total") & ~victims.is_total
    ]
    for year in sorted(deaths.year.unique()):
        year_crashes = crashes[crashes.ANYO == year]
        year_deaths = deaths[deaths.year == year]
        for group, spec in vehicles.VEHICLE_GROUPS.items():
            expected = float(year_deaths[year_deaths.unit_type.isin(spec["units"])].value.sum())
            actual = float(year_crashes[str(spec["microdata"])].fillna(0).sum())
            results.append(
                Result("table_2_2_deaths", int(year), group, expected, actual, expected == actual)
            )
    return results


# --------------------------------------------------------------------------- runner


def run_checks(crashes: pd.DataFrame | None = None) -> pd.DataFrame:
    if crashes is None:
        crashes = io_microdata.read_all()
    annual = io_tables.read_table("series_annual")
    monthly = io_tables.read_table("series_monthly")
    province_table = io_tables.read_table("tables_2024_province")
    month_table = io_tables.read_table("tables_2024_month")
    census = io_exposure.read_exposure("censo_conductores")
    census_table = io_exposure.read_exposure("censo_provincias_2025")
    driver_victims = io_tables.read_table("tables_driver_victims")
    road_users = io_tables.read_table("series_road_users")
    census_age_tables = io_exposure.read_exposure("censo_edad_tablas")
    census_age_text = io_exposure.read_exposure("censo_edad")
    units = io_tables.read_table("tables_units_by_type")
    victims = io_tables.read_table("tables_victims_by_mode")

    results: list[Result] = []
    results += check_row_counts(crashes, annual)
    results += check_victim_totals(crashes, annual, monthly)
    results += check_tables_2024(crashes, province_table, month_table)
    results += check_unique_keys(crashes)
    results += check_code_domains(crashes)
    results += check_census(census, census_table)
    results += check_driver_tables(driver_victims, road_users)
    results += check_census_age(census_age_tables, census_age_text)
    results += check_vehicle_tables(crashes, units, victims)
    return pd.DataFrame([asdict(result) for result in results])


def run_all(output_dir: Path = TABLES_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    crashes = io_microdata.read_all()
    results = run_checks(crashes)
    results.to_csv(output_dir / VALIDATION_PATH.name, index=False)
    summary = results.groupby("check").passed.agg(["size", "sum"])
    for check, (size, passed) in summary.iterrows():
        log.info("validate %-20s %4d checks, %4d passed", check, size, passed)
    failed = results[~results.passed]
    if not failed.empty:
        log.warning("validate: %d checks failed", len(failed))

    profile = missingness_profile(crashes)
    profile.to_csv(output_dir / MISSINGNESS_PATH.name, index=False)
    log.info("validate: wrote %s and %s", VALIDATION_PATH.name, MISSINGNESS_PATH.name)
    return results, profile
