# Data contract

This file is the authority for what the project may do with each dataset: its unit of
observation, its key, what it may be joined to and how, what it may never be joined to, and the
limits that follow from how it was selected. Code that breaks a rule here is a bug. Where a
statement depends on the data, the check that enforces it is named; the figures themselves are
generated in [`DATA_QUALITY_MICRODATA.md`](DATA_QUALITY_MICRODATA.md),
[`RAW_FILE_INVENTORY.md`](RAW_FILE_INVENTORY.md) and the reconciliation table
`reports/tables/validation.csv`, so they are not repeated here where they could drift.

## Rules that apply to every dataset

1. **The data define the analysis.** Every result comes from rows and columns of files under
   `data/raw`. External publications may define a variable or a method; they never supply an
   observation, a coefficient, a relative risk, a missing variable, a join or a confirmation.
2. **Raw files are immutable.** `data/raw/<source>/` holds files byte for byte, each listed in
   `data/raw/manifest.csv` with its SHA-256 (checked by `tests/test_paths.py`). Cleaning writes
   new files in `data/staging`, `data/processed` and `data/features`; nothing is edited by hand.
3. **A join needs a real key.** Records are joined only on an identifier both tables carry.
   Datasets without a shared identifier meet only at an aggregation level both genuinely have
   (province and year, Spain and year), with the definitions checked, and the result is a
   comparison of aggregates, never a record-level link.
4. **A denominator must match its numerator** in population, geography, scope and period. A
   national or provincial denominator is never attached to an individual crash or person.
5. **Frequency, severity and risk are different questions.** Counts answer frequency; shares of
   an outcome among recorded crashes answer severity; a rate per unit of exposure answers risk and
   needs an exposure denominator that matches. The regional microdata have none.
6. **Recorded is not caused.** A cause flag means the police recorded that cause for the crash.
   Models report association and prediction, never effects.
7. **Missing is not "no".** Blank, `NA`, "Sense especificar" and "not recorded" stay as their own
   states unless the source's own structure proves what they mean (see each dataset).

## Source hierarchy: which dataset answers which question

Four layers, each with its own unit of observation, declared in `src/dgt_stats/layers.py` and
shown on the site's [sources page](https://rahv-fb.github.io/dgt-stats/sources.html). No layer is
merged into another and there is no master crash database.

| Layer | Sources | Used for | Not used for |
|---|---|---|---|
| National context | DGT crash microdata, yearbook series and tables, driver census and kilometre estimates; INE residents; traffic and fuel series | trends, exposure and denominators, province and year comparisons, historical context, aggregate rates, benchmarks for the regional files | training a severity model unless the [DGT audit](DGT_MICRODATA_AUDIT.md) allows it; denominators for individual crashes |
| Crash microdata: Catalonia | Servei Català de Trànsit file | the fatal-against-serious crash model; its temporal and geographic validation; the training domain of the transfer tests | crash frequency (no slight-injury crashes); driving speed; record linkage |
| Rich microdata: Barcelona | Guàrdia Urbana tables | person and crash severity; road users; recorded causes; diagnostics and external checks of the Catalan model | trends (one year); unique vehicles; a fatal-against-serious benchmark (too few fatal crashes) |
| Validation and transportability | not a source: a use | models trained in one layer scored on another's real records; population comparisons | creating observations; joining records |

How each source came to exist (who records it, inclusion rule, severity definition, when each
variable is known, recording artefacts) is generated in
[`SOURCE_COMPARISON.md`](SOURCE_COMPARISON.md). Two rules follow from the hierarchy:

8. **Cross-source data test models; they never manufacture observations.** A model trained on
   one source may be scored on another source's real records with harmonised variables validated
   on the crashes both hold. No source's rows are added to another's training data, imputed into
   it, or reweighted into a synthetic population (reweighting appears only as a labelled
   sensitivity check).
9. **A source enters a model only if it passes its audit.** The DGT crash microdata train a
   model only if all seven checks of [`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md) pass
   (unit, target, definitions, construction, severity and inclusion definitions, comparability
   across provinces, recording artefacts); otherwise they stay the national analytical layer and
   a test domain for fields validated on the crashes both sources hold.

## Layers on disk

| Layer | Path | Written by | Contents |
|---|---|---|---|
| raw | `data/raw/<source>/` | download, `scripts/microdata.py organise` | source files, manifest |
| staging | `data/staging/<source>/` | `scripts/ingest.py`, `scripts/microdata.py build` | parsed files; source column names normalised, values unchanged |
| processed | `data/processed/` | `scripts/build_tables.py`, `scripts/microdata.py build` | validated tables at one documented unit |
| features | `data/features/` | `scripts/microdata.py features` | model matrices: id, target, group, features, provenance |

Sources in `data/raw`: `dgt/` (Dirección General de Tráfico), `ine/`, `transportes/`
(Ministerio de Transportes), `cores/`, `comunidad_madrid/`, `catalonia/` (Servei Català de
Trànsit export), `barcelona/` (Guàrdia Urbana, Open Data BCN), and `compiled/` (values typed by
hand from publications: not source data, see below).

## National datasets

### DGT crash microdata, 2016-2024 (`dgt/microdata/`)

- **Unit**: one road crash with at least one victim, Spain. **Key**: (`ANYO`, `ID_ACCIDENTE`),
  unique (validate.py check 4). Processed: `data/processed/dgt_accidentes.parquet`.
- **Variables**: date parts, province, municipality (coarsened to `00000` below 5,000
  inhabitants), zone, road type and owner, crash type, junction, priority, surface, lighting,
  weather, alignment, victims by severity at 24 hours and 30 days, deaths by vehicle type, total
  vehicles. **No person records**: no driver age, sex, alcohol, drugs or speed.
- **Allowed joins**: code dictionary by code; aggregation to province-year or Spain-year and
  comparison with other aggregates at that level; the Catalan file at province-year
  (definitions validated, below).
- **Forbidden**: linking a DGT crash to a Catalan or Barcelona record by date, place or counts;
  treating deaths by vehicle type as vehicle involvement (they are outcome counts).
- **Selection and quality**: reconciled with the yearbook by 482 checks; recording practice
  differs by region (the share of unrecorded values by field and province, and how much of a
  model's ranking the unrecorded fields alone would carry, are measured in
  [`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md)); coding breaks are listed on the site's
  data page.
- **Role**: national analytical layer and external test domain; it trains a model only if the
  audit allows it (decision regenerated each run).

### DGT yearbook series and statistical tables (`dgt/tables/`)

- **Unit**: published aggregate cells (year, month, province, age band, sex, road user...).
- **Allowed**: comparison at the published aggregation; denominators at the same aggregation and
  scope (e.g. driver victims by age band with licence holders by age band).
- **Forbidden**: disaggregating to crashes or people.

### DGT driver census (`dgt/census/`) and kilometre estimates (`dgt/km_itv_*`)

- **Census unit**: licence holders by province, sex, licence class or age band, year. Denominator
  for driver outcomes of the same sex, age band and year; not for passengers or pedestrians.
- **Kilometres**: vehicle-kilometres by vehicle type (2022) and by the **owner's** age band
  (2024), from ITV odometer readings. Owner age is not driver age: per-km rates by age are "per km
  driven by cars registered to owners of this age" and are reported as ranges.

### INE population (`ine/ine_poblacion_provincias_edad_sexo.csv`)

- **Unit**: residents by province, five-year age group, sex and reference date, 2002-2025.
- **Allowed**: rates per resident at province-year or Spain-year, labelled as per resident (not
  per trip or kilometre). **Forbidden**: attaching residents to crashes or people.

### Traffic and fuel (`transportes/`, `cores/`) and surveys (`ine/` EHMA, ECEPOV; MOVILIA)

- Vehicle-km by type of road (Ministry Tabla 1.2.14; interurban networks only, excluding some
  municipal roads), toll-motorway traffic, monthly road fuel by product, and survey tables.
- A traffic series is a denominator only for deaths on the network it measures; national fuel is
  not a denominator for interurban deaths, and toll-motorway traffic is not one for all roads.
  Survey tables are context and cannot stand in for missing variables.

### Compiled registers (`compiled/`)

`compiled/evidence/*.csv` (parameters copied from external studies) and
`compiled/driving_activity_by_age.csv` (shares typed from travel surveys) are values transcribed
from publications, not data. Under rule 1 no analysis reads them; they are kept, unmodified and
hashed, as the record of what the withdrawn models used.

## Catalonia: crashes with a death or serious injury, 2010-2023 (`catalonia/`)

- **Source**: Servei Català de Trànsit export (downloaded as `export.csv`; download URL not
  recorded). **Unit**: one crash with at least one death or serious injury in Catalonia.
- **Key**: none in the source. `cat_crash_id` is a surrogate (the data row of the hash-pinned
  file); `row_sha1` hashes the raw row to detect repeats.
- **Coverage**: 2010-2023 by `Any`; four demarcations (= the provinces with INE codes 08, 17, 25,
  43), 43 comarques, the municipalities in `nomMun`.
- **Variables**: date, hour (`hor` is "H,MM" with a trailing zero dropped), zone, road and
  kilometre point, municipality, comarca, demarcation, deaths, serious and minor injuries,
  victims, units involved by type (pedestrians count as units), road speed limit, crash type,
  road type, owner, geometry, surface, lighting, weather, wind, fog, junction, priority, special
  lanes, and the police's "did this influence the crash" fields (`D_INFLUIT_*`).
- **Selection limitation**: the file contains only serious and fatal crashes. It supports
  frequency of serious crashes and severity *among* them (fatal against serious); it cannot say
  whether a crash happens or how likely a crash is to become serious.
- **Definitions, validated by data**: `D_GRAVETAT` "Accident mortal" if and only if `F_MORTS` > 0;
  every "Accident greu" has a serious injury. The file's fatal counts equal the DGT microdata's
  24-hour fatal counts in every province-year 2016-2023 and its total counts equal DGT's 24-hour
  fatal-or-serious counts within one crash (`crosssource.py`), so its severity behaves as the
  24-hour definition.
- **`C_VELOCITAT_VIA` is the road's speed limit, not a vehicle's speed.** It is a limit only when
  `D_LIMIT_VELOCITAT` is "Senyal velocitat". Under "Genérica via" it holds 100, 999 or `NA`
  whatever the road (100 even on urban streets): a code. `speed_limit_kmh` keeps posted limits
  only.
- **Recording artefacts**: the "not specified" levels of several fields are far rarer among fatal
  crashes (the file does not say why) and vary by year and place; those fields are
  excluded from the primary model (`recording.py`, `ML_LEAKAGE_AUDIT.md`). Structural `NA`s
  (road owner on urban streets, junction type away from junctions) are kept.
- **Allowed joins**: none at record level. Aggregates by province-year with the DGT microdata and
  INE residents (definitions above).
- **Forbidden**: matching any Catalan row to a Barcelona 2025 or DGT record by date, hour,
  coordinates, street, municipality, injury count, vehicles or any fuzzy rule.

## Barcelona 2025: Guàrdia Urbana crashes, people and causes (`barcelona/2025/`)

Six tables sharing `Numero_expedient` (spelt `Número_expedient` in the driver-cause file; only the
column name is normalised). Each table holds exactly the same set of crash ids (checked in
`DATA_QUALITY_MICRODATA.md` and `tests/test_microdata_tables.py`).

| Table (downloaded as) | Unit | Rows per crash | Reaches the crash table by |
|---|---|---|---|
| crashes (`download.csv`) | one crash | exactly 1 | is the crash table |
| accident types (`download(5).csv`) | one crash | exactly 1 | `merge(validate="one_to_one")` |
| mediate causes (`download(3).csv`) | one recorded cause, or one blank row | 1 or more | aggregation to one row per crash first |
| driver causes (`download(4).csv`) | one recorded driver-related cause | 1 or more | aggregation to one row per crash first |
| people (`download(1).csv`) | one person record | 1 or more | stays person-level; crash context joins `many_to_one` |
| vehicle records (`download(2).csv`) | not established | 1 or more | type presence only (quarantined) |

- **Crash table**: date, hour, shift, district, neighbourhood, street, coordinates, victims by
  severity, vehicles involved, pedestrian cause. Count cells leave zero blank: no count cell holds
  "0" and victims = deaths + serious + minor on every row only with blank read as zero; deaths
  match persons who died within 24 hours and serious injuries persons hospitalised over 24
  hours. The crash file's UTM labels are exchanged (its `X` column holds northings); corrected
  columns sit beside the source columns, and maps use WGS84.
- **People**: age, sex, role (driver, passenger, pedestrian), vehicle type on the record,
  pedestrian location and trip purpose, victimisation. `person_record_id` is a surrogate
  (crash id and order within the crash). `Descripcio_victimitzacio` is kept as published;
  `serious_or_fatal` is 1 for "Ferit greu" and either "Mort", 0 for "Il.lès" and the three "Ferit
  lleu", and missing for a blank (not recorded) and for "Mort natural" (not an injury outcome).
  `Descripcio_causa_vianant` repeats one value on every person of a crash: crash context, not the
  person's own.
- **Causes**: a crash's cause flags say the cause was *recorded* for the crash. Mediate causes
  have no "explicitly none" category: a single blank row means none was recorded, so `False` is
  "not recorded". Driver causes keep "No determinada" as its own status and have **no person or
  vehicle key**: they can never be attached to a person or vehicle.
- **Vehicle records**: more rows than reported vehicles and no vehicle identifier, so counting
  vehicles, per-vehicle rates, vehicle-person links and reading licence fields as a driver's are
  out of scope. Presence of a vehicle type in a crash is allowed (the set of types agrees with
  the person records for every crash). See [`BARCELONA_VEHICLE_AUDIT.md`](BARCELONA_VEHICLE_AUDIT.md).
- **Allowed joins**: within the six tables on `Numero_expedient`, as above.
- **Forbidden**: any record-level link to Catalonia or the DGT microdata; any rate per resident
  or per km (no municipal denominator in the repository); any person-level use of the cause
  tables.

## Where sources meet

Every cross-source comparison is listed with its key, cardinality, units before and after, the
definitions on each side and what was validated in `reports/tables/gen_cross_source_register.csv`
(rendered in [`GENERALISABILITY.md`](GENERALISABILITY.md)). In short:

| Comparison | Key | Status |
|---|---|---|
| Catalan file vs DGT microdata | province x year, 2016-2023 | counts compared; 24-hour definition validated |
| Catalan file per resident | province x year | rate per resident, not risk |
| Catalan model applied to DGT crashes | none (model applied to rows) | ten fields harmonised and validated on the shared crashes |
| Catalan model applied to Barcelona 2025 | none (model applied to rows) | eight fields harmonised; too few fatal crashes to benchmark |

The harmonised fields, with exact, defensible, approximate and unusable mappings, are in
`reports/tables/ml_common_features.csv`; only exact and defensible fields that pass the overlap
check enter a cross-source model.

## Machine-learning tables

Each table in `data/features/` has one row per real observation, a stable id, the target, the
grouping key where rows share a crash, the features the catalogue allows and a provenance record
(source files and SHA-256). The catalogue in `src/dgt_stats/microdata/ml/features.py` decides every
column's status (safe, questionable, direct leakage, excluded) and generates
[`ML_LEAKAGE_AUDIT.md`](ML_LEAKAGE_AUDIT.md). Rows of one crash never fall on both sides of a split
(`tests/test_microdata_models.py`); categorical gaps are explicit categories and numeric gaps are
imputed inside the pipeline on training rows only; no synthetic or oversampled rows are created.

Every model is compared with a descriptive lookup table before it is presented, and kept only if
it beats it (`src/dgt_stats/microdata/ml/rules.py`); the decision for every model, with where it
works and fails, is generated in [`MODEL_DECISIONS.md`](MODEL_DECISIONS.md). Transfer results
are always reported beside an in-domain reference, and representativeness (how populations
differ) is reported separately from transportability (whether a model keeps its ranking):
[`GENERALISABILITY.md`](GENERALISABILITY.md).
