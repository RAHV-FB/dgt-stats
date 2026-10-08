"""Read, harmonise and check the EMEF respondent and trip files.

One harmonised table per unit, all years stacked:

* ``persons``: one row per respondent, those who made no trip on the reference day included,
  with sex, the published age group (``age_code`` and its label ``age_group``), the three-group
  age that every year supports (``age3``), the four-group age from 2019 (``age4``), residence,
  employment, the expansion factor ``weight`` (``PESAIX``) and the derived car-driving counts of
  the reference day from the trip file;
* ``trips``: one row per trip, keyed by ``person_id`` and ``trip_order``, with the means of
  transport of each stage, flags for driving a car in any stage and for a trip made only by car as
  driver, the banded straight-line distance (2021 on), duration, origin and destination zones and
  the respondent's weight.

``PESAIX`` is a respondent weight: it is constant over a respondent's trips and sums to the
survey universe over respondents, so a weighted count of trips is a number of trips per working
day and a weighted count of respondents is a number of residents. ``PESMOS`` is the same weight
rescaled to the sample size and is not used. Every check in :func:`validate` must pass before any
estimate is made.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd

from dgt_stats.emef import variables as v
from dgt_stats.paths import PROCESSED_DATA_DIR, RAW_DATA_DIR

RAW_EMEF_DIR = RAW_DATA_DIR / "emef"
PERSONS_PATH = PROCESSED_DATA_DIR / "emef_persons.parquet"
TRIPS_PATH = PROCESSED_DATA_DIR / "emef_trips.parquet"


def raw_path(year: int, kind: str) -> Path:
    """``kind`` is ``trips``, ``persons`` or ``dictionary``."""
    suffix = "xlsx" if kind == "dictionary" else "csv"
    return RAW_EMEF_DIR / str(year) / f"emef_{year}_{kind}.{suffix}"


@cache
def read_raw(year: int, kind: str) -> pd.DataFrame:
    """A raw file as strings, column names stripped (2017 and 2024 carry a byte-order mark)."""
    frame = pd.read_csv(
        raw_path(year, kind),
        sep=";",
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False,
    )
    frame.columns = frame.columns.str.strip()
    return frame.apply(lambda column: column.str.strip())


def _code(series: pd.Series) -> pd.Series:
    """Integer codes; blanks become missing."""
    return pd.to_numeric(series.replace("", np.nan), errors="raise").astype("Int64")


def _decimal(series: pd.Series) -> pd.Series:
    """Weights are written with a decimal comma and sometimes without a leading zero (",88")."""
    return pd.to_numeric(series.str.replace(",", ".", regex=False), errors="raise").astype(float)


def _labelled(codes: pd.Series, labels: dict[int, str], what: str, year: int) -> pd.Series:
    unknown = set(codes.dropna().unique()) - set(labels)
    if unknown:
        raise ValueError(f"EMEF {year}: unexpected {what} codes {sorted(unknown)}")
    return codes.map(labels).astype("string")


def _age_columns(codes: pd.Series, year: int) -> dict[str, pd.Series]:
    labels = v.age_labels(year)
    group = _labelled(codes, labels, "age", year)
    if year >= v.AGE4_FROM:
        age4 = group
        age3 = group.replace({"30-44": "30-64", "45-64": "30-64"})
    else:
        age4 = pd.Series(pd.NA, index=codes.index, dtype="string")
        age3 = group
    return {"age_code": codes, "age_group": group, "age3": age3, "age4": age4}


def persons_year(year: int) -> pd.DataFrame:
    """The respondent file of one year, harmonised."""
    raw = read_raw(year, "persons")
    sex = _code(raw[v.SEX_COLUMN[year]])
    age = _code(raw[v.AGE_COLUMN[year][1]])
    zone = _code(raw["CAMB"])
    comarca = _code(raw["COMARCA"])
    employment = _code(raw[v.EMPLOYMENT_COLUMN[year]])
    out = pd.DataFrame(
        {
            "year": np.full(len(raw), year, dtype="int16"),
            "person_id": raw["ID"].astype("int64"),
            "sex": _labelled(sex, v.SEX_LABELS, "sex", year),
            **_age_columns(age, year),
            "zone_code": zone,
            "zone": _labelled(zone, v.ZONES, "zone", year),
            "rmb": zone.isin(v.RMB_ZONES).to_numpy(),
            "comarca_code": comarca,
            "comarca": _labelled(comarca, v.comarcas(year), "comarca", year),
            "employment": _labelled(
                employment.where(employment != 9), v.EMPLOYMENT_LABELS, "employment", year
            ),
            "weight": _decimal(raw["PESAIX"]),
            "mobility_professional": (
                _code(raw[v.PROFESSIONAL_COLUMN[year]]) == v.PROFESSIONAL_CODE
            ).to_numpy(),
        }
    )
    if year in v.WORK_TRIPS_COLUMN:
        work = _code(raw[v.WORK_TRIPS_COLUMN[year]])
        out["work_trips"] = work.where(out.mobility_professional, 0).astype("Float64")
    else:
        out["work_trips"] = pd.array([pd.NA] * len(raw), dtype="Float64")
    if year in v.CAR_DRIVER_FREQUENCY:
        column, scale = v.CAR_DRIVER_FREQUENCY[year]
        frequency = _code(raw[column])
        missing = {9, 99}
        out["car_driver_frequency"] = frequency.where(~frequency.isin(missing))
        out["car_driver_frequency_scale"] = scale
    else:
        out["car_driver_frequency"] = pd.array([pd.NA] * len(raw), dtype="Int64")
        out["car_driver_frequency_scale"] = pd.NA
    out["car_driver_frequency_scale"] = out.car_driver_frequency_scale.astype("string")
    if year in v.LICENCE_COLUMN:
        licence = _code(raw[v.LICENCE_COLUMN[year]])
        out["car_licence"] = licence.map({1: True, 2: False}).astype("boolean")
    else:
        out["car_licence"] = pd.array([pd.NA] * len(raw), dtype="boolean")
    return out


def trips_year(year: int) -> pd.DataFrame:
    """The trip file of one year, harmonised; respondent attributes come from the trip file."""
    raw = read_raw(year, "trips")
    modes = {
        name: _code(raw[column])
        for name, column in zip(("mode1", "mode2", "mode3"), ("V03G", "V03H", "V03I"))
    }
    # "No further mode" is blank in most years and 0 in a few; both mean no stage.
    modes = {name: codes.where(codes != 0) for name, codes in modes.items()}
    stages = pd.concat(modes, axis=1)
    known = stages.notna() & (stages != v.MISSING_MODE)

    def any_stage(*codes: int | None) -> np.ndarray:
        wanted = [code for code in codes if code is not None]
        return stages.isin(wanted).any(axis=1).to_numpy()

    car_driver = any_stage(v.MODE_CAR_DRIVER)
    only_car_driver = (stages.eq(v.MODE_CAR_DRIVER) | stages.isna()).all(
        axis=1
    ).to_numpy() & car_driver
    duration = _code(raw["V03F"])
    hour = _code(raw["V03D"])
    if v.DISTANCE_FROM <= year:
        band = _code(raw["DISTANCIA_ORTO_REC_R1"])
        if set(band.dropna().unique()) - set(v.DISTANCE_BANDS):
            raise ValueError(f"EMEF {year}: unexpected distance bands")
    else:
        band = pd.array([pd.NA] * len(raw), dtype="Int64")
    sex = _code(raw[v.SEX_COLUMN[year]])
    age = _code(raw[v.AGE_COLUMN[year][0]])
    origin = _code(raw["CAMB_O1"])
    destination = _code(raw["CAMB_D1"])
    out = pd.DataFrame(
        {
            "year": np.full(len(raw), year, dtype="int16"),
            "person_id": raw["ID"].astype("int64"),
            "trip_order": _code(raw["ORDRE"]),
            "tipol": _code(raw["TIPOL"]),
            "sex": _labelled(sex, v.SEX_LABELS, "sex", year),
            **_age_columns(age, year),
            "zone_code": _code(raw["CAMB"]),
            "purpose3": _labelled(_code(raw["V03A_R1"]), v.PURPOSE3_LABELS, "purpose", year),
            "depart_hour": hour.where(hour != 99),
            # 998 is "998 minutes or more"; 999 is no answer.
            "duration_min": duration.where(duration != 999),
            "distance_band": band,
            # 1-5 are the survey's zones (``variables.ZONES``), 6 is outside the survey area.
            "origin_zone": origin.where(origin != 9),
            "destination_zone": destination.where(destination != 9),
            "same_municipality": _code(raw["V03B_C2"]).map({1: True, 0: False}).astype("boolean"),
            **modes,
            "n_stages": known.sum(axis=1).astype("int8").to_numpy(),
            "mode_unknown": (stages == v.MISSING_MODE).any(axis=1).to_numpy(),
            "car_driver": car_driver,
            "car_driver_only": only_car_driver,
            "car_passenger": any_stage(v.MODE_CAR_PASSENGER),
            "motorcycle_driver": any_stage(v.MODE_MOTORCYCLE_DRIVER, v.MOPED_DRIVER_MODE[year]),
            "van_or_lorry": any_stage(*v.VAN_LORRY_MODES[year]),
            "weight": _decimal(raw["PESAIX"]),
        }
    )
    return out


@cache
def persons() -> pd.DataFrame:
    """Every respondent, 2014–2024, with the reference day's car driving from the trip file."""
    frame = pd.concat([persons_year(year) for year in v.YEARS], ignore_index=True)
    trip = trips()
    keys = ["year", "person_id"]
    driving = (
        trip.assign(
            n_trips=1,
            n_car_driver_trips=trip.car_driver.astype(int),
            n_car_driver_only_trips=trip.car_driver_only.astype(int),
            car_driver_minutes=trip.duration_min.where(trip.car_driver).astype(float),
        )
        .groupby(keys)[
            ["n_trips", "n_car_driver_trips", "n_car_driver_only_trips", "car_driver_minutes"]
        ]
        .sum(min_count=1)
    )
    out = frame.merge(driving, on=keys, how="left", validate="one_to_one")
    for column in ("n_trips", "n_car_driver_trips", "n_car_driver_only_trips"):
        out[column] = out[column].fillna(0).astype("int16")
    out["drove_car"] = out.n_car_driver_trips > 0
    return out


@cache
def trips() -> pd.DataFrame:
    return pd.concat([trips_year(year) for year in v.YEARS], ignore_index=True)


# --------------------------------------------------------------------------- checks


def validate() -> pd.DataFrame:
    """Checks every estimate depends on; one row per check and year, ``passed`` True or False."""
    rows: list[dict[str, object]] = []

    def check(year: int, name: str, passed: bool, detail: str) -> None:
        rows.append({"year": year, "check": name, "passed": bool(passed), "detail": detail})

    people = pd.concat([persons_year(year) for year in v.YEARS], ignore_index=True)
    trip = trips()
    for year in v.YEARS:
        p = people[people.year == year]
        t = trip[trip.year == year]
        population, sample = v.UNIVERSE[year]
        check(
            year, "sample size", len(p) == sample, f"{len(p):,} respondents, published {sample:,}"
        )
        check(
            year,
            "weighted population",
            abs(p.weight.sum() - population) < 1,
            f"{p.weight.sum():,.1f} against the published {population:,}",
        )
        check(year, "unique respondents", p.person_id.is_unique, "ID unique in the respondent file")
        check(
            year,
            "unique trips",
            not t.duplicated(["person_id", "trip_order"]).any(),
            "(ID, ORDRE) unique in the trip file",
        )
        orphan = ~t.person_id.isin(p.person_id)
        check(
            year, "trips have a respondent", not orphan.any(), f"{orphan.sum()} trips without one"
        )
        merged = t[["person_id", "weight", "sex", "age_group", "zone_code"]].merge(
            p[["person_id", "weight", "sex", "age_group", "zone_code"]],
            on="person_id",
            suffixes=("_trip", "_person"),
        )
        for column in ("weight", "sex", "age_group", "zone_code"):
            left, right = merged[f"{column}_trip"], merged[f"{column}_person"]
            same = np.allclose(left, right) if column == "weight" else (left == right).all()
            check(year, f"{column} agrees", same, "trip file against respondent file")
        # Three 2020 respondents skip a trip number (1, 3 for two trips); their reported trip
        # counts equal the rows present, so the gap is in the numbering, not a lost trip.
        orders = t.groupby("person_id").trip_order.agg(["min", "max", "count"])
        gaps = int(((orders["min"] == 1) & (orders["max"] != orders["count"])).sum())
        check(
            year,
            "trip order starts at 1",
            (orders["min"] == 1).all(),
            f"{gaps} respondents with a gap in ORDRE",
        )
        raw = read_raw(year, "persons")
        reported_column = v.REPORTED_TRIPS_COLUMN[year]
        if reported_column in raw:
            reported = pd.Series(
                _code(raw[reported_column]).to_numpy(), index=raw["ID"].astype("int64")
            )
            rows_per_person = t.groupby("person_id").size().reindex(reported.index, fill_value=0)
            differ = int((rows_per_person != reported).sum())
            check(
                year,
                "trips match reported count",
                differ == 0,
                f"{differ} respondents whose trip rows differ from {reported_column}",
            )
        first_trip = t.sort_values("trip_order").groupby("person_id").tipol.first()
        professional = p.set_index("person_id").mobility_professional
        trip_says = first_trip.eq(v.PROFESSIONAL_CODE).reindex(professional.index)
        disagree = int((trip_says.notna() & (trip_says != professional)).sum())
        check(
            year,
            "professional status agrees",
            disagree <= 5 or year == 2016,
            f"{disagree} respondents whose first trip's TIPOL disagrees with the respondent file"
            + (" (known in 2016; the respondent file is used)" if year == 2016 else ""),
        )
        check(year, "positive weights", (p.weight > 0).all(), "PESAIX > 0")
        unknown_mode = t.mode1.isna().sum()
        check(year, "first mode recorded", unknown_mode == 0, f"{unknown_mode} trips without V03G")
    return pd.DataFrame(rows)


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write the two harmonised tables after every check has passed."""
    checks = validate()
    failed = checks[~checks.passed]
    if not failed.empty:
        raise ValueError(f"EMEF checks failed:\n{failed.to_string()}")
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    people, trip = persons(), trips()
    people.to_parquet(PERSONS_PATH, index=False)
    trip.to_parquet(TRIPS_PATH, index=False)
    return people, trip


# --------------------------------------------------------------------------- inventory

METHOD_NOTES: dict[int, str] = {
    2014: "survey area STI; age in three groups; MITJA_PRIVAT does not separate driver from passenger",
    2015: "dictionary names the trip-file age variable V23_R1; the file has V15_R1; area extended "
    "to the whole of Osona",
    2016: "only year asking whether the respondent holds a car licence (V21A), in an opinion module "
    "put to about 77% of respondents; the trip file's TIPOL disagrees with the respondent file for "
    "504 people",
    2017: "area extended to the Berguedà and the Moianès; comarca codes renumbered; the reported "
    "trip count is V02C",
    2018: "respondent file published as 'Opinió'",
    2019: "area becomes the province of Barcelona (SIMMB): the Baix Penedès and the Selva leave it; "
    "age in four groups from this year; respondent file published as 'Opinió'",
    2020: "COVID-19: fieldwork under pandemic restrictions; usual car use asked only for before "
    "the pandemic; respondent file published as 'Opinió'",
    2021: "straight-line distance band (DISTANCIA_ORTO_REC_R1) published from this year; "
    "first year with trip coordinates; mode code 24 is another private vehicle",
    2022: "the first-release dictionary matches the file; the later 'revised' one carries the 2021 "
    "labels for mode codes 23-25 and V03G_R1 (car driver 13 instead of 14)",
    2023: "respondent file published as 'Opinió'; Saturday nights away from the municipality in the "
    "last four weekends (V11) asked in both waves; accidents or falls in public space in the last "
    "12 months asked in the first wave only",
    2024: "Barcelona city sample enlarged by 1,300 respondents (3,500 in all); respondent-file "
    "columns renamed (S02, COMARCA, V01A, TIPOL) without changing their codes",
}


def inventory() -> pd.DataFrame:
    """One row per EMEF year: files, counts, the fields each harmonised variable comes from,
    missing values in the trip fields the exposure estimates use, and changes of method."""
    from dgt_stats.microdata import sources

    manifest = {row["path"]: row for row in sources.read_manifest()}
    people = persons()
    trip = trips()
    rows = []
    for year in v.YEARS:
        p = people[people.year == year]
        t = trip[trip.year == year]
        files = {kind: f"emef/{year}/emef_{year}_{kind}" for kind in ("trips", "persons")}
        cars = t[t.car_driver]
        rows.append(
            {
                "year": year,
                "survey_area": v.AREA[year],
                "trips_file": f"{files['trips']}.csv",
                "trips_downloaded_as": manifest[f"{files['trips']}.csv"]["downloaded_as"],
                "persons_file": f"{files['persons']}.csv",
                "persons_downloaded_as": manifest[f"{files['persons']}.csv"]["downloaded_as"],
                "respondents": len(p),
                "respondents_with_trips": int((p.n_trips > 0).sum()),
                "trips": len(t),
                "car_driver_trips": len(cars),
                "respondents_driving": int(p.drove_car.sum()),
                "population_16_plus": round(float(p.weight.sum())),
                "weighted_trips": round(float(t.weight.sum())),
                "sex_column": v.SEX_COLUMN[year],
                "age_column": v.AGE_COLUMN[year][0],
                "age_groups": " / ".join(v.age_labels(year).values()),
                "car_driver_frequency": v.CAR_DRIVER_FREQUENCY.get(year, ("", ""))[0],
                "distance_band": year >= v.DISTANCE_FROM,
                "weights": "PESAIX (expansion), PESMOS (PESAIX rescaled to the sample)",
                "missing_duration_share": float(t.duration_min.isna().mean()),
                "missing_mode_share": float(t.mode_unknown.mean()),
                "missing_distance_share_car_driver": float(cars.distance_band.isna().mean())
                if year >= v.DISTANCE_FROM
                else np.nan,
                "dictionary_file_date": manifest[f"emef/{year}/emef_{year}_dictionary.xlsx"][
                    "description"
                ].rsplit("file date on omc.cat ", 1)[-1],
                "method_notes": METHOD_NOTES[year],
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- reproduction

# Published EMEF 2024 results (Principals resultats and Publicació, ATM 2025), reproduced from the
# microdata as a check on the files, the weights and the codes: trips per working day in
# thousands, by sex; main-mode shares; and the share of residents who never drive a car, drive
# at least monthly ("habitual") or less often ("esporàdic"), by area.
PUBLISHED_2024: tuple[tuple[str, float, str], ...] = (
    ("trips, thousands", 19_819.6, "Principals resultats 2024, mode table: Total SIMMB"),
    ("trips by men, thousands", 9_713.3, "Principals resultats 2024, mode table"),
    ("trips by women, thousands", 10_106.4, "Principals resultats 2024, mode table"),
    ("walking trips, thousands", 9_152.4, "Principals resultats 2024, mode table"),
    ("main mode private vehicle, %", 33.5, "Principals resultats 2024, p. 6"),
    ("main mode public transport, %", 18.2, "Principals resultats 2024, p. 6"),
    ("main mode active, %", 48.3, "Principals resultats 2024, p. 6"),
    ("car among private vehicle, %", 85.7, "Principals resultats 2024, p. 6"),
    ("habitual car drivers, SIMMB, %", 53.7, "Publicació 2024, table 21"),
    ("habitual car drivers, Barcelona, %", 37.4, "Publicació 2024, table 21"),
    ("habitual car drivers, rest of AMB, %", 50.2, "Publicació 2024, table 21"),
    ("habitual car drivers, rest of RMB, %", 66.0, "Publicació 2024, table 21"),
    ("habitual car drivers, rest of SIMMB, %", 73.9, "Publicació 2024, table 21"),
    ("non-users of the car as driver, SIMMB, %", 40.8, "Publicació 2024, table 21"),
    ("non-users of the car as driver, Barcelona, %", 54.4, "Publicació 2024, table 21"),
)
AREA_OF_ZONE = {
    1: "Barcelona",
    2: "rest of AMB",
    3: "rest of AMB",
    4: "rest of RMB",
    5: "rest of SIMMB",
}


def reproduce_2024() -> pd.DataFrame:
    """Each published 2024 figure beside the same figure computed from the microdata."""
    raw = read_raw(2024, "trips")
    weight = _decimal(raw.PESAIX)
    main3 = _code(raw.V03G_R3)
    main = _code(raw.V03G_R1)
    people = persons_year(2024)
    frequency = people.car_driver_frequency
    area = people.zone_code.map(AREA_OF_ZONE)

    def share(mask: pd.Series, base: pd.Series | None = None) -> float:
        base = pd.Series(True, index=mask.index) if base is None else base
        w = people.weight if mask.index.equals(people.index) else weight
        return float(100 * (w * (mask & base)).sum() / (w * base).sum())

    habitual = frequency.between(3, 7)
    never = frequency == 0
    computed = {
        "trips, thousands": weight.sum() / 1e3,
        "trips by men, thousands": weight[raw.S01 == "1"].sum() / 1e3,
        "trips by women, thousands": weight[raw.S01 == "2"].sum() / 1e3,
        "walking trips, thousands": weight[main.isin([0, 1])].sum() / 1e3,
        "main mode private vehicle, %": 100 * weight[main3 == 3].sum() / weight.sum(),
        "main mode public transport, %": 100 * weight[main3 == 2].sum() / weight.sum(),
        "main mode active, %": 100 * weight[main3 == 1].sum() / weight.sum(),
        "car among private vehicle, %": 100
        * weight[main.isin([14, 15])].sum()
        / weight[main3 == 3].sum(),
        "habitual car drivers, SIMMB, %": share(habitual),
        "habitual car drivers, Barcelona, %": share(habitual, area == "Barcelona"),
        "habitual car drivers, rest of AMB, %": share(habitual, area == "rest of AMB"),
        "habitual car drivers, rest of RMB, %": share(habitual, area == "rest of RMB"),
        "habitual car drivers, rest of SIMMB, %": share(habitual, area == "rest of SIMMB"),
        "non-users of the car as driver, SIMMB, %": share(never),
        "non-users of the car as driver, Barcelona, %": share(never, area == "Barcelona"),
    }
    rows = [
        {"figure": name, "published": value, "computed": computed[name], "source": source}
        for name, value, source in PUBLISHED_2024
    ]
    out = pd.DataFrame(rows)
    out["difference"] = out.computed - out.published
    return out
