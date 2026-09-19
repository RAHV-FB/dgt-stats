# DGT Road Safety Analytics

Reproducible analysis of road crashes in Spain using official data from the Dirección General de Tráfico (DGT), exposure estimates, road context and published road-safety research.

> **Status:** early-stage portfolio project. The repository currently defines the research design and project structure; it does not yet publish analytical results.

## Objective

The project will move beyond raw crash counts to examine:

- which factors are associated with crash occurrence and severity;
- how alcohol, speeding, distraction and other factors interact;
- whether road design changes the likelihood or consequences of a crash;
- how trucks, buses and other vehicle types differ after accounting for exposure;
- whether prevention and enforcement campaigns are followed by measurable changes; and
- which findings support realistic, evidence-based prevention measures.

The end product should be useful both as a public road-safety analysis and as a transparent data-analytics portfolio project.

## Why this requires careful analysis

Road crashes are usually multi-factor events. The European Road Safety Observatory describes crash causation as an interaction between human, technical and organisational factors, rather than a simple exercise in assigning blame. Its recent reviews estimate that speeding is involved in roughly 30% of fatal crashes in Europe and alcohol in roughly 25%, while also warning that speed is often a contributing or aggravating factor rather than the sole cause ([main factors report](https://road-safety.transport.ec.europa.eu/document/download/a7428369-8eaf-4032-806e-ea08b46028c0_en?filename=ERSO-TR-MainCauses.pdf), [speed report](https://road-safety.transport.ec.europa.eu/document/download/9826c063-bc55-423e-84a3-24200dca3547_en?filename=ERSO-TR-speed_2026.pdf)).

That distinction is central to this project. If alcohol and speeding are both recorded, the analysis will not simply declare one of them the “real cause.” It will test:

1. their separate associations with crash severity;
2. whether their joint presence is associated with additional risk beyond the separate effects;
3. whether speeding could be part of the pathway through which alcohol affects outcomes; and
4. whether the available variables and research design are strong enough to support any causal interpretation.

## Research tracks

### 1. Crash factors and interactions

- Alcohol, drugs, excessive or inappropriate speed, distraction, fatigue and protective-equipment use.
- Single-factor versus multi-factor crashes.
- Interaction terms such as alcohol × speed, road type × speed and vehicle type × road environment.
- Separate models for crash incidence and injury severity.

### 2. Speed and road design

- Distinguish exceeding the legal limit from travelling too fast for the conditions.
- Compare road type, junctions, curvature, lighting, median, shoulder, surface and roadside context where data permit.
- Add road geometry, speed-limit, traffic-volume and weather data before making design-related causal claims.
- Examine both average speed and speed dispersion if suitable observed-speed data become available.

### 3. Trucks, buses and other vehicle types

- Compare involvement and severity using vehicle-kilometres, fleet size or another defensible exposure denominator.
- Separate risk to vehicle occupants from risk imposed on other road users.
- Investigate mass mismatch, blind spots, fatigue, working conditions and road compatibility.

European evidence illustrates why denominators and severity both matter: HGVs were involved in an estimated 4–5% of police-reported crashes but about 14% of road deaths, with most fatalities occurring among the other road users ([ERSO professional drivers report](https://road-safety.transport.ec.europa.eu/document/download/e19cf119-eed4-4cb3-b1fd-1fd0b4554992_en?filename=Road_Safety_Thematic_Report_Professional_drivers_trucks_and_buses_2023.pdf)). These figures are context, not results for Spain.

### 4. Prevention and enforcement campaigns

- Build a dated register of DGT campaigns, enforcement periods and relevant policy changes.
- Use interrupted time-series or difference-in-differences designs when a credible comparison group exists.
- Check pre-trends, seasonality, traffic exposure, simultaneous policies and displacement effects.
- Avoid interpreting a simple before/after comparison as causal evidence.

## Initial data inventory

The seed material currently available includes:

- DGT crash microdata for 2016–2024, one row per injury crash;
- DGT annual statistical tables for injury crashes in 2024;
- DGT historical crash series through 2024;
- driver-census data for 2023–2025 by province, sex, licence class and licence seniority;
- annual-distance estimates by vehicle type and vehicle age, based on ITV and fleet information;
- DGT reports on speed, older road users and Easter 2026 interurban fatalities; and
- the 2025 DGT driver-census workbook.

The official [DGT en Cifras](https://www.dgt.es/menusecundario/dgt-en-cifras/) portal also provides annual definitive statistics, historical series and annual crash microdata. See [`docs/data_sources.md`](docs/data_sources.md) for the working source register.

A file-by-file audit of everything currently in the repository, with reconciliation results and known quality issues, is in [`docs/data_inventory.md`](docs/data_inventory.md). The resulting analytics plan is in [`docs/analytics_plan.md`](docs/analytics_plan.md).

Raw source files are tracked under `data/raw/`, grouped by role (microdata, tables, exposure, reports), and never edited in place. `data/raw/manifest.csv` records size, SHA-256 and source URL for each file.

## Analytical standards

- **Counts are not risks.** Whenever possible, results will use vehicle-kilometres, trips, registered vehicles, licensed drivers or population as an exposure denominator.
- **Incidence and severity are different outcomes.** A factor may affect whether a crash occurs, how serious it becomes, or both.
- **Crash-only data have selection bias.** They can describe crashes and model severity among recorded crashes, but they cannot by themselves estimate population crash risk.
- **Association is not causation.** Causal language will be reserved for designs with explicit identification assumptions and sensitivity checks.
- **Unknown is not “no.”** Missing and untested alcohol, drug, speed and distraction fields will remain distinct from negative observations.
- **Uncertainty will be visible.** Estimates will include confidence intervals, sample sizes and robustness checks.
- **Transparent models come first.** Reproducible descriptive statistics and interpretable regression models will precede predictive machine learning.

Full details are in [`docs/methodology.md`](docs/methodology.md).

## Results so far

The first results are published as a static site built from the validated data: an overview with
the 2024 headline numbers, long-run trends since 1993, the timing of crashes and fatal crashes, the
distribution of deaths across road-user types, a geography page with province rates per resident and
per licence holder (exact Poisson intervals), an older-drivers page that keeps driver deaths fixed and
changes only the denominator (residents, licence holders, travel-weighted drivers, drivers involved in
crashes), and a data page with the sources, definitions and the reconciliation checks. The pages live
in [`site/`](site/) and are deployed to GitHub Pages from `main`; the tables and SVG figures behind
them are in [`reports/`](reports/). A severity page adds two logistic models of every crash since
2016: given that an injury crash happened, head-on collisions and pedestrian strikes carry about six
times the odds of a death of a side collision, interurban roads two to three times the odds of a
street, darkness without lighting about 1.4 times daylight; a fit on 2016–2022 scores the crashes of
2023–2024 with an area under the curve of 0.80 for a fatal outcome and stays calibrated across the
deciles of predicted risk.

Two findings from the older-drivers page: per resident, drivers aged 75 and over die less often than
drivers aged 35–64 (ratio about 0.7 in 2024), per licence holder more often (about 1.6), and per driver
involved in an injury crash about three times as often; and licence holders aged 75+ are involved in
injury crashes about half as often per licence as those aged 35–64, which mostly reflects how much less
they drive. No Spanish source gives the share of people who drive by age, so the travel-weighted
denominator is an estimate with stated limits ([`docs/phase3_plan.md`](docs/phase3_plan.md)).

A vehicles-per-kilometre page uses the one year, 2022, for which DGT publishes a distance estimate by
vehicle type. Per registered vehicle a heavy truck is in a fatal crash about ten times as often as a
car; per kilometre driven the ratio is 2.5, because a heavy truck covers four times a car's distance
in a year. Motorcycles are in a fatal crash ten times as often as cars per kilometre and their riders
die eighteen times as often. In fatal crashes involving a heavy truck, more than four in five of the
people killed were outside the truck, so a rate of a vehicle type's own occupant deaths, the only
per-type measure the microdata allow, misses most of the harm heavy vehicles are involved in
([`docs/phase5_plan.md`](docs/phase5_plan.md)).

A policy page runs two interrupted time series. The points-based licence of July 2006 coincided
with a 12 percent drop in the monthly level of road deaths (interval 6 to 17 percent) beyond the
pre-trend, larger than any of the 38 placebo breaks placed in 2002 to 2005 and stable under most
alternative fits; the speed-camera programme and the December 2007 Penal Code reform arrived close
enough that the drop cannot be attributed to the licence alone. The 90 km/h limit on conventional
roads of January 2019 shows a 13 percent fall relative to motorways in the clean window, but a
placebo break placed in January 2018 gives the same result, so no claim is made
([`docs/phase6_plan.md`](docs/phase6_plan.md)).

```bash
python scripts/ingest.py all        # raw -> data/interim, validation report
python scripts/build_tables.py      # data/interim -> data/processed (derived fields, labels)
python scripts/model.py             # reports/tables/q3_*.csv (severity models, about 30 seconds)
python scripts/analyse.py all       # reports/tables/q*.csv and reports/figures/*.svg
python scripts/build_site.py        # site/
```

## Planned outputs

- A reproducible data-ingestion and validation pipeline.
- A data-quality and coverage report.
- Exploratory analysis of trends, road users, vehicles, geography and severity.
- Exposure-adjusted rates and clearly defined denominators.
- Interpretable statistical models for factor interactions and severity.
- GIS analysis of road and location characteristics where coordinates permit.
- A campaign-evaluation case study.
- Publication-quality charts, maps and a concise final report or dashboard.

## Project structure

```text
data/                  Data layers; interim and processed contents are git-ignored
  raw/                 Immutable source files with a checksum manifest
  interim/             Parsed and partially cleaned data
  processed/           Analysis-ready tables
docs/                  Source register, methodology and project decisions
notebooks/             Ordered exploratory and reporting notebooks
reports/               Exported figures and tables
scripts/               Command-line ingestion and build entry points
src/dgt_stats/         Reusable Python package
tests/                 Data-contract and code tests
```

## Roadmap

- [x] Define the scope, standards and repository structure.
- [x] Audit each source, identify the unit of observation and build a data dictionary ([`docs/data_inventory.md`](docs/data_inventory.md)).
- [x] Create ingestion scripts with schema, range, uniqueness and reconciliation checks (`scripts/ingest.py`).
- [x] Reproduce official headline totals before producing new analysis ([`reports/tables/validation.csv`](reports/tables/validation.csv)).
- [x] Publish the first descriptive results (trends, timing, road users) as a static site.
- [x] Build the first exposure-adjusted trend analysis (province rates and the older-driver denominator ladder).
- [x] Model crash severity from the recorded circumstances (the crash-level file has no driver, vehicle or alcohol fields, so factor interactions such as alcohol × speed are out of reach until person-level microdata are obtained).
- [x] Compare vehicle types per registered vehicle and per kilometre driven for 2022, the one year with a distance estimate, with the limits of the modelled kilometres stated.
- [ ] Add road-design and geospatial variables.
- [x] Evaluate one well-defined policy intervention (the 2006 points licence, with the 2019 speed limit as a second, failed case) with placebo checks and stated confounders.
- [ ] Publish a final report and documented dashboard.

## Quick start

```bash
git clone https://github.com/RAHV-FB/dgt-stats.git
cd dgt-stats

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,geo]"

pytest
jupyter lab
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`.

## Reproducibility and data use

Every result should be traceable to a source file, transformation and defined population. Download dates, source URLs, checksums, row counts and validation outcomes will be recorded during ingestion. Published outputs will use aggregated, non-identifying data and will preserve the limitations stated by the original providers.

No licence has been selected for the repository yet. DGT and third-party data retain their own reuse terms.
