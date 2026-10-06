# Methodology

How the numbers on the site are made, as built (October 2026). The site answers one question,
what changes when road risk is measured rather than counted, through six pillars set out in
[`goal_alignment_audit.md`](goal_alignment_audit.md), and then asks what a speed law would do
(sections 11 and 12); every method below names the module that implements it. What was cut from an earlier, larger version of this site is in
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
| crash microdata | injury crash | 2016–2024 | scoped totals for the speed comparison, the severity models, darkness shares, the simulator's baseline and risk per km by road class |
| yearbook series | year, month or province totals | 1993–2024 | 2019–2024 risk, the long run, seasonality, the monthly deaths of the forecasting model, the 2006 case study, reference totals |
| yearly statistical tables | aggregate cells | 2014–2024 | vehicles involved by type, driver deaths and involvements by age and vehicle, drivers by recorded infraction |
| ITV kilometre estimates 2022 | fleet and mean km by vehicle type and age | 2022 | vehicle rates per km |
| ITV kilometre estimates 2024 | vehicles and km by category and owner age band | 2024 | the driving-exposure denominator |
| driver census | licence holders by province, sex, age | 2014–2025 | risk per licence holder, sex rates, contrast denominators |
| INE population | residents by province, age, sex | 2002–2025 | risk per resident, contrast denominators |
| CORES fuel; toll-motorway traffic | month | 1996– / 1990– | the traffic denominators of the risk, long-run and seasonality analyses; exposure controls on the 2006 case study; the traffic input of the forecasting model; the biofuel share of road fuel |
| Ministerio de Transportes, yearbook table 1.2.14 | year, road type | 2004–2023 | measured interurban vehicle-km and the share of heavy vehicles: the check on road fuel, risk per km by road class, light vehicles' travel time in the simulator |
| simulator evidence register | published value | various | Power Model exponents, the response of speed to a limit change, car speeds measured in Spain in 2022, legal limits, DGT's values of a casualty |
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

Three inputs are checked in their readers rather than in `validation.csv`, because no separate
publication gives a total to check them against. The 2024 kilometres by owner age must reproduce
the same release's published fleet and kilometres by category to within 0.5 % (`io_exposure.py`,
the margin left by owners DGT could not classify). The two monthly traffic series must be complete
monthly series with no gaps or duplicates, and each CORES automotive subtotal must equal the sum of
its product columns (bioethanol, biodiesel and blends included) to one part in a million in every
month (`io_traffic.py`). The Ministry's annual kilometres by road type (table 1.2.14) must add up
to the published total within one part in ten thousand and have no missing years (`io_traffic.py`;
the tolerance is wider than the table's rounding because the published 2009 row is itself 5
million vehicle-km short). The INE population, the 2022 ITV tables, the transcribed speed-factor
report and the survey register are covered by unit tests that check their internal totals.

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
  and the 2019 speed-limit study (section 15) group the raw codes differently; the simulator's road
  classes (section 12) group them by zone first.
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

**An ordinary year, not only chance** (`year_to_year_dispersion`). A Poisson interval assumes a
year's count varies only by chance. Spain's annual counts scatter more than that around their own
trend: fitted log-linearly over the 2013–2019 plateau, the Pearson dispersion is about 1.5 for
deaths, 8 for hospital admissions and 68 for injury crashes, whose count depends on how
completely slight injuries are recorded. The dispersion is a ratio of variances (floored at 1):
the variance of crashes around their trend is about 68 times that of a Poisson count of the same
size, so their spread is about √68 ≈ 8 times the Poisson spread. The page reads every change against the interval widened by the
square root of that ratio (`ratio_low_yty`, `ratio_high_yty`), so a change outside it is larger
than an ordinary year. This changed several readings. Under a Poisson interval the 2024 falls in
crashes against 2019, as a count and per resident, licence holder and vehicle, all look certain;
against an ordinary year all are within it except the fall per registered vehicle (−6.9 %, −13.3 %
to −0.03 %), which is just beyond it, as it was in 2022 and 2023. The 2024 rise in hospital
admissions stays beyond an ordinary year as a count (+11.0 %) and per tonne of road fuel
(+13.0 %), and is within it per resident, per licence holder and per vehicle. Deaths in 2024 are
within an ordinary year of 2019 as a count and under all four denominators.

**How often against how hard** (`frequency_severity`). Deaths per tonne of road fuel is the exact
product of injury crashes per tonne and deaths per injury crash; the three are indexed to 1996, the
first year of the fuel series. Over 1996–2024 the first fell 76 %, the second 13 % and the third
73 %. The split depends on how completely slight-injury crashes are recorded, which moves the two
factors in opposite directions without moving their product; deaths are counted completely.

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
dispersion, continuous at its turning points; the dispersion is floored at 1, so a series that
happens to scatter less than Poisson chance in a dozen points does not get an interval narrower
than Poisson noise would give (`_fit`). For 0 to 3 turning points every admissible placement
(segments at least four years long) is fitted and the lowest-deviance one kept; the number of
turning points is chosen by QBIC, the Poisson BIC divided by the dispersion of the largest model
with each turning point costing two parameters, taking the simplest model within two points of the
minimum (`joinpoint_search`). The segment slopes are reported as annual percentage
changes with intervals from the scaled covariance (`segment_changes`). All three measures choose two
turning points, within two years of each other: about 2003 and 2011–2013.

The last segment is projected through 2020–2024 (`project`) with a 95 % prediction interval that
combines the uncertainty of the fitted line (delta method on the linear predictor) with
overdispersed noise around it. For the per-vehicle and per-fuel forms the projection is multiplied
back by each year's fleet or fuel, so all three are in deaths and `observed / expected` reads the
same way. The per-fuel trend's last segment runs from 2011, so its projection carries the growth in
kilometres per tonne of 2011–2019 and assumes it went on at that pace;
`long_run_efficiency_sensitivity` asks what an extra 1 % or 2 % a year from 2020 would do.

The question this answers is the one the pillar asks: whether 2020–2024 is a distortion or a change
of trend. As a count, 2020 is far below trend and 2022–2024 are back on it. Per tonne of fuel, 2020
and 2021 are on trend (the fall in deaths was the fall in traffic) and 2023–2024 are above it,
beyond the interval unless kilometres per tonne grew faster than before from 2020: about 1.4 points
a year faster for 2023 to fall inside it, and 0.7 points for 2024.

**Re-run on measured kilometres** (`interurban_km_panel`, `km_trend_check`). The Ministerio de
Transportes' yearbook table 1.2.14 gives the vehicle-kilometres measured each year on the whole
interurban network of the State, the regions and the provincial councils, by type of road, from
2004 (`io_traffic.read_road_traffic`; the four road types must add up to the published total, and
the series is comparable from 2008, when the road inventory was redone). Kilometres on that network
per tonne of all road fuel grew 0.5 % a year over 2011–2019, the span of the national per-fuel
trend's last segment, and 1.9 % a year over 2019–2023: about 1.4 points a year faster, just enough
for the 2023 per-fuel excess to fall inside the interval (the condition named above). The ratio is
kilometres per tonne, not fuel economy: it also moves when traffic shifts between towns and
interurban roads, and with the mix of freight. Biofuel does not explain the rise
(`fuel_bio_share`, `longrun_fuel_bio.csv`): CORES publishes the mass share of biofuel blended into
each subtotal, and it was 6.6 % of road fuel by mass in 2019 and 7.8 % in 2023 (7.1 % in 2024).
Biofuel carries less energy per tonne than the petrol and diesel it replaces, so a point more of it
lowers kilometres per tonne slightly. The same joinpoint search is fitted to interurban deaths over
2008–2019, once with the log of measured kilometres and once with the log of fuel as offset; both
choose a turning point in 2013 and a decline of 1.8 % a year after it. Projected on, 2023 is 13 %
above the per-fuel trend, outside the interval, and 5 % above the per-kilometre trend, inside it;
2022 per tonne of fuel is just inside its interval, and 2020 lies exactly on the per-kilometre
trend. Per kilometre, every year from 2020 to 2023 is inside the interval of the 2013–2019 decline
continued. The long-run finding is therefore stated with that limit: the counts cannot yet tell
whether the decline carried on or stalled, but they rule out a jump in risk. The kilometres leave
out municipal interurban roads (up to a tenth of traffic, the Ministry estimates) and urban
streets, and end in 2023.

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

**Owner's age against driver's age** (`owner_age_check`). Drivers aged 18–34 hold 0.45 cars per
licence and are credited with about 6,200 km per licence holder, against 0.79 cars and 10,200 km at
35–54: part of the young's driving is registered to older owners, most plausibly in the baseline
band. That inflates the baseline's kilometres and so every ratio to it. In the extreme case,
kilometres are moved from the baseline to the 18–34 band until the two drive the same distance per
licence holder: a transfer of 15.24 billion km, which leaves both bands at 8,899 km per licence
holder. The 75-and-over involvement ratio then falls from 1.02 to 0.89; the fatality ratio once
involved needs no kilometres and does not move. The conclusion, that older drivers crash about as
often for their driving and die far more often once they do, holds.

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

## 11. Predicting deaths, and what a before-and-after comparison can see (`forecast.py`)

A law is judged by comparing the deaths after it with the deaths that would have happened without
it, and the second number is a forecast whose error decides what the comparison can see.

**The model.** A Poisson regression of monthly 30-day deaths (the yearbook series) fitted on the
four years before the year it predicts: month of year, a linear trend, the log of the month's road
fuel (CORES petrol plus diesel) with a free coefficient, and the counts of Fridays, Saturdays and
Sundays in the month. Traffic and calendar are known once the month is over, so the forecast is
what the month's traffic and calendar would have produced on the recent trend. Easter is left out:
in a four-year window it often falls in the same month every year and cannot then be told from
that month's effect.

**How it was chosen.** Four specifications (trend; trend and calendar; trend and traffic; trend,
traffic and calendar) at windows of three to eight years were compared by rolling-origin forecasts
of annual totals: fit on the years before a year, predict its twelve months, move on. The choice
was made on the forecast years 2006–2015 alone (`SELECTION_YEARS`); 2016–2019 and 2022–2024
(`HOLDOUT_YEARS`) and the lockdown years 2020–2021 are scored separately and played no part in it.
Two naive forecasts (the same months last year; the mean of the last three years) and
gradient-boosted trees with the same inputs (scikit-learn, Poisson loss) are scored beside it. The
trees are tuned the same way: their minimum leaf size, the one setting that matters on 48 monthly
rows, is chosen on the selection years from 1, 2, 3, 5, 8, 12 and 20 (`TREE_LEAF_CANDIDATES`), and
the choice is 1; the library's default of 20 leaves room for only one split in 48 rows.
`forecast_selection.csv` marks each method's family (model, trees or naive) and the chosen model
and trees.

**What it found.** The error of the annual total of all deaths (root mean square of the log
ratio), by set of years:

| Forecast | Selection, 2006–2015 | Held back, 2016–2019 and 2022–2024 | Lockdown, 2020–2021 |
|---|---|---|---|
| the model | 4.9 % | 6.6 % | 7.3 % |
| last year's count | 11.7 % | 5.9 % | 19.2 % |
| the tuned trees | 7.5 % | 8.4 % | 16.9 % |

In the flat held-back years the model does slightly worse than repeating last year (6.6 % against
5.9 %); it earns its place when the trend or the traffic moves, which is when a law's effect has to
be told apart from them. Its worst held-back year is 2022, forecast from a window that contains the
lockdowns. The tuned trees do worse than the model on every kind of road (all roads, interurban
roads, urban streets) and in every set of years: a tree cannot extend a trend beyond the years it
has seen, and with 48 rows a small leaf fits the noise. Trees whose leaves hold at least 8 months,
worse on the selection years (10.3 %), would have done best of all on the held-back years (3.7 %,
in every zone better than both the model and last year's count) and worse than the model in the
lockdowns (14.2 %); leaves of 12 and 20 months did worse again on the held-back years (5.9 % and
7.1 %). A setting that wins only in flat years cannot be picked in advance, because whether the
years ahead will be flat is not known when a forecast is made. A synthetic test checks that the fit
recovers a known traffic elasticity and weekday effect, and that its forecast follows a traffic
shock that last year's count misses.

**Detectability** (`horizon_errors`, `detectability`, `detection_power`). The error of the forecast
of an `n`-year total is measured the same way at every origin from 2006, leaving out every forecast
that covers 2020 or 2021. The origins 2022–2024, whose four-year fitting windows include the
lockdowns, are kept, because a forecast made for a law today is fitted on such a window too; they
make the error, and so the detectable change, somewhat larger than for windows with no lockdown.
The error splits into Poisson chance (one over the observed total) and an extra, multiplicative
part `tau_n` from the trend drifting away from its extrapolation. The chance that a two-sided
comparison at the 5 % level shows a change in its own direction is `Φ(d − z_0.975)`, with
`d = |log(1 + change / expected)| / sqrt(1 / expected + tau_n²)`: a result in the other direction
does not count as showing it, so the chance is 2.5 % when nothing changes and rises with the size
of the change. The minimum detectable effect is the proportional fall detected four times in five
(80 % power at the 5 % level), `1 − exp(−(z_0.975 + z_0.80) · sqrt(1 / expected + tau_n²))`; on the
log scale a rise has to reach `exp((z_0.975 + z_0.80) · sqrt(1 / expected + tau_n²)) − 1` to be
detected as often. Smaller changes are detected less often, not never. For all interurban deaths
one year after a law (1,284 a year, the mean of
2022–2024) it is about 15 % (about 195 deaths a year); for urban streets about 22 %; and it grows
with the horizon, to about 36 % over five years, because the drift grows faster than the count.

## 12. The speed-law simulator (`simulator.py`, `assets/simulator.js`)

A chain of four links, each with its source, run in the reader's browser.

1. **Baseline** (`baseline`). Mean annual injury crashes, 30-day deaths, injured admitted to
   hospital and other injured, 2022–2024, by road class: autopistas (interurban road types 1 and
   2, toll and free motorways), autovías (3), conventional roads (4–6), other interurban roads (the
   rest) and urban streets (the urban zone). Each class groups the codes swapped between years
   (5 and 6 in 2021, toll and free motorways in 2022 and 2024, the urban codes in 2024), so it is
   stable across them. The classes add up to the yearbook exactly. Deaths a year: autopistas 93,
   autovías 257 and conventional roads 850 (1,200 on the three simulated classes), other
   interurban roads 84, urban streets 495.
2. **Today's speeds** (`SpeedDistribution`). The EU Baseline project measured free-flowing car
   speeds by radar in Spain in August–October 2022 (weekday daytime) and published, by road type,
   the mean, the share within the limit and the 85th percentile. The simulator uses five measured
   sites, each with its own speeds: autopistas (Baseline's Table 9, p. 37: mean 121.3 km/h, 50.8 %
   within 120, 85th percentile 136), autovías (the Annex 1 text introducing Tables 12a–12c, p. 42:
   117.2 km/h, 62.5 %, 130), conventional roads (Table 10, pp. 37–38: 94.4 km/h, 42.6 % within 90,
   109), and urban streets at 50 and at 30 km/h (Tables 11 and 12a). A log-normal through the
   share within the limit and the 85th percentile reproduces both exactly; its mean is within 0.7
   km/h of the measured one on every road type. Autopistas are driven faster than autovías: the
   expected excess over the limit per car, which full compliance removes, is 6.2 km/h on
   autopistas, 3.7 on autovías and 7.8 on conventional roads.
3. **From a law to a mean speed.** A law sets three limits (`LEVERS`): one for autopistas and
   autovías together, as the Reglamento General de Circulación does (120 km/h on both today), one
   for conventional roads (90) and one for urban streets now at 50 km/h; streets at 30 stay at 30.
   Each measured site then responds from its own speeds. How far drivers follow a new limit and
   how many keep to the limit are set separately for each kind of road (`GROUPS`: autopistas and
   autovías, conventional roads, urban streets at 50 and at 30), so that a law on one kind of road
   leaves the others as they are; a single number still applies to all of them. A change of limit moves the mean by
   Elvik's curve through 143 before-and-after results (Trafikksikkerhetshåndboken, figure 3.11.2,
   published as `y = −0.0047x² + 0.2682x − 0.3125`, R² 0.51), with the intercept dropped so that no
   change means no change and offered only within the fitted range of −33 to +24 km/h, or by a
   share of the change the reader sets. Without its intercept the curve gives 7.2 km/h for a 20
   km/h cut and 3.5 for a 20 km/h rise, where the handbook rounds the scatter to about 8
   and 5. Compliance brings a share of the drivers above the limit in force (the new one, if
   there is one) down to it, which lowers the mean by that share of `E[(v − limit)+]` under the
   fitted distribution, scaled to the new mean. `speed_steps` returns the two moves separately
   (`limit_shift`, `compliance_cut`), and two measures of the flow under the limit in force: the
   share of cars above it, `(1 − c) · P(v > limit)`, and the spread of speeds, the standard
   deviation of the fitted distribution once the complying share `c` of the cars above the limit
   has moved to it (`E[v]` and `E[v²]` each lose `c` times their part above the limit, net of the
   limit's own contribution). The Power Model counts only the mean, so the spread is reported and
   not turned into casualties.
4. **From mean speed to casualties.** The Power Model: a count changes by `(v1 / v0) ** p`, with
   Elvik's 2009 exponents and 95 % intervals (TØI report 1034/2009, table S1) for deaths,
   seriously injured, slightly injured and injury crashes, separately for rural roads and motorways
   and for urban streets. Ranges are the exponent intervals, computed with the same end of the
   interval on every road so that totals do not mix them.

Value is DGT's 2024 update: €1,965,850 per death prevented, €385,480 per serious injury, €8,506 per
slight injury. Time is vehicle-hours of cars and other light vehicles, the traffic the speeds were
measured on, over the measured interurban kilometres of 2023 at free-flow mean speeds: each type of
road's vehicle-km in table 1.2.14 times one minus its published share of heavy vehicles (toll
motorways 11.1 %, autovías and free motorways 14.6 %, multi-lane roads 6.4 %, conventional roads
8.6 %). Heavy vehicles have their own limits, which a scenario leaves alone. Toll motorways are
timed at the autopistas' speeds, multi-lane and conventional roads at the conventional roads'
speeds; the table counts free motorways with autovías (its column "Autovía y Autopista libre"), so
their kilometres are timed at autovía speeds. No Spanish official value of travel time was found
to cite, so time is not priced. Every value in links 2 to 4 is read from
`data/raw/evidence/simulator_parameters.csv`, one row per value with its source, its place in the
source and a verbatim quote, and a test requires every quote to contain the value it supports.

**Risk per kilometre by road class** (`class_risk`). Deaths, people admitted to hospital and injury
crashes are put over billion vehicle-km for autopistas and autovías together and for conventional
roads (with the table's multi-lane roads), 2016–2023, the years both the crash microdata and table
1.2.14 cover. Autopistas and autovías are pooled here because the table puts free motorways with
autovías and the crash data put them with toll motorways. Conventional roads killed 3.38 times as
many people per kilometre as autopistas and autovías in 2023, and 3.42 times over 2016–2023. Speed
alone does not explain the gap: conventional roads also differ in two-way traffic without a
barrier, junctions and direct access, none of which these data measure.

**What the counts could show** (`power_in_one_year`). For each scenario the simulator gives the
chance that the first year's death count on the three simulated classes would show the change, by
the formula of section 11 with the interurban one-year `tau`, at the 1,200 deaths a year on those
classes. There the fall detected four times in five is about 184 deaths (15 %), and the rise
about 217, against a fall of about 195 for all 1,284 interurban deaths in section 11, which
include the other interurban roads. A
change of under half a death a year counts as none, and no chance is computed for it.

The presets, with drivers responding to a new limit as they typically do
(`simulator_presets.csv`; road by road in `simulator_preset_roads.csv`):

| Preset | Deaths a year | Injury crashes a year | Light-vehicle hours a year | Chance the first year's count shows it |
|---|---|---|---|---|
| Everyone keeps to today's limits | −335 (−370 to −298) | −3,365 | +134 million | over 99 % |
| Half of today's speeders keep to the limit | −179 (−200 to −158) | −1,702 | +64.7 million | 78 % |
| Everyone keeps to 90 km/h on conventional roads | −280 (−309 to −249) | −2,675 | +96.8 million | 99 % |
| Everyone keeps to 120 km/h on autopistas and autovías | −55 (−62 to −49) | −690 | +37.4 million | 12 % |
| Conventional roads 90 → 80 km/h | −123 (−138 to −108) | −1,092 | +36.9 million | 45 % |
| Autopistas and autovías 120 → 110 km/h | −41 (−46 to −36) | −486 | +30.2 million | 8 % |
| Autopistas and autovías 120 → 130 km/h | +31 (+27 to +35) | +346 | −20.3 million | 6 % |
| Autopistas and autovías at 130 km/h, and everyone keeps to it | +2 (+2 to +3) | +12 | −4.4 million | 3 % |
| Autopistas and autovías 120 → 140 km/h | +50 (+43 to +57) | +547 | −31.6 million | 10 % |
| Autopistas and autovías at 140 km/h, and everyone keeps to it | +39 (+33 to +44) | +418 | −26.2 million | 8 % |
| Urban streets 50 → 30 km/h | no interurban change | no interurban change | no interurban change | not computed |

**A higher limit that everyone keeps to** (`break_even`, `simulator_break_even.csv`). Raising the
autopista and autovía limit to 140 km/h moves the mean up by the typical response, +3.5 km/h (17 %
of the change), and every driver keeping to 140 takes off only what lies above 140: 1.4 km/h on
autopistas, where 10 % of cars exceed 140 today, and 0.6 on autovías. Deaths on the two rise by
about 39 a year against today, and by about 94 against everyone keeping to 120 (−55). Deaths would
fall against today only if less than 2.4 % of the rise reached the mean. With the typical
response and everyone keeping to the limit, the limit at which deaths equal today's is about
129.5 km/h. The spread of speeds on autopistas narrows from 14.9 to 12.8 km/h at 140 kept by
everyone, and to 7.9 km/h at 120 kept by everyone; for the narrower spread at 140 to cancel the
rise it would have to cut deaths on the two roads by about 10 % on its own, and the Aarts and van
Schagen (2006) review gives no dose-response from which to judge that.

Full compliance is worth about €1.0 billion a year at DGT's values. Conventional roads at 80 km/h
cost about 300,000 hours for each life saved, and autopistas and autovías at 130 km/h save about
650,000 hours for each life lost. On the streets now at 50 km/h, a limit of 30 changes deaths by
−40 % (−67 % to +9 %) and admissions by −29 % (−42 % to −13 %); the interval for deaths includes
no effect, as the urban exponent's does.

`limit_grid` (`simulator_limit_grid.csv`) runs every pair of interurban limits the page offers
(autopistas and autovías at 100 to 140 km/h, conventional roads at 70 to 100) with the typical
response. With that response, full compliance with today's limits (−335) saves more than any
single new limit, the largest being conventional roads at 70 km/h (−261); only lowering both limits
at once can save
more, and only one pair does: autopistas and autovías at 100 km/h with conventional roads at 70
(−350). The chance that the first year's count shows the change is 99 % for conventional roads at
70 km/h and 45 % at 80 km/h, and no more than 25 % for any change of the autopista and autovía
limit alone.

The page states its verdict as a chance: that the change would stand out from an ordinary year in
the first year's count with a chance of about 45 % for conventional roads at 80 km/h, for example,
or almost certainly at 99 % or more, beside the fall (184) or the rise (217) the count picks up
four times in five, whichever is the direction of the change; between 50 % and 80 % it adds that a
year without a clear signal would not mean the law had failed (for a fall) or was harmless (for a
rise). It
says "Nothing changes" only when no road and no street changes; it has its own message when only
urban streets change, since DGT publishes no deaths by street limit and so there is no count to
watch; it says when the changes on the three roads cancel to under half a death a year; and it
says when rises on some roads offset falls on others.

Left out, and said on the page: other interurban roads, for which no speed was measured; urban
casualties as a national count, because DGT does not publish how many urban casualties happen on
30 and on 50 km/h streets, so the urban effect is given per kind of street; trucks, night traffic
and congestion, which the speed measurements do not cover; time on municipal interurban roads,
which table 1.2.14 leaves out; and the narrowing of the speed distribution that compliance brings,
which the Power Model does not count and which would make the compliance figures larger.

The browser code is a port of the Python. Its normal distribution function is W. J. Cody's
rational approximation, as in R's `pnorm`, accurate to about one part in 10^15. A test runs it
under Node on every combination of the page's limits (5 × 4 × 3 = 60), each with the response
typical, 0, 35 % and 100 % of the change or set for some kinds of road only, and compliance 0,
5 %, 50 % and 100 % or set for some kinds of road only, and on the presets: 1,512 scenarios,
which must agree with the Python to one part in a million on every quantity the page shows
(speeds and their steps, the share above the limit and the spread, casualties, ranges, value and
hours by road and in total, and the urban speeds, deaths with their range and admissions), on
both thresholds and on the chance of detection.

## 13. Assumptions tested

Every headline rests on an assumption the data can be asked about; these are the ones tested, all
listed with their results on the data page.

| Assumption | Test | Result |
|---|---|---|
| A year's count varies only by chance | dispersion around the 2013–2019 trend | fails for crashes and admissions; intervals widened (section 4); against 2019, the 2024 rise in admissions stays beyond an ordinary year as a count and per tonne of fuel, and the fall in crashes only per registered vehicle, just |
| Road fuel tracks kilometres | measured interurban vehicle-km | holds to 2019, drifts after; the long-run finding corrected (section 5) |
| CORES road fuel includes the biofuel blended into it, and a tonne means the same every year | each subtotal against the sum of its products, biofuels included, every month; the published biofuel share | holds: biofuel was 6.6 % of road fuel by mass in 2019 and 7.8 % in 2023, and as it carries less energy per tonne it cannot explain the rise in kilometres per tonne (section 5) |
| The owner's age stands for the driver's | cars and km per licence holder by band | bounded: 1.02 to 0.89 at the extreme; the conclusion holds (section 7) |
| The fall in deaths was in how deadly crashes are | exact frequency × severity split | holds; the split, not the product, depends on recording (section 4) |
| A forecast can show a law's effect | out-of-sample forecast errors | only for large effects: a fall of about 15 % of interurban deaths is detected four times in five in the first year, smaller ones less often (section 11) |
| Two numbers describe how fast cars drive | log-normal checked on the measured mean | holds, within 0.7 km/h (section 12) |

## 14. Supporting analysis: severity models (`features.py`, `models.py`, `scripts/model.py`)

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

### 14.1 The adverse-conditions sensitivity (`models.adverse_conditions`)

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

## 15. Supporting analysis: the 2006 case study (`policy.py`)

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

## 16. Rates and intervals (`rates.py`)

Counts of deaths, crashes or involved drivers are treated as Poisson with a known denominator, and
every rate built against a counted denominator (residents, licence holders, drivers involved,
circulating vehicles, vehicle-kilometres) carries an exact 95 % (Garwood) interval. Ratios of two
such rates carry a log-normal interval. The speed-infraction share among drivers whose status is
known carries a Wilson interval. Shares taken entirely within one source's own counts (road-user
shares, the night shares, deaths per 100 crashes, occupant deaths per fatal involvement) are
population counts, not samples, and are reported without intervals.

## 17. Figures, pages and wording

Twenty-two figures, matplotlib SVG with no date metadata, so a rebuild in the same environment
(`requirements.lock`) changes nothing unless a number changes. One axis per chart, intervals drawn
where they exist, direct labels where a legend would be ambiguous, colour never the only encoding.
`figures.build_all` deletes any SVG in its output directory that no longer has a caption, so a
removed figure cannot linger.

The main navigation carries the overview, the seven analysis pages (2019–2024, the long run,
seasons, age and sex, vehicles, speed, other factors), the simulator and the data page; the
overview ends on what connects the findings, and the data page lists the assumptions tested. The
severity model and the
2006 case study sit in a second row labelled as supporting analyses, each opening with a note that
says why it is outside the central question. Pages renamed in the reorganisation
(`older-drivers.html`, `context.html`) are kept as pointers that refresh to their successors.

Nearly every number in a page's sentences, the front-page digest included, is computed from the
result tables at build time, so a rebuilt table rewrites the text that quotes it; where a sentence
says which results lie inside or outside an interval, the build stops if the table no longer
supports it. Full result tables are
copied into `site/tables/` and linked as CSV rather than printed: the default on a page is one
figure, one interpretation and one limits note per finding. Tests check that every internal link
and anchor resolves, every image has alt text, every page has one heading and a description, that
no page but the simulator carries a script (and the simulator only its own file and a data block),
and that each page's headline numbers match the tables they come from. The site builder is the
`dgt_stats.site` package, one module per page.

## 18. Reproducibility

- Raw inputs immutable and manifested; interim and processed layers rebuilt from them by the
  command sequence in the README, with Python 3.11 and the library versions in `requirements.lock`
  (pandas 3.0.6, numpy 2.4.6, scipy 1.17.1, statsmodels 0.15.0, matplotlib 3.11.2, scikit-learn
  1.9.1, pyarrow 25.0.1). The lock file is compiled from `pyproject.toml` with
  `uv pip compile --extra dev --generate-hashes`. At the dependency floors in `pyproject.toml` the
  numbers agree to the precision printed on the pages, but every figure differs, because matplotlib
  writes its own version into the SVG and the tight-bbox geometry changes with it. Descriptive
  result tables are written with ten significant digits and the severity-model tables with six, so
  last-bit differences between library versions do not reach the committed files.
- All logic in `src/dgt_stats/` and `scripts/`; no notebooks. The gradient-boosted trees of the
  forecast comparison are given a fixed seed and, at these sizes, draw nothing at random; every
  other fit is deterministic and needs no seed.
- `pytest` runs the data-contract, reconciliation and analysis tests; the SHA-256 check of every
  raw file against `data/raw/manifest.csv` is marked slow and run with `pytest -m slow`. `ruff`
  for lint and format.
- The Pages workflow renders the site from the committed tables and never rebuilds the data.

## 19. Limits that apply throughout

- Crash-level records only: no driver age, sex, alcohol, drug, speed, belt or helmet fields, so
  factor interactions and person-level risk are out of reach.
- Police-recorded circumstances, whose completeness varies by year and by severity.
- All model results are associations; the 2006 case study is a coincidence in time unless its
  falsification tests agree, and they only partly do.
- The simulator's effects of speed come from international before-and-after evidence applied to
  Spanish baselines and Spanish measured speeds; they are projections under stated assumptions, not
  estimates from Spanish crash data, which carry no speeds.
- Vehicle-kilometres by vehicle type exist in detail for 2022 only (2024 by category, and each
  year on interurban roads only as heavy against other vehicles); kilometres by age are the
  owner's age; the speed
  report excludes two regions; road-type coding changed in 2021 (interurban conventional roads),
  2022 and 2024 (toll and free motorways, with 2023 back at the earlier split) and 2024 (urban),
  and the junction field changed in 2023.
