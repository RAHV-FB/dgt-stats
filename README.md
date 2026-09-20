# DGT Road Safety Analytics

Road safety in Spain, analysed from the open data of the Dirección General de Tráfico (DGT): 875,013
injury crashes from the 2016–2024 microdata, the yearbook series since 1993, the yearly statistical
tables, the driver census, the 2022 kilometre estimates and INE population. Every number on the site
is reconciled against DGT's published totals and reproducible from this repository with Python alone.

**The results are a static site:** <https://rahv-fb.github.io/dgt-stats/> (HTML and CSS, no
JavaScript; built by `scripts/build_site.py` from the committed tables and figures in `reports/`).

## What the site answers

The analytics plan ([`docs/analytics_plan.md`](docs/analytics_plan.md)) set nine questions after an
audit of the data. Each has a page.

| Question | Page | Method | Finding |
|---|---|---|---|
| How have crashes, deaths and injuries evolved since 1993? | [Trends](https://rahv-fb.github.io/dgt-stats/trends.html) | yearbook series, indexed lines, rates per vehicle and per resident | 1,785 deaths in 2024, 72 % fewer than in 1993; the fall stopped around 2013 |
| When do crashes happen, and when do they kill? | [Timing](https://rahv-fb.github.io/dgt-stats/timing.html) | hour × weekday and month × zone grids from the microdata | crashes in darkness are a quarter of interurban crashes but a third of interurban deaths |
| Who dies on the road? | [Road users](https://rahv-fb.github.io/dgt-stats/road-users.html) | death columns by road-user type, series since 1993 | vulnerable road users are 79 % of urban deaths; motorcyclist deaths (415 in 2024) are above their late-1990s average |
| Which provinces have high rates once exposure is considered? | [Geography](https://rahv-fb.github.io/dgt-stats/geography.html) | deaths per 100,000 residents and licence holders with exact Poisson intervals | rates run from 1.2 (Melilla) to 14.5 (Zamora) per 100,000, most intervals overlapping |
| Are older drivers at higher risk? | [Older drivers](https://rahv-fb.github.io/dgt-stats/older-drivers.html) | the same driver deaths against four denominators | 75+ drivers die 0.7 times as often as 35–64 per resident, 1.6 per licence holder, 3 per driver involved |
| Given a crash, what makes it fatal or serious? | [Severity](https://rahv-fb.github.io/dgt-stats/severity.html) | two logistic models on all 875,013 crashes, province-clustered intervals, 2023–2024 holdout | head-on collisions and pedestrian strikes carry six times the odds of a death; holdout AUC 0.80 |
| How dangerous are heavy vehicles per kilometre? | [Vehicles per km](https://rahv-fb.github.io/dgt-stats/vehicles.html) | 2022 involvement and occupant deaths over the ITV kilometre estimates | a heavy truck is in a fatal crash 10× a car per vehicle, 2.5× per km; four in five of those killed are outside it |
| Did a policy change coincide with a break in monthly deaths? | [Policy](https://rahv-fb.github.io/dgt-stats/policy.html) | segmented Poisson regression with placebo breaks; a two-group design for 2019 | July 2006 coincided with a 12 % drop beyond the trend (placebo rank 1 of 39); the 2019 limit fails its placebo, no claim |
| How large is the speed factor and where does it concentrate? | [Speed](https://rahv-fb.github.io/dgt-stats/speed.html) | driver tables 6.1 with the unknown share in view; DGT's speed report transcribed | 52 % of drivers have no speed record since 2016; the report puts speed in 7 % of crashes, two thirds of its deaths on interurban roads other than motorways and dual carriageways |

The [data page](https://rahv-fb.github.io/dgt-stats/data.html) lists the sources, the definitions
and the 434 reconciliation checks. Each phase has a plan with an outcome section that records what
was built and what deviated from the design: [`docs/phase3_plan.md`](docs/phase3_plan.md) to
[`docs/phase8_plan.md`](docs/phase8_plan.md).

## What could not be done, and why

The project was framed around factor interactions, road design and campaign evaluation. The audit
([`docs/data_inventory.md`](docs/data_inventory.md)) showed what the files in hand support:

- Factor interactions such as alcohol × speed require person-level data. The public microdata
  are one row per crash with no driver, vehicle or person fields: no age, sex, alcohol or drug test,
  speed, seat belt or helmet. The severity models therefore explain outcomes from where, when and
  how a crash happened, and the speed page describes the police judgement the two aggregate sources
  record. European evidence that speed and alcohol are each present in a large share of fatal
  crashes and often interact ([ERSO main factors](https://road-safety.transport.ec.europa.eu/document/download/a7428369-8eaf-4032-806e-ea08b46028c0_en?filename=ERSO-TR-MainCauses.pdf),
  [ERSO speed](https://road-safety.transport.ec.europa.eu/document/download/9826c063-bc55-423e-84a3-24200dca3547_en?filename=ERSO-TR-speed_2026.pdf))
  is context, not a result for Spain; testing it here needs the vehicle and person files that DGT
  does not publish for download.
- Road design needs geometry and traffic data. The microdata carry road type, junction,
  alignment, surface and lighting, all used in the severity models, but no coordinates, curvature,
  shoulder, median or traffic volume. The 2019 speed-limit case study, which would have benefited
  from section-level speeds and volumes, is the clearest casualty.
- A campaign register was replaced by two dated policy changes. DGT campaigns are not published
  as a dated list with enforcement intensity; the policy page uses the two changes with a legal date
  and a clean window, and states the confounders that arrived with them.
- Vehicle-kilometres exist for one year, so the heavy-vehicle comparison is a 2022 cross-section.

## Standards, as applied

- Counts are not risks: every rate names its denominator and year, and the older-drivers page shows
  the same deaths under four denominators because the answer changes with each.
- Unknown is not no: "not specified", "not applicable" and explicit unknown codes are kept apart
  in every table, the data page profiles them by year, and the speed page puts the drivers with no
  record in the same chart as those with one.
- Uncertainty is visible where a denominator or a sample gives it a meaning. Exact Poisson
  intervals on the rates built against an external denominator (residents, licence holders,
  circulating vehicles, vehicle-kilometres, drivers involved), log-normal intervals on the ratios
  between them, Wilson intervals on the speed-infraction share among drivers whose status is
  known, province-clustered intervals on the models and placebo distributions on the time series.
  Shares and ratios computed entirely within the microdata (the fatal share by hour and road
  group, the night shares, the vulnerable and road-user shares, deaths per 100 crashes, occupant
  deaths per fatal involvement and the raw speed-status shares) are shown without intervals.
- Association is not causation: model results are associations, and the policy page says
  "coincided with" unless the pre-trend, the placebos and the sensitivity fits agree.
- Transparent models first: descriptive tables, then interpretable regressions with their
  calibration and stability reported; no machine learning.
- Every number reconciles: 434 checks tie the interim data to DGT's published totals before any
  analysis runs, and the microdata match the yearbook exactly, year by year.

The methods as built, with the module that implements each, are in
[`docs/methodology.md`](docs/methodology.md); the methods the data could not support are in "What
could not be done, and why" above.

## Data

Raw files are tracked under `data/raw/`, grouped by role, never edited, and listed with size, SHA-256
and source URL in `data/raw/manifest.csv`. The register is [`docs/data_sources.md`](docs/data_sources.md);
the audit with reconciliation results and known quality issues is
[`docs/data_inventory.md`](docs/data_inventory.md); the build of the interim and processed layers is
described in [`data/README.md`](data/README.md).

| Group | Files | Used for |
|---|---|---|
| Crash microdata 2016–2024 | nine yearly workbooks, the code dictionary | timing, road users, severity, the 2019 case study, monthly deaths by road type |
| Yearbook series 1993–2024 | one workbook, 69 sheets | trends, occupant deaths by vehicle, the 2006 case study |
| Statistical tables 2014–2024 | chapter workbooks to 2019, one workbook per year from 2020 | province and month totals, vehicles involved, victims by mode, drivers by age, sex and infraction |
| Driver census 2014–2025 | text extracts and published tables | licence-holder denominators by province and age |
| INE population 2002–2025 | one CSV | resident denominators by province and age |
| ITV kilometre estimates 2022 | two workbooks and the methodology note | vehicle-kilometres by type and age; the circulating fleet |
| Travel and driving surveys | MOVILIA 2006–2007, ECEPOV 2021, EHMA 2008, ESRA shares | the travel-weighted driver denominator (MOVILIA 2006 and the ESRA shares); the others are registered for context |
| DGT thematic reports | speed factor, older road users, Easter 2026 | the speed page (transcribed), definitions |

## Reproduce

```bash
git clone https://github.com/RAHV-FB/dgt-stats.git
cd dgt-stats
python -m venv .venv && source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock          # exact versions behind the committed outputs
python -m pip install -e ".[dev]"                   # the package; keeps the pinned versions

python scripts/ingest.py all        # raw -> data/interim, speed report, 434 checks (about 6 minutes)
python scripts/build_tables.py      # data/interim -> data/processed (derived fields, labels)
python scripts/model.py             # reports/tables/q3_*.csv, the severity models (about 30 seconds)
python scripts/analyse.py all       # reports/tables/q*.csv and reports/figures/*.svg (under a minute)
python scripts/build_site.py        # site/
pytest                              # the test suite, the reconciliation checks among them
pytest -m slow                      # SHA-256 of every raw file against data/raw/manifest.csv
```

The result tables and figures under `reports/` and the site's HTML and CSS are committed, so the
pages can be read and reviewed without rebuilding; `site/figures/` is not committed, and
`python scripts/build_site.py` copies the SVGs from `reports/figures/` into it, so run it once
before opening the pages locally. The committed outputs were produced with the versions in
`requirements.lock`; with the dependency floors of `pyproject.toml` alone the numbers agree to the
precision printed on the pages but the SVG metadata and layout differ (`docs/methodology.md`,
section 10). A push to
`main` runs `.github/workflows/pages.yml`, which only renders `site/` from the committed tables and
deploys it; the data never rebuild in CI. Lint with `ruff check` and `ruff format --check` over
`src`, `scripts` and `tests`.

## Project structure

```text
data/                  raw/ is tracked with a manifest; interim/ and processed/ are rebuilt
docs/                  analytics plan, source register, audit, methodology, one plan per phase
notebooks/             not used: the scripts, tests and site replaced the planned notebooks
reports/               result tables (CSV), figures (SVG) and captions, all committed
scripts/               ingest, build_tables, model, analyse, build_site; fetch_ine rebuilds the
                       committed INE population extract, outside the sequence above
site/                  the published pages, rebuilt by build_site.py (figures copied in at build time)
src/dgt_stats/         the package: readers, derived fields, summaries, models, plots, site
tests/                 data-contract, reconciliation and code tests
requirements.lock      the exact library versions behind the committed tables, figures and pages
```

Package modules by role: readers (`io_microdata`, `io_tables`, `io_exposure`, `io_population`,
`io_activity`, `io_reports`), codes and labels (`codes`, `labels`, `agebands`, `vehicles`), derived
fields and validation (`derive`, `validate`), analysis (`summaries`, `rates`, `features`, `models`,
`policy`, `speed`), output (`plots`, `figures`, `site`).

## How it was built

The code, the documents and the pages were written with Claude Code, Anthropic's coding
assistant, working from written instructions and reviewed at each step. The choice of sources,
questions and methods, the reading of the results and the decision to publish each page are the
author's, and so is the responsibility for them. Every number is generated by the scripts from the
raw files, so the assistant's part can be checked the way anyone else's would be: rerun the
sequence above and read the tests. The phase plans under `docs/` record what was asked for, what
was built and where the two differ, and [`docs/final_review.md`](docs/final_review.md) records the
review pass that closed the project.

## What remains

- Person-level data: a request to DGT's Observatorio Nacional de Seguridad Vial for the vehicle
  and person files would unlock the factor-interaction work; the models and pages are built to take
  them.
- Road design: coordinates or road-section identifiers, with traffic volumes, would turn the
  road-type terms into a road-design analysis and give the 2019 case study a proper control.

## Licence and data reuse

The code is released under the [MIT licence](LICENSE), which allows commercial use. The data files
under `data/raw/` are not covered by it: each keeps the terms of the body that publishes it. DGT's
crash microdata are catalogued on datos.gob.es under its legal notice (name the source, do not
distort the meaning, keep the dates, imply no endorsement); DGT's legal notice grants no reuse
licence for its other files, which are redistributed here as public-sector information under Ley
37/2007 with the datos.gob.es conditions applied by this project's choice; INE population is under
Creative Commons Attribution 4.0; the Ministerio de Transportes MOVILIA workbooks may be reused with
attribution; the five Comunidad de Madrid MOVILIA tables may not be used directly for commercial
purposes; the ESRA reports offer no reuse licence, so none is archived here and the two shares
taken from them are short quotations with attribution. The terms and their URLs are in
[`docs/data_sources.md`](docs/data_sources.md) and on the data page.

Every result is traceable to a source file, a transformation and a defined population; source URLs,
checksums, row counts and validation outcomes are recorded during ingestion. Published outputs are
aggregated, non-identifying, and preserve the limitations stated by the original providers.
