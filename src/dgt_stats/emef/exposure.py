"""Car driving on a working day, by age, sex, area and year, from the EMEF.

**What is counted.** A *car-driver trip* is a trip with at least one stage as a car driver (code 12
in every year), whoever else travelled; car passenger, motorcycle, van and lorry stages are kept
apart. A respondent *drove* on the reference day if they made at least one such trip. The day is
the working day before the interview (Monday to Friday, not a public holiday); a respondent who
drove that day is not necessarily a regular driver, and one who did not may be one.

**Kilometres.** For 2021–2024, each car-driver trip's straight-line distance is the mean of the
fitted distance model within the trip's band (:mod:`distance`, the driving model, fitted on the
trips of 2021–2024), times 1.45, the road-to-straight-line ratio the EMEF 2021 distance report
measured for driving trips. A trip that combines car driving with walking only is counted in full;
a trip that combines it with public transport or another vehicle counts for half its distance in
the central estimate (the car leg is not recorded), and for nothing or all of it in the
sensitivity bounds. Before 2021 the files have no distance band, so the distance is the same
model's mean given the trip's duration, flows and the respondent's age without the band, and
no more than the distance the duration allows at 100 km/h door to door: *modelled*, not
measured, and labelled so. On 2021-2024 trips, where both can be computed
(:func:`imputation_check`), the duration-only total is within 10% of the band-based one in every
year and age group, 3% above it pooled, about 10% above it for trips of an hour or more and 8%
below it for trips to or from outside the survey area. The same bounded model fills the 1.2% of
trips from 2021 that lack a band.

**Weights and intervals.** Totals are weighted by ``PESAIX`` (the respondent weight, constant over
a respondent's trips) and every rate is a ratio of weighted totals over all respondents of the
group, those who made no trip included. Intervals come from a rescaling bootstrap of respondents
within strata of year and comarca of residence (Rao and Wu): in each stratum of ``n`` respondents,
``n - 1`` are drawn with replacement and their weights rescaled by ``n / (n - 1)``. The public
files carry no sampling units or design strata beyond residence, age and sex, so clustering in the
fieldwork, if any, is not reflected and the intervals may be too narrow.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd

from dgt_stats.emef import distance, ingest
from dgt_stats.emef import variables as v

ROAD_RATIO = distance.ROAD_RATIO["driving"]
ROAD_RATIO_RANGE = (1.30, 1.60)
UNBANDED_MAX_SPEED = 100.0  # km/h door to door, for trips whose distance band is unknown
MULTIMODAL_SHARE = 0.5
N_REPLICATES = 300
SEED = 20261008
CONTEMPORARY_YEARS: tuple[int, ...] = (2022, 2023, 2024)
WALK = v.MODE_WALK


@cache
def driving_model() -> distance.IntervalModel:
    """The straight-line distance model of driving trips, fitted on 2021-2024."""
    trips = ingest.trips()
    measured = trips[trips.year >= v.DISTANCE_FROM]
    return distance.fit(measured[distance.mode_group(measured) == "driving"])


def car_driver_trips(
    multimodal_share: float = MULTIMODAL_SHARE,
    unbanded: str = "bounded",
    road_ratio: float = ROAD_RATIO,
) -> pd.DataFrame:
    """Every car-driver trip with its expected straight-line and road kilometres.

    ``unbanded`` sets the treatment of trips without a distance band (every trip before 2021 and
    1.2% of car-driver trips from 2021, mostly to, from or outside the survey area):

    * ``bounded`` (central): the duration model's mean, but no more than the distance the
      duration allows at ``UNBANDED_MAX_SPEED`` door to door;
    * ``truncated``: the mean of the duration model's distribution truncated at that distance,
      which also removes the possible long distances of every shorter trip;
    * ``uncapped``: the duration model's mean;
    * ``excluded``: nothing, as the EMEF 2021 distance report did.

    :func:`imputation_check` compares them on banded trips, where the band-based distance is
    known: ``bounded`` is the closest. Banded trips are never bounded: their band-based means
    reproduce the report's mean distance of driving trips, and a bound lowers it.
    """
    trips = ingest.trips()
    car = trips[trips.car_driver].copy()
    model = driving_model()
    measured = car.distance_band.notna().to_numpy()
    km = np.zeros(len(car))
    km[measured] = model.expected_km(car[measured], use_band=True)
    km[~measured] = unbanded_km(car[~measured], unbanded, road_ratio)
    stages = car[["mode1", "mode2", "mode3"]]
    other = stages.where(~stages.isin([v.MODE_CAR_DRIVER, WALK]))
    with_other_vehicle = other.notna().any(axis=1).to_numpy()
    share = np.where(with_other_vehicle, multimodal_share, 1.0)
    car["km_straight"] = km
    car["km_source"] = np.where(measured, "band and duration", "duration only (modelled)")
    car["car_share"] = share
    car["km_road"] = km * share * road_ratio
    car["minutes"] = car.duration_min.astype(float) * share
    car["with_other_vehicle"] = with_other_vehicle
    return car


def unbanded_km(trips: pd.DataFrame, treatment: str, road_ratio: float = ROAD_RATIO) -> np.ndarray:
    """Expected straight-line km of trips from duration alone (see :func:`car_driver_trips`)."""
    model = driving_model()
    if treatment == "excluded":
        return np.zeros(len(trips))
    if treatment == "truncated":
        return model.expected_km(
            trips, use_band=False, max_speed_kmh=UNBANDED_MAX_SPEED, road_ratio=road_ratio
        )
    mean = model.expected_km(trips, use_band=False)
    if treatment == "uncapped":
        return mean
    if treatment != "bounded":
        raise ValueError(f"unbanded: {treatment!r}")
    duration = trips.duration_min.astype(float).to_numpy()
    reachable = np.where(
        np.isnan(duration), np.inf, duration / 60 * UNBANDED_MAX_SPEED / road_ratio
    )
    return np.minimum(mean, reachable)


UNBANDED_TREATMENTS = ("bounded", "truncated", "uncapped")


def imputation_check() -> pd.DataFrame:
    """The duration-only treatments applied to 2021-2024 trips that have a band, against the
    band-based distance: weighted kilometres relative to the band-based total, by year and the
    three age groups, pooled, and for long trips."""
    car = car_driver_trips()
    car = car[car.distance_band.notna()].copy()
    for treatment in UNBANDED_TREATMENTS:
        car[treatment] = unbanded_km(car, treatment)
    subsets: dict[str, pd.Series] = {}
    for (year, age), index in car.groupby(["year", "age3"]).groups.items():
        subsets[f"{year} {age}"] = car.index.isin(index)
    for age, index in car.groupby("age3").groups.items():
        subsets[f"2021-2024 {age}"] = car.index.isin(index)
    subsets["2021-2024 all"] = np.ones(len(car), bool)
    duration = car.duration_min.astype(float)
    subsets["trips of 60 minutes or more"] = (duration >= 60).to_numpy()
    subsets["trips of 120 minutes or more"] = (duration >= 120).to_numpy()
    outside = (car.origin_zone == 6) | (car.destination_zone == 6)
    subsets["trips to or from outside the survey area"] = outside.fillna(False).to_numpy()
    rows = []
    for name, mask in subsets.items():
        part = car[mask]
        banded = float((part.weight * part.km_straight).sum())
        row = {"subset": name, "sample_trips": int(mask.sum())}
        row["band_based_mean_km"] = banded / float(part.weight.sum())
        for treatment in UNBANDED_TREATMENTS:
            row[f"{treatment}_relative"] = float((part.weight * part[treatment]).sum()) / banded
        rows.append(row)
    return pd.DataFrame(rows)


@cache
def person_day() -> pd.DataFrame:
    """One row per respondent: the reference day's car driving (zeros for those who did not)."""
    people = ingest.persons()
    car = car_driver_trips()
    keys = ["year", "person_id"]
    totals = car.groupby(keys).agg(
        car_trips=("km_road", "size"),
        car_km=("km_road", "sum"),
        car_minutes=("minutes", "sum"),
        car_km_lower=("km_road", lambda s: s[car.loc[s.index, "car_share"] == 1].sum()),
        car_km_upper=("km_road", lambda s: (s / car.loc[s.index, "car_share"]).sum()),
    )
    out = people.merge(totals, on=keys, how="left", validate="one_to_one")
    for column in ("car_trips", "car_km", "car_minutes", "car_km_lower", "car_km_upper"):
        out[column] = out[column].fillna(0.0)
    out["drove"] = out.car_trips > 0
    out["stratum"] = out.year.astype(str) + "|" + out.comarca.astype(str)
    return out


def replicate_factors(frame: pd.DataFrame, n_replicates: int = N_REPLICATES) -> np.ndarray:
    """Rao-Wu rescaling bootstrap factors, one column per replicate, aligned with ``frame``."""
    rng = np.random.default_rng(SEED)
    factors = np.zeros((len(frame), n_replicates), dtype=np.float32)
    positions = frame.groupby("stratum").indices
    for _, index in sorted(positions.items()):
        n = len(index)
        if n < 2:
            factors[index] = 1.0
            continue
        draws = rng.integers(0, n, size=(n - 1, n_replicates))
        counts = np.zeros((n, n_replicates), dtype=np.float32)
        for b in range(n_replicates):
            counts[:, b] = np.bincount(draws[:, b], minlength=n)
        factors[index] = counts * n / (n - 1)
    return factors


RATES: dict[str, tuple[str, str]] = {
    # name: (numerator column, denominator column); "residents" is a column of ones, "drove" the
    # respondents who drove.
    "share_driving": ("drove", "residents"),
    "car_trips_per_resident": ("car_trips", "residents"),
    "car_trips_per_driver": ("car_trips", "drove"),
    "km_per_resident": ("car_km", "residents"),
    "km_per_driver": ("car_km", "drove"),
    "km_per_trip": ("car_km", "car_trips"),
    "minutes_per_resident": ("car_minutes", "residents"),
}
TOTALS = ("residents", "drove", "car_trips", "car_km")


def estimates(
    frame: pd.DataFrame,
    by: list[str],
    factors: np.ndarray | None = None,
    pooled: bool = False,
) -> pd.DataFrame:
    """Weighted totals and rates by group, with 95% bootstrap intervals.

    With ``pooled``, every weight is divided by the number of years (each year's weights already
    sum to that year's population), so a pooled rate is the mean working day of those years, each
    year counting in proportion to its population; totals are then per average year.
    """
    if factors is None:
        factors = replicate_factors(frame)
    data = frame.assign(residents=1.0, drove=frame.drove.astype(float))
    weight = data.weight.to_numpy()
    if pooled:
        n_years = data.year.nunique()
        weight = weight / n_years
    rows = []
    for key, group in data.groupby(by, observed=True, sort=True):
        index = data.index.get_indexer(group.index)
        w = weight[index]
        f = factors[index]
        values = {}
        for column in TOTALS + ("car_minutes",):
            x = group[column].to_numpy(dtype=float)
            values[column] = (float(w @ x), (w * x) @ f)
        row = dict(zip(by, key if isinstance(key, tuple) else (key,)))
        row["respondents"] = len(group)
        row["respondents_driving"] = int(group.drove.sum())
        for column in TOTALS:
            row[column] = values[column][0]
        for name, (numerator, denominator) in RATES.items():
            point = values[numerator][0] / values[denominator][0]
            replicates = values[numerator][1] / values[denominator][1]
            low, high = np.nanpercentile(replicates, [2.5, 97.5])
            row[name] = point
            row[f"{name}_low"] = float(low)
            row[f"{name}_high"] = float(high)
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- results

AREAS: dict[str, tuple[int, ...]] = {
    "Barcelona city": (1,),
    "rest of the metropolitan area (AMB)": (2, 3),
    "rest of the metropolitan region (RMB)": (4,),
    "rest of the province": (5,),
}


def _with_all_sexes(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([frame, frame.assign(sex="all")], ignore_index=True)


def contemporary(years: tuple[int, ...] = CONTEMPORARY_YEARS) -> pd.DataFrame:
    """The mean working day of ``years`` by four age groups and sex, survey area."""
    frame = person_day()
    frame = frame[frame.year.isin(years)].reset_index(drop=True)
    factors = replicate_factors(frame)
    both = _with_all_sexes(frame)
    factors = np.vstack([factors, factors])
    by_age = estimates(both, ["sex", "age4"], factors, pooled=True)
    every = estimates(both.assign(age4="16+"), ["sex", "age4"], factors, pooled=True)
    out = pd.concat([by_age, every], ignore_index=True)
    out.insert(0, "years", f"{min(years)}-{max(years)}")
    return out


def by_area(years: tuple[int, ...] = CONTEMPORARY_YEARS) -> pd.DataFrame:
    """The mean working day of ``years`` by area of residence and four age groups."""
    frame = person_day()
    frame = frame[frame.year.isin(years)].reset_index(drop=True)
    area = pd.Series(pd.NA, index=frame.index, dtype="object")
    for name, zones in AREAS.items():
        area[frame.zone_code.isin(zones)] = name
    frame["area"] = area
    factors = replicate_factors(frame)
    out = pd.concat(
        [
            estimates(frame, ["area", "age4"], factors, pooled=True),
            estimates(frame.assign(age4="16+"), ["area", "age4"], factors, pooled=True),
        ],
        ignore_index=True,
    )
    out.insert(0, "years", f"{min(years)}-{max(years)}")
    return out


def series() -> pd.DataFrame:
    """Each year 2014-2024 by the three age groups every year supports, for the survey area of
    that year and for the seven-comarca metropolitan region every edition covers (RMB). Before
    2021 the kilometres are modelled from durations."""
    frame = person_day()
    factors = replicate_factors(frame)
    pieces = []
    for area, mask in (("survey area", np.ones(len(frame), bool)), ("RMB", frame.rmb.to_numpy())):
        part = frame[mask]
        f = factors[mask]
        table = pd.concat(
            [
                estimates(part.reset_index(drop=True), ["year", "age3"], f),
                estimates(part.assign(age3="16+").reset_index(drop=True), ["year", "age3"], f),
            ],
            ignore_index=True,
        )
        table.insert(0, "area", area)
        pieces.append(table)
    out = pd.concat(pieces, ignore_index=True)
    out["km_source"] = np.where(out.year >= v.DISTANCE_FROM, "measured band", "modelled")
    return out


PERIODS: dict[str, tuple[int, ...]] = {
    "2014-2016": (2014, 2015, 2016),
    "2017-2019": (2017, 2018, 2019),
    "2021-2024": (2021, 2022, 2023, 2024),
    "2014-2024 without 2020": tuple(y for y in v.YEARS if y != 2020),
}


def periods() -> pd.DataFrame:
    """Pooled periods by the three age groups every year supports, in the metropolitan region
    every edition covers (RMB). 2020, surveyed under COVID-19 restrictions, is left out."""
    frame = person_day()
    frame = frame[frame.rmb].reset_index(drop=True)
    pieces = []
    for label, years in PERIODS.items():
        part = frame[frame.year.isin(years)].reset_index(drop=True)
        factors = replicate_factors(part)
        table = pd.concat(
            [
                estimates(part, ["age3"], factors, pooled=True),
                estimates(part.assign(age3="16+"), ["age3"], factors, pooled=True),
            ],
            ignore_index=True,
        )
        table.insert(0, "period", label)
        table.insert(
            1, "km_source", "modelled" if min(years) < v.DISTANCE_FROM else "measured band"
        )
        pieces.append(table)
    out = pd.concat(pieces, ignore_index=True)
    out.loc[out.period.str.startswith("2014-2024"), "km_source"] = "modelled to 2020, band after"
    return out


def km_shares(frame: pd.DataFrame, column: str = "car_km", by: str = "age4") -> pd.Series:
    """Share of the group's car-driver kilometres by age, years weighted equally."""
    totals = frame.assign(wkm=frame.weight * frame[column]).groupby(["year", by]).wkm.sum()
    yearly = totals / totals.groupby(level="year").transform("sum")
    return yearly.groupby(level=by).mean()


def per_resident(frame: pd.DataFrame, column: str = "car_km", by: str = "age4") -> pd.Series:
    totals = (
        frame.assign(wkm=frame.weight * frame[column])
        .groupby(["year", by])
        .agg(km=("wkm", "sum"), residents=("weight", "sum"))
    )
    return (totals.km / totals.residents).groupby(level=by).mean()


BOUNDED_SPEEDS: tuple[float, ...] = (80.0, 100.0)


def bounded_road_km(
    km_straight: np.ndarray, duration_min: np.ndarray, ratio: float, max_speed_kmh: float
) -> np.ndarray:
    """Road distance as ``ratio`` times the straight line, but no more than the trip's duration
    allows at ``max_speed_kmh`` door to door, and never less than the straight line."""
    reachable = np.where(np.isnan(duration_min), np.inf, duration_min / 60 * max_speed_kmh)
    return np.maximum(km_straight, np.minimum(ratio * km_straight, reachable))


@cache
def bounded_road_ratio(max_speed_kmh: float) -> float:
    """The road ratio that, with road distance bounded by ``max_speed_kmh``, reproduces the
    report's mean road distance of a 2021 driving trip (8.9 km x 1.45 = 12.9 km).

    A single ratio of means overstates the road distance of long trips, which run on motorways:
    applied to trips over 100 km in a straight line it implies a median door-to-door speed above
    130 km/h. Bounding the speed and recalibrating the ratio keeps the report's mean and moves
    kilometres from long trips to short ones."""
    from scipy import optimize

    trips = ingest.trips()
    year = trips[(trips.year == 2021) & trips.distance_band.notna()]
    year = year[distance.mode_group(year) == "driving"]
    km = driving_model().expected_km(year)
    duration = year.duration_min.astype(float).to_numpy()
    weight = year.weight.to_numpy()
    target = distance.REPORT_STRAIGHT_LINE_KM["driving"] * ROAD_RATIO

    def gap(ratio: float) -> float:
        road = bounded_road_km(km, duration, ratio, max_speed_kmh)
        return float(np.average(road, weights=weight)) - target

    return float(optimize.brentq(gap, 1.0, 3.0))


BAND_LABELS: dict[int, str] = {
    code: f"{low:g} km or more" if np.isinf(high) else f"{low:g}-{high:g} km"
    for code, (low, high) in v.DISTANCE_BANDS.items()
}


def km_by_band(years: tuple[int, ...] = CONTEMPORARY_YEARS) -> pd.DataFrame:
    """Each straight-line band's share of car-driver trips and kilometres by age group, with the
    sample trips behind it and the median door-to-door road speed the central method implies."""
    car = car_driver_trips()
    car = car[car.year.isin(years)]
    car = car.assign(
        band=car.distance_band.astype("Int64").map(BAND_LABELS).fillna("no band"),
        wkm=car.weight * car.km_road,
        speed=car.km_road / (car.duration_min.astype(float) * car.car_share / 60),
    )
    rows = []
    for (age, label), group in car.groupby(["age4", "band"]):
        within = car[car.age4 == age]
        rows.append(
            {
                "age4": age,
                "band": label,
                "sample_trips": len(group),
                "share_of_trips": float(group.weight.sum() / within.weight.sum()),
                "share_of_km": float(group.wkm.sum() / within.wkm.sum()),
                "mean_straight_km": float(np.average(group.km_straight, weights=group.weight)),
                "median_road_speed_kmh": float(group.speed.median()),
            }
        )
    order = [*BAND_LABELS.values(), "no band"]
    out = pd.DataFrame(rows)
    out["band"] = pd.Categorical(out.band, order, ordered=True)
    return out.sort_values(["age4", "band"]).reset_index(drop=True)


def sensitivity() -> pd.DataFrame:
    """Kilometres per resident and each age group's share of car-driver kilometres under
    alternative choices: years pooled, area, multimodal trips, unbanded trips, the distance within
    bands, the edges of the bands that carry most kilometres, and a speed-bounded road distance.
    A uniform road ratio and annualisation multiply every group alike and change no share.
    Rates here are means of yearly rates, so the central row differs slightly from
    :func:`contemporary`, which divides pooled totals."""
    people = ingest.persons()
    rows = []

    def record(label: str, choice: str, frame: pd.DataFrame, column: str = "car_km") -> None:
        shares = km_shares(frame, column)
        rates = per_resident(frame, column)
        for age in shares.index:
            rows.append(
                {
                    "variant": label,
                    "choice": choice,
                    "age4": age,
                    "km_per_resident": float(rates[age]),
                    "share_of_km": float(shares[age]),
                }
            )

    base = person_day()
    contemporary_mask = base.year.isin(CONTEMPORARY_YEARS)
    record("central", "2022-2024, unbanded bounded, multimodal half", base[contemporary_mask])
    for years in ((2021, 2022, 2023, 2024), (2023, 2024), (2024,), (2019, 2021, 2022, 2023, 2024)):
        record("years", "-".join(map(str, years)), base[base.year.isin(years)])
    record(
        "area",
        "RMB only",
        base[contemporary_mask & base.rmb],
    )
    record("multimodal", "car leg counted as nothing", base[contemporary_mask], "car_km_lower")
    record(
        "multimodal", "car leg counted as the whole trip", base[contemporary_mask], "car_km_upper"
    )
    for treatment in ("excluded", "truncated", "uncapped"):
        car = car_driver_trips(unbanded=treatment)
        km = car.groupby(["year", "person_id"]).km_road.sum().rename("alt_km")
        frame = people.merge(km, on=["year", "person_id"], how="left").fillna({"alt_km": 0.0})
        record("unbanded trips", treatment, frame[frame.year.isin(CONTEMPORARY_YEARS)], "alt_km")
    # Banded trips under alternative distances (2021-2024 only); unbanded trips keep theirs.
    car = car_driver_trips()
    band = car.distance_band.astype("Int64")
    banded = band.notna().to_numpy()
    current = car.km_straight.to_numpy()

    def record_banded(label: str, choice: str, km_road: np.ndarray) -> None:
        km = np.where(banded, km_road * car.car_share.to_numpy(), car.km_road.to_numpy())
        total = car.assign(alt=km).groupby(["year", "person_id"]).alt.sum().rename("alt_km")
        frame = people.merge(total, on=["year", "person_id"], how="left").fillna({"alt_km": 0.0})
        record(label, choice, frame[frame.year.isin(CONTEMPORARY_YEARS)], "alt_km")

    # Fixed points within each band instead of the duration model.
    for label, points in (
        ("geometric midpoint", {1: 0.25, 2: 1.0, 3: 3.16, 4: 7.07, 5: 22.4, 6: 70.7, 7: 141.0}),
        ("arithmetic midpoint", {1: 0.25, 2: 1.25, 3: 3.5, 4: 7.5, 5: 30.0, 6: 75.0, 7: 150.0}),
    ):
        fixed = band.map(points).astype(float).to_numpy()
        record_banded("distance within band", label, fixed * ROAD_RATIO)
    # The two bands that carry most kilometres, pushed to their edges: the 10-50 km band holds
    # about half of all car-driver kilometres, the open band over 100 km a sixth of those of
    # drivers aged 65 and over.
    for code, edge, choice in (
        (5, 10.0, "10-50 km band at 10 km"),
        (5, 50.0, "10-50 km band at 50 km"),
        (7, 100.0, "over-100 km band at 100 km"),
    ):
        km = np.where(band.eq(code).fillna(False).to_numpy(), edge, current)
        record_banded("band edges", choice, km * ROAD_RATIO)
    # Road distance bounded by a door-to-door speed, the ratio recalibrated to the report.
    duration = car.duration_min.astype(float).to_numpy()
    for speed in BOUNDED_SPEEDS:
        ratio = bounded_road_ratio(speed)
        km = bounded_road_km(current, duration, ratio, speed)
        record_banded(
            "road distance", f"bounded at {speed:.0f} km/h door to door (ratio {ratio:.3f})", km
        )
    return pd.DataFrame(rows)


FREQUENCY_LABELS = {
    0: "never",
    1: "occasionally",
    2: "less than monthly",
    3: "once a month",
    4: "several times a month",
    5: "once a week",
    6: "several times a week",
    7: "every day or almost",
}


def usual_frequency(years: tuple[int, ...] = CONTEMPORARY_YEARS) -> pd.DataFrame:
    """How often respondents say they drive a car, by age, and the share who drove on the
    reference working day within each frequency (2022-2024, eight-point scale)."""
    frame = person_day()
    frame = frame[frame.year.isin(years) & frame.car_driver_frequency.notna()]
    frame = frame.assign(frequency=frame.car_driver_frequency.astype(int).map(FREQUENCY_LABELS))
    rows = []
    for (age, label), group in frame.groupby(["age4", "frequency"]):
        within = frame[frame.age4 == age]
        rows.append(
            {
                "age4": age,
                "frequency": label,
                "code": int(group.car_driver_frequency.iloc[0]),
                "respondents": len(group),
                "share_of_age": float(group.weight.sum() / within.weight.sum()),
                "share_drove_on_reference_day": float(
                    (group.weight * group.drove).sum() / group.weight.sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["age4", "code"]).reset_index(drop=True)


WEEKEND_MODES = ("V14A_1", "V14A_2", "V14A_3", "V14B_1", "V14B_2", "V14B_3")


def weekend_away_2023() -> pd.DataFrame:
    """EMEF 2023: share of residents who spent at least one of the last four weekends away from
    their municipality, and share who did so driving a car on the way out or back, by age."""
    raw = ingest.read_raw(2023, "persons")
    people = ingest.persons_year(2023)
    weekends = pd.to_numeric(raw.V11.replace({"": np.nan, "99": np.nan}))
    drove = raw[list(WEEKEND_MODES)].eq(str(v.MODE_CAR_DRIVER)).any(axis=1)
    frame = people.assign(
        away=(weekends > 0).to_numpy(),
        away_driving=((weekends > 0) & drove).to_numpy(),
        weekends_away=weekends.to_numpy(),
        answered=weekends.notna().to_numpy(),
    )
    frame = frame[frame.answered]
    rows = []
    for age, group in pd.concat([frame, frame.assign(age4="16+")]).groupby("age4"):
        w = group.weight
        rows.append(
            {
                "age4": age,
                "respondents": len(group),
                "share_away": float((w * group.away).sum() / w.sum()),
                "share_away_driving": float((w * group.away_driving).sum() / w.sum()),
                "weekends_away_per_resident": float((w * group.weekends_away).sum() / w.sum()),
            }
        )
    return pd.DataFrame(rows)
