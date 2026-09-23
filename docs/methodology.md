# Methodology

How the numbers on the site are made, as built (September 2026). The site answers one question,
what changes when road risk is measured rather than counted, through six pillars set out in
[`goal_alignment_audit.md`](goal_alignment_audit.md); every method below names the module that
implements it. What was cut from an earlier, larger version of this site is in
[`refocus_audit.md`](refocus_audit.md); what the published files can and cannot support is in
[`data_inventory.md`](data_inventory.md).

## 1. Units and sources

The public DGT crash microdata are one row per injury crash: 875,013 rows for 2016–2024, with the
place, time, road, conditions and victim counts by severity and road-user type. There are no
vehicle or person rows, so nothing here is estimated at the driver, vehicle or victim level; where
the site speaks of drivers it uses DGT's aggregate yearly tables, which count drivers by age, sex,
vehicle and recorded infraction but cannot be linked to crashes.

| Source | Unit | Years | Used for |
|---|---|---|---|
| crash microdata | injury crash | 2016–2024 | scoped totals for the speed comparison, the severity models, darkness shares |
| yearbook series | year, month or province totals | 1993–2024 | 2019–2024 risk, the long run, seasonality, the 2006 case study, reference totals |
| yearly statistical tables | aggregate cells | 2014–2024 | vehicles involved by type, driver deaths and involvements by age and vehicle, drivers by recorded infraction |
| ITV kilometre estimates 2022 | fleet and mean km by vehicle type and age | 2022 | vehicle rates per km |
| ITV kilometre estimates 2024 | vehicles and km by category and owner age band | 2024 | the driving-exposure denominator |
| driver census | licence holders by province, sex, age | 2014–2025 | risk per licence holder, sex rates, contrast denominators |
| INE population | residents by province, age, sex | 2002–2025 | risk per resident, contrast denominators |
| CORES fuel; toll-motorway traffic | month | 1996– / 1990– | the traffic denominators of the risk, long-run and seasonality analyses; exposure controls on the 2006 case study |
| DGT speed-factor report | year, factor, road type | 2014–2023 | speed as a severity factor; the other recorded factors |
| MOVILIA 2006 | trips by mode, sex and age | 2006 | the travel bracket for the sex comparison |

Raw files are never edited (`data/raw/`, listed in `manifest.csv` with SHA-256 and source URL).
`ingest.py` parses them into typed Parquet tables (`data/interim/`), `build_tables.py` adds the
derived fields (`data/processed/`), and every result table and figure is written by `model.py` and
`analyse.py` from those layers. The site reads only the committed result tables.

## 2. Reconciliation before analysis

No summary is published until the crash microdata, the yearbook tables and the driver census
reconcile with DGT's own totals (`validate.py`, 482 checks, all enforced by
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
| speed_report_scope | the speed report's own crashes and deaths by year and zone against the microdata restricted to its provinces, 2016–2023 | exact |

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
  conventional (4, 6), urban street (9), other (7, 8, 10–14). The speed comparison (section 9)
  and the 2019 speed-limit study (section 12) group the raw codes differently.
- **Time of day**: six bands, 00:00–06:59 the first. **Night** means the lighting was recorded as
  no natural light (`CONDICION_ILUMINACION` codes 4 to 6), not a clock hour. **Weekend**:
  Saturday, Sunday and Friday from 20:00.
- **Missing states**. Four are kept apart everywhere: not specified (999), not applicable (998), a
  field's explicit unknown code (six fields have one) and an empty cell. Each condition column has
  a `status_*` companion that names the state, and the data page profiles them by year. Fields that
  carry no code list use a placeholder instead of an empty cell (`KM` 9999, and 1000 in 2019;
  `CARRETERA` "No inventariada"; `COD_MUNICIPIO` 00000), and the missingness profile counts those
  as not observed, so a year that swapped an empty cell for a placeholder does not read as an
  improvement in recording. Two undocumented quirks are handled as the data page states: code 0 in
  the island field from 2018, and the strong-wind flag in 2021.

## 4. Counts against risk, 2019–2024 (`risk_trends.py`)

Each annual outcome, injury crashes, 30-day deaths and injured admitted to hospital, is divided by
four denominators and indexed to 2019 (`risk_index`):

| Denominator | Source | Years | What it counts |
|---|---|---|---|
| residents | INE resident population on 1 July | 2002– | everyone, most of whom are not driving |
| licence holders | DGT driver census, end of year | 2014– | everyone allowed to drive |
| registered vehicles | DGT fleet in the yearbook rate table | 1993– | every registered vehicle, used or not |
| road fuel | CORES automotive petrol plus diesel, complete years | 1996– | the closest annual measure of traffic |

The ratio of each year's rate to the 2019 rate carries a log-normal interval that treats both counts
as Poisson and the denominators as known; for the count itself the ratio is the change in the count.
The intervals therefore describe the chance variation of a single year's counts and nothing else.

Road fuel is a proxy for vehicle-kilometres, not a count of them, and it drifts in a known
direction: a fleet that burns less per kilometre, and electric kilometres that burn none, drive
further per tonne. `fuel_efficiency_sensitivity` grosses fuel up by 1 % and 2 % a year from 2019 to
bound that. DGT's two published kilometre estimates (2022, from ITV odometer readings; 2024, an
annualised estimate) are compared with fuel in `km_crosscheck` and are not chained into a trend:
they are built differently, and between the two years they move −1.6 % while fuel moves +1.5 %.

## 5. The long run and the pandemic (`risk_trends.py`)

A segmented log-linear (joinpoint) trend is fitted to the yearbook's 30-day deaths, 1993–2019, in
three forms: the count, the count with the log registered fleet as offset, and the count with the
log road fuel as offset (from 1996). The model is a Poisson GLM with quasi-likelihood (Pearson)
dispersion, continuous at its turning points. For 0 to 3 turning points every admissible
placement (segments at least four years long) is fitted and the lowest-deviance one kept; the
number of turning points is chosen by QBIC, the Poisson BIC divided by the dispersion of the
largest model with each turning point costing two parameters, taking the simplest model within two
points of the minimum (`joinpoint_search`). The segment slopes are reported as annual percentage
changes with intervals from the scaled covariance (`segment_changes`). All three measures choose two
turning points, within two years of each other: about 2003 and 2011–2013.

The last segment is projected through 2020–2024 (`project`) with a 95 % prediction interval that
combines the uncertainty of the fitted line (delta method on the linear predictor) with
overdispersed noise around it. For the per-vehicle and per-fuel forms the projection is multiplied
back by each year's fleet or fuel, so all three are in deaths and `observed / expected` reads the
same way. The per-fuel trend already carries the fuel-economy gains of 1996–2019, so its projection
assumes they continued at that pace; `long_run_efficiency_sensitivity` asks what an extra 1 % or
2 % a year from 2020 would do.

The question this answers is the one the pillar asks: whether 2020–2024 is a distortion or a change
of trend. As a count, 2020 is far below trend and 2022–2024 are back on it. Per tonne of fuel, 2020
and 2021 are on trend (the fall in deaths was the fall in traffic) and 2023–2024 are above it,
beyond the interval unless fuel economy improved about two points a year faster than before.

## 6. Seasonality and mobility (`seasonality.py`)

Monthly 30-day deaths from the yearbook series are set against three monthly traffic series, each
wrong in a known direction: road fuel (petrol plus diesel, CORES), which includes freight that
slows in August and kept moving in the lockdown; petrol alone, burnt mostly by private cars and
motorcycles; and toll-motorway intensity (average daily vehicles per kilometre of the state toll
network), measured traffic on long-distance holiday routes. Intensity is used rather than
vehicle-kilometres because the network shrank from about 2,500 to 1,400 km as concessions expired
in 2018–2021.

The seasonal profile (`seasonal_profile`) divides each month by the mean month of its own year and
averages over 2014–2019 and 2022–2024, leaving out the pandemic years. The month effects
(`month_effects`) come from quasi-Poisson models of monthly deaths with year effects and
sum-to-zero month effects, with no exposure and with the log of each traffic series as an offset;
with an offset the month effect is deaths per unit of that traffic against the average month. A
synthetic test checks that an offset exactly proportional to the outcome removes all seasonality.
The lockdown comparison (`lockdown_months`) sets each month of 2020 against the same month's
2017–2019 mean for deaths and for each traffic series.

## 7. Age and driving exposure (`driver_risk.py`, `agebands.py`)

The question is whether older drivers are riskier, and the answer depends on the divisor. The
denominator used is **kilometres driven**, from DGT's 2024 release *Kilómetros anualizados
recorridos por el parque móvil*, whose additional material gives vehicles, total annual kilometres
and mean annual kilometres **by vehicle category and by the age band of the registered owner**.

- **Numerator**: car drivers involved in injury crashes (table 4.2) and killed within 30 days
  (table 4.1.1), car rows only, both zones and both sexes, 2024, the same year as the kilometres.
- **Denominator**: kilometres driven in 2024 by cars whose registered owner is in the band.
- **Bands** (`agebands.EXPOSURE_BANDS`): 18–34, 35–54 (the baseline), 55–64, 65–74, 75+. They nest
  both DGT's driver bands and the owner bands of the kilometre release exactly, so numerator and
  denominator are cut in the same places and **the baseline is built the same way as the older
  groups**. The 15–17 row exists only in the driver tables and is reported, never compared.
  Drivers of unrecorded age (about 5 % of those involved) are kept as their own row.

Three quantities, reported separately because they answer different questions:

1. `involved_per_bn_km`: how often a driver of this age is in an injury crash per kilometre
   driven. This is about crashing.
2. `deaths_per_1000_involved`: how often an involved driver of this age is killed. This needs no
   exposure at all, so the kilometre estimate cannot affect it.
3. `deaths_per_bn_km`: the product of the two.

Intervals are exact Poisson on the count with the kilometres treated as known; ratios to the
baseline carry log-normal intervals.

What the denominator is not: it is the **owner's** age, not the driver's, and cars registered to
companies carry no age at all (2.2 million cars, 40 billion km in 2024). Those kilometres leave the
denominator while their drivers stay in the numerator. `company_km_sensitivity` brackets the
effect: spreading them over every band cannot change a ratio between two bands, and spreading them
over the bands from 18 to 64, on the assumption that a company car is driven by someone of
working age, raises the 75-and-over ratio, so the published figure is the conservative end.

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

### 7.1 Sex (`driver_risk.py`)

Drivers involved (table 4.2) and killed within 30 days (table 4.1.1), by sex and age band, are
divided by licence-holder-years from the driver census, pooling 2022–2024 so that the rates for
women over 65 (a few deaths a year) are readable (`sex_age_rates`). Two scopes: car drivers, and
drivers of all motor vehicles, which leaves out cyclists and personal-mobility-vehicle riders, who
need no licence, and rows of unknown vehicle. Three rates: involvement per 1,000 licence holders,
deaths per million licence holders and deaths per 1,000 involved; the second is the product of the
other two, and a test holds that identity. `sex_ratios` gives men against women on each, with
log-normal intervals.

No Spanish source measures kilometres by sex. `sex_travel_bracket` sets the male-to-female ratio of
car-or-motorcycle trips per resident in MOVILIA 2006 (weekday × 5 + weekend day × 2, INE 2006
residents) beside the ratio of car-driver involvement and deaths per resident in 2022–2024, by
MOVILIA's age bands. MOVILIA counts passengers with drivers and is from 2006, so its ratio
understates the driving gap and is used only to say whether the involvement gap is of the size a
travel gap could produce. The fatality ratio once involved needs no travel data at all.

## 8. Vehicles per kilometre (`vehicles.py`)

A 2022 cross-section. The numerator is vehicles involved in injury crashes and in fatal crashes by
type, from yearbook table 2.3, and occupant deaths by vehicle from table 2.2. The denominator is
DGT's ITV estimate of the circulating fleet (its *parque circulante*) and its mean annual kilometres
by vehicle type and age, which is valid for aggregates only. Six rate groups: motorcycles, mopeds,
cars, vans with light trucks, heavy trucks, buses. Vans and light trucks are one group because the
crash record codes most light commercial vehicles as vans while the register splits them; heavy
trucks include tractor units because the kilometre table's heavy category is the union of the
methodology note's two heavy categories. Rates are per billion vehicle-kilometres and per 100,000
circulating vehicles, with exact Poisson intervals.

## 9. Speed as a severity factor and speed status (`factors.py`, `speed.py`, `io_reports.py`)

**Speed as a severity factor** (`factors.speed_severity`). The report gives injury crashes and
deaths with inappropriate speed recorded, by year and by road type (motorways, dual carriageways,
other interurban roads, urban streets). Deaths per 100 such crashes are set against deaths per 100
of the remaining injury crashes of the same scope, year and road type. The totals by zone come from
the report; the totals by interurban road type, which the report does not publish, come from the
microdata restricted to the report's provinces, which reproduce the report's zone totals exactly
(`speed_report_scope`). The road types map from the microdata's zone and road-type code (motorways
1–2, dual carriageways 3, every other interurban code to the rest); the mapping reproduces the
report's interurban total. Rate ratios carry log-normal intervals; `speed_severity_pooled` pools
2016–2023 by road type and fits a quasi-Poisson model of deaths with the log of crashes as offset
and road type and year as factors, whose speed coefficient is the ratio on the same kind of road.
The crude ratio is reported beside it. The ratio is an association subject to two biases the data
cannot measure: differential recording (speed is more likely to be found in a fatal crash, which
inflates it) and unrecorded speed in the comparison group (which deflates it).

**Speed status in the driver tables.** Tables 6.1 count drivers involved by recorded infraction,
2014–2024, interurban and urban. The speed page shows the share of drivers with no speed record beside the share with one, and gives
the infraction share both over all drivers and among those with a record, with Wilson intervals,
because the unrecorded share moved from 17 % to 52 % in 2016 and a single share would hide it. That
discontinuity is the point of the section; the two readings of the same table move in opposite
directions across it.

DGT's speed-factor report is transcribed by `io_reports.py` (61 of its 64 tables) and kept in the
interim layer. Two of its tables are inputs to analyses (speed-related crashes and deaths by road
type; crashes by concurrent factor); **none of its breakdowns is republished on the site**, and its
territory (Spain without Cataluña and País Vasco) differs from every other source here, so its
figures are never added to yearbook totals.

## 10. Other recorded factors (`factors.py`)

DGT's speed-factor report gives, for 2014–2023 and Spain without Cataluña and País Vasco, the injury
crashes with each of five police-recorded concurrent factors (distraction, inappropriate speed,
illegal manoeuvres, alcohol, drugs) by zone. Each factor's share of the zone's injury crashes (the
report's own totals) is computed by year (`factor_shares`), and every year-to-year change is tested
(`factor_consistency`): a change in share beyond a ratio of 1.25 either way in a single year is
flagged as a recording break, because no change in behaviour moves a share by a quarter in one year
across 20,000–50,000 crashes; a change where either year has fewer than 200 crashes cannot be tested
and is treated as a break too. `comparable_windows` lists the runs of years between breaks, and the
page reads trends only within them. The threshold is a rule, not a test with a known error rate;
every change is published so another threshold can be applied. A synthetic test checks that the
rule splits runs at a jump and at an untestable change.

The rule finds the breaks the report's own tables show on inspection: urban distraction in 2016
and 2019, urban alcohol in 2016, and drugs throughout. Interurban alcohol, inappropriate speed in
both zones and interurban distraction run unbroken across the decade.

## 11. Supporting analysis: severity models (`features.py`, `models.py`, `scripts/model.py`)

Kept outside the main navigation: a multivariate model of crash outcomes is not what these data are best at, since they carry no driver, vehicle or speed records. It shows which recorded circumstances go with a fatal outcome, given a crash.

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

### 11.1 The adverse-conditions sensitivity (`models.adverse_conditions`)

The finding the page leads with, that rain, a wet road and junctions go with *lower* odds of a
death, is tested rather than asserted. Four levels (`ADVERSE_LEVELS`) are refitted under eight variants
(`ADVERSE_VARIANTS`):

- **Collinearity.** Weather and road surface describe overlapping states, so the full model can be
  splitting one effect between two columns. The variants drop surface, drop weather, drop both, and
  drop lighting. They show exactly that: on its own either predictor gives about 0.56, while the
  full model reports 0.86 for rain and 0.62 for wet. The page reports the single wet-conditions
  effect and says why.
- **Road context.** Three stratified fits (interurban roads, urban streets, conventional roads)
  hold the road context fixed by construction instead of adjusting for it, with the zone dropped as constant, and
  the road predictor too in the two road-specific fits. This is what shows that the
  hail-and-snow coefficient is not stable: it disappears on conventional roads alone.
- **Composition** (`level_composition`) reports where a level's crashes actually are, by province,
  zone and road type; `level_exclusions` refits with the level's most concentrated provinces
  removed. Hail and snow are concentrated but the coefficient survives the exclusions.

Both outcomes are run. The interpretation section on the page cites peer-reviewed research for the
mechanisms it proposes and states explicitly that the microdata cannot demonstrate any of them.

## 12. Supporting analysis: the 2006 case study (`policy.py`)

Kept outside the main navigation: the site makes no causal claim about policies or campaigns, and this analysis shows how weak even a dated policy break is as evidence.

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
  unusual. The same model is refitted with the break at 1 July of every year whose window is clean:
  60 months before, 17 after, never containing the true intervention or the pandemic. The true
  break is refitted on the same shape. July 2006 ranks first of fifteen, but the runner-up is
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
  added as the centred log of the series, as a free covariate rather than an offset, so the data
  say how much of the movement it explains. Neither moves the estimate materially, which rules out a
  traffic-volume explanation without pretending to measure exposure properly. Neither is
  vehicle-kilometres on all Spanish roads by month, which does not exist.

Other sensitivity fits: quadratic trend; a knot fixed at January 2004; 24-hour deaths; interurban
and urban deaths separately; a level change without the slope term; a registered-fleet offset; a
negative binomial whose dispersion is set by moments from the Poisson fit; and the window extended
to December 2009 with a second break at the Penal Code reform.

**The 2019 speed-limit study is not published.** Its design, conventional roads (raw codes 5 and 6)
against motorways and dual carriageways (codes 1 to 3), month by month from the microdata, fails
its own falsification check: a break placed in January 2017 makes the two groups diverge by +12 %
with an interval that excludes zero, so a divergence at February 2019 cannot be told from the
ordinary divergence of the two series. Improving it would need road-section identifiers, section
limits, measured speeds and traffic volumes, none of which is published (see
[`data_sources.md`](data_sources.md), "Not available"). `speed_limit_fits` keeps the two tables that
record the negative result, the placebos and the sensitivity fits, and nothing else.

## 13. Rates and intervals (`rates.py`)

Counts of deaths, crashes or involved drivers are treated as Poisson with a known denominator, and
every rate built against a counted denominator (residents, licence holders, drivers involved,
circulating vehicles, vehicle-kilometres) carries an exact 95 % (Garwood) interval. Ratios of two
such rates carry a log-normal interval. The speed-infraction share among drivers whose status is
known carries a Wilson interval. Shares taken entirely within one source's own counts (road-user
shares, the night shares, deaths per 100 crashes, occupant deaths per fatal involvement) are
population counts, not samples, and are reported without intervals.

## 14. Figures, pages and wording

Eighteen figures, matplotlib SVG with no date metadata, so a rebuild in the same environment
(`requirements.lock`) changes nothing unless a number changes. One axis per chart, intervals drawn
where they exist, direct labels where a legend would be ambiguous, colour never the only encoding.
`figures.build_all` deletes any SVG in its output directory that no longer has a caption, so a
removed figure cannot linger.

The main navigation carries the overview, the seven analysis pages (2019–2024, the long run,
seasons, age and sex, vehicles, speed, other factors) and the data page; the severity model and the
2006 case study sit in a second row labelled as supporting analyses, each opening with a note that
says why it is outside the central question. Pages renamed in the reorganisation
(`older-drivers.html`, `context.html`) are kept as pointers that refresh to their successors.

Every sentence on a page that contains a number is computed from the result tables at build time,
including the front-page digest, so the prose cannot contradict the tables. Full result tables are
copied into `site/tables/` and linked as CSV rather than printed: the default on a page is one
figure, one interpretation and one limits note per finding. Tests check that every internal link
and anchor resolves, every image has alt text, every page has one heading, a description and no
script, and that each page's headline numbers match the tables they come from.

## 15. Reproducibility

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

## 16. Limits that apply throughout

- Crash-level records only: no driver age, sex, alcohol, drug, speed, belt or helmet fields, so
  factor interactions and person-level risk are out of reach.
- Police-recorded circumstances, whose completeness varies by year and by severity.
- All model results are associations; the 2006 case study is a coincidence in time unless its
  falsification tests agree, and they only partly do.
- Vehicle-kilometres by type exist for one year; kilometres by age are the owner's age; the speed
  report excludes two regions; road-type coding changed in 2021 (interurban) and 2024 (urban), and
  the junction field changed in 2023.
