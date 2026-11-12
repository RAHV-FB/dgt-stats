"""Car-driver crashes and deaths by sex, against licence holders.

DGT's driver tables give, by sex and the driver's age band, drivers involved in injury crashes
(table 4.2) and drivers killed within 30 days (table 4.1.1). Against holders of a licence from the
driver census, three rates follow for 2022-2024 pooled: drivers involved and drivers killed per
licence holder, and drivers killed per driver involved (which needs no exposure at all). No file
in the repository measures driving by sex, so these rates are per licence holder and per driver
involved; the per-kilometre comparison of men and women is
:func:`dgt_stats.exposure_risk.national.sex_per_km`.

The bands are ``agebands.EXPOSURE_BANDS``: 18-24 and 25-34 apart, 35-54, then 55-64, 65-74 and 75
and over.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import agebands, io_exposure, io_tables, rates

KM_YEAR = 2024

# The car rows of DGT's driver tables. Both publication spellings appear across the years.
CAR_VEHICLE_TYPES = (
    "TURISMO SIN REMOLQUE",
    "TURISMO CON REMOLQUE",
    "TURISMO DE SP HASTA 9 PLAZAS",
    "Turismo sin remolque",
    "Turismo con remolque",
    "Turismo de SP hasta 9 plazas",
)
# Private cars only: taxi and ride-hailing drivers ("de SP", public service) drive for a living and
# are left out of the comparison of men and women, as of the driver-age rates per kilometre.
PRIVATE_CAR_TYPES = tuple(t for t in CAR_VEHICLE_TYPES if " SP " not in f" {t} ".upper())


def _exposure_band_key(band: str) -> str | None:
    if band not in agebands.DGT_BANDS:
        return None
    return agebands.band_for(*agebands.DGT_BANDS[band], agebands.EXPOSURE_BANDS)


# --------------------------------------------------------------------------- sex


SEX_BANDS = ("18-24", "25-34", "35-54", "55-64", "65-74", "75+")
ADULT_BAND = "18+"
# Three years pooled, so that the rates for women over 65, a few deaths a year, are readable.
SEX_POOL_YEARS = (2022, 2023, 2024)
SEX_LABELS = {"male": "Men", "female": "Women"}
VEHICLE_SCOPES = {
    "motor": "Drivers of motor vehicles",
    "car": "Drivers of private cars (taxis and ride-hailing cars excluded)",
}
# Rows of DGT's driver tables that are not a licensed motor vehicle: cyclists and personal
# mobility vehicles need no licence, and the rest are not vehicles or not known.
NOT_MOTOR = frozenset(
    {
        "bicicleta",
        "vmp",
        "peatón",
        "tren/metro/tranvía",
        "tren/metro",
        "tranvía",
        "se desconoce",
        "sin especificar",
        "otras categorías",
        "total",
    }
)
SEX_MEASURES = {
    "involved_per_1000_licences": ("drivers_involved", "licence_holder_years", 1000),
    "deaths_per_million_licences": ("driver_deaths", "licence_holder_years", 1e6),
    "deaths_per_1000_involved": ("driver_deaths", "drivers_involved", 1000),
}
SEX_MEASURE_LABELS = {
    "involved_per_1000_licences": "Involved in an injury crash, per 1,000 licence holders",
    "deaths_per_million_licences": "Killed, per million licence holders",
    "deaths_per_1000_involved": "Killed, per 1,000 drivers involved",
}


def _in_scope(vehicle_type: pd.Series, scope: str) -> pd.Series:
    if scope == "car":
        return vehicle_type.isin(PRIVATE_CAR_TYPES)
    return ~vehicle_type.str.casefold().isin(NOT_MOTOR)


def driver_counts_by_sex(years: tuple[int, ...], scope: str) -> pd.DataFrame:
    """Drivers involved and killed, and licence holders, by sex and exposure band, summed over years.

    Licence holders summed over the years are licence-holder-years, the denominator for a pooled
    rate. They are holders of a licence of any class (the census total) in both scopes: B-permit
    holders by sex and age exist only from 2021 (published tables) and 2023 (text files), so the
    2014–2024 series cannot use them. The numerator counts every driver involved, including
    unlicensed and foreign drivers. Drivers whose sex or age the tables do not record are left
    out (in 2022–2024, under 1 % and about 2 % of car drivers involved).
    """
    victims = io_tables.read_table("tables_driver_victims")
    involved = io_tables.read_table("tables_drivers_involved")
    licences = io_exposure.read_exposure("conductores_por_edad")
    victims = victims[
        victims.year.isin(years)
        & (victims.severity == "deaths_30d")
        & _in_scope(victims.vehicle_type, scope)
    ]
    involved = involved[involved.year.isin(years) & _in_scope(involved.vehicle_type, scope)]
    licences = licences[licences.year.isin(years)]
    frames = {}
    for name, frame, value in (
        ("driver_deaths", victims, "value"),
        ("drivers_involved", involved, "value"),
        ("licence_holder_years", licences, "n_drivers"),
    ):
        keyed = frame.assign(exposure_band=frame.band.map(_exposure_band_key))
        keyed = keyed[keyed.sex.isin(SEX_LABELS) & keyed.exposure_band.isin(SEX_BANDS)]
        frames[name] = keyed.groupby(["sex", "exposure_band"])[value].sum()
    out = pd.DataFrame(frames).fillna(0.0)
    out.index.names = ["sex", "band"]
    adult = out.groupby(level="sex").sum()
    adult.index = pd.MultiIndex.from_product([adult.index, [ADULT_BAND]], names=["sex", "band"])
    return pd.concat([out, adult]).reset_index()


def sex_age_rates(years: tuple[int, ...] = SEX_POOL_YEARS) -> pd.DataFrame:
    """The three driver rates by sex and age band, for motor-vehicle drivers and car drivers."""
    frames = []
    for scope, scope_label in VEHICLE_SCOPES.items():
        counts = driver_counts_by_sex(years, scope)
        for measure, (count, exposure, per) in SEX_MEASURES.items():
            counts = rates.add_rate(counts, count, exposure, measure, per=per)
        counts.insert(0, "scope", scope)
        counts.insert(1, "scope_label", scope_label)
        counts["sex_label"] = counts.sex.map(SEX_LABELS)
        counts["band_label"] = [
            "18 and over" if band == ADULT_BAND else agebands.band_label(band)
            for band in counts.band
        ]
        counts["years"] = f"{min(years)}-{max(years)}"
        frames.append(counts)
    return pd.concat(frames, ignore_index=True)


def sex_ratios(years: tuple[int, ...] = SEX_POOL_YEARS) -> pd.DataFrame:
    """Men against women on each measure, by band, with 95 % log-normal intervals."""
    table = sex_age_rates(years).set_index(["scope", "band", "sex"])
    records = []
    for scope, scope_label in VEHICLE_SCOPES.items():
        for band in (*SEX_BANDS, ADULT_BAND):
            men, women = table.loc[(scope, band, "male")], table.loc[(scope, band, "female")]
            for measure, (count, exposure, _) in SEX_MEASURES.items():
                ratio, low, high = rates.rate_ratio(
                    float(men[count]),
                    float(men[exposure]),
                    float(women[count]),
                    float(women[exposure]),
                )
                records.append(
                    {
                        "scope": scope,
                        "scope_label": scope_label,
                        "band": band,
                        "band_label": men.band_label,
                        "measure": measure,
                        "measure_label": SEX_MEASURE_LABELS[measure],
                        "ratio": ratio,
                        "low": low,
                        "high": high,
                    }
                )
    return pd.DataFrame.from_records(records)


def sex_b_licence(years: tuple[int, ...] = (2023, 2024)) -> pd.DataFrame:
    """Private-car drivers aged 18 and over killed per million licence holders, men against
    women, with licence holders of any class (the page's measure) and with B (car) licence
    holders only, which the census gives by sex and age only for the text-file years."""
    victims = io_tables.read_table("tables_driver_victims")
    victims = victims[
        victims.year.isin(years)
        & (victims.severity == "deaths_30d")
        & _in_scope(victims.vehicle_type, "car")
    ]
    victims = victims.assign(exposure_band=victims.band.map(_exposure_band_key))
    deaths = victims[victims.exposure_band.isin(SEX_BANDS)].groupby("sex").value.sum()
    every = io_exposure.read_exposure("conductores_por_edad")
    every = every[every.year.isin(years)].assign(
        exposure_band=lambda f: f.band.map(_exposure_band_key)
    )
    every = every[every.exposure_band.isin(SEX_BANDS)].groupby("sex").n_drivers.sum()
    b_holders = pd.concat([io_exposure.b_permit_holders_by_age(year) for year in years])
    b_holders = b_holders.assign(exposure_band=b_holders.band.map(_exposure_band_key))
    b_holders = (
        b_holders[b_holders.exposure_band.isin(SEX_BANDS)].groupby("sex").n_b_permit_holders.sum()
    )
    rows = []
    for label, holders in (
        ("licence holders of any class", every),
        ("B-licence holders", b_holders),
    ):
        ratio, low, high = rates.rate_ratio(
            float(deaths["male"]),
            float(holders["male"]),
            float(deaths["female"]),
            float(holders["female"]),
        )
        rows.append(
            {
                "years": f"{min(years)}-{max(years)}",
                "denominator": label,
                "deaths_men": float(deaths["male"]),
                "deaths_women": float(deaths["female"]),
                "holder_years_men": float(holders["male"]),
                "holder_years_women": float(holders["female"]),
                "ratio": ratio,
                "low": low,
                "high": high,
            }
        )
    return pd.DataFrame(rows)
