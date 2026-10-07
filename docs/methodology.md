# Methodology

How the numbers on the site are made, as built (October 2026). The site answers four questions,
each from its own data:

1. **Spain.** What is happening across the country, and what changes when road risk is measured
   against residents, licence holders, vehicles and traffic rather than counted (sections 1 to
   10, 13 and 16, and the two supporting analyses in sections 14 and 15). This part ends with a
   forecasting model of monthly deaths (section 11).
2. **Individual crash records.** What the Catalan and Barcelona crash records show (section 20).
3. **Which models earn their place.** A severity model is presented only if it beats a
   descriptive table of outcome shares on the same test rows; otherwise the table replaces it
   (section 21).
4. **How far they generalise.** Whether a model holds in later years, other places and another
   recording source, and how the training population differs from Spain (section 22).

The data are in four layers, each with one role (`src/dgt_stats/layers.py`): the **national
context** (DGT and INE: trends, denominators, exposure, rates, forecasting and aggregate
comparison); the **crash microdata of Catalonia** (the crash-severity model and its temporal and
geographic validation); the **rich microdata of Barcelona** (crash and person analysis and the
person-severity model); and **validation** (harmonisation and transfer tests only, never creating
observations). No record is linked across sources and no merged database is built. Every result
comes from rows of the files in `data/raw/`; studies published elsewhere may define a variable or
a method but never supply an observation, a coefficient or an effect size. The speed-law
simulator, the distraction and alcohol-and-drug models and the enforcement comparison drew their
results from coefficients in external studies and were withdrawn; their old pages are short
notices (section 17). Every method below names the module that implements it. What each dataset
may be used for and joined to is in [`DATA_CONTRACT.md`](DATA_CONTRACT.md); how each source came
to exist is compared in [`SOURCE_COMPARISON.md`](SOURCE_COMPARISON.md); what the published files
can and cannot support is in [`data_inventory.md`](data_inventory.md).

## 1. Units and sources

The public DGT crash microdata are one row per injury crash: 875,013 rows for 2016–2024, with the
place, time, road, conditions and victim counts by severity and road-user type. They have no
vehicle or person rows, so no national result is estimated at the driver, vehicle or victim
level; where the national pages speak of drivers they use DGT's aggregate yearly tables, which
count drivers by age, sex, vehicle and recorded infraction but cannot be linked to crashes. Person
records exist only in the Barcelona files (sections 20 and 21).

| Source | Unit | Years | Used for |
|---|---|---|---|
| crash microdata | injury crash | 2016–2024 | scoped totals for the speed comparison, the association analysis of severity (section 14), darkness shares, road-class deaths per measured km (`road_class.py`, section 5); in the validation layer, the audit and the national transfer test (section 22) |
| yearbook series | year, month or province totals | 1993–2024 | 2019–2024 risk, the long run, seasonality, the monthly deaths of the forecasting model, the 2006 case study, reference totals |
| yearly statistical tables | aggregate cells | 2014–2024 | vehicles involved by type, driver deaths and involvements by age and vehicle, drivers by recorded infraction |
| ITV kilometre estimates 2022 | fleet and mean km by vehicle type and age | 2022 | vehicle rates per km |
| ITV kilometre estimates 2024 | vehicles and km by category and owner age band | 2024 | the driving-exposure denominator |
| driver census | licence holders by province, sex, age; B-permit holders by age | 2014–2025 | driver casualties per licence holder, sex rates; B-permit holders (2024 text file) for the owner-age check and the contrast denominators |
| INE population | residents by province, age, sex | 2002–2025 | risk per resident, contrast denominators |
| CORES road fuel | month | 1996– | the all-road traffic denominator or offset of the risk, long-run and seasonality analyses; the traffic input of the forecasting model; a covariate in the 2006 case study; the biofuel share of road fuel |
| toll-motorway traffic | month | 1990– | a traffic index shown beside deaths (seasons) and an intensity covariate in the 2006 case study; never a denominator |
| Ministerio de Transportes, yearbook table 1.2.14 | year, road type | 2004–2023 | measured interurban vehicle-km: the long run per measured km and road-class deaths per measured km (section 5) |
| DGT speed-factor report | year, factor, road type | 2014–2023 | speed as a severity factor; the other recorded factors |
| Servei Català de Trànsit export | crash with a death or serious injury | 2010–2023 | the crash microdata layer of Catalonia (sections 20 to 22) |
| Guàrdia Urbana, six tables | crash; person record | 2025 | the rich microdata layer of Barcelona (sections 20 to 22) |

Raw files are never edited (`data/raw/<source>/`, listed in `data/raw/manifest.csv` with SHA-256,
the source URL where one was recorded and the name each file was downloaded as). `ingest.py`
parses the national files into typed Parquet tables (`data/staging/dgt/`), `build_tables.py` adds
the derived fields (`data/processed/`), and every national result table and figure is written by
`model.py` and `analyse.py` from those layers; `scripts/microdata.py` builds the regional layers
(section 20). The site reads only the committed result tables.

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
million vehicle-km short). The INE population, the 2022 ITV tables and the transcribed
speed-factor report are covered by unit tests that check their internal totals.

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
  and the 2019 speed-limit study (section 15) group the raw codes differently; the road classes of
  `road_class.py` (section 5) group them by zone first, and the severity regressions (section 14)
  take codes 4 to 6 as conventional roads.
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

Each annual outcome, 30-day deaths, injured admitted to hospital and injury crashes, is set against
up to four denominators and indexed to 2019 (`risk_index`). Each denominator divides only the
casualties it can contain (`numerator_for`):

| Denominator | Source | Years | What it counts | What it divides |
|---|---|---|---|---|
| residents | INE resident population on 1 July | 2002– | everyone, most of whom are not driving | every casualty, and injury crashes |
| licence holders | DGT driver census, end of year | 2014– | holders of every permit class | only drivers of motorcycles, cars, vans, trucks and buses killed or admitted to hospital |
| registered vehicles | DGT fleet in the yearbook rate table | 1993– | every registered vehicle, used or not | only occupants (drivers and passengers) of those vehicles |
| road fuel | CORES automotive petrol plus diesel, complete years | 1996– | the only annual traffic series covering every road | every casualty, and injury crashes |

The driver and occupant numerators come from the yearbook's road-user series by vehicle type
(`road_user_outcomes`, `MOTOR_VEHICLE_TYPES`). Pedestrians, passengers, cyclists and riders of
personal mobility vehicles need no licence for the trip in which they are hurt, so only drivers
are set against licence holders; pedestrians and cyclists are in no registered vehicle, so only
occupants are set against the fleet. Bicycles and personal mobility vehicles need neither a
licence nor a registration and are in neither numerator. "Otros" is left out because it held
personal mobility vehicles until they got their own column in 2020, and mopeds because the
repository does not establish whether the fleet in the rate table counts them. Injury crashes are
not split by vehicle type in the yearbook series, so they are divided by residents and road fuel
only.

The ratio of each year's rate to the 2019 rate carries a log-normal interval that treats both counts
as Poisson and the denominators as known; for the count itself the ratio is the change in the count.

**An ordinary year, not only chance** (`year_to_year_dispersion`). A Poisson interval assumes a
year's count varies only by chance. Spain's annual counts scatter more than that around their own
trend: fitted log-linearly over the 2013–2019 plateau, the Pearson dispersion is about 1.5 for
deaths, 8 for hospital admissions and 68 for injury crashes, whose count depends on how completely
slight injuries are recorded. Each numerator has its own: 1.0 for driver deaths, 1.76 for drivers
admitted to hospital, 2.35 for occupant deaths and 3.83 for occupants admitted to hospital
(`risk_dispersion.csv`). The dispersion is a ratio of variances (floored at 1): the variance of
crashes around their trend is about 68 times that of a Poisson count of the same size, so their
spread is about √68 ≈ 8 times the Poisson spread. The page reads every change against the interval
widened by the square root of that ratio (`ratio_low_yty`, `ratio_high_yty`), so a change outside it
is larger than an ordinary year. In 2024, against 2019, no change in injury crashes is beyond an
ordinary year; a pure Poisson interval would flag the falls as a count and per resident. Hospital
admissions are beyond an ordinary year as a count (+11.0 %) and per tonne of road fuel (+13.0 %);
within it are admissions per resident (+7.1 %), drivers admitted per licence holder (+4.5 %) and
occupants admitted per registered vehicle (+3.4 %). Deaths in 2024 are within an ordinary year of
2019 under all five pairings: the count, per resident, per tonne of road fuel, drivers per licence
holder and occupants per registered vehicle.

**How often against how hard** (`frequency_severity`). Deaths per tonne of road fuel is the exact
product of injury crashes per tonne and deaths per injury crash; the three are indexed to 1996, the
first year of the fuel series. Over 1996–2024 the first fell 76 %, the second 13 % and the third
73 %. The split depends on how completely slight-injury crashes are recorded, which moves the two
factors in opposite directions without moving their product; deaths are counted completely.

Road fuel is a proxy for vehicle-kilometres, not a count of them. No series in the repository
measures kilometres per tonne on all roads; `fuel_efficiency_sensitivity` shows the per-fuel
change under hypothetical drifts of 0, 1 % and 2 % a year from 2019 (`hypothetical_annual_gain`),
which support no conclusion. DGT's two published kilometre estimates (2022, from ITV odometer
readings; 2024, an annualised estimate) are compared with fuel in `km_crosscheck` and are not
chained into a trend: they are built differently, and between the two years they move −1.6 % while
fuel moves +1.5 %.

## 5. The long run and the pandemic (`risk_trends.py`)

A segmented log-linear (joinpoint) trend is fitted to the yearbook's 30-day deaths, 1993–2019, in
three forms: the count; occupant deaths of motorcycles, cars, vans, trucks and buses with the log
registered fleet as offset; and the count with the log road fuel as offset (from 1996). The model is
a Poisson GLM with quasi-likelihood (Pearson) dispersion, continuous at its turning points; the
dispersion is floored at 1, so a series that happens to scatter less than Poisson chance in a dozen
points does not get an interval narrower than Poisson noise would give (`_fit`). For 0 to 3 turning
points every admissible placement (segments at least four years long) is fitted and the
lowest-deviance one kept; the number of turning points is chosen by QBIC, the Poisson BIC divided by
the dispersion of the largest model with each turning point costing two parameters, taking the
simplest model within two points of the minimum (`joinpoint_search`). The segment slopes are
reported as annual percentage changes with intervals from the scaled covariance (`segment_changes`).
All three measures choose two turning points: 2003 and 2013 for the count and for occupants per
vehicle, 2002 and 2011 per tonne of road fuel (`longrun_model_choice.csv`).

The last segment is projected through 2020–2024 (`project`) with a 95 % prediction interval that
combines the uncertainty of the fitted line (delta method on the linear predictor) with
overdispersed noise around it. For the per-vehicle and per-fuel forms the projection is multiplied
back by each year's fleet or fuel, so all three are in deaths and `observed / expected` reads the
same way. The per-fuel trend's last segment runs from 2011, so its projection carries whatever
kilometres per tonne did over 2011–2019 into the years after. No series measures that on all
roads; `long_run_efficiency_sensitivity` shows how the per-fuel ratio would move under hypothetical
extra gains of 1 % and 2 % a year from 2020 (`hypothetical_extra_annual_gain`), which support no
conclusion.

The question this answers is whether 2020–2024 is a distortion or a change of trend. As a count,
2020 is far below trend and the count is inside its interval from 2021. Occupant deaths per
registered vehicle are below the interval in 2020 and 2021 and inside it from 2022. Per tonne of
road fuel, deaths stayed inside the trend's interval in 2020–2022, and 2023–2024 are above it,
beyond the interval.

**Re-run on measured kilometres** (`interurban_km_panel`, `km_trend_check`). The Ministerio de
Transportes' yearbook table 1.2.14 gives the vehicle-kilometres measured each year on the
interurban networks of the State, the regions and the provincial councils, by type of road, from
2004 (`io_traffic.read_road_traffic`; the four road types must add up to the published total, and
the series is comparable from 2008, when the road inventory was redone). The same joinpoint search
is fitted to interurban deaths over 2008–2019 with the log of measured kilometres as offset
(`per_km`, the rate); it chooses a turning point in 2013 and a decline of 1.8 % a year after it.
Projected on, every year from 2020 to 2023 is inside the interval of the 2013–2019 decline
continued: 2020 lies exactly on the trend, and per measured interurban km 2023 is +5 % on trend,
inside its interval (−4 % to +15 %). The kilometres end in 2023.

**Which roads the kilometres cover** (`interurban_network_coverage`, `longrun_km_coverage.csv`).
The kilometres leave out interurban roads run by municipalities and other bodies, and urban
streets, while the yearbook's interurban deaths, the numerator of the rate, include every
interurban road. The crash microdata record the road's owner (`TITULARIDAD_VIA`), so the share of
interurban deaths on roads the kilometres leave out (owners 4, 5 and 999) is measured year by
year: 8.7 % to 11.2 % in 2016–2024, 10.1 % in 2019 and 9.9 % in 2023. The microdata reproduce the
yearbook's interurban count every year. The share cannot be measured before 2016, so the
2008–2019 fit assumes it was similar then.

**Interurban deaths over national road fuel: a diagnostic, not a rate.** The same deaths are also
fitted with the log of national road fuel as offset (`per_fuel`). Fuel is sold for every road,
towns included, so its scope does not match the numerator, and its ratios describe how the fuel
proxy behaves beside the measured kilometres. On that fit 2023 is 13 % above trend, outside the
interval, and 2022 just inside it. Interurban kilometres per tonne of all road fuel
(`km_per_tonne`) grew 0.5 % a year over 2011–2019 and 1.9 % a year over 2019–2023; the ratio mixes
interurban kilometres with fuel for every road, so it is not fuel economy and also moves when
traffic shifts between towns and interurban roads, and with the mix of freight. CORES publishes
the mass share of biofuel blended into each subtotal (`fuel_bio_share`, `longrun_fuel_bio.csv`):
6.6 % of road fuel by mass in 2019 and 7.8 % in 2023 (7.1 % in 2024). Biofuel carries less energy
per tonne than the petrol and diesel it replaces, so a point more of it lowers kilometres per tonne
slightly; it cannot explain the rise in interurban kilometres per tonne.

### 5.1 Deaths per measured kilometre by road class (`road_class.py`)

`class_risk` puts deaths, people admitted to hospital and injury crashes over billion vehicle-km for
autopistas and autovías together and for conventional roads (with the table's multi-lane roads),
2016–2023, the years both the crash microdata and table 1.2.14 cover. Autopistas and autovías are
pooled because the table puts free motorways with autovías and the crash data put them with toll
motorways. Interurban crashes are classed by road-type code (autopistas 1 and 2, autovías 3,
conventional roads 4 to 6), so each class keeps together the codes DGT swapped between years.

The numerator of every rate is restricted to roads of owners (`TITULARIDAD_VIA`) 1 to 3, the
State, the autonomous communities and the provincial councils, which are the networks the
kilometres cover (`KM_COVERAGE_OWNERS`). What the restriction removes is published beside each
rate, year by year and class by class, with the rate every owner would give
(`*_all_owners_per_bn_km`): over 2016–2023 the deaths outside the coverage are 4.6 % to 7.7 % of a
year's conventional-road deaths and 3.7 % to 6.5 % on autopistas and autovías, and the injury
crashes outside it 18.4 % to 21.8 % and 14.0 % to 18.9 % (`outside_coverage_death_share`,
`outside_coverage_crash_share`). One mismatch is counted rather than corrected: deaths on these
kinds of road of covered owners recorded in the urban zone (urban crossings and urban autovías)
are in no numerator, while whether their kilometres are in table 1.2.14 is not stated;
`urban_zone_deaths_on_covered_roads` gives them, 20 to 34 a year on conventional roads and 0 to 4
on autopistas and autovías. In 2023 conventional roads recorded 7.41 deaths per billion vehicle-km
and autopistas and autovías 2.15 (`road_class_risk.csv`): recorded rates by class, not the effect
of the class of road. `baseline` gives the mean annual crashes and casualties by road class over
2022–2024, which add up to the yearbook totals (`road_class_baseline.csv`).

## 6. Seasonality and mobility (`seasonality.py`)

Monthly 30-day deaths from the yearbook series are set beside three monthly traffic series
(`TRAFFIC_SERIES`), and only one of them is used as an offset or denominator: road fuel (petrol
plus diesel, CORES), the one series whose scope, every road and every vehicle, matches deaths on
all roads. It is fuel sold, not kilometres driven, and it mixes freight with private travel, so
deaths per tonne of road fuel are a proxy rate and are labelled as one. Petrol sold alone leaves
out every diesel vehicle, and toll-motorway intensity (average daily vehicles per kilometre of the
state toll network) measures traffic on a small part of the network; both are traffic indices
shown beside deaths, never an offset or a denominator. Intensity is read rather than
vehicle-kilometres because the network shrank from about 2,500 to 1,400 km as concessions expired
in 2018–2021.

The seasonal profile (`seasonal_profile`) divides each month by the mean month of its own year and
averages over 2014–2019 and 2022–2024, leaving out the pandemic years; its
`deaths_per_road_fuel_tonnes` column is the deaths index divided by the road-fuel index. The month
effects (`month_effects`) come from quasi-Poisson models of monthly deaths with year effects and
sum-to-zero month effects, with no exposure and with the log of road fuel as an offset
(`EXPOSURES`); with the offset the month effect is deaths per tonne of road fuel against the
average month. A synthetic test checks that an offset exactly proportional to the outcome removes
all seasonality. The lockdown comparison (`lockdown_months`) sets each month of 2020 against the
same month's 2017–2019 mean for deaths, for each traffic series and for deaths per tonne of road
fuel (`deaths_per_road_fuel_tonnes_change`).

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
  Drivers of unrecorded age (2.2 % of those involved in 2024, 2,243 of 100,660 car drivers
  involved; 2.0 % and 2.3 % in 2022 and 2023) are kept as their own row.

Three quantities, reported separately because they answer different questions:

1. `involved_per_bn_km`: drivers of this age involved in an injury crash per billion km driven by
   cars registered to owners of this age.
2. `deaths_per_1000_involved`: how often an involved driver of this age is killed. This needs no
   exposure at all, so the kilometre estimate cannot affect it.
3. `deaths_per_bn_km`: drivers of this age killed per billion km driven by cars registered to
   owners of this age; the product of the two.

Intervals are exact Poisson on the count with the kilometres treated as known; ratios to the
baseline carry log-normal intervals.

What the denominator is not: it is the **owner's** age, not the driver's, and cars registered to
companies carry no age at all (2.2 million cars, 40 billion km in 2024). Those kilometres leave the
denominator while their drivers stay in the numerator. `company_km_sensitivity` gives two
scenarios, because the data hold no driver age for company cars: spreading those kilometres over
every band in proportion cannot change a ratio between two bands, and spreading them over the
bands from 18 to 64 adds kilometres to the 35–54 reference and none to 65 and over, so by
arithmetic it raises the 75-and-over ratio of deaths per km from 3.99 to 4.76.

**Owner's age against driver's age** (`owner_age_check`). The check uses holders of a B (car) permit
(`io_exposure.b_permit_holders_by_age`, `NUM_PERMISOS_B` of the 2024 census text file). If every car
were registered to the person who drives it, cars per B-permit holder would say how many cars each
driver has. Cars registered to owners aged 18–34 come to 0.46 per B-permit holder of that age, with
6,247 km per holder, against 0.80 cars and 10,345 km at 35–54; at 75 and over there are 1.14 cars
per B-permit holder, more cars than there are B-permit holders of that age. So the owner's age does
not stand for the driver's at either end of the range. No band supports an owner-equals-driver
reference either (0.93 and 0.94 cars per B-permit holder at 55–64 and 65–74 do not show that the
owner drives), so 35–54 is kept as the reference and the per-km ratios are published as ranges. One
end of each range is the published ratio; the other is a scenario, not an estimate: 15.29 billion km
move from the 35–54 band to 18–34 until the two drive the same distance per B-permit holder, as if
the whole gap were young drivers' driving registered to owners aged 35–54. The data say neither how
much of the gap that is nor which older band holds it. Under the scenario the 18–34 involvement
ratio per km goes from 2.57 to 1.55 and the 75-and-over one from 1.02 to 0.89; deaths per driver
involved need no kilometres and do not move. Every band and measure, with both ratios and their
intervals, is in `q7_owner_age_check.csv`.

`denominator_contrast` puts the same deaths over residents, B-permit holders, drivers involved and
kilometres of cars registered to owners of the band, as ratios to the 35–54 band, because the
movement between them is the point: at 75 and over the ratio is 1.23 per resident, 3.10 per
B-permit holder, 3.93 per driver involved and 3.99 per owner-age km. Residents start at 35 because
INE publishes five-year groups and no resident count can be cut at 18.

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
log-normal intervals. `sex_trend` gives the three rates for drivers aged 18 and over, by sex and
year, 2014–2024.

No file in the repository measures kilometres driven by sex, so the sex comparison is per licence
holder (any class) and per driver involved. The MOVILIA 2006 bracket that used to sit beside it was
withdrawn: it divided a 2022–2024 crash ratio by a 2006 car-or-motorcycle trip ratio that counts
passengers. B-permit holders by sex exist only from 2021, so the rates keep holders of any class.

## 8. Vehicles per kilometre (`vehicles.py`)

A 2022 cross-section. The numerator is vehicles involved in injury crashes and in fatal crashes by
type, from yearbook table 2.3, and occupant deaths by vehicle from table 2.2. The denominator is
DGT's ITV estimate of the circulating fleet (its *parque circulante*) and its mean annual kilometres
by vehicle type and age, which is valid for aggregates only. Six rate groups: motorcycles, mopeds,
cars, vans with light trucks, heavy trucks, buses. Vans and light trucks are one group because the
crash record codes most light commercial vehicles as vans while the register splits them; heavy
trucks include tractor units because the kilometre table's heavy category is the union of the
methodology note's two heavy categories. Rates are per billion vehicle-kilometres and per 100,000
circulating vehicles, with exact Poisson intervals. Vehicle-kilometres exist for all roads only,
so the rows by zone (interurban, urban) carry counts and rates per 100,000 circulating vehicles and
no rate per kilometre. The two sides of the division do not cover quite the same vehicles: the
crash counts include foreign-registered vehicles, and the kilometres include the distance Spanish
vehicles drive abroad. The kilometres are annualised over inspection readings taken across
2014–2023, so they describe a normal year imputed to the 2022 fleet rather than 2022 travel.

## 9. Speed as a severity factor and speed status (`factors.py`, `speed.py`, `io_reports.py`)

**Speed as a severity factor** (`factors.speed_severity`). The report gives injury crashes and
deaths with inappropriate speed recorded, by year and by road type (motorways, dual carriageways,
other interurban roads, urban streets). Deaths per 100 such crashes are set against deaths per 100
of the remaining injury crashes of the same scope, year and road type. The totals by zone come from
the report; the totals by interurban road type, which the report does not publish, come from the
microdata restricted to the report's provinces, which reproduce the report's zone totals exactly
(`speed_report_scope`). The road types map from the microdata's zone and road-type code (motorways
1–2, dual carriageways 3, every other interurban code to the rest). The mapping is not reconciled
by road type, because `speed_report_scope` checks year by zone only, and the ratio adjusted for
road type and year (2.00, `speed_severity_pooled.csv`) rests on it. Rate ratios carry log-normal
intervals; `speed_severity_pooled` pools 2016–2023 by road type and fits a quasi-Poisson model of
deaths with the log of crashes as offset and road type and year as factors, whose speed
coefficient is the ratio on the same kind of road.
The crude ratio is reported beside it. The ratio is an association subject to two biases the data
cannot measure: differential recording (speed is more likely to be found in a fatal crash, which
inflates it) and unrecorded speed in the comparison group (which deflates it).

**Speed status in the driver tables.** Tables 6.1 count drivers involved by recorded infraction,
2014–2024, interurban and urban. The speed page shows the share of drivers with no speed record
beside the share with one, and gives the infraction share both over all drivers and among those
with a record, with Wilson intervals, because the unrecorded share rose from 19 % in 2015 to 52 %
in 2016 and a single share would hide it. That discontinuity is the point of the section; the two
readings of the same table move in opposite directions across it.

DGT's speed-factor report is transcribed by `io_reports.py` (61 of its 64 tables) and kept in the
staging layer (`data/staging/dgt/speed_report.parquet`). Two of its tables are inputs to analyses
(speed-related crashes and deaths by road type; crashes by concurrent factor); **none of its
breakdowns is republished on the site**, and its territory (Spain without Cataluña and País Vasco)
differs from every other source here, so its figures are never added to yearbook totals.

## 10. Other recorded factors (`factors.py`)

DGT's speed-factor report gives, for 2014–2023 and Spain without Cataluña and País Vasco, the injury
crashes with each of five police-recorded concurrent factors (distraction, inappropriate speed,
illegal manoeuvres, alcohol, drugs) by zone. Each factor's share of the zone's injury crashes (the
report's own totals) is computed by year (`factor_shares`), and every year-to-year change is tested
(`factor_consistency`): a change in share beyond a ratio of 1.25 either way in a single year is
flagged as a recording break and is not read as a change in what drivers did; a change where
either year has fewer than 200 crashes cannot be tested and is treated as a break too.
`comparable_windows` lists the runs of years between breaks, and the page reads trends only within
them. The threshold is a rule, not a test with a known error rate;
every change is published so another threshold can be applied. A synthetic test checks that the
rule splits runs at a jump and at an untestable change.

The rule finds the breaks the report's own tables show on inspection: urban distraction in 2016
and 2019, urban alcohol in 2016, and drugs throughout. Interurban alcohol, inappropriate speed in
both zones and interurban distraction run unbroken across the decade.

## 11. Predicting deaths, and what a before-and-after comparison can see (`forecast.py`)

Any before-and-after reading compares the deaths after a change with the deaths that would have
been recorded without it, and the second number is a forecast whose error decides what the
comparison can see. The model card is
[`models/dgt_monthly_deaths_forecast.md`](models/dgt_monthly_deaths_forecast.md).

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
5.9 %); it earns its place when the trend or the traffic moves, which is when a change has to be
told apart from them. Its worst held-back year is 2022, forecast from a window that contains the
lockdowns. The tuned trees do worse than the model on every kind of road (all roads, interurban
roads, urban streets) and in every set of years: a tree cannot extend a trend beyond the years it
has seen, and with 48 rows a small leaf fits the noise. Trees whose leaves hold at least 8 months
are disclosed as a comparator, not chosen: worse on the selection years (10.3 %), they would have
done best of all on the held-back years (3.7 %, in every zone better than both the model and last
year's count) and worse than the model in the lockdowns (14.2 %); leaves of 12 and 20 months did
worse again on the held-back years (5.9 % and 7.1 %). A setting that wins only in flat years cannot
be picked in advance, because whether the years ahead will be flat is not known when a forecast is
made. A synthetic test checks that the fit
recovers a known traffic elasticity and weekday effect, and that its forecast follows a traffic
shock that last year's count misses.

**Detectability** (`horizon_errors`, `detectability`, `detection_power`). The error of the forecast
of an `n`-year total is measured the same way at every origin from 2006, leaving out every forecast
that covers 2020 or 2021. The origins 2022–2024, whose four-year fitting windows include the
lockdowns, are kept, because a forecast made today is fitted on such a window too; they
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
one year after a change (1,284 a year, the mean of 2022–2024) it is about 15 % (about 195 deaths a
year); for urban streets about 22 %; and it grows with the horizon, to about 36 % over five years,
because the drift grows faster than the count.

## 13. Assumptions tested

Every headline rests on an assumption the data can be asked about; these are the ones tested, all
listed with their results on the data page.

| Assumption | Test | Result |
|---|---|---|
| A year's count varies only by chance | dispersion around the 2013–2019 trend | fails for crashes and admissions; intervals widened (section 4); against 2019, the 2024 rise in admissions is beyond an ordinary year as a count and per tonne of road fuel, and no change in injury crashes is |
| Road fuel tracks the kilometres driven | measured interurban vehicle-km against national road fuel (the scopes differ, so a diagnostic of the proxy, not a rate) | cannot be tested on all roads: the measured kilometres cover only State, regional and provincial interurban roads; per measured km, interurban deaths in 2023 are +5 % on trend, inside the interval; 8.7 % to 11.2 % of interurban deaths are on roads the kilometres leave out (section 5) |
| CORES road fuel includes the biofuel blended into it, and a tonne means the same every year | each subtotal against the sum of its products, biofuels included, every month; the published biofuel share | holds: biofuel was 6.6 % of road fuel by mass in 2019 and 7.8 % in 2023, and as it carries less energy per tonne it cannot explain the rise in interurban kilometres per tonne (section 5) |
| The owner's age stands for the driver's | cars and km per B-permit holder by band | does not hold at either end (0.46 cars per B-permit holder at 18–34, 1.14 at 75+); per-km ratios published as ranges; deaths per driver involved need no kilometres (section 7) |
| The fall in deaths was in how deadly crashes are | exact frequency × severity split | holds; the split, not the product, depends on recording (section 4) |
| A forecast can show a change in the counts | out-of-sample forecast errors | only for large changes: a fall of about 15 % of interurban deaths is detected four times in five in the first year, smaller ones less often (section 11) |

## 14. Supporting analysis: associations in DGT crash records (not a predictive model) (`features.py`, `models.py`, `scripts/model.py`)

Listed under "Spain: supporting" in the navigation, with a note that says why. DGT's national crash
microdata carry no driver, vehicle or speed records, and their audit
([`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md), section 22) keeps them out of model training:
the DGT microdata do not train a predictive model. This analysis describes which recorded
circumstances go with a fatal or serious outcome, given an injury crash. The model card is
[`models/dgt_crash_severity.md`](models/dgt_crash_severity.md).

Two logistic regressions on all 875,013 crashes: the odds that a crash is fatal, and that it is
serious. Predictors are the circumstances the crash record carries: zone, road type, crash type,
junction, lighting, weather, surface, alignment, time of day, weekend, number of vehicles and year.
Road type comes from the road-type code itself (`TIPO_VIA`), with codes 4 to 6 as conventional
roads. DGT recoded most code-5 crashes as code 6 from 2021; grouping the two keeps that recoding
inside one level, and the model card states it. Each predictor is an ordered categorical whose
reference is its most common level. Missing states are separate levels, as in section 3, never
pooled with each other or with a recorded value. Three
exceptions, all named on the page: a level with fewer than 500 crashes merges into its reference;
the alignment "not applicable" code folds into "straight" because it is exactly the urban-street
zone and would otherwise duplicate the zone predictor; and a level with no event in a fit is left
out rather than estimated.

The fit is main effects only, by iteratively reweighted least squares in `numpy`, with a
cluster-robust sandwich covariance by province. It reports odds ratios with 95 % intervals, average
marginal effects, predicted probabilities for six named crash profiles, and three checks: a holdout
(fit on 2016–2022 with every predictor but the year, scored on 2023–2024), year-by-year stability
of the ten largest effects, and separation. The holdout checks that the associations carry across
years; it does not measure a predictive tool. Small levels are merged on the training years alone,
so the held-out years decide nothing about the model scored on them, and the Brier skill is
measured against giving every held-out crash the training years' share of the outcome: 4.2 % for
fatal and 5.3 % for serious (`q3_holdout_summary.csv`).

**Nuisance levels and the recording regime** (`features.is_nuisance`, `models.recording_regime`,
`models.regime_sensitivity`). The missing states record how a police force fills in the form,
which differs between forces and years. They are kept so that no crash is dropped, flagged
`is_nuisance` in the coefficient and marginal-effect tables, and never read as an effect.
Alignment "unknown" is the clearest case: 78,990 crashes, 95.7 % of them in the four Catalan
provinces (8, 17, 25, 43), where the level is 34.7 % of crashes against 0.5 % elsewhere, while
Cataluña has 24.9 % of all crashes (`q3_recording_regime.csv`). Both models are refitted without
those provinces (657,047 crashes, `q3_regime_sensitivity.csv`): for the fatal outcome all 32 odds
ratios that are not nuisance terms stay inside the full model's interval, and for the serious
outcome 30 of 32 do (zone "urban crossing" and road type "other road" move outside it). The
fatal odds ratio of alignment "unknown" moves from 0.12 to 0.44.

### 14.1 The adverse-conditions sensitivity (`models.adverse_conditions`)

The finding the page leads with, that rain, a wet road and junctions go with *lower* odds of a
death, is tested rather than asserted. Four levels (`ADVERSE_LEVELS`) are refitted under eight
variants (`ADVERSE_VARIANTS`):

- **Collinearity.** Weather and road surface describe overlapping states, so the full model can be
  splitting one effect between two columns. The variants drop surface, drop weather, drop both, and
  drop lighting. They show exactly that: on its own either predictor gives about 0.56, while the
  full model reports 0.86 for rain and 0.62 for wet. The page reports the single wet-conditions
  effect and says why.
- **Road context.** Three stratified fits (interurban roads, urban streets, conventional roads)
  hold the road context fixed by construction instead of adjusting for it, with the zone dropped
  as constant, and the road predictor too in the two road-specific fits. This is what shows that
  the hail-and-snow coefficient is not stable: it disappears on conventional roads alone.
- **Composition** (`level_composition`) reports where a level's crashes actually are, by province,
  zone and road type; `level_exclusions` refits with the level's most concentrated provinces
  removed. Hail and snow are concentrated but the coefficient survives the exclusions.

Both outcomes are run. The page proposes no mechanism; these data cannot identify one.

## 15. Supporting analysis: the 2006 case study (`policy.py`)

Listed under "Spain: supporting" in the navigation: the site makes no causal claim about policies
or campaigns, and this analysis shows how weak even a dated policy break is as evidence.

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
  road, and the average daily intensity on the state toll-motorway network (vehicles a day on the
  average kilometre, from 1990), a direct traffic measurement on a small and changing part of the
  network. The toll network's vehicle-kilometres are not used: they step up with the length of the
  network in service in July 2006, the very month of the break, as new sections open. Each series
  is added as its centred log, as a free covariate rather than an offset, so the data say how much
  of the movement it explains. Neither moves the estimate materially: the step does not track these
  traffic measures, and neither measures exposure. Neither is vehicle-kilometres on all Spanish
  roads by month, which does not exist.

Other sensitivity fits: quadratic trend; a knot fixed at January 2004; 24-hour deaths; interurban
and urban deaths separately; a level change without the slope term; a negative binomial whose
dispersion is set by moments from the Poisson fit; and the window extended to December 2009 with a
second break at the Penal Code reform.

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
every rate built against a counted denominator (residents, licence holders, B-permit holders,
drivers involved, circulating vehicles, vehicle-kilometres) carries an exact 95 % (Garwood)
interval. Ratios of two such rates carry a log-normal interval. The speed-infraction share among
drivers whose status is known carries a Wilson interval. Shares taken entirely within one source's
own counts (road-user shares, the night shares, deaths per 100 crashes, occupant deaths per fatal
involvement) are population counts, not samples, and are reported without intervals.

## 17. Figures, pages and wording

Figures are matplotlib SVG with no date metadata, so a rebuild in the same environment
(`requirements.lock`) changes nothing unless a number changes. One axis per chart, intervals drawn
where they exist, direct labels where a legend would be ambiguous, colour never the only encoding.
`figures.build_all` writes the national figures and then the regional crash-record figures
(Catalonia, Barcelona, models, generalisability; `microdata/charts.py`, skipped when the microdata
tables are not built), and deletes any SVG in its output directory that no longer has a caption, so
a removed figure cannot linger.

The navigation (`NAV_GROUPS` in `src/dgt_stats/site/components.py`) follows the source hierarchy of
`layers.py`:

- **Start**: the overview.
- **Spain: DGT and INE**: the seven findings in reading order (2019–2024, the long run, seasons,
  age and sex, vehicles, speed, factors).
- **Spain: supporting**: associations in DGT records (section 14) and the 2006 break (section 15),
  each opening with a note that says why it is a supporting analysis.
- **Catalonia**: serious and fatal crashes.
- **Barcelona**: crashes and people.
- **Models**: the severity models (section 21) and the deaths forecast (section 11).
- **Generalisability**: how far the results reach (section 22).
- **Sources and methods**: the four layers of data, and data and methods (with the assumptions
  tested, section 13).

Pages renamed in an earlier reorganisation (`older-drivers.html`, `context.html`) are kept as
pointers that refresh to their successors. The four withdrawn analyses (`simulator.html`,
`distraction.html`, `alcohol-drugs.html`, `enforcement.html`) are kept as short notices, not
redirects, that say what the page was, why it was withdrawn and which live pages hold what the
repository's own data show on the subject; no live page links to them.

Nearly every number in a page's sentences, the front-page digest included, is computed from the
result tables at build time, so a rebuilt table rewrites the text that quotes it; where a sentence
says which results lie inside or outside an interval, the build stops if the table no longer
supports it. Full result tables are copied into `site/tables/` and linked as CSV rather than
printed: the default on a page is one figure, one interpretation and one limits note per finding.
Tests check that every internal link and anchor resolves, every image has alt text, every page has
one heading and a description, that no page runs a script, and that each page's headline numbers
match the tables they come from. The site builder is the `dgt_stats.site` package: one module per
national page, the regional, model, generalisability and sources pages in `microdata_pages`, and the
shared furniture in `components`.

## 18. Reproducibility

- Raw inputs immutable and manifested; staging, processed and feature layers rebuilt from them by
  the command sequence in the README, with Python 3.11 and the library versions in
  `requirements.lock` (pandas 3.0.6, numpy 2.4.6, scipy 1.17.1, statsmodels 0.15.0, matplotlib
  3.11.2, scikit-learn 1.9.1, pyarrow 25.0.1). The lock file is compiled from `pyproject.toml` with
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

- DGT's national microdata are crash-level records only: no driver age, sex, alcohol, drug, speed,
  belt or helmet fields, so factor interactions and person-level risk are out of reach nationally.
  Person records exist only for Barcelona in 2025 (sections 20 and 21).
- Police-recorded circumstances, whose completeness varies by year and by severity.
- All model results are associations; the 2006 case study is a coincidence in time unless its
  falsification tests agree, and they only partly do.
- Vehicle-kilometres by vehicle type exist in detail for 2022 only (2024 by category, and each
  year on interurban roads only as heavy against other vehicles); kilometres by age are the
  owner's age; the speed
  report excludes two regions; road-type coding changed in 2021 (interurban conventional roads),
  2022 and 2024 (toll and free motorways, with 2023 back at the earlier split) and 2024 (urban),
  and the junction field changed in 2023.

## 20. The crash-level microdata layer (`src/dgt_stats/microdata/`, `scripts/microdata.py`)

Two regional sources add what the national files lack: individual records with real keys.

- **Catalonia, 2010–2023**: one row per crash with a death or serious injury (Servei Català de
  Trànsit export). No identifier: `cat_crash_id` is a surrogate on the hash-pinned file. The
  universe is conditioned on severity, so it supports frequency of serious crashes and severity
  among them, never the chance of a crash. Its fatal counts equal the DGT microdata's 24-hour
  counts province by province (`crosssource.py`), so its severity is read as the 24-hour
  definition.
- **Barcelona, 2025**: six Guàrdia Urbana tables sharing `Numero_expedient`: crashes, accident
  types (one-to-one), mediate causes and driver causes (one-to-many, aggregated to one row per
  crash before any join), people (person level, crash context joined many-to-one) and vehicle
  records (row meaning not established: only type presence is used).

Files are identified by their columns, de-duplicated by SHA-256 and by content, and a conflict
between two files claiming the same table and year stops the pipeline (`sources.py`). Column
names are normalised; values never are. Every cleaning rule that interprets a value is checked
on the data on every build and reported in the generated
[`DATA_QUALITY_MICRODATA.md`](DATA_QUALITY_MICRODATA.md): blank Barcelona counts are zeros
(the victim identity holds on every row only that way, and the person table agrees), the crash
file's UTM labels are exchanged (decided by magnitude, confirmed by a constant ED50/WGS84 offset),
`hor` is hours and minutes, and the Catalan speed-limit field is a code wherever the generic
limit applies. The vehicle table is audited in
[`BARCELONA_VEHICLE_AUDIT.md`](BARCELONA_VEHICLE_AUDIT.md). The rules for what may be joined to
what are in [`DATA_CONTRACT.md`](DATA_CONTRACT.md).

## 21. Severity models (`microdata/ml/`: `features.py`, `modelling.py`, `rules.py`, `reporting.py`)

Three tasks on real rows: fatal against serious among Catalan serious-or-fatal crashes (one row
per crash), serious-or-fatal injury of a Barcelona person (one row per person record with a
recorded victimisation), and a Barcelona crash with a serious or fatal injury (one row per
crash). A single feature catalogue classes every candidate column as safe, questionable, direct
leakage or excluded and generates [`ML_LEAKAGE_AUDIT.md`](ML_LEAKAGE_AUDIT.md); the primary model
of each task uses safe features only. Questionable features (police judgements of what
influenced a crash, recorded causes, and Catalan fields whose "not specified" level is far rarer
among fatal crashes, measured on the training years by `recording.py`) enter only a labelled
retrospective variant.

Each task compares a prior-only baseline, an L2 logistic regression and gradient-boosted trees,
each with a two-point grid chosen on validation data: in Catalonia the design is temporal (train
on the early years, choose on the next two, test on the last); in Barcelona the last three months
are the test set and cross-validation inside the training months is grouped by crash, so the
people of one crash never straddle a split (checked in code and in the tests). Metrics are
ROC-AUC and PR-AUC with bootstrap intervals (crashes resampled), Brier score and skill, balanced
accuracy, precision, recall and F1 at a threshold chosen on validation data, and the confusion
matrix, always with N and prevalence. Calibration is the slope and intercept of a logistic
recalibration; probabilities are shown as estimates only when a pre-declared rule passes.
Permutation importance on the test rows says what a model uses, not what causes severity.
Geography enters at three grains so that memorisation of places shows up as a gap between
training and test scores. No synthetic or oversampled rows are used. Model cards:
[`docs/models/`](models/).

Before a model is presented it must beat the simplest honest competitor: a lookup table of the
outcome share of each group in the training rows (crash subtype by zone detail in Catalonia, road
role by vehicle for Barcelona people, accident type for Barcelona crashes), smoothed toward the
prevalence and scored on the same test rows (`rules.py`). A model adds signal when its ROC-AUC
exceeds the table's by at least 0.02 and the paired bootstrap interval of the difference excludes
zero; a model that does not is replaced by its table on the site and kept only as a diagnostic.
The decision for every model, with where it works and fails, is generated in
[`MODEL_DECISIONS.md`](MODEL_DECISIONS.md) (`validation/decisions.py`).

## 22. Validation: transportability, representativeness and the outward path (`microdata/validation/`)

The source hierarchy (`src/dgt_stats/layers.py`) gives each dataset one role: DGT and INE are the
national context, the Catalan file is the crash microdata the severity model is trained on, the
Barcelona files are the rich microdata, and validation tests models across them without merging
records. How each source came to exist is compared against the same questions in
[`SOURCE_COMPARISON.md`](SOURCE_COMPARISON.md) (`source_profile.py`).

**Can the DGT microdata train a model?** Seven checks are declared before any result is read
(`dgt_audit.py`): one row per crash, target observed, definitions documented, construction
understood (rows reproduce the published totals), severity and inclusion definitions known,
fields recorded alike across provinces, and recording artefacts not dominating (a model that sees
only which fields were left unrecorded must reach less than half the lift of a model that sees
the recorded values). Unless all seven pass, the file remains the national analytical layer and
an external test domain for fields validated against the Catalan file on the crashes both hold;
the decision is regenerated on every run. The national transfer test itself is checked: same target (24-hour
death), same inclusion rule, no Catalan record in the test, coding validated, missingness and
prevalence reported. Generated: [`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md).

**Transportability** (`transport.py`). Each model is tested on records it could not have seen:
inside the Catalan file (Barcelona municipality from the rest and the reverse, each demarcation
left out, later Barcelona years from earlier years elsewhere); across sources with models
restricted to variables recorded the same way (validated on the overlap; road class and junction
fail); and in Barcelona, each district scored by a model trained on the others. Every transfer
score sits beside an in-domain reference (the same kind of model cross-validated inside the
target domain, including the test year of the temporal holdouts: the target domain's native
score) and the transfer gap, transferred minus native, is reported with the sample size, the
positives and the calibration; a negative gap is ranking lost in the move. A reweighting to the national mix is a sensitivity check, not a national model.

**Why Barcelona is harder** (`diagnosis.py`). The fall from the rest of Catalonia (in-domain) to
Barcelona (transferred) telescopes into a training-size cost (the rest of Catalonia with its
training folds cut to Barcelona's size), an intrinsic difference (that size-matched score
against Barcelona's own in-domain score, and against the rest of Catalonia's urban crashes) and
a transport cost (Barcelona in-domain minus transferred, on the same crashes). Feature loss is
measured separately, full against Barcelona-common features on the same rows. Domain-specific,
other-domain, pooled, pooled-with-flag and universal (common-feature) models are compared on the
same held-out crashes of each target domain (Barcelona, the rest of Catalonia, urban, interurban).

**Representativeness** is reported separately from transportability (`generalisability.py`):
how Catalonia and Barcelona differ from the rest of Spain on variables the DGT microdata record
identically, outcome shares, residents and severe crashes per resident by province. Neither
question answers the other.

**The outward path toward Spain.** Five stages: held-out rows of the same source; later years;
another region inside the source; another independently recorded Spanish dataset; national
aggregates showing whether the training population resembles Spain. A transfer stage passes when
the ROC-AUC interval stays above 0.5 and the transfer gap is no worse than -0.05;
stage 5 passes when no shared variable's mix differs by more than 0.02 (Jensen-Shannon). Only a
model that passes all five would be called potentially nationally transferable. Everything is
generated in [`GENERALISABILITY.md`](GENERALISABILITY.md) and `reports/model_metrics.json`.
