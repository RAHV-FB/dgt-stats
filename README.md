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
distribution of deaths across road-user types, and a data page with the sources, definitions and the
reconciliation checks. The pages live in [`site/`](site/) and are deployed to GitHub Pages from
`main`; the tables and SVG figures behind them are in [`reports/`](reports/).

```bash
python scripts/ingest.py all        # raw -> data/interim, validation report
python scripts/build_tables.py      # data/interim -> data/processed (derived fields, labels)
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
- [ ] Build the first exposure-adjusted trend analysis.
- [ ] Analyse factor co-occurrence and alcohol × speed interactions.
- [ ] Add road-design and geospatial variables.
- [ ] Evaluate one well-defined campaign or policy intervention.
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
