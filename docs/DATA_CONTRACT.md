# Data contract

What the project may do with each dataset: its unit of observation, its key, what it may be joined
to, and what it may never be joined to. Code that breaks a rule here is a bug. The sources, their
coverage and their reuse terms are in [`data_sources.md`](data_sources.md); the reconciliation of
the national files against the published statistics is `reports/tables/validation.csv`.

## Rules for every dataset

1. **The data define the analysis.** Every result comes from rows and columns of files under
   `data/raw`. External publications may define a variable or a method; they never supply an
   observation, a coefficient, a missing variable or a join. One typed input remains: the EMEF's
   road-to-straight-line distance ratio for driving trips, 1.45, taken from the EMEF 2021
   distance report (`src/dgt_stats/emef/distance.py`). The report is not archived, so the value
   rests on the transcription.
2. **Raw files are immutable.** `data/raw/<source>/` holds files byte for byte, each listed in
   `data/raw/manifest.csv` with its SHA-256 (checked by `tests/test_paths.py`). Only files the
   code reads, or a published document a check compares against, are kept. Cleaning writes new
   files in `data/staging`, `data/processed` and `data/features`; nothing is edited by hand.
3. **A join needs a real key.** Records are joined only on an identifier both tables carry.
   Datasets without a shared identifier meet only at an aggregation level both really have
   (province and year, Spain and year), with the definitions checked. The result is a comparison
   of aggregates, never a record-level link.
4. **A denominator must match its numerator** in population, geography, scope and period. A
   national or provincial denominator is never attached to an individual crash or person.
5. **Frequency, severity and risk are different questions.** Counts answer frequency; shares of an
   outcome among recorded crashes answer severity; a rate per unit of exposure answers risk and
   needs a matching exposure denominator. The regional microdata have none.
6. **Recorded is not caused.** A cause flag means the police recorded that cause for the crash.
7. **Missing is not "no".** Blank, `NA`, "Sense especificar" and "not recorded" stay as their own
   states unless the source's own structure proves what they mean.

## Layers

`data/raw` holds the source files; `data/staging`, `data/processed` and `data/features` are each
produced only from the layer before it by the scripts and are not tracked. No source's records are
merged into another's and there is no master crash database.

## National datasets

**DGT crash microdata, 2016-2024 (`dgt/microdata/`).** Unit: one road crash with at least one
victim, Spain. Key: (`ANYO`, `ID_ACCIDENTE`); the identifier is a sequence that restarts every
year and carries no information of its own. Records identical in every other column exist (urban
crashes have no coordinates), so a repeated record is not by itself a duplicate. There are no person
records: no driver age, sex, alcohol, drugs or speed. Allowed: the code dictionary by code;
aggregation to province-year or Spain-year and comparison with other aggregates at that level.
Forbidden: linking a crash to a Catalan or Barcelona record by date, place or counts; reading
deaths by road-user type as vehicle involvement.

**DGT yearbook series and statistical tables (`dgt/tables/`).** Unit: published aggregate cells.
Allowed: comparison and denominators at the published aggregation and scope. Forbidden:
disaggregating to crashes or people.

**DGT driver census (`dgt/census/`).** Unit: licence holders by province, sex, licence class or
age band, year. The text files count each driver once, by highest class; the published tables
count permits, so the two are not mixed. Denominator for driver outcomes of the same sex, age band
and year; not for passengers or pedestrians.

**DGT kilometre estimates (`dgt/km_itv_2022/`, `dgt/km_itv_2024/`).** Vehicle-kilometres from ITV
odometer readings, by vehicle type, class of service, autonomous community and the registered
owner's age band. Valid in aggregate, not per vehicle. The owner's age is not the driver's, so it is never the
denominator of a rate by driver age.

**INE population (`ine/`).** Residents by province, five-year age group and sex, and of Spain by
single year of age (the file's overlapping "85 y más" and "100 y más" are never summed). Allowed:
rates per resident at province-year or Spain-year. Forbidden: attaching residents to crashes or
people.

**Traffic and fuel (`transportes/`, `cores/`).** Vehicle-kilometres by type of road (Ministry
table 1.2.14: State, regional and provincial interurban networks only), toll-motorway traffic,
monthly road fuel, and the MOVILIA tables. A traffic series is a denominator only for deaths on
the network it measures; national fuel is not a denominator for interurban deaths, and
toll-motorway traffic is not one for all roads. MOVILIA counts trips, not kilometres, and does
not separate drivers from passengers.

**Travel surveys (`emef/`, `crtm/edm2018/`).** Unit: a respondent and the trips made on one
reference day (EMEF: a working day in the Barcelona area, 2014-2024; EDM2018: a weekday in the
Community of Madrid, 2018), with the survey's expansion weight. Allowed: weighted kilometres,
trips and shares of residents by sex and age group, with intervals from the respondents or
households. Forbidden: attaching respondents to crashes or people; publishing an EMEF estimate
that rests on fewer than 20 sample observations; splitting the EMEF's 65+ group, which no public
file allows.

## Regional crash microdata

**Catalonia, 2010-2023 (`catalonia/`).** Servei Català de Trànsit export. Unit: one crash with at
least one death or serious injury. No source key (`cat_crash_id` is a surrogate). Slight-injury crashes are absent, so the
file supports severity among serious crashes, not how often crashes happen. `C_VELOCITAT_VIA` is
the road's speed limit, not a vehicle's speed, and a limit only where `D_LIMIT_VELOCITAT` is
"Senyal velocitat". Severity follows the 24-hour definition. Allowed: aggregates by province and
year with the DGT microdata and INE residents. Forbidden: matching any Catalan row to a Barcelona
or DGT record by date, hour, coordinates, street, municipality, injury count or any fuzzy rule.

**Barcelona 2025 (`barcelona/2025/`).** Guàrdia Urbana, six tables sharing `Numero_expedient`
(spelt `Número_expedient` in the driver-cause file; only the column name is normalised), each
holding the same set of crash ids.

The crash and accident-type tables have one row per crash and merge one-to-one. The mediate-cause
and driver-cause tables have one row per recorded cause (or one blank row) and are aggregated to
one row per crash before joining. The people table stays person-level, with crash context joined
many-to-one. The vehicle table is used for type presence only.

Count cells leave zero blank. A cause flag says the cause was recorded; mediate causes have no
explicit "none", so `False` means not recorded. Driver causes have no person or vehicle key and
can never be attached to either. The vehicle table has more rows than reported vehicles and no
vehicle identifier, so counting vehicles and per-vehicle rates are out of scope. Forbidden: any record-level link to Catalonia or
the DGT microdata; any rate per resident (no municipal population denominator is held); any
person-level use of the cause tables.

## Where sources meet

Aggregates only: the Catalan file against the DGT microdata by province and year (2016-2023;
counts compared, 24-hour definition validated); the Catalan file per resident (a rate per
resident, not risk); DGT drivers against a regional survey's working-day kilometres by age group
(ratios between ages, with a sensitivity range). No record is matched in any of them.
