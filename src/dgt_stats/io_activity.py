"""Driving-activity sources: the hand-typed survey register and MOVILIA 2006 trips by mode.

Neither source gives the share of people who drive by age band for Spain. The register carries the
ESRA national shares (2018, 2023) and the Fundación MAPFRE frequencies among older drivers; MOVILIA
gives trips by main mode ("coche o moto", driver and passenger together) by sex and broad age band
on an average weekday and weekend day in 2006.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import agebands
from dgt_stats.paths import DRIVING_ACTIVITY_PATH, MOVILIA_2006_PATH

MOVILIA_SHEETS = {"T64-1": "weekday", "T64-5": "weekend"}
MOVILIA_SEX_BLOCKS = {"Ambos sexos": "total", "Varones": "male", "Mujeres": "female"}
MOVILIA_MODES = (
    "all_modes",
    "walk_or_bicycle",
    "car_or_motorcycle",
    "urban_bus_or_metro",
    "interurban_bus",
    "train",
    "other",
)
MOVILIA_END_MARKER = "Porcentajes horizontales"


def read_activity_register() -> pd.DataFrame:
    """The survey register as typed, with numeric columns cast."""
    frame = pd.read_csv(DRIVING_ACTIVITY_PATH, dtype=str)
    out = frame.astype(
        {
            "source": "string",
            "question": "string",
            "definition": "string",
            "sex": "string",
            "url": "string",
            "notes": "string",
        }
    )
    out["wave"] = pd.to_numeric(out.wave).astype("int16")
    out["age_low"] = pd.to_numeric(out.age_low).astype("Int16")
    out["age_high"] = pd.to_numeric(out.age_high).astype("Int16")
    out["share"] = pd.to_numeric(out.share).astype("float64")
    out["n"] = pd.to_numeric(out.n).astype("Int64")
    return out


def esra_shares() -> pd.DataFrame:
    """ESRA national shares of adults who drove a car at least a few days a month, by wave."""
    register = read_activity_register()
    rows = register[register.source.str.startswith("ESRA")]
    out = rows[["source", "wave", "definition", "age_low", "age_high", "share", "n"]]
    return out.sort_values("wave").reset_index(drop=True)


def _text(value: object) -> str:
    return "" if pd.isna(value) else " ".join(str(value).split())


def read_movilia_trips() -> pd.DataFrame:
    """MOVILIA 2006 table 64: trips (thousands per day) by day type, sex, age band and main transport mode."""
    book = pd.ExcelFile(MOVILIA_2006_PATH)
    records: list[dict[str, object]] = []
    for sheet, day_type in MOVILIA_SHEETS.items():
        frame = book.parse(sheet, header=None)
        sex: str | None = None
        for row in frame.itertuples(index=False):
            label = _text(row[0])
            if label == MOVILIA_END_MARKER:
                break
            if label in MOVILIA_SEX_BLOCKS:
                sex = MOVILIA_SEX_BLOCKS[label]
                parsed: tuple[int, int | None] | None = (0, None)
                band = "all"
            elif label and sex is not None:
                parsed = agebands.parse_age_label(label)
                band = agebands.band_for(*parsed, agebands.MOVILIA_BANDS)
            else:
                continue
            if band is None or parsed is None:
                raise ValueError(f"MOVILIA: unexpected age label {label!r}")
            for offset, mode in enumerate(MOVILIA_MODES):
                records.append(
                    {
                        "day_type": day_type,
                        "sex": sex,
                        "age_label": label,
                        "age_low": parsed[0],
                        "age_high": parsed[1],
                        "band": band,
                        "transport_mode": mode,
                        "trips_thousands": float(row[1 + offset]),
                        "source_sheet": sheet,
                    }
                )
    out = pd.DataFrame.from_records(records)
    totals = out[out.band == "all"].set_index(["day_type", "sex", "transport_mode"]).trips_thousands
    parts = (
        out[out.band != "all"].groupby(["day_type", "sex", "transport_mode"]).trips_thousands.sum()
    )
    if ((parts - totals.loc[parts.index]).abs() > 0.01).any():
        raise ValueError("MOVILIA: age bands do not sum to the sex total")
    return out.astype(
        {
            "day_type": "string",
            "sex": "string",
            "age_label": "string",
            "age_low": "Int16",
            "age_high": "Int16",
            "band": "string",
            "transport_mode": "string",
            "source_sheet": "string",
        }
    )
