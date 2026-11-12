# Methodology

How the numbers on the site are made. The results themselves are in [`FINDINGS.md`](FINDINGS.md)
and on the site. What each dataset may be used for and joined to is in
[`DATA_CONTRACT.md`](DATA_CONTRACT.md). The files, their terms and their quirks are in
[`data_sources.md`](data_sources.md).

Most of the study is descriptive analysis of official data. Each count of deaths or crashes is
divided by a denominator that could contain it, and each analysis is compared with the other ways
the same data could have been read. The regional crash records add a severity model, which is kept
only because it was tested against a simple table. Every result comes from rows of the files in
`data/raw/`. Studies published elsewhere may define a variable or a method but never supply an
observation, a coefficient or an effect size. One value is typed in from a document: the
road-to-straight-line distance ratio of driving trips (1.45) and the 2021 distance benchmarks, from
the EMEF 2021 distance report, which measured them on the same survey's trips and is not archived.

## Units and records

| Source | Unit | Years | Used for |
|---|---|---|---|
| DGT crash microdata | injury crash | 2016-2024 | associations with severity, the crash explorer, deaths per measured kilometre by road class |
| DGT yearbook series | year, month or province totals | 1993-2024 | long-run trends, seasons, the 2006 licence, reference totals |
| DGT yearly statistical tables | aggregate cells | 2014-2024 | vehicles involved by type, driver deaths and involvements by age and vehicle |
| DGT kilometre estimates (ITV) | fleet and mean kilometres by vehicle type and age; vehicles and kilometres by category | 2022, 2024 | vehicle rates per kilometre; the national car-kilometre total for driver age |
| DGT driver census | licence holders by province, sex and age | 2014-2025 | casualties per licence holder |
| DGT speed-factor report | year, factor, road type | 2014-2023 | speed and other recorded factors |
| INE population | residents by province, age and sex | 2002-2025 | rates per resident |
| CORES road fuel | month | 1996- | traffic denominator for long-run and seasonal risk |
| Toll-motorway traffic | month | 1990- | a traffic index shown beside deaths, never a denominator |
| Ministerio de Transportes, yearbook table 1.2.14 | year, road type | 2004-2023 | measured interurban vehicle-kilometres |
| Servei Català de Trànsit | crash with a death or serious injury | 2010-2023 | Catalonia |
| Guàrdia Urbana | crash; person record | 2025 | Barcelona |
| EMEF, EDM2018, MOVILIA | survey trips and respondents | 2006-2024 | car-driving kilometres by driver age |

The DGT crash microdata have no vehicle or person rows, so no national result is estimated at the
driver, vehicle or victim level. Where the national pages speak of drivers, they use DGT's
aggregate yearly tables, which count drivers by age, sex, vehicle and recorded infraction but
cannot be linked to crashes. Person records exist only in the Barcelona files.

Raw files are never edited. They are listed in `data/raw/manifest.csv` with a SHA-256 checksum, the
source URL where one was recorded and the name each file was downloaded as. `ingest.py` parses the
national files into typed tables (`data/staging/dgt/`), `build_tables.py` adds derived fields
(`data/processed/`), and `model.py`, `analyse.py` and the other scripts write the result tables.
`microdata.py` builds the Catalan and Barcelona layers. The site reads only the committed result
tables.

## Reconciliation with DGT's published totals

No summary is published until the crash microdata, the yearbook tables and the driver census agree
with DGT's own totals (`validate.py`, enforced by `tests/test_validate.py`). The checks compare:

- crashes, deaths, hospitalised and non-hospitalised people per year with the yearbook, on both the
  30-day and the 24-hour definition, exactly;
- 2024 crashes and deaths by province and by month with the 2024 tables, exactly;
- deaths by means of transport and vehicles involved in the yearly tables with the microdata;
- driver deaths in the yearly tables with the yearbook series, in both zones;
- the driver census text files with the published census tables, and the blocks of table 6.1 that
  publish a total with table 4.2;
- the speed report's own crashes and deaths with the microdata restricted to its provinces;
- that each crash has one identifier per year and that every code is in the dictionary or is a
  documented missing state.

Some inputs have no separate total to check against, so their readers check them instead. The
kilometres by category in the 2024 estimates must add up to the same release's published totals,
the monthly traffic series must be complete, each CORES subtotal must equal the sum of its product
columns, and the Ministry's annual kilometres by road type must add up to the published total.
Smaller sources are covered by unit tests of their internal totals.

Where two publications of the same quantity differ, one is kept for as long as it exists rather
than mixing them. Licence holders by age come from the published class-by-age tables to 2023 and
the text files from 2024. 24-hour and 30-day deaths are never combined. Provisional figures are not
used.

## Definitions

- **Injury crash**: at least one person killed or injured. **Fatal crash**: at least one death.
- **Death**: within 30 days of the crash, DGT's definition from the yearbook. The 24-hour count,
  which the microdata and the Catalan file use, is lower. The two are never mixed.
- **Serious crash**: at least one death or one person admitted to hospital for more than 24 hours.
- **Zone**: interurban road, or urban street and crossing. **Road group**: motorway, dual
  carriageway, conventional road, urban street, other, from DGT's road-type code.
- **Night** means the lighting was recorded as no natural light, not a clock hour. **Weekend**
  means Saturday, Sunday and Friday from 20:00.
- **Missing states** are kept apart everywhere: not specified, not applicable, a field's explicit
  unknown code, and an empty cell. Placeholders such as kilometre point 9999 count as not observed,
  so a year that swapped an empty cell for a placeholder does not read as better recording.

## Rates and denominators

Every rate names its denominator and what it misses.

- **Residents** (INE): a population rate, not a risk. It ignores how much people travel.
- **Licence holders** (DGT census): counts who may drive, not who does. Drivers with a licence
  differ by age and sex in how much they drive.
- **Vehicles** (DGT register and ITV): the circulating fleet, with mean kilometres by type from
  inspections. Crash counts include foreign vehicles and the kilometres include driving abroad, so
  the two sides do not cover quite the same vehicles.
- **Road fuel sold** (CORES): covers every road, matching deaths on all roads. It is tonnes sold,
  not kilometres. It leaves out electric and gas vehicles and mixes freight with private travel,
  so deaths per tonne are a proxy rate and are labelled so.
- **Measured kilometres** (Ministerio de Transportes): vehicle-kilometres on the state, regional
  and provincial interurban networks only. Urban streets and some interurban roads are outside
  them.
- **Kilometres by driver age**: not measured nationally. They are estimated from travel surveys
  (see the driver paragraph below).

Death rates are split where the data allow into how often crashes happen (frequency) and how
deadly they are once they happen (severity).

## Intervals

- Counts of deaths, crashes or involved drivers are treated as Poisson with a known denominator,
  and a rate against a counted denominator carries an exact 95% (Garwood) interval. Ratios of two
  rates carry a log-normal interval.
- Trends use quasi-Poisson models. The dispersion is estimated from year-to-year scatter and floored
  at 1, so a series that scatters less than chance does not get an interval narrower than Poisson
  noise.
- Shares of a known total, such as the speed share among drivers whose status is known and the
  fatal share in the crash explorer, carry a Wilson interval. Shares taken entirely within one
  source's own counts are population counts and carry no interval.
- Involvement per kilometre by driver age uses survey-based kilometres. Its interval comes from a
  bootstrap over the survey's respondents and from the sampling of the crash counts.
- A sampling interval is not a range across assumptions. Where the denominator rests on a choice
  (how far older drivers drive, how the survey region stands for Spain), the results carry a range
  across the alternatives beside the interval, and the text reports the range.

## The analyses

**Long-run trends** ([Long-run trends](https://rahv-fb.github.io/dgt-stats/long-run.html),
`risk_trends.py`). A segmented log-linear (joinpoint) trend is fitted to 30-day deaths, 1993-2019,
in three forms: the count, occupant deaths per registered vehicle, and the count with road fuel as
offset. The number of turning points is chosen by a quasi-likelihood information criterion, taking
the simplest model within two points of the best. Segment slopes are annual percentage changes. From
2020 each measure is projected from its last segment with a prediction interval, and later years
are read against it. The since-2019 section compares recent years with the projections and with
deaths per measured kilometre on interurban roads (`road_class.py`). Because the choice of last
segment moves the projection, the page shows more than one.

**Seasons** ([Seasons](https://rahv-fb.github.io/dgt-stats/seasons.html), `seasonality.py`). Monthly
deaths are divided by the mean month of their own year and averaged over 2014-2019 and 2022-2024,
leaving out the pandemic years. Month effects come from quasi-Poisson models with year effects.
Deaths per tonne of road fuel show whether the summer peak survives a traffic denominator. Fuel is
not distance, so the page cannot say whether summer is riskier per kilometre.

**The 2006 points licence** ([policy](https://rahv-fb.github.io/dgt-stats/policy.html),
`policy.py`). A segmented Poisson regression of monthly deaths on a pre-trend, month-of-year terms,
a level change at July 2006 and a slope change, fitted to January 2000 to November 2007 with
Newey-West standard errors. The pre-trend is chosen on the months before the intervention only.
Calendar-matched placebos refit the same model with the break at July of every other year. Deaths
usually peak in summer, so a fall after one July is compared with falls after other Julys. The
estimate is read together with its sensitivity to the pre-trend. No causal claim is made.

**Drivers** ([Drivers](https://rahv-fb.github.io/dgt-stats/drivers.html),
`driver_risk.py`, `exposure_risk/`, `emef/`, `edm2018.py`). Three measures are kept apart. Deaths
per driver involved in an injury crash are counted from DGT's tables. Casualties per licence holder
use the census. Involvement per kilometre needs kilometres by driver age, which no national source
gives. They are estimated by applying the working-day car-driving distance by age from the EMEF
survey (Barcelona area) to DGT's national car-kilometre total, with the Madrid survey's age profile
and the older MOVILIA surveys as alternatives, and a check in Barcelona on working days. The
estimates, their bootstrap intervals and the ranges across assumptions are described in
[`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md). The one table of ranges is
`risk_national_ranges.csv`. Sex rates are per licence holder, by sex and licence class.

**Vehicles** ([Vehicles](https://rahv-fb.github.io/dgt-stats/vehicles.html), `vehicles.py`). A 2022
cross-section. Vehicles involved in injury and fatal crashes by type are divided by vehicle-kilometres
from DGT's ITV estimates, for six groups: motorcycles, mopeds, cars, vans with light trucks, heavy
trucks and buses. Rates are per billion vehicle-kilometres, with exact Poisson intervals.
Kilometres by vehicle type exist for all roads only, so rows by zone carry rates per vehicle but
not per kilometre. The kilometres describe a normal year imputed from inspection readings, not
2022 travel.

**Speed and other recorded factors** ([factors](https://rahv-fb.github.io/dgt-stats/factors.html),
`factors.py`, `speed.py`). From DGT's speed-factor report and yearly tables: the share of crashes
and deaths with each factor recorded, and deaths per 100 crashes with and without inappropriate
speed on the same kind of road. The report covers all regions except two. Police-recorded factors
are judgements, and how often they are recorded varies by year and by severity, so these are
associations open to recording bias.

**Crash circumstances in Spain** ([severity](https://rahv-fb.github.io/dgt-stats/severity.html),
`features.py`, `models.py`, `scripts/model.py`). Logistic regressions on all injury crashes in the
microdata give the odds that a crash is fatal or serious, given the zone, road type, crash type,
junction, lighting, weather, surface, alignment, time of day, weekend, number of vehicles and year.
They are main-effects fits with a cluster-robust covariance by province, reported as odds ratios
with intervals, average marginal effects and predicted probabilities for named crash profiles. Their
checks are a holdout (fit on 2016-2022, scored on 2023-2024), year-by-year stability of the largest
effects, and separation. The records for the four Catalan provinces code the junction flag the wrong
way round from 2023, and a sensitivity fit reads it the other way. These are associations, not a
prediction tool: the national microdata hold no driver, vehicle or speed fields.

**Catalonia and Barcelona** ([Catalonia](https://rahv-fb.github.io/dgt-stats/catalonia.html),
[Barcelona](https://rahv-fb.github.io/dgt-stats/barcelona.html), `microdata/`,
`scripts/microdata.py`). The Catalan file holds crashes with a death or serious injury, so it
supports the frequency of serious crashes and severity among them, never the chance of a crash. Its
fatal counts equal DGT's 24-hour counts province by province and year (2016-2023), so its severity is
read on the 24-hour definition. The Barcelona files are six tables sharing a case number. Aggregates
of causes and vehicle types are built to one row per crash before any join. Files are identified by
their columns and de-duplicated by checksum and content, and two different files claiming the same
table and year stop the build. Cleaning rules that interpret a value (blank Barcelona counts are
zeros, the crash file's UTM labels are exchanged, the Catalan speed field is a code where the generic
limit applies) are checked on every build. Neither source has a measure of travel, so both describe
severity among recorded crashes.

**The Catalan severity model** ([model page](https://rahv-fb.github.io/dgt-stats/severity-models.html),
`severity_model.py`, `scripts/severity_model.py`; described in [`SEVERITY_MODEL.md`](SEVERITY_MODEL.md)).
A penalised logistic model of whether a Catalan severe crash was fatal. It is evaluated by nested
rolling origin: each year's penalty and specification are chosen on earlier years only. It is
compared on unseen later years with a simple table of outcome shares by crash type and place, and
its calibration and ranking (area under the curve) are reported with the table's. Within-Catalonia
tests vary the year, the province and the road. The model has not been tested outside Catalonia.

## Reproducibility

The pipeline, in order, is in the [README](../README.md#reproduce). It uses Python 3.11 and the
versions in `requirements.lock`, compiled with hashes from `pyproject.toml`.

- Raw inputs are immutable and manifested. Staging, processed and feature layers are rebuilt from
  them.
- All logic is in `src/dgt_stats/` and `scripts/`. There are no notebooks.
- The fitted models run with a single BLAS thread (`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
  `MKL_NUM_THREADS=1`) so that their coefficients agree to the digits written. Seeds are fixed in the
  modules that draw random numbers (the severity model, the survey bootstraps). Result tables are
  written with a fixed number of significant digits so that last-bit differences between library
  versions do not reach the committed files.
- CI rebuilds every table, figure and document from the raw files and fails if a table or
  document differs from the committed copy, or a figure by more than a tenth of a point (a
  figure's coordinates carry last digits that differ between machines). It then builds the site
  and compares it with the committed pages.
- `pytest` runs the reconciliation, the data-contract, analysis and site tests. `pytest -m slow`
  checks every raw file against its checksum in `data/raw/manifest.csv`.
- Numbers on the site and in `FINDINGS.md` are computed from the committed tables. Tests guard the
  qualitative claims, so a sentence that the tables stop supporting fails the build.

## Limits

- DGT's national microdata are crash-level records only: no driver age, sex, alcohol, drug, speed,
  belt or helmet fields. Person-level risk and factor interactions are out of reach nationally.
- Police-recorded circumstances vary in completeness by year and by severity, and road-type coding
  changed in several years.
- All model results are associations. The 2006 analysis describes a fall that coincides in time with
  a policy change, and its placebo tests show that similar falls occur without one.
- Vehicle-kilometres by vehicle type exist in detail for 2022 only. Kilometres by driver age are
  estimated from regional travel surveys and carried to Spain, and the public EMEF files stop at 65
  and over.
- The regional crash records have no measure of travel. The Catalan file holds only serious crashes.
- No record is linked across sources.
