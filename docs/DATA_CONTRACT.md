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
   Two exceptions remain. The first is the EMEF's road-to-straight-line distance ratio for
   driving trips (1.45) and the 2021 distance benchmarks, typed into
   `src/dgt_stats/emef/distance.py` from the EMEF 2021 distance report, the survey producer's
   measurement on the same survey's 2021 trips. The report is not archived and could not be
   found again, so these values rest on the transcription
   ([`research/DRIVER_AGE_EXPOSURE.md`](research/DRIVER_AGE_EXPOSURE.md)). The second is the
   Fundació RACC 2013 survey of licence holders aged 65 and over: the shares who do not drive
   and the days a week the others drive, typed into `src/dgt_stats/exposure_risk/national.py`
   from the published slide dossier and not archived, because RACC grants no reuse licence.
   They set the upper limit on men's kilometres at 75 and over in one split of the 65-and-over
   kilometres ([`data_sources.md`](data_sources.md)).
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
| National context | DGT crash microdata, yearbook series and tables, driver census and kilometre estimates; INE residents; traffic and fuel series | trends, exposure and denominators, province and year comparisons, historical context, aggregate rates, benchmarks for the regional files | training a predictive model unless the [DGT audit](DGT_MICRODATA_AUDIT.md) allows it (the severity regression of `scripts/model.py` is a supporting association analysis, never used for prediction); denominators for individual crashes |
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
9. **A source enters a predictive model only if it passes its audit.** The DGT crash microdata
   train a predictive model only if all seven checks of [`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md) pass
   (unit, target, definitions, construction, severity and inclusion definitions, comparability
   across provinces, recording artefacts); otherwise they stay the national analytical layer (the
   supporting association analysis among them) and a test domain for fields validated on the
   crashes both sources hold.

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
- **Selection and quality**: reconciled with the yearbook by 482 checks; how often fields are
  left unrecorded differs by region (the share of unrecorded values by field and province, and how much of a
  model's ranking the unrecorded fields alone would carry, are measured in
  [`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md)); coding breaks are listed on the site's
  data page.
- **Role**: national analytical layer (including the supporting association analysis) and
  external test domain; it trains a predictive model only if the audit allows it (decision
  regenerated each run).

### DGT yearbook series and statistical tables (`dgt/tables/`)

- **Unit**: published aggregate cells (year, month, province, age band, sex, road user...).
- **Allowed**: comparison at the published aggregation; denominators at the same aggregation and
  scope (e.g. driver victims by age band with licence holders by age band).
- **Forbidden**: disaggregating to crashes or people.

### DGT driver census (`dgt/census/`) and kilometre estimates (`dgt/km_itv_*`)

- **Census unit**: licence holders by province, sex, licence class or age band, year. Denominator
  for driver outcomes of the same sex, age band and year; not for passengers or pedestrians.
- **Kilometres**: vehicle-kilometres by vehicle type (2022), by the **owner's** age band (2024)
  and by class of service (2024), from ITV odometer readings. Owner age is not driver age, so the
  owner-age kilometres are never the denominator of a per-km rate by driver age: they are the
  comparison Method D, a bound for the age mix of the kilometres the travel survey does not
  cover (reported with its values and left out of the sensitivity ranges) and diagnostics of the
  75-and-over checks; since October 2026 no split of the 65-and-over kilometres takes its 75+
  share from them. The car total by class of service, less taxis and ride-hailing cars, sets the
  level of the driver-age rates (Method B).

### INE population (`ine/ine_poblacion_provincias_edad_sexo.csv`, `ine/ine_poblacion_edad_simple_sexo.csv`)

- **Unit**: residents by province, five-year age group, sex and reference date, 2002-2025; and
  residents of Spain by single year of age and sex, read from single years and "105 y más" only
  (the file's overlapping aggregates "85 y más" and "100 y más" are never summed). Annual rates
  divide by the 1 July population.
- **Allowed**: rates per resident at province-year or Spain-year, labelled as per resident (not
  per trip or kilometre). **Forbidden**: attaching residents to crashes or people.

### Travel surveys (`emef/`, `crtm/edm2018/`)

- **Unit**: a respondent and the trips they made on one reference day (EMEF: a working day in the
  Barcelona area, 2014–2024; EDM2018: a weekday in the Community of Madrid, 2018), with the
  survey's expansion weight. Car-driver trips are those with a stage coded as car driver; a
  passenger stage never makes a driving trip.
- **Allowed**: weighted kilometres, trips and shares of residents by sex and age group, as the
  denominator of car drivers' crash involvement by age once transferred to a population by
  Methods A to C ([`research/DRIVER_AGE_EXPOSURE.md`](research/DRIVER_AGE_EXPOSURE.md)).
  Estimates carry bootstrap intervals from the respondents (EMEF, within year and comarca) or
  households (EDM2018).
- **Forbidden**: attaching respondents to crashes or people; publishing an EMEF estimate that
  rests on fewer than 20 sample observations (the data holders' rule); splitting the EMEF's 65+
  group, which no public file allows, except under a stated assumption (the conditional estimate
  beside its sensitivity range) or, for one bound and one validation, through the questionnaire's
  P1b routing, as aggregates under the 20-observation rule (`emef/older_routing.py`).

### Traffic and fuel (`transportes/`, `cores/`) and surveys (`ine/` EHMA, ECEPOV; MOVILIA)

- Vehicle-km by type of road (Ministry Tabla 1.2.14; interurban networks only, excluding some
  municipal roads), toll-motorway traffic, monthly road fuel by product, and survey tables.
- A traffic series is a denominator only for deaths on the network it measures; national fuel is
  not a denominator for interurban deaths, and toll-motorway traffic is not one for all roads.
  Survey tables are context and cannot stand in for missing variables. MOVILIA 2006 and 2007
  tables, and the fuel and toll-motorway series, enter the driver-age rates only as alternative
  age mixes and coverage settings in the sensitivity analysis, never as a denominator.

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
  match persons who died within 24 hours, and serious injuries persons hospitalised over 24
  hours plus persons who died after 24 hours (the 24-hour classification of the Catalan file).
  Minor injuries include people who refused medical care, whom DGT's definition of a slight
  injury, which requires medical care, would not count. The crash file's UTM labels are exchanged (its `X` column holds northings); corrected
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
- **Allowed with stated limits**: car drivers involved in crashes with a victim per kilometre
  driven inside the city on working days, by age group, as ratios to the 45-64 group
  (`exposure_risk.barcelona`): aggregate matching to the EMEF 2022-2024 working-day car-driver
  kilometres of residents of the province, never record linkage. The numerator counts every
  driver, residents of the province or not, in 2025; the denominator counts residents' kilometres
  in other years, and trips crossing the city boundary are bracketed by three denominators.
- **Forbidden**: any record-level link to Catalonia or the DGT microdata; any rate per resident
  (no municipal population denominator in the repository); any per-km rate other than the one
  above; any person-level use of the cause tables.

## Where sources meet

Every cross-source comparison is listed with its key, cardinality, units before and after, the
definitions on each side and what was validated in `reports/tables/gen_cross_source_register.csv`
(rendered in [`GENERALISABILITY.md`](GENERALISABILITY.md)). In short:

| Comparison | Key | Status |
|---|---|---|
| Catalan file vs DGT microdata | province x year, 2016-2023 | counts compared; 24-hour definition validated |
| Catalan file per resident | province x year | rate per resident, not risk |
| Catalan model applied to DGT crashes | none (model applied to rows) | eleven fields harmonised and validated on the shared crashes (DGT's inverted Catalan junction flag of 2023 read the other way round) |
| Catalan model applied to Barcelona 2025 | none (model applied to rows) | eight fields harmonised; too few fatal crashes to benchmark |
| Car drivers involved per km by age, Spain | age group, no record matched | DGT drivers of 2024 against a regional working-day survey profile transferred to Spain's population and DGT's car-km total: ratios between ages, with a sensitivity range |
| Car drivers involved per km by age, Barcelona city working days | age group x working day, no record matched | Guàrdia Urbana drivers of 2025 against EMEF 2022-2024 residents' km inside the city: a range of ratios between ages |

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
