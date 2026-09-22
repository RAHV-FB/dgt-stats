# Methodology

How the numbers on the site are made, as built (September 2026). The planning document that
preceded the data audit is superseded by this one; the scope decisions it forced are in
[`analytics_plan.md`](analytics_plan.md) and the per-phase plans, and the reasons the project could
not do what it first set out to do are in the README. Every method below names the module that
implements it.

## 1. Units and sources

The public DGT crash microdata are one row per injury crash: 875,013 rows for 2016–2024, with the
place, time, road, conditions and victim counts by severity and road-user type. There are no
vehicle or person rows, so nothing here is estimated at the driver, vehicle or victim level; where
the site speaks of drivers it uses DGT's aggregate yearly tables, which count drivers by age, sex,
vehicle and recorded infraction but cannot be linked to crashes.

| Source | Unit | Years | Used for |
|---|---|---|---|
| crash microdata | injury crash | 2016–2024 | timing, road users, severity models, 2019 case study |
| yearbook series | year, month or province totals | 1993–2024 | trends, occupant deaths by vehicle, 2006 case study, reference totals for reconciliation |
| yearly statistical tables | aggregate cells | 2014–2024 | vehicles involved, victims by mode, drivers by age, sex and infraction |
| driver census | licence holders by province, sex, age | 2014–2025 | denominators |
| INE population | residents by province, age, sex | 2002–2025 | denominators |
| ITV kilometre estimates | fleet and mean km by vehicle type and age | 2022 | per-km rates |
| DGT speed report | 61 of its 64 tables, transcribed from the PDF | 2014–2023 | speed page, as published |

Raw files are never edited (`data/raw/`, listed in `manifest.csv` with SHA-256 and source URL).
`ingest.py` parses them into typed Parquet tables (`data/interim/`), `build_tables.py` adds the
derived fields (`data/processed/`), and every result table and figure is written by `model.py` and
`analyse.py` from those layers. The site reads only the committed result tables.

## 2. Reconciliation before analysis

No summary is published until the crash microdata, the yearbook tables and the driver census
reconcile with DGT's own totals (`validate.py`, 434 checks, all enforced by
`tests/test_validate.py`):

| Check | What must agree | Tolerance |
|---|---|---|
| row_count, victim_total | crashes, deaths, hospitalised and non-hospitalised per year against the yearbook, 30-day and 24-hour | exact |
| table_1_1_province, table_3_1_month | 2024 crashes and deaths by province and by month against the 2024 tables | exact |
| unique_key, code_domain | one identifier per crash and year; every code in the dictionary or a documented missing state | exact |
| driver_deaths | driver deaths in tables 4.1.1 against the series, 2014–2024, both zones | exact |
| table_2_2_deaths | deaths by means of transport in tables 2.2 against the microdata death columns, 2020–2024 | exact |
| table_2_3_vehicles | vehicles involved in tables 2.3 against the microdata vehicle count, 2020–2024 | 0.1 % |
| census_2025, census_age_2023 | the census text files against the published census tables | 0.5 % and 2 % |
| table_6_1_drivers | the blocks of table 6.1 that publish a total agree (two in 2014–2015, six from 2016), within 1.5 % of table 4.2 | 1.5 % |

The other interim inputs have no row in `validation.csv`, because DGT publishes no total to check
them against: the INE population, the 2022 ITV kilometre tables, the transcribed speed-factor
report and the MOVILIA and ESRA shares are covered by unit tests (`tests/test_population.py`,
`test_exposure.py`, `test_reports.py`, `test_activity.py`) that check their internal totals instead.

Where two publications of the same quantity differ, one is kept for as long as it exists rather
than mixing them: licence holders by age come from the published class-by-age tables to 2023 and
the text files from 2024; 24-hour and 30-day deaths are never combined; provisional figures are not
used.

## 3. Definitions and derived fields (`derive.py`, `codes.py`)

- **Injury crash**: at least one person killed or injured. **Death**: within 30 days. **Serious
  crash**: at least one death or one person admitted to hospital for more than 24 hours. A crash
  is `fatal` when its 30-day death count is positive.
- **Zone**: DGT's grouped zone, interurban road or urban street and crossing. **Road group**
  (`TIPO_VIA`, `derive.ROAD_GROUP_BY_TYPE`, labels from the DGT dictionary): motorway (1 "Autopista
  de peaje", 2 "Autopista libre"), dual carriageway (3 "Autovía", 5 "Carretera Convencional de doble
  calzada"), conventional (4 "Vía para automóviles", 6 "Carretera Convencional de calzada única"),
  urban street (9 "Calle"), other (7 "Vía de servicio", 8 "Ramal de enlace", 10 "Camino vecinal",
  11 "Recinto delimitado", 12 "Vía ciclista", 13 "Senda ciclable", 14 "Otro"). The 2019 case study
  groups the raw codes differently (section 7).
- **Time of day**: six bands, 00:00–06:59 the first. **Night** on the timing page means the
  lighting was recorded as no natural light, `CONDICION_ILUMINACION` codes 4 to 6 ("Sin luz natural
  y con iluminación artificial encendida", "... no encendida", "Sin luz natural ni artificial"), not
  a clock hour; daylight (1), dawn and dusk (2 "Amanecer o atardecer, sin luz artificial", 3 "... con
  luz artificial") and rows with no lighting code all count as not night. **Weekend**: Saturday,
  Sunday and Friday from 20:00.
- **Vulnerable road users**: pedestrians, cyclists, moped riders, motorcyclists and personal
  mobility vehicle users, summed from the death columns by type.
- **Missing states**. Four are kept apart in every table: not specified (999), not applicable (998),
  an explicit unknown code (six fields have one) and an empty cell. Each condition column has a
  `status_*` companion that names the state, and the data page profiles them by year. The fields
  that carry no code list use a placeholder instead of an empty cell — `KM` 9999, and 1000 in 2019,
  the year DGT used it; `CARRETERA` "No inventariada"; `COD_MUNICIPIO` 00000 for towns under 5,000
  inhabitants — and the missingness profile counts those values as not observed (`validate.py`,
  `codes.TEXT_PLACEHOLDERS` and `codes.NUMERIC_PLACEHOLDERS`; the km fill value counts only where
  the road is not inventoried, because km 1000 is a real post on a long N-road), so a year that
  swapped an empty cell for a placeholder does not read as an improvement in recording. No analysis
  drops a row for a missing value except in two places, each stated where it is used: the hour-band
  by road-group table leaves out the 85 crashes (39 in 2017, 46 in 2018) whose road type is an
  empty cell, as its caption says, and the driver age-band rates leave out drivers of unknown age
  (section 4). Two undocumented quirks are handled as stated on the data page: code 0 in the island
  field from 2018 and the strong-wind flag in 2021.

## 4. Rates and intervals (`rates.py`, `summaries.py`)

Counts of deaths, crashes or involved drivers are treated as Poisson with a known denominator, and
every rate built against a counted denominator — residents, licence holders, drivers involved,
circulating vehicles, vehicle-kilometres — carries an exact 95 % interval (Garwood, from the
chi-square quantiles); the travel-weighted rate is the exception, and its bullet below says what it
carries instead. Ratios of two such rates carry a log-normal interval. The survey shares and the
speed-infraction share among drivers whose status is known carry Wilson intervals. Shares and
ratios taken entirely within one source's own counts (the fatal share by hour and road group, the
night shares and the vulnerable and road-user shares from the microdata; deaths per 100 crashes
from the yearbook series; occupant deaths per fatal involvement from tables 2.2 and 2.3; the raw
speed-status shares from tables 6.1) are population counts, not samples, and are reported without
intervals.

Denominators, each named on the page that uses it:

- **Residents**: INE's estimate on 1 July of the year, by province and five-year age group.
- **Licence holders**: DGT's yearly census, people holding any driving permit or a moped or
  agricultural licence, by province, sex and age band. DGT publishes no reference date for the
  census, only the year, so a calendar-year death count is divided by one undated yearly snapshot,
  unlike the residents on 1 July.
- **Travel-weighted drivers** (older-drivers page only): the ESRA share of adults aged 18–74 who
  drive at least a few days a month (80.2 % in 2018, 75.9 % in 2023), interpolated between the two
  waves and held flat outside them, spread across age bands in proportion to the MOVILIA 2006
  weekday car-travel profile and capped at the licence-holding share of the band. The profile is
  car-or-motorcycle trips per resident in the MOVILIA bands (15–29, 30–39, 40–49, 50–64, 65+),
  given to every INE five-year group inside them, averaged into the analysis bands and normalised
  so its residents-weighted mean over the analysis bands 15–74 is 1;
  MOVILIA's top band is 65 and over, so 75+ inherits the 65+ intensity. The cap is not
  redistributed, so the estimate no longer reproduces the ESRA level: over 2014–2024 it sums to
  roughly 60–66 % of residents aged 15–74 against an ESRA share of 76–80 %, and the 15–44 bands
  throughout, plus 45–54 through 2020, sit at their licence share rather than a travel weight —
  about a third of the 35–64 reference group from 2021 and roughly 70 % of it before that. It is a
  weight for how much each band travels by car, not a count of drivers. MOVILIA counts passengers
  as well as drivers, which overstates older people's driving and pushes the ratio down, while its
  2006 profile is frozen across 2014–2024 and could move it either way, so the direction of the net
  bias is not established; the page says so. The travel-weighted rate is published as a point
  estimate only: the `deaths_per_100k_travel_low` and `_high` columns of `q7_driver_ladder.csv` are
  an envelope, the Poisson bound of the death count divided by the opposite bound of the
  survey-based exposure, not an exact interval, and no page or figure reads them.
- **Drivers involved in injury crashes**: from tables 4.2, giving deaths per 1,000 involved drivers
  (fatality given involvement) and involvement per 10,000 licence holders. Drivers of unknown age
  (about 3 % of those involved, 0.4 % of those killed) and the few recorded in DGT's 0–14 band
  (0.3 % and 0.2 %) are left out of the age-band rates.
- **Circulating vehicles and vehicle-kilometres**: section 6.

Province rates are shown with their intervals and ranked, and the page states how far one death
more or less would move the two smallest provinces in the ranking. Age comparisons are ratios of
the 65+ and 75+ bands to 35–64 under each denominator in turn, because the answer changes with the
denominator and the page is built to show that.

## 5. Severity models (`features.py`, `models.py`, `scripts/model.py`)

Two logistic regressions on all 875,013 crashes: the odds that a crash is fatal, and that it is
serious. Predictors are the circumstances the crash record carries: zone, road group, crash type,
junction, lighting, weather, surface, alignment, time of day, weekend, number of vehicles and year.
Each is an ordered categorical whose reference is its most common level, so an odds ratio reads
"relative to the typical crash". The missing states are separate levels, as in section 3: "not
specified" (999), "not applicable" (998) and, where the field has one, its explicit unknown code
(weather 7, surface 9, alignment 4) each stand on their own and are never pooled with each other or
with a recorded value. Three things are exceptions to keeping every level, and the page names all
three. A level with fewer than 500 crashes is merged into its reference and the grouping table on
the page records it. The "not applicable" alignment code folds into "straight" for a different
reason: it is exactly the urban-street zone (546,619 crashes, every one of them zone 3 and no zone-3
crash coded otherwise), so as a level of its own it would duplicate the zone predictor. And a level
with no event in a fit is left out rather than estimated, as the separation check below says.

The fit is main effects only, by iteratively reweighted least squares written in `numpy` (the
`statsmodels` route ran out of memory on the design), with a cluster-robust sandwich covariance by
province. It reports odds ratios with 95 % intervals, average marginal effects in probability
points (every crash set to a level, then to the reference, and the mean predicted probabilities
compared), predicted probabilities for six named crash profiles, and three checks:

- **Holdout**: fit on 2016–2022 without the year terms, scored on 2023–2024; area under the ROC
  curve, Brier score against the base rate, and calibration by decile of predicted probability.
- **Stability**: the ten largest effects, missing-state levels excluded from the choice, refitted
  year by year with the same clustering by province as the full model; a level whose yearly
  estimate leaves the full model's interval is named on the page, and the count of such estimates
  is the `within_full_interval` column of `q3_year_stability.csv`. The 2024 change in DGT's
  urban road-type coding shows up here, and the page says road type and zone must be read
  together; the 2021 interurban change (code 5 collapsing into code 6, `data_inventory.md`) means
  the pooled dual-carriageway and conventional odds ratios span two coding regimes.
- **Separation**: a level with no events in a fit is left out and listed rather than estimated, and
  so is a column that a per-year subset makes a linear combination of the others.

The models describe association between recorded circumstances and outcome. They carry no
driver, vehicle, speed or impairment information, so they cannot attribute a death to a factor and
the page does not.

## 6. Vehicles per kilometre (`vehicles.py`)

A 2022 cross-section. The numerator is vehicles involved in injury crashes and in fatal crashes by
type, from yearbook table 2.3 (the microdata record only the total number of vehicles in a crash,
`TOTAL_VEHICULOS`, and deaths by road-user type, never which vehicle types were involved; the check
in section 2 reconciles table 2.3's counts against that microdata vehicle total), and occupant
deaths by vehicle from table 2.2 and the yearbook series. The denominator is DGT's ITV estimate of
the circulating fleet and its mean annual kilometres by vehicle type and age, which the methodology
note derives from annualised odometer readings at roadworthiness inspections and which is valid for
aggregates only. The fleet in that table is DGT's "parque circulante": the vehicles with an ITV,
insurance, ownership-change, re-registration or fine record in the previous ten years, which DGT
says leaves out between 5 % and 45 % of the active register depending on the vehicle type. The
per-vehicle rates are therefore per circulating vehicle, not per registered vehicle, and are
higher than a register-based rate would be.

Six rate groups: motorcycles, mopeds, cars, vans with light trucks, heavy trucks, buses. Vans and
light trucks are one group because the crash record codes most light commercial vehicles as vans
while the register splits them, so only the sum means the same thing in numerator and denominator.
Heavy trucks include tractor units and articulated vehicles because the kilometre table's heavy
category is the sum of the note's "camiones de más de 3.500 kg" and "tractores industriales". Rates
are per billion vehicle-kilometres and per 100,000 circulating vehicles, with Poisson intervals. The
seven kilometre-table types are DGT's whole circulating fleet, 32,522,330 vehicles, and add up to
91 % of the 35,668,443 on the register in 2022; the two totals are not nested, since the register
also holds machinery, trailers and other types with no kilometre estimate while the circulating
fleet leaves out registered vehicles with no record in ten years. Everything outside the table —
bicycles, personal mobility vehicles, machinery, unknown vehicles and pedestrians — has no
denominator and no rate.

## 7. Interrupted time series (`policy.py`)

Two policy changes with a legal date and a clean window; the page uses "coincided with" unless the
pre-trend, the placebo distribution and the sensitivity fits agree, and it makes no claim when they
do not.

**Points-based licence, 1 July 2006**: a segmented Poisson regression of the yearbook's monthly
30-day deaths on a linear trend, eleven month-of-year terms, a level change at July 2006 and a
slope change after it, fitted from January 2000 to November 2007 (the month before the Penal Code
reform on driving offences) with Newey–West standard errors at twelve lags. The level change is
reported as a percentage with its interval, together with the raw twelve-month comparison and the
pre-trend, so the two can be read against each other. Placebos re-estimate the level change with
the break at every month that leaves at least 24 months before it and the true post-window length
after it, ending before July 2006, and the true estimate's rank among them is printed. Sensitivity
fits: 24-hour deaths; interurban and urban deaths separately; the pre-period run from January 1993
instead of 2000; a level change without the slope term; a log fleet offset (registered
vehicles interpolated between mid-years); a negative binomial whose dispersion is set by moments
from the Poisson fit (the likelihood search did not converge reliably when the data are close to
Poisson); and the window extended to December 2009 with a second break at the Penal Code reform.

**90 km/h limit on conventional roads, 29 January 2019**: monthly 30-day deaths in two groups of
road-type codes from the microdata, January 2016 to February 2020. The groups are built from the
raw `TIPO_VIA` code, not from the road group of section 3: the treated group is the conventional
roads, codes 5 ("Carretera Convencional de doble calzada") and 6 ("Carretera Convencional de
calzada única"), and the control group is codes 1, 2 and 3 (toll motorway, free motorway,
autovía). Code 5 belongs with the treated roads because a conventional road with two carriageways
is conventional under Real Decreto 1514/2018, and keeping 5 and 6 together also removes a coding
artefact: from 2021 most crashes that had been coded 5 are coded 6 (`data_inventory.md`), which
would otherwise show up as a shift between the groups. Code 4 ("Vía para automóviles", a handful of
deaths a year) is in neither group. The treated group mixes roads the decree cut from 100 to
90 km/h (conventional roads with a paved shoulder of 1.5 m or more) with roads already at 90 km/h,
so the estimate is diluted by the share of conventional-road deaths on roads whose limit did not
change, which the microdata cannot separate. The model is a Poisson regression with a shared linear
trend, month-of-year terms, a group term, a post term and the post × conventional interaction as
the estimate, so what is reported is the treated group's change relative to the control, not the
conventional roads' own level change, with Newey–West errors computed within each group. Neither
design applies a small-sample correction to the Newey–West covariance (`use_correction=False` in
both), so the two sets of intervals are built the same way. Two
placebo breaks (January 2017 and 2018) test whether the two groups were already diverging; the
extended fit through December 2024 adds lockdown (March–June 2020) and restriction (July 2020 to
December 2021) periods, each as a level for both groups and a further level for conventional roads.
The page reports the estimate, the placebos and the sensitivity fits together and draws no
conclusion about the limit unless they agree.

## 8. Speed factor (`speed.py`, `io_reports.py`)

Two aggregate sources, neither linkable to crashes. Tables 6.1 count drivers involved by recorded
infraction, 2014–2024, interurban and urban; the site shows the share of drivers with no speed
record beside the share with one, and gives the infraction share both over all drivers and among
those with a record, with Wilson intervals, because the unrecorded share changed from 17 % to 52 %
in 2016 and a single share would hide it. The DGT speed-factor report prints 64 tables (numbered 1
to 61, three numbers used twice); 61 of them are transcribed from the PDF text, all but the three
"Variaciones 2023/2022 y 2023/2019" tables, and the 12 day-and-hour tables, Tablas 50 to 61, are
its Anexo I; every row carries the report's regional scope (Spain without
Cataluña and País Vasco, 28 % of injury crashes), and its figures are never added to yearbook
totals. Where the report's own unknown category dominates a breakdown (the speed limit in 2014),
the page compares shares among the known categories and says so. "Speed factor" throughout means
the police officer's recorded judgement of inappropriate speed, not a measurement.

## 9. Figures, pages and wording

Figures are matplotlib SVG with no date metadata, so a rebuild in the same environment
(`requirements.lock`) changes nothing unless a number changes; a different matplotlib version
changes the embedded version string and the tight-bbox geometry in every figure. One axis per
chart, intervals drawn where they exist, direct labels where a legend would
be ambiguous, colour never the only encoding. Every sentence on a page that contains a number is
computed from the result tables at build time, including the digest on the front page, so the
prose cannot contradict the tables; conditional sentences (a rank, a placebo that passes or fails)
are gated on the same values. The exceptions are a few figures no result table holds and the
pages state as facts about the sources (the 61 of 64 tables of the speed report, the publisher's
5 November 2025 update of the 2024 microdata, the share of drivers of unknown age), and the
per-year coding shares the severity and data pages quote from the audit. Two thresholds gate
wording. A rate ratio between 0.95 and 1.05 reads
"about as often", outside that band "less often" or "more often" (`site.py`, `ABOUT_AS_OFTEN`);
where the comparison carries an interval — the per-kilometre occupant-death and involvement rates —
the wording follows the interval instead, so a ratio whose interval contains 1 reads "about as
often". The 2024 road-type paragraph on the severity page appears only when every 2024 road-type
odds ratio falls below the full model's interval and inside 0.67–1.5 (`COLLAPSE_BAND`) while every
zone odds ratio is above its full-model estimate. Tests check that every internal link and anchor
resolves, every image has alt text, every page has one heading, a description and no script.

## 10. Reproducibility

- Raw inputs immutable and manifested; interim and processed layers rebuilt from them by the
  command sequence in the README, which was run end to end from an empty interim layer and
  reproduced every committed table, figure and page byte for byte with Python 3.11.15 and the
  library versions recorded in `requirements.lock` (pandas 3.0.6, numpy 2.4.6, scipy 1.17.1,
  statsmodels 0.15.0, matplotlib 3.11.2, scikit-learn 1.9.1, pyarrow 25.0.1); the lock file records
  the libraries, not the interpreter, which `pyproject.toml` only bounds at 3.11 or later. At the
  dependency floors in `pyproject.toml` the numbers agree to the precision printed on the pages,
  but every figure differs, because matplotlib writes its own version into the SVG and the
  tight-bbox geometry changes with it; where that geometry crosses a rounding boundary it also
  changes the `width` and `height` attributes the pages give the images (`site.py`,
  `_svg_dimensions`), so some pages differ in those two attributes and in nothing else. The
  descriptive result tables are written with ten significant digits (`analyse.py`,
  `float_format="%.10g"`) and the severity-model tables with six (`model.py`,
  `float_format="%.6g"`), so that last-bit differences between library versions in the fitted
  coefficients do not reach the committed files.
- All logic in `src/dgt_stats/` and `scripts/`; no notebooks. No random procedure is used: the
  fits are deterministic and need no seed.
- The test suite (`pytest`, the reconciliation checks among them; the SHA-256 check of every raw
  file against `data/raw/manifest.csv` is marked slow and deselected by default, `pytest -m slow`
  runs it); `ruff` for lint and format.
- The Pages workflow renders the site from the committed tables and never rebuilds the data.

## 11. Limits that apply throughout

- Crash-level records only: no driver age, sex, alcohol, drug, speed, belt or helmet fields, so
  factor interactions and person-level risk are out of reach.
- Police-recorded circumstances, whose completeness varies by year (the missingness profile) and
  by severity.
- All model results are associations; the case studies are coincidences in time unless the checks
  above agree.
- Vehicle-kilometres exist for one year; the speed report excludes two regions; road-type coding
  changed in 2021 (interurban, code 5 collapsing into code 6) and in 2024 (urban); two
  publications of the driver census by age differ by up to 1.1 %.
