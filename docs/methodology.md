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
| crash microdata | injury crash | 2016–2024 | timing, road users, severity models, 2019 case study, occupant deaths by vehicle |
| yearbook series | year, month or province totals | 1993–2024 | trends, 2006 case study, reference totals for reconciliation |
| yearly statistical tables | aggregate cells | 2014–2024 | vehicles involved, victims by mode, drivers by age, sex and infraction |
| driver census | licence holders by province, sex, age | 2014–2025 | denominators |
| INE population | residents by province, age, sex | 2002–2025 | denominators |
| ITV kilometre estimates | fleet and mean km by vehicle type and age | 2022 | per-km rates |
| DGT speed report | annex tables transcribed from the PDF | 2014–2023 | speed page, as published |

Raw files are never edited (`data/raw/`, listed in `manifest.csv` with SHA-256 and source URL).
`ingest.py` parses them into typed Parquet tables (`data/interim/`), `build_tables.py` adds the
derived fields (`data/processed/`), and every result table and figure is written by `model.py` and
`analyse.py` from those layers. The site reads only the committed result tables.

## 2. Reconciliation before analysis

No summary is published until the interim layer reconciles with DGT's own totals
(`validate.py`, 434 checks, all enforced by `tests/test_validate.py`):

| Check | What must agree | Tolerance |
|---|---|---|
| row_count, victim_total | crashes, deaths, hospitalised and non-hospitalised per year against the yearbook, 30-day and 24-hour | exact |
| table_1_1_province, table_3_1_month | 2024 crashes and deaths by province and by month against the 2024 tables | exact |
| unique_key, code_domain | one identifier per crash and year; every code in the dictionary or a documented missing state | exact |
| driver_deaths | driver deaths in tables 4.1.1 against the series, 2014–2024, both zones | exact |
| table_2_2_deaths | deaths by means of transport in tables 2.2 against the microdata death columns, 2020–2024 | exact |
| table_2_3_vehicles | vehicles involved in tables 2.3 against the microdata vehicle count, 2020–2024 | 0.1 % |
| census_2025, census_age_2023 | the census text files against the published census tables | 0.5 % and 2 % |
| table_6_1_drivers | the six blocks of table 6.1 share one total, within 1.5 % of table 4.2 | 1.5 % |

Where two publications of the same quantity differ, one is kept for as long as it exists rather
than mixing them: licence holders by age come from the published class-by-age tables to 2023 and
the text files from 2024; 24-hour and 30-day deaths are never combined; provisional figures are not
used.

## 3. Definitions and derived fields (`derive.py`, `codes.py`)

- **Injury crash**: at least one person killed or injured. **Death**: within 30 days. **Serious
  crash**: at least one death or one person admitted to hospital for more than 24 hours. A crash
  is `fatal` when its 30-day death count is positive.
- **Zone**: DGT's grouped zone, interurban road or urban street and crossing. **Road group**:
  motorway (motorway and urban motorway codes), dual carriageway (dual carriageway and multi-lane),
  conventional (conventional with and without shoulder), urban street, other.
- **Time of day**: six bands, 00:00–06:59 the first. **Night** on the timing page means the
  lighting was recorded as dark (with or without street lighting or at dusk), not a clock hour.
  **Weekend**: Saturday, Sunday and Friday from 20:00.
- **Vulnerable road users**: pedestrians, cyclists, moped riders, motorcyclists and personal
  mobility vehicle users, summed from the death columns by type.
- **Missing states**. Four are kept apart in every table: not specified (999), not applicable (998),
  an explicit unknown code (six fields have one) and an empty cell. Each condition column has a
  `status_*` companion that names the state, the data page profiles them by year, and no analysis
  drops a row for a missing value. Two undocumented quirks are handled as stated on the data page:
  code 0 in the island field from 2018 and the strong-wind flag in 2021.

## 4. Rates and intervals (`rates.py`, `summaries.py`)

Counts of deaths, crashes or involved drivers are treated as Poisson with a known denominator, and
every rate carries an exact 95 % interval (Garwood, from the chi-square quantiles). Ratios of two
rates carry a log-normal interval. Survey shares carry Wilson intervals.

Denominators, each named on the page that uses it:

- **Residents**: INE's estimate on 1 July of the year, by province and five-year age group.
- **Licence holders**: DGT's census at its reference date, people holding any driving permit or a
  moped or agricultural licence, by province, sex and age band.
- **Travel-weighted drivers** (older-drivers page only): the ESRA share of adults who drive,
  interpolated between the 2018 and 2023 waves and held flat outside them, spread across age bands
  in proportion to the MOVILIA 2006 car-travel profile and capped at the licence-holding share of
  the band. It is a weight for how much each band travels by car, not a count of drivers. MOVILIA
  counts passengers as well as drivers, so the estimate overstates older people's driving and the
  per-driver ratio it yields is a lower bound; the page says so.
- **Drivers involved in injury crashes**: from tables 4.2, giving deaths per 1,000 involved drivers
  (fatality given involvement) and involvement per 10,000 licence holders. Drivers of unknown age
  (about 3 % of those involved, 0.4 % of those killed) are left out of the age-band rates.
- **Registered vehicles and vehicle-kilometres**: section 6.

Province rates are shown with their intervals and ranked; small provinces are flagged where their
intervals span most of the range. Age comparisons are ratios of the 65+ and 75+ bands to 35–64
under each denominator in turn, because the answer changes with the denominator and the page is
built to show that.

## 5. Severity models (`features.py`, `models.py`, `scripts/model.py`)

Two logistic regressions on all 875,013 crashes: the odds that a crash is fatal, and that it is
serious. Predictors are the circumstances the crash record carries: zone, road group, crash type,
junction, lighting, weather, surface, alignment, time of day, weekend, number of vehicles and year.
Each is an ordered categorical whose reference is its most common level, so an odds ratio reads
"relative to the typical crash". Missing states are levels of their own. A level with fewer than
500 crashes is merged into its reference and the grouping table on the page records it; the
"not applicable" alignment code, which is exactly the street zone, folds into "straight" for the
same reason.

The fit is main effects only, by iteratively reweighted least squares written in `numpy` (the
`statsmodels` route ran out of memory on the design), with a cluster-robust sandwich covariance by
province. It reports odds ratios with 95 % intervals, average marginal effects in probability
points (every crash set to a level, then to the reference, and the mean predicted probabilities
compared), predicted probabilities for six named crash profiles, and three checks:

- **Holdout**: fit on 2016–2022 without the year terms, scored on 2023–2024; area under the ROC
  curve, Brier score against the base rate, and calibration by decile of predicted probability.
- **Stability**: the ten largest effects refitted year by year without clustering; a level whose
  yearly estimate leaves the full model's interval is named on the page. The 2024 change in DGT's
  road-type coding shows up here, and the page says road type and zone must be read together.
- **Separation**: a level with no events in a fit is left out and listed rather than estimated.

The models describe association between recorded circumstances and outcome. They carry no
driver, vehicle, speed or impairment information, so they cannot attribute a death to a factor and
the page does not.

## 6. Vehicles per kilometre (`vehicles.py`)

A 2022 cross-section. The numerator is vehicles involved in fatal crashes, from the microdata
vehicle-type columns reconciled with table 2.3, and occupant deaths by vehicle from table 2.2 and
the yearbook series. The denominator is DGT's ITV estimate of the registered fleet and its mean
annual kilometres by vehicle type and age, which the methodology note derives from annualised
odometer readings at roadworthiness inspections and which is valid for aggregates only.

Six rate groups: motorcycles, mopeds, cars, vans with light trucks, heavy trucks, buses. Vans and
light trucks are one group because the crash record codes most light commercial vehicles as vans
while the register splits them, so only the sum means the same thing in numerator and denominator.
Heavy trucks include tractor units and articulated vehicles because the kilometre table's heavy
category is the sum of the note's "camiones de más de 3.500 kg" and "tractores industriales". Rates
are per billion vehicle-kilometres and per 100,000 registered vehicles, with Poisson intervals. The
seven kilometre-table types cover 91 % of the fleet; the rest has no denominator and no rate.

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
fits: 24-hour deaths; interurban and urban deaths separately; a log fleet offset (registered
vehicles interpolated between mid-years); a negative binomial whose dispersion is set by moments
from the Poisson fit (the likelihood search did not converge reliably when the data are close to
Poisson); and the window extended to December 2009 with a second break at the Penal Code reform.

**90 km/h limit on conventional roads, 29 January 2019**: monthly deaths by road group from the
microdata, conventional roads against motorways and dual carriageways, January 2016 to February
2020, a Poisson regression with month-of-year terms, a group term, a post term and the post ×
conventional interaction as the estimate, with Newey–West errors computed within each group. Two
placebo breaks (January 2017 and 2018) test whether the two groups were already diverging; the
extended fit through December 2024 adds lockdown (March–June 2020) and restriction (July 2020 to
December 2021) periods as their own terms. The January 2018 placebo is as large as the estimate, so
the page reports the numbers and draws no conclusion about the limit.

## 8. Speed factor (`speed.py`, `io_reports.py`)

Two aggregate sources, neither linkable to crashes. Tables 6.1 count drivers involved by recorded
infraction, 2014–2024, interurban and urban; the site shows the share of drivers with no speed
record beside the share with one, and gives the infraction share both over all drivers and among
those with a record, with Wilson intervals, because the unrecorded share changed from 17 % to 52 %
in 2016 and a single share would hide it. The DGT speed-factor report's 61 annex tables are
transcribed from the PDF text; every row carries the report's regional scope (Spain without
Cataluña and País Vasco, 28 % of injury crashes), and its figures are never added to yearbook
totals. Where the report's own unknown category dominates a breakdown (the speed limit in 2014),
the page compares shares among the known categories and says so. "Speed factor" throughout means
the police officer's recorded judgement of inappropriate speed, not a measurement.

## 9. Figures, pages and wording

Figures are matplotlib SVG with no date metadata, so a rebuild changes nothing unless a number
changes. One axis per chart, intervals drawn where they exist, direct labels where a legend would
be ambiguous, colour never the only encoding. Every sentence on a page that contains a number is
computed from the result tables at build time, including the digest on the front page, so the
prose cannot contradict the tables; conditional sentences (a rank, a placebo that passes or fails)
are gated on the same values. Tests check that every internal link and anchor resolves, every
image has alt text, every page has one heading, a description and no script.

## 10. Reproducibility

- Raw inputs immutable and manifested; interim and processed layers rebuilt from them by the
  command sequence in the README, which was run end to end from an empty interim layer and
  reproduced every committed table, figure and page byte for byte.
- All logic in `src/dgt_stats/` and `scripts/`; no notebooks. No random procedure is used: the
  fits are deterministic and need no seed.
- 140 tests, the reconciliation checks among them; `ruff` for lint and format.
- The Pages workflow renders the site from the committed tables and never rebuilds the data.

## 11. Limits that apply throughout

- Crash-level records only: no driver age, sex, alcohol, drug, speed, belt or helmet fields, so
  factor interactions and person-level risk are out of reach.
- Police-recorded circumstances, whose completeness varies by year (the missingness profile) and
  by severity.
- All model results are associations; the case studies are coincidences in time unless the checks
  above agree.
- Vehicle-kilometres exist for one year; the speed report excludes two regions; the 2024
  road-type coding differs from earlier years; two publications of the driver census by age differ
  by up to 1.1 %.
