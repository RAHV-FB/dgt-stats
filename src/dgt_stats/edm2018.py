"""The Madrid household travel survey 2018 (EDM2018): car driving by exact age.

The EDM2018 (Consorcio Regional de Transportes de Madrid) interviewed 85,064 residents of the
Comunidad de Madrid about one weekday, Monday to Thursday, in 2018. Unlike the EMEF, its public
files give **exact age**, so it shows how car driving falls between 65 and 85, which no EMEF
file can. It is read here only for that age profile; it is a different region and year, so any
transfer to the EMEF or to Spain is labelled as model-dependent.

Files: the extracts written by ``scripts/fetch_edm.py`` under ``data/raw/crtm/edm2018``.
A *car-driver trip* is a trip whose main mode (``MODO_PRIORITARIO``) is car driver (11 private,
12 company, 13 rental). A trip combining car driving with public transport is classed by its
public-transport stage, so a few car legs are missed. ``DISTANCIA_VIAJE`` is "the distance in km
from the trip's origin to its destination"; the codebook does not say whether it is a straight
line or a network distance, so only ratios between ages are used. Eight car-driver trips record
4,199 to 4,517 km, more than a day's drive (the next longest is 528 km); a distance above
``DISTANCE_LIMIT_KM`` is treated as an error and counts as nothing, the trip itself still counting.
Every rate divides weighted
totals by the weighted residents of the group (person weight ``ELE_G_POND``), those who made no
trip included. Intervals come from a bootstrap of households (the sampling unit).

Source and licence: CRTM open-data licence (https://www.crtm.es/licencia-de-uso). Reuse requires
citing the CRTM and showing "Powered by CRTM" with a link to www.crtm.es on digital platforms.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd

from dgt_stats.paths import RAW_DATA_DIR

EDM_DIR = RAW_DATA_DIR / "crtm" / "edm2018"
SURVEY_YEAR = 2018
CAR_LICENCE_CODES = (4, 5)  # "car (B) or higher" and "motorcycle and car"
BANDS: tuple[tuple[int, int, str], ...] = (
    (18, 24, "18-24"),
    (25, 29, "25-29"),
    (30, 44, "30-44"),
    (45, 64, "45-64"),
    (65, 69, "65-69"),
    (70, 74, "70-74"),
    (75, 79, "75-79"),
    (80, 84, "80-84"),
    (85, 200, "85+"),
)
GROUPS: tuple[tuple[int, int, str], ...] = (
    (16, 29, "16-29"),
    (30, 44, "30-44"),
    (45, 64, "45-64"),
    (65, 74, "65-74"),
    (75, 200, "75+"),
)
SEXES = {1: "male", 2: "female"}
DISTANCE_LIMIT_KM = 1_000.0
N_REPLICATES = 300
SEED = 20261008


def _label(age: pd.Series, bands: tuple[tuple[int, int, str], ...]) -> pd.Series:
    out = pd.Series(pd.NA, index=age.index, dtype="string")
    for low, high, label in bands:
        out[(age >= low) & (age <= high)] = label
    return out


@cache
def person_day() -> pd.DataFrame:
    """One row per respondent aged 16 or over, with the day's car-driver trips and km."""
    people = pd.read_csv(EDM_DIR / "edm2018_individuos.csv")
    trips = pd.read_csv(EDM_DIR / "edm2018_viajes_conductor.csv")
    keys = ["ID_HOGAR", "ID_IND"]
    if people.duplicated(keys).any() or trips.duplicated([*keys, "ID_VIAJE"]).any():
        raise ValueError("EDM2018: duplicated respondent or trip keys")
    if not trips.set_index(keys).index.isin(people.set_index(keys).index).all():
        raise ValueError("EDM2018: car-driver trips without a respondent")
    trips = trips.assign(
        DISTANCIA_VIAJE=trips.DISTANCIA_VIAJE.where(trips.DISTANCIA_VIAJE <= DISTANCE_LIMIT_KM, 0.0)
    )
    driving = trips.groupby(keys).agg(
        car_trips=("ID_VIAJE", "size"), car_km=("DISTANCIA_VIAJE", "sum")
    )
    out = people.merge(driving, on=keys, how="left").fillna({"car_trips": 0, "car_km": 0.0})
    out = out[out.EDAD_FIN >= 16].reset_index(drop=True)
    out["sex"] = out.C2SEXO.map(SEXES).astype("string")
    out["band"] = _label(out.EDAD_FIN, BANDS)
    out["group"] = _label(out.EDAD_FIN, GROUPS)
    out["licence"] = out.C6CARNE.isin(CAR_LICENCE_CODES)
    out["drove"] = out.car_trips > 0
    out["weight"] = out.ELE_G_POND.astype(float)
    return out


@cache
def replicate_factors(n_replicates: int = N_REPLICATES) -> np.ndarray:
    """Household bootstrap factors aligned with :func:`person_day` (one column per replicate)."""
    frame = person_day()
    households, index = np.unique(frame.ID_HOGAR.to_numpy(), return_inverse=True)
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(households), size=(n_replicates, len(households)))
    counts = np.stack([np.bincount(row, minlength=len(households)) for row in draws], axis=1)
    return counts[index].astype(np.float32)


def profile(by: str = "band", sex: str | None = None) -> pd.DataFrame:
    """Car-driver km per resident, share driving, km per licence holder and licence prevalence by
    age, with household-bootstrap intervals for km per resident."""
    frame = person_day()
    factors = replicate_factors()
    mask = np.ones(len(frame), bool) if sex is None else (frame.sex == sex).to_numpy()
    rows = []
    for label, index in frame[mask].groupby(by).groups.items():
        part = frame.loc[index]
        position = frame.index.get_indexer(index)
        w = part.weight.to_numpy()
        f = factors[position]
        km = part.car_km.to_numpy()
        replicate = ((w * km) @ f) / (w @ f)
        licensed = part.licence.to_numpy()
        rows.append(
            {
                by: label,
                "sex": sex or "all",
                "respondents": len(part),
                "respondents_driving": int(part.drove.sum()),
                "residents": float(w.sum()),
                "share_driving": float((w * part.drove).sum() / w.sum()),
                "licence_share": float((w * licensed).sum() / w.sum()),
                "km_per_resident": float((w * km).sum() / w.sum()),
                "km_per_resident_low": float(np.percentile(replicate, 2.5)),
                "km_per_resident_high": float(np.percentile(replicate, 97.5)),
                "km_per_licence_holder": float((w * km).sum() / (w * licensed).sum()),
            }
        )
    return pd.DataFrame(rows)


def older_split() -> pd.DataFrame:
    """Within the 65-and-over group: the 75-and-over share of residents, licence holders and
    car-driver km, and the ratio of 75-and-over to 65-74 km per resident, by sex, with intervals."""
    frame = person_day()
    factors = replicate_factors()
    rows = []
    for sex in ("all", "male", "female"):
        mask = (frame.EDAD_FIN >= 65).to_numpy().copy()
        if sex != "all":
            mask &= (frame.sex == sex).to_numpy()
        part = frame[mask]
        f = factors[mask]
        w = part.weight.to_numpy()
        old = (part.EDAD_FIN >= 75).to_numpy()
        km = part.car_km.to_numpy()
        licensed = part.licence.to_numpy()

        point_older = (w * km * old).sum() / (w * old).sum()
        point_younger = (w * km * ~old).sum() / (w * ~old).sum()
        rep_older = ((w * km * old) @ f) / ((w * old) @ f)
        rep_younger = ((w * km * ~old) @ f) / ((w * ~old) @ f)
        rep_ratio = rep_older / rep_younger
        rep_share = ((w * km * old) @ f) / ((w * km) @ f)
        rows.append(
            {
                "sex": sex,
                "respondents_65_plus": int(mask.sum()),
                "respondents_75_plus": int(old.sum()),
                "drivers_75_plus": int((part.drove & old).sum()),
                "share_of_residents_75_plus": float((w * old).sum() / w.sum()),
                "share_of_licence_holders_75_plus": float(
                    (w * licensed * old).sum() / (w * licensed).sum()
                ),
                "share_of_km_75_plus": float((w * km * old).sum() / (w * km).sum()),
                "share_of_km_75_plus_low": float(np.percentile(rep_share, 2.5)),
                "share_of_km_75_plus_high": float(np.percentile(rep_share, 97.5)),
                "km_per_resident_65_74": float(point_younger),
                "km_per_resident_75_plus": float(point_older),
                "ratio_75_plus_to_65_74": float(point_older / point_younger),
                "ratio_low": float(np.percentile(rep_ratio, 2.5)),
                "ratio_high": float(np.percentile(rep_ratio, 97.5)),
                "licence_share_65_74": float((w * licensed * ~old).sum() / (w * ~old).sum()),
                "licence_share_75_plus": float((w * licensed * old).sum() / (w * old).sum()),
                "km_per_licence_holder_65_74": float(
                    (w * km * ~old).sum() / (w * licensed * ~old).sum()
                ),
                "km_per_licence_holder_75_plus": float(
                    (w * km * old).sum() / (w * licensed * old).sum()
                ),
            }
        )
    return pd.DataFrame(rows)
