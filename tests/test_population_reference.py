"""Every annual rate per resident divides by the mid-year (1 July) population.

The national rates and the Catalan per-resident rates use the same reference date, so they can be
compared. These tests read the committed tables, so they run without the data layers.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import io_population
from dgt_stats.microdata import crosssource
from dgt_stats.paths import TABLES_DIR


def _july(year: int) -> pd.Series:
    table = io_population.population_by_province(year, "1 July")
    table = table[table.province_code != io_population.NATIONAL_CODE]
    return table.set_index(table.province_code.astype(int)).population


def test_the_shared_reference_is_mid_year() -> None:
    assert crosssource.RESIDENTS_REFERENCE == "1 July"


def test_committed_rates_use_the_1_july_population() -> None:
    frame = pd.read_csv(TABLES_DIR / "cat_per_resident_province_year.csv")
    for year, rows in frame.groupby("year"):
        july = _july(int(year))
        expected = rows.province_code.map(july)
        assert (rows.population.to_numpy() == expected.to_numpy()).all(), year
