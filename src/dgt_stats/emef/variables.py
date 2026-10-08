"""Year-by-year layout of the EMEF public-use files, read from each year's dictionary.

Nothing here is harmonised by name alone. Each entry was checked against the year's dictionary
(``data/raw/emef/<year>/emef_<year>_dictionary.xlsx``) and against the codes present in the
files; where the two disagree the file wins and the disagreement is noted:

* 2015: the trip dictionary labels the age group ``V23_R1``; the file calls it ``V15_R1`` with the
  same three codes (the 2016 name was copied into the 2015 value-label sheet).
* 2024: the respondent dictionary lists ``S02_R3``, ``S03A``, ``COMARCA2`` and ``V01D1``; the file
  has ``S02``, ``S03``, ``COMARCA`` and ``V01A`` instead, and each matches its trip-file counterpart
  respondent by respondent (``tests/test_emef.py``).

Age is published only in groups: 16–29, 30–64 and 65 and over in 2014–2018, and 16–29, 30–44,
45–64 and 65 and over from 2019. No public file separates 65–74 from 75 and over.
"""

from __future__ import annotations

YEARS: tuple[int, ...] = tuple(range(2014, 2025))

# Table 1 of the survey's technical document (Document tècnic relatiu a l'EMEF 2025, May 2026):
# the population aged 16 and over in the survey area and the final sample. The weighted respondent
# files must reproduce both exactly (``ingest.validate``).
UNIVERSE: dict[int, tuple[int, int]] = {
    2014: (4_644_923, 9_461),
    2015: (4_692_584, 9_490),
    2016: (4_713_222, 9_601),
    2017: (4_780_181, 10_010),
    2018: (4_815_772, 10_117),
    2019: (4_749_821, 10_106),
    2020: (4_833_042, 10_145),
    2021: (4_826_057, 10_164),
    2022: (4_853_758, 10_151),
    2023: (4_927_771, 10_154),
    2024: (5_019_771, 11_420),
}

# The survey area changed twice (technical document, Table 1).
AREA: dict[int, str] = {
    **{y: "STI (Integrated Fare System area)" for y in (2014, 2015, 2016)},
    **{y: "STI and Berguedà" for y in (2017, 2018)},
    **{y: "SIMMB (province of Barcelona)" for y in range(2019, 2025)},
}

# Residence zone (``CAMB``), identical codes in every year. Zones 1-4 make up the seven-comarca
# Barcelona Metropolitan Region (RMB), the only area every edition covers in full; zone 5 is the
# rest of the survey area, which grew in 2017 and 2019.
ZONES: dict[int, str] = {
    1: "Barcelona city",
    2: "Rest of first ring",
    3: "Rest of AMB",
    4: "Rest of RMB",
    5: "Rest of survey area",
}
RMB_ZONES: tuple[int, ...] = (1, 2, 3, 4)

# Comarca of residence. The codes were renumbered in 2017, after the Moianès was created.
COMARCAS_2014: dict[int, str] = {
    3: "Alt Penedès",
    6: "Anoia",
    7: "Bages",
    11: "Baix Llobregat",
    12: "Baix Penedès",
    13: "Barcelonès",
    17: "Garraf",
    21: "Maresme",
    24: "Osona",
    34: "Selva",
    40: "Vallès Occidental",
    41: "Vallès Oriental",
}
COMARCAS_2017: dict[int, str] = {
    3: "Alt Penedès",
    6: "Anoia",
    7: "Bages",
    11: "Baix Llobregat",
    12: "Baix Penedès",
    13: "Barcelonès",
    14: "Berguedà",
    17: "Garraf",
    21: "Maresme",
    22: "Moianès",
    25: "Osona",
    35: "Selva",
    41: "Vallès Occidental",
    42: "Vallès Oriental",
}


def comarcas(year: int) -> dict[int, str]:
    return COMARCAS_2014 if year < 2017 else COMARCAS_2017


# Age group of the respondent: column name in the trip and respondent files, and the scheme.
AGE_COLUMN: dict[int, tuple[str, str]] = {
    2014: ("V15_R1", "V15_R1"),
    2015: ("V15_R1", "V15_R1"),
    2016: ("V23_R1", "V23_R1"),
    2017: ("V19_R1", "V19_R1"),
    2018: ("V19_R1", "V19_R1"),
    **{y: ("S02_R3", "S02_R3") for y in range(2019, 2024)},
    2024: ("S02_R3", "S02"),
}
AGE3_LABELS: dict[int, str] = {1: "16-29", 2: "30-64", 3: "65+"}
AGE4_LABELS: dict[int, str] = {1: "16-29", 2: "30-44", 3: "45-64", 4: "65+"}
AGE4_FROM = 2019
# The last edition that sampled 65-74 and 75 and over as separate strata (methodology report
# 2003-2018, Table 5); no public file publishes either group.
OLDER_STRATA_LAST = 2016


def age_labels(year: int) -> dict[int, str]:
    return AGE4_LABELS if year >= AGE4_FROM else AGE3_LABELS


# Sex as recorded in the population register: 1 man, 2 woman.
SEX_COLUMN: dict[int, str] = {y: "V00" if y < 2019 else "S01" for y in YEARS}
SEX_LABELS: dict[int, str] = {1: "male", 2: "female"}

# Employment situation (V01D1; V01A in the 2024 respondent file, same codes).
EMPLOYMENT_COLUMN: dict[int, str] = {y: "V01D1" for y in YEARS} | {2024: "V01A"}
EMPLOYMENT_LABELS: dict[int, str] = {
    1: "employed",
    2: "unemployed",
    3: "retired",
    4: "home duties",
    5: "student",
    6: "other",
}

# Means of transport of each stage (V03G, V03H, V03I). The codes used here have the same meaning
# in every year's dictionary; others (20-25) change meaning between years and are not used.
MODE_CAR_DRIVER = 12
MODE_CAR_PASSENGER = 13
MODE_MOTORCYCLE_DRIVER = 14
MODE_MOTORCYCLE_PASSENGER = 15
MODE_WALK = 1
# Van and lorry: one code (16, "Furgoneta/Camió") to 2019; 16 van and 22 lorry from 2020.
# Neither says whether the respondent drove, so they are kept apart from car driving.
VAN_LORRY_MODES: dict[int, tuple[int, ...]] = {y: (16,) if y < 2020 else (16, 22) for y in YEARS}
# Moped driver has its own code only from 2020; before, mopeds were part of "Moto".
MOPED_DRIVER_MODE: dict[int, int | None] = {y: None if y < 2020 else 20 for y in YEARS}
MISSING_MODE = 99

# Straight-line origin-destination distance, published from 2021 in seven bands (metres).
DISTANCE_FROM = 2021
DISTANCE_BANDS: dict[int, tuple[float, float]] = {
    1: (0.0, 0.5),
    2: (0.5, 2.0),
    3: (2.0, 5.0),
    4: (5.0, 10.0),
    5: (10.0, 50.0),
    6: (50.0, 100.0),
    7: (100.0, float("inf")),
}

# How often the respondent drives a car, as asked in the opinion module. Two scales: a five-point
# frequency to 2019 (1 never or almost never ... 5 always) and from 2021 an eight-point one (0 never
# ... 7 every day or almost). 2020 asked only about use before COVID-19, and is left out.
CAR_DRIVER_FREQUENCY: dict[int, tuple[str, str]] = {
    2014: ("V09C", "five_point"),
    2015: ("V09C", "five_point"),
    2016: ("V09C", "five_point"),
    2017: ("V08C", "five_point"),
    2018: ("V08A_3", "five_point"),
    2019: ("V08A_3", "five_point"),
    2021: ("V09A_4", "eight_point"),
    2022: ("V08_4", "eight_point"),
    2023: ("V08_4", "eight_point"),
    2024: ("V08_4", "eight_point"),
}

# Holds a car driving licence: asked only in 2016 (V21A: 1 yes, 2 no, 9 no answer).
LICENCE_COLUMN: dict[int, str] = {2016: "V21A"}

# Trip purpose in three groups (V03A_R1); identical codes in every year.
PURPOSE3_LABELS: dict[int, str] = {1: "return home", 2: "work or study", 3: "personal"}

# Population type: 1 general population, 2 mobility professional (eight or more work trips a day,
# whose trips in the course of work are not recorded).
TIPOL_LABELS: dict[int, str] = {1: "general", 2: "mobility professional"}
