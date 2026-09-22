# Methodology

How the numbers on the site are made, as built (September 2026). Every method below names the
module that implements it. What was cut from an earlier, larger version of this site, and why, is
in [`refocus_audit.md`](refocus_audit.md); what the published files can and cannot support is in
[`data_inventory.md`](data_inventory.md).

## 1. Units and sources

The public DGT crash microdata are one row per injury crash: 875,013 rows for 2016–2024, with the
place, time, road, conditions and victim counts by severity and road-user type. There are no
vehicle or person rows, so nothing here is estimated at the driver, vehicle or victim level; where
the site speaks of drivers it uses DGT's aggregate yearly tables, which count drivers by age, sex,
vehicle and recorded infraction but cannot be linked to crashes.

| Source | Unit | Years | Used for |
|---|---|---|---|
| crash microdata | injury crash | 2016–2024 | severity models, context |
| yearbook series | year, month or province totals | 1993–2024 | the 2006 case study, context, reference totals for reconciliation |
| yearly statistical tables | aggregate cells | 2014–2024 | vehicles involved by type, driver deaths and involvements by age and vehicle, drivers by recorded infraction |
| ITV kilometre estimates 2022 | fleet and mean km by vehicle type and age | 2022 | vehicle rates per km |
| ITV kilometre estimates 2024 | vehicles and km by category and owner age band | 2024 | the driving-exposure denominator |
| driver census | licence holders by province, sex, age | 2014–2025 | contrast denominators |
| INE population | residents by province, age, sex | 2002–2025 | contrast denominators |
| CORES fuel; toll-motorway traffic | month | 1996– / 1990– | exposure controls on the 2006 case study |

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

Two inputs are checked in their readers rather than in `validation.csv`, because DGT publishes no
separate total to check them against: the 2024 kilometres by owner age must reproduce the same
release's published fleet and kilometres by category to within 0.5 % (`io_exposure.py`, the margin
left by owners DGT could not classify), and the two monthly traffic series must be complete monthly
series with no gaps or duplicates (`io_traffic.py`). The INE population, the 2022 ITV tables, the
transcribed speed-factor report and the survey register are covered by unit tests that check their
internal totals.

Where two publications of the same quantity differ, one is kept for as long as it exists rather
than mixing them: licence holders by age come from the published class-by-age tables to 2023 and
the text files from 2024; 24-hour and 30-day deaths are never combined; provisional figures are not
used.

## 3. Definitions and derived fields (`derive.py`, `codes.py`)

- **Injury crash**: at least one person killed or injured. **Death**: within 30 days. **Serious
  crash**: at least one death or one person admitted to hospital for more than 24 hours.
- **Zone**: DGT's grouped zone, interurban road or urban street and crossing. **Road group**
  (`TIPO_VIA`, `derive.ROAD_GROUP_BY_TYPE`): motorway (codes 1, 2), dual carriageway (3, 5),
  conventional (4, 6), urban street (9), other (7, 8, 10–14). The 2006 case study groups the raw
  codes differently (section 7).
- **Time of day**: six bands, 00:00–06:59 the first. **Night** means the lighting was recorded as
  no natural light (`CONDICION_ILUMINACION` codes 4 to 6), not a clock hour. **Weekend**:
  Saturday, Sunday and Friday from 20:00.
- **Missing states**. Four are kept apart everywhere: not specified (999), not applicable (998), a
  field's explicit unknown code (six fields have one) and an empty cell. Each condition column has
  a `status_*` companion that names the state, and the data page profiles them by year. Fields that
  carry no code list use a placeholder instead of an empty cell — `KM` 9999 (and 1000 in 2019),
  `CARRETERA` "No inventariada", `COD_MUNICIPIO` 00000 — and the missingness profile counts those
  as not observed, so a year that swapped an empty cell for a placeholder does not read as an
  improvement in recording. Two undocumented quirks are handled as the data page states: code 0 in
  the island field from 2018, and the strong-wind flag in 2021.

## 4. Age and driving exposure (`driver_risk.py`, `agebands.py`)

The question is whether older drivers are riskier, and the answer depends on the divisor. The
denominator used is **kilometres driven**, from DGT's 2024 release *Kilómetros anualizados
recorridos por el parque móvil*, whose additional material gives vehicles, total annual kilometres
and mean annual kilometres **by vehicle category and by the age band of the registered owner**.

- **Numerator**: car drivers involved in injury crashes (table 4.2) and killed within 30 days
  (table 4.1.1), car rows only, both zones and both sexes, 2024 — the same year as the kilometres.
- **Denominator**: kilometres driven in 2024 by cars whose registered owner is in the band.
- **Bands** (`agebands.EXPOSURE_BANDS`): 18–34, 35–54 (the baseline), 55–64, 65–74, 75+. They nest
  both DGT's driver bands and the owner bands of the kilometre release exactly, so numerator and
  denominator are cut in the same places and **the baseline is built the same way as the older
  groups**. The 15–17 row exists only in the driver tables and is reported, never compared.
  Drivers of unrecorded age (about 5 % of those involved) are kept as their own row.

Three quantities, reported separately because they answer different questions:

1. `involved_per_bn_km` — how often a driver of this age is in an injury crash per kilometre
   driven. This is about crashing.
2. `deaths_per_1000_involved` — how often an involved driver of this age is killed. This needs no
   exposure at all, so the kilometre estimate cannot affect it.
3. `deaths_per_bn_km` — the product of the two.

Intervals are exact Poisson on the count with the kilometres treated as known; ratios to the
baseline carry log-normal intervals.

What the denominator is not: it is the **owner's** age, not the driver's, and cars registered to
companies carry no age at all (2.2 million cars, 40 billion km in 2024). Those kilometres leave the
denominator while their drivers stay in the numerator. `company_km_sensitivity` brackets the
effect: spreading them over every band cannot change a ratio between two bands, and spreading them
over the bands from 18 to 64 — the assumption that a company car is driven by someone of working
age — raises the 75-and-over ratio, so the published figure is the conservative end.

`denominator_contrast` puts the same deaths over residents, licence holders, drivers involved and
kilometres, as ratios to the 35–54 band, because the movement between them is the point. Residents
start at 35 because INE publishes five-year groups and no resident count can be cut at 18.

**Sources considered and not used**, with the reason (registered in
[`data_sources.md`](data_sources.md)): MOVILIA 2006/2007 count trips and travel time, not
kilometres, and do not separate drivers from passengers, and MOVILIA's top band is 65+; INE's EHMA
2008 gives mean annual kilometres per household vehicle by the reference person's age in four bands
stopping at 65+, sixteen years before the crash counts; ESRA gives a national driving share with no
age split. An earlier version of this site combined the last two into a "travel-weighted driver"
denominator; it is withdrawn, because it was not kilometres, it gave 65–74 and 75+ the same assumed
intensity, and it applied a 2006 travel profile to 2014–2024.

## 5. Severity models (`features.py`, `models.py`, `scripts/model.py`)

Two logistic regressions on all 875,013 crashes: the odds that a crash is fatal, and that it is
serious. Predictors are the circumstances the crash record carries: zone, road group, crash type,
junction, lighting, weather, surface, alignment, time of day, weekend, number of vehicles and year.
Each is an ordered categorical whose reference is its most common level. Missing states are
separate levels, as in section 3, never pooled with each other or with a recorded value. Three
exceptions, all named on the page: a level with fewer than 500 crashes merges into its reference;
the alignment "not applicable" code folds into "straight" because it is exactly the urban-street
zone and would otherwise duplicate the zone predictor; and a level with no event in a fit is left
out rather than estimated.

The fit is main effects only, by iteratively reweighted least squares in `numpy`, with a
cluster-robust sandwich covariance by province. It reports odds ratios with 95 % intervals, average
marginal effects, predicted probabilities for six named crash profiles, and three checks: a holdout
(fit on 2016–2022, scored on 2023–2024), year-by-year stability of the ten largest effects, and
separation.

### 5.1 The adverse-conditions sensitivity (`models.adverse_conditions`)

The finding the page leads with — rain, a wet road and junctions going with *lower* odds of a death
— is tested rather than asserted. Four levels (`ADVERSE_LEVELS`) are refitted under eight variants
(`ADVERSE_VARIANTS`):

- **Collinearity.** Weather and road surface describe overlapping states, so the full model can be
  splitting one effect between two columns. The variants drop surface, drop weather, drop both, and
  drop lighting. They show exactly that: on its own either predictor gives about 0.56, while the
  full model reports 0.86 for rain and 0.62 for wet. The page reports the single wet-conditions
  effect and says why.
- **Road context.** Three stratified fits (interurban roads, urban streets, conventional roads)
  hold the road context fixed by construction instead of adjusting for it, with the zone — and, in
  the two road-specific fits, the road predictor — dropped as constant. This is what shows that the
  hail-and-snow coefficient is not stable: it disappears on conventional roads alone.
- **Composition** (`level_composition`) reports where a level's crashes actually are, by province,
  zone and road type; `level_exclusions` refits with the level's most concentrated provinces
  removed. Hail and snow are concentrated but the coefficient survives the exclusions.

Both outcomes are run. The interpretation section on the page cites peer-reviewed research for the
mechanisms it proposes and states explicitly that the microdata cannot demonstrate any of them.

## 6. Vehicles per kilometre (`vehicles.py`)

A 2022 cross-section. The numerator is vehicles involved in injury crashes and in fatal crashes by
type, from yearbook table 2.3, and occupant deaths by vehicle from table 2.2. The denominator is
DGT's ITV estimate of the circulating fleet (its *parque circulante*) and its mean annual kilometres
by vehicle type and age, which is valid for aggregates only. Six rate groups: motorcycles, mopeds,
cars, vans with light trucks, heavy trucks, buses. Vans and light trucks are one group because the
crash record codes most light commercial vehicles as vans while the register splits them; heavy
trucks include tractor units because the kilometre table's heavy category is the union of the
methodology note's two heavy categories. Rates are per billion vehicle-kilometres and per 100,000
circulating vehicles, with exact Poisson intervals.

## 7. The 2006 case study (`policy.py`)

A segmented Poisson regression of the yearbook's monthly 30-day deaths on a pre-trend, eleven
month-of-year terms, a level change at July 2006 and a slope change after it, fitted from January
2000 to November 2007 (the month before the Penal Code reform), with Newey–West standard errors at
twelve lags.

**The pre-trend is chosen on the pre-intervention months alone** (`choose_trend_knot`). Every
candidate month that leaves 18 months on each side is tried as the single knot of a continuous
piecewise-linear trend fitted to the months before July 2006, with the same month terms and nothing
else; the straight line is in the comparison as the no-knot case and the lowest AIC wins. The
pre-2006 series prefers a knot in 2003 over a straight line by about 16 points of AIC, and that
choice, made without the post-period, moves the estimated level change from about −12 % to about
−7 %. The straight-line fit is kept as the first sensitivity row.

Four falsification tests, each aimed at a specific alternative explanation:

- **Calendar-matched placebos** (`calendar_placebo_fits`). Spanish road deaths peak every July and
  August, so moving the break to arbitrary months does not answer whether the summer of 2006 was
  unusual. The same model is refitted with the break at 1 July of every year whose window is clean
  — 60 months before, 17 after, never containing the true intervention or the pandemic — and the
  true break is refitted on the same shape. July 2006 ranks first of fifteen, but the runner-up is
  close, so the one-sided empirical p-value is about 0.07.
- **Seasonality-free transitions** (`seasonal_transitions`). For each year, the log change from
  June to July, July to August and August to September, and the log ratio of the twelve months from
  July to the twelve months before. The last statistic has the same twelve calendar months on each
  side, so seasonality cancels exactly and no model is involved. July 2006 is the fourth largest
  fall of the 27 years that can be measured; 2019–2021 are excluded from the ranking.
- **Out-of-sample forecasts** (`forecast_validation`). The 60 months before each July are fitted
  with a trend and month terms and *no* intervention term, and the next 17 months are forecast. The
  statistic is the log ratio of observed to predicted over that window, with a z score scaling it
  by the Poisson standard error inflated by the fit's own dispersion. Run at every admissible July,
  it puts 2006 fourth of fifteen: three other Julys undershot their own forecast by more. This is
  the test that most weakens the original headline, and the page says so.
- **Exposure** (`exposure_covariate`). Two monthly Spanish series reach back past 2006: CORES's
  national road-fuel consumption (petrol plus road diesel, tonnes, from 1996), which covers every
  road, and the Ministerio de Transportes' vehicle-kilometres on the state toll-motorway network
  (from 1990), a direct traffic measurement on a small and changing part of the network. Each is
  added as the centred log of the series — a free covariate rather than an offset, so the data say
  how much of the movement it explains. Neither moves the estimate materially, which rules out a
  traffic-volume explanation without pretending to measure exposure properly. Neither is
  vehicle-kilometres on all Spanish roads by month, which does not exist.

Other sensitivity fits: quadratic trend; a knot fixed at January 2004; 24-hour deaths; interurban
and urban deaths separately; a level change without the slope term; a registered-fleet offset; a
negative binomial whose dispersion is set by moments from the Poisson fit; and the window extended
to December 2009 with a second break at the Penal Code reform.

**The 2019 speed-limit study is not published.** Its design — conventional roads (raw codes 5 and
6) against motorways and dual carriageways (codes 1 to 3), month by month from the microdata — fails
its own falsification check: a break placed in January 2017 makes the two groups diverge by +12 %
with an interval that excludes zero, so a divergence at February 2019 cannot be told from the
ordinary divergence of the two series. Improving it would need road-section identifiers, section
limits, measured speeds and traffic volumes, none of which is published (see
[`data_sources.md`](data_sources.md), "Not available"). `speed_limit_fits` keeps the two tables that
record the negative result — the placebos and the sensitivity fits — and nothing else.

## 8. Speed status (`speed.py`, `io_reports.py`)

Tables 6.1 count drivers involved by recorded infraction, 2014–2024, interurban and urban. The
context page shows the share of drivers with no speed record beside the share with one, and gives
the infraction share both over all drivers and among those with a record, with Wilson intervals,
because the unrecorded share moved from 17 % to 52 % in 2016 and a single share would hide it. That
discontinuity is the point of the section; the two readings of the same table move in opposite
directions across it.

DGT's speed-factor report is transcribed by `io_reports.py` (61 of its 64 tables) and kept in the
interim layer for reproducibility. **None of it is published on the site**: republishing another
body's report is not analysis, and its territory (Spain without Cataluña and País Vasco, 28 % of
injury crashes) differs from every other source here, so its figures are never added to yearbook
totals.

## 9. Rates and intervals (`rates.py`)

Counts of deaths, crashes or involved drivers are treated as Poisson with a known denominator, and
every rate built against a counted denominator — residents, licence holders, drivers involved,
circulating vehicles, vehicle-kilometres — carries an exact 95 % (Garwood) interval. Ratios of two
such rates carry a log-normal interval. The speed-infraction share among drivers whose status is
known carries a Wilson interval. Shares taken entirely within one source's own counts (road-user
shares, the night shares, deaths per 100 crashes, occupant deaths per fatal involvement) are
population counts, not samples, and are reported without intervals.

## 10. Figures, pages and wording

Eleven figures, matplotlib SVG with no date metadata, so a rebuild in the same environment
(`requirements.lock`) changes nothing unless a number changes. One axis per chart, intervals drawn
where they exist, direct labels where a legend would be ambiguous, colour never the only encoding.
`figures.build_all` deletes any SVG in its output directory that no longer has a caption, so a
removed figure cannot linger.

Every sentence on a page that contains a number is computed from the result tables at build time,
including the front-page digest, so the prose cannot contradict the tables. Full result tables are
copied into `site/tables/` and linked as CSV rather than printed: the default on a page is one
figure, one interpretation and one limits note per finding. Tests check that every internal link
and anchor resolves, every image has alt text, every page has one heading, a description and no
script, and that each page's headline numbers match the tables they come from.

## 11. Reproducibility

- Raw inputs immutable and manifested; interim and processed layers rebuilt from them by the
  command sequence in the README, with Python 3.11 and the library versions in `requirements.lock`
  (pandas 3.0.6, numpy 2.4.6, scipy 1.17.1, statsmodels 0.15.0, matplotlib 3.11.2, scikit-learn
  1.9.1, pyarrow 25.0.1). The lock file is compiled from `pyproject.toml` with
  `uv pip compile --extra dev --generate-hashes`. At the dependency floors in `pyproject.toml` the
  numbers agree to the precision printed on the pages, but every figure differs, because matplotlib
  writes its own version into the SVG and the tight-bbox geometry changes with it. Descriptive
  result tables are written with ten significant digits and the severity-model tables with six, so
  last-bit differences between library versions do not reach the committed files.
- All logic in `src/dgt_stats/` and `scripts/`; no notebooks. No random procedure is used: the fits
  are deterministic and need no seed.
- `pytest` runs the data-contract, reconciliation and analysis tests; the SHA-256 check of every
  raw file against `data/raw/manifest.csv` is marked slow and run with `pytest -m slow`. `ruff`
  for lint and format.
- The Pages workflow renders the site from the committed tables and never rebuilds the data.

## 12. Limits that apply throughout

- Crash-level records only: no driver age, sex, alcohol, drug, speed, belt or helmet fields, so
  factor interactions and person-level risk are out of reach.
- Police-recorded circumstances, whose completeness varies by year and by severity.
- All model results are associations; the 2006 case study is a coincidence in time unless its
  falsification tests agree, and they only partly do.
- Vehicle-kilometres by type exist for one year; kilometres by age are the owner's age; the speed
  report excludes two regions; road-type coding changed in 2021 (interurban) and 2024 (urban), and
  the junction field changed in 2023.
