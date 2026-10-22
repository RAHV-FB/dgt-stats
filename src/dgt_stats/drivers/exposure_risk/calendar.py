"""Working days, Saturdays, and Sundays or public holidays.

The EMEF describes a working day: Monday to Friday, not a public holiday. A crash numerator
matched to it must use the same days. Public holidays in Barcelona in 2025 are the thirteen
Catalan holidays set by Ordre EMT/85/2024 (DOGC 9151, 26 April 2024) and the city's two local
holidays, 9 June (Whit Monday) and 24 September (La Mercè), set by mayoral decree (Gaseta
Municipal, 21 June 2024). Two of the fifteen fell on a Saturday in 2025 (1 November and
6 December) and count as holidays; the other thirteen fell on weekdays, leaving 248 working
days.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

HOLIDAYS_BARCELONA_2025: dict[dt.date, str] = {
    dt.date(2025, 1, 1): "New Year's Day",
    dt.date(2025, 1, 6): "Epiphany",
    dt.date(2025, 4, 18): "Good Friday",
    dt.date(2025, 4, 21): "Easter Monday",
    dt.date(2025, 5, 1): "Labour Day",
    dt.date(2025, 6, 9): "Whit Monday (Barcelona local holiday)",
    dt.date(2025, 6, 24): "Sant Joan",
    dt.date(2025, 8, 15): "Assumption",
    dt.date(2025, 9, 11): "National Day of Catalonia",
    dt.date(2025, 9, 24): "La Mercè (Barcelona local holiday)",
    dt.date(2025, 11, 1): "All Saints' Day",
    dt.date(2025, 12, 6): "Constitution Day",
    dt.date(2025, 12, 8): "Immaculate Conception",
    dt.date(2025, 12, 25): "Christmas Day",
    dt.date(2025, 12, 26): "Sant Esteve",
}
WORKING_DAY = "working day"
SATURDAY = "Saturday"
SUNDAY_OR_HOLIDAY = "Sunday or holiday"
DAY_TYPES = (WORKING_DAY, SATURDAY, SUNDAY_OR_HOLIDAY)


def day_type(dates: pd.Series, holidays: dict[dt.date, str] = HOLIDAYS_BARCELONA_2025) -> pd.Series:
    """Each date as a working day, a Saturday, or a Sunday or public holiday.

    A holiday that falls on a Saturday is counted as a holiday."""
    days = pd.to_datetime(dates)
    holiday = days.dt.date.isin(set(holidays))
    weekday = days.dt.dayofweek
    out = np.where(
        holiday | (weekday == 6), SUNDAY_OR_HOLIDAY, np.where(weekday == 5, SATURDAY, WORKING_DAY)
    )
    return pd.Series(out, index=dates.index, dtype="string")


def days_in_year(
    year: int = 2025, holidays: dict[dt.date, str] = HOLIDAYS_BARCELONA_2025
) -> dict[str, int]:
    """How many days of each type the year has."""
    dates = pd.Series(pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D"))
    counts = day_type(dates, holidays).value_counts()
    return {kind: int(counts.get(kind, 0)) for kind in DAY_TYPES}
