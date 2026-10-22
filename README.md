# Road safety in Spain

[![Checks](https://github.com/RAHV-FB/dgt-stats/actions/workflows/ci.yml/badge.svg)](https://github.com/RAHV-FB/dgt-stats/actions/workflows/ci.yml)

**Live site: <https://rahv-fb.github.io/dgt-stats/>** · [Where every result comes from](docs/catalogue.md) ·
[Documents](docs/README.md) · [Reproduce](#reproduce) · [Methodology](docs/methodology.md) ·
[Data contract](docs/sources/contract.md)

A statistical study of road deaths and injuries in Spain, built only from published data. It asks
how road safety has changed since 1993 and how it differs between drivers, vehicles and roads once
each count of deaths or crashes is set against a measure of who could be on the road or how much
they travel, and what police crash records with more detail than the national file show about how
deadly a crash is once it has happened. Every result is computed by the code in this repository,
from the files in [`data/raw`](data/raw) and a few values typed into the code from cited documents
(see [Methodological rules](#methodological-rules)). Results are not repeated here, where they
could drift from the data: they are on the site and in the generated documents.

## How the project is organised

The project is divided into five sections by **where the data come from**. The same five sections
organise the code, the pipeline, the result tables and the documents (in folders named `national`,
`drivers`, `regional`, `models` and `sources`) and the site's menu (under the names below), so a
result can be followed from its page back to its table, its code and its source files.

| Section | What it answers | Sources | Code · results · documents | On the site |
|---|---|---|---|---|
| **National statistics** | How deaths and injuries in Spain have changed since 1993, and how they differ between vehicles, roads, months and recorded circumstances, set against residents, licence holders, vehicles, fuel and kilometres | DGT crash microdata, yearbook series and tables, driver census, kilometre estimates and speed report; INE population; Ministry of Transport traffic and road-km; CORES fuel | [`src/dgt_stats/national`](src/dgt_stats/national) · [`reports/tables/national`](reports/tables/national) · [`docs/national`](docs/national) | Long-run trends, Since 2019, Seasons, The 2006 points licence, Vehicles, Speed, Recorded factors, Crash circumstances in Spain |
| **Drivers** | How often drivers of each age and sex are in crashes per licence holder and per kilometre driven, and how often a crash kills them | DGT driver tables, census and kilometres; INE population; the EMEF, EDM2018 and MOVILIA travel surveys, which put kilometres on driver ages, with figures typed from the EMEF 2021 distance report and the RACC 2013 survey; the Idescat census; CORES fuel and toll-motorway traffic (the km outside the surveys); Barcelona's crash records for a working-day check | [`src/dgt_stats/drivers`](src/dgt_stats/drivers) · [`reports/tables/drivers`](reports/tables/drivers) · [`docs/drivers`](docs/drivers) | Drivers |
| **Catalonia and Barcelona** | What police crash records with more detail show: Catalonia's crashes with a death or serious injury (2010–2023) and Barcelona's crashes and people (2025) | Servei Català de Trànsit; Guàrdia Urbana; DGT crash microdata and INE population (province-year comparison only) | [`src/dgt_stats/regional`](src/dgt_stats/regional) · [`reports/tables/regional`](reports/tables/regional) · [`docs/regional`](docs/regional) | Catalonia, Barcelona |
| **Severity model** | Which severe crashes in Catalonia were fatal, as a model kept only if it beats a simple table on later records, and how far the models hold elsewhere | the Catalan records (training of the published model); Barcelona's records (two research models, and tests); DGT's records and series, INE population and CORES fuel (tests, and the review of the withdrawn forecast) | [`src/dgt_stats/models`](src/dgt_stats/models) · [`reports/tables/models`](reports/tables/models) · [`docs/models`](docs/models) | Crash severity model, Model method and tests |
| **Data and methods** | What every raw file holds, how each source came to exist and how the results are made | every raw file | [`src/dgt_stats/sources`](src/dgt_stats/sources) · [`reports/tables/sources`](reports/tables/sources) · [`docs/sources`](docs/sources) | Data sources and scope, Methodology |

The interactive tools on the site's Explore menu each compute from one section's tables; the crash
statistics explorer also takes the caveat on DGT's junction coding from the severity model's audit
of the DGT records.

**What comes from where.** [`docs/catalogue.md`](docs/catalogue.md) is the map: for every section
its sources, its pipeline stages, its pages and every one of its tables with the sources it is
computed from, and for every source the files it owns. Each folder of result tables has a `README.md` listing every table, what
it holds, the sources it is computed from, the stage that writes it and the page that publishes it.
On the site, every analysis page's closing "Data and method" block lists the sources of the tables it
links. All three are generated from one registry, [`src/dgt_stats/catalogue.py`](src/dgt_stats/catalogue.py),
and the tests fail if a table, a raw file or a source is missing from it.

No record is linked across sources and there is no merged crash database: sources meet only at an
aggregate both genuinely have (province and year) or as a model trained on one and tested on
another's real records ([data contract](docs/sources/contract.md)).

## Repository layout

```text
data/raw/<publisher>/   every source file, never edited, listed with its checksum in manifest.csv
data/staging, processed, features/   the data layers the pipeline rebuilds (not committed)
src/dgt_stats/
  catalogue.py          the sections, every source and every result table: the project's map
  pipeline.py           every stage of every section, in the order they run
  national/  drivers/  regional/  models/  sources/   one package per section
  charts/               the figures, with their fonts
  site/                 the static site: one module per page, the tools, styles and fonts
  paths.py  rates.py  agebands.py  regions.py         shared helpers
scripts/run.py          the one command that builds everything (tools/: utilities outside the build)
reports/tables/<section>/   result tables (CSV), committed, each folder with a README index
reports/figures/        figures (SVG) and their captions; narrow/ holds the phone versions
reports/models/         the calculator's exported model
reports/model_metrics.json   the severity models' test metrics (models.validate)
docs/                   documents by section, the methodology and the catalogue (docs/README.md)
site/                   the built site, committed
tests/<section>/        tests by section; tests/test_catalogue.py keeps the map in step
```

## Reproduce

```bash
git clone https://github.com/RAHV-FB/dgt-stats.git
cd dgt-stats
python -m venv .venv && source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock          # pinned and hashed

python scripts/run.py --list      # every stage, in order, with what it does and writes
python scripts/run.py all         # everything, in order (about 95 minutes on four cores)
python scripts/run.py national    # or one section: national, regional, drivers, models,
                                  # sources, charts, site
python scripts/run.py national.ingest --force   # or one stage
pytest                            # the tests (pip install -e .[browser] adds the browser tests)
pytest -m slow                    # SHA-256 of every raw file against data/raw/manifest.csv
```

A full build runs the sections in the order their inputs require: national (staging, 482
reconciliation checks, the processed crash table, the result tables), regional (the Catalan and
Barcelona tables), drivers (the travel surveys and the rates per kilometre), models (fits,
validation, the calculator and the model review), the national model cards, the source documents,
the figures, the site and finally the catalogue. Each stage runs in its own process; the
travel-survey stages run on one BLAS thread so that their tables reproduce on any machine. Refitting
the severity models on another machine can move the last digit of a few model scores; the committed
tables are the reference.
`national.withdrawn` (the withdrawn forecast's tables, slow) and `regional.organise` (filing new
regional downloads) run only by name.

Raw files are tracked under `data/raw/<publisher>/` with their size, SHA-256, source URL, a
description and the date added in `data/raw/manifest.csv`, which also gives the name a file was
downloaded as where it was filed under a new one ([`data/README.md`](data/README.md)). The staging,
processed and feature layers are rebuilt by the pipeline and not committed. Result tables, figures,
generated documents and the site's HTML are committed, so the pages can be read and reviewed
without rebuilding.

Every pull request and every push to `main` runs [`ci.yml`](.github/workflows/ci.yml): Ruff, then
the national and regional data layers from the raw files, a check that every table and document
they regenerate matches the committed copy, and `pytest`; a second job builds the site, checks it
matches the committed pages and tests it in a browser. CI does not refit the models or rerun the
validation (about half an hour); the tests that need their outputs read the committed tables. A
push to `main` that touches the site or its inputs runs [`pages.yml`](.github/workflows/pages.yml),
which renders `site/` from the committed tables and publishes it.

## Methodological rules

- The national data are reconciled before they are analysed: 482 checks tie the DGT crash
  microdata, yearbook tables, driver census and speed report to DGT's published totals
  (`src/dgt_stats/national/reconcile.py`). The Catalan file's fatal crashes equal DGT's 24-hour
  counts province by province, and the rules that interpret regional values are checked on every
  build ([regional data-quality report](docs/regional/data_quality.md)).
- Every rate names its denominator, chosen to contain its numerator in population, geography and
  period. Where it cannot, the page says so: visitors in rates per resident, foreign and unlicensed
  drivers in rates per licence holder, foreign vehicles in rates per vehicle, and kilometres by
  driver age estimated from a regional travel survey. No denominator is attached to an individual
  crash.
- A predictive model is compared with a simple descriptive table on later records it never saw,
  and is kept only if it beats the table by a margin set in advance. Its probabilities are read as
  estimates only if they pass a calibration rule; otherwise it is used for ranking only. A model
  that does not beat its table is replaced by the table. Every model's decision is in
  [`docs/models/decisions.md`](docs/models/decisions.md) and its card in
  [`docs/models/cards/`](docs/models/cards).
- An external test is always reported beside a model trained in the test population, with the
  gap, the sample size and the number of positive cases
  ([generalisability report](docs/models/generalisability.md)).
- Negative results are reported: models that do not beat their table, weak transfer, and recording
  differences between sources and zones.
- Nearly every number in the site's sentences is computed from a committed result table at build
  time, and qualitative claims stop the build if the tables no longer support them.
- Published studies may define a variable or a method, but never supply an observation or a
  coefficient. Analyses whose results came from coefficients in published studies (a speed-law
  simulator, distraction and drink-driving models, an enforcement comparison) were withdrawn; so
  was the monthly deaths forecast, which did worse than last year's count on the years it had not
  seen. Two exceptions remain, and the catalogue lists both as sources typed from documents that
  are not archived. The first is the ratio of road to straight-line distance for driving trips
  (1.45) and the 2021 distance benchmarks in `src/dgt_stats/drivers/emef/distance.py`, typed from
  the EMEF 2021 distance report (Institut Metròpoli for the ATM, October 2022, Table 1), which
  measured them on the same survey's 2021 trips. The report could not be found again, so they rest
  on the transcription ([driver-age exposure study](docs/drivers/driver_age_exposure.md),
  [EMEF inventory](docs/drivers/emef_inventory.md)). The ratio scales every age group's kilometres
  alike, so it moves the rates per kilometre but hardly the ratios between ages. The second is the
  Fundació RACC 2013 survey of licence holders aged 65 and over: the shares who do not drive and
  the days a week the others drive (slides 5, 11 and 19 of its published dossier) are typed into
  `src/dgt_stats/drivers/exposure_risk/national.py` and not archived, because RACC grants no
  licence to reuse its documents. They set the upper limit on men's kilometres at 75 and over in
  one of the four splits of the 65-and-over kilometres, and so the lowest 75+ combination not
  marked as at odds with men's driving ([source register](docs/sources/register.md)).

## What the data cannot do

- The regional crash records carry no measure of travel (trips or kilometres), so the Catalan and
  Barcelona crash analyses describe severity among recorded crashes, not rates per journey or
  kilometre. The one exception is the working-day check of involvement per kilometre in
  Barcelona, whose kilometres come from the EMEF travel survey.
- No crash file records vehicle speeds: the Catalan speed field is the road's posted limit.
- No national source measures kilometres by the driver's age. They are estimated from one
  region's working-day survey applied to Spain, so per-kilometre comparisons by age carry
  sensitivity ranges beside their confidence intervals, and at 75 and over a conditional
  estimate (Madrid's 2018 age pattern) is shown beside the sensitivity range.
- There are no person records nationally or in Catalonia, and in Barcelona no key links a recorded
  cause to the driver or vehicle concerned.
- No record is linked between sources: they share no identifier, and matching on date or place is
  not attempted.
- No result is a causal effect: every result is descriptive, an association or a prediction, and a
  police-recorded factor is a judgement, not a measured cause.

## How it was built

The project was developed through a reproducible, source-driven workflow. The research questions,
the choice of sources, the statistical design, the interpretation, the review and the decision to
publish each result are the author's, and so is responsibility for them. AI coding assistants,
including Claude Code, ChatGPT Work and GitHub Copilot, were used during implementation, debugging,
data-processing work and review. All published results are generated from the recorded source data
and can be reproduced from this repository, except two transcribed inputs (the EMEF 2021 distance
figures and the RACC 2013 survey figures, above), which can be checked only against their
published reports. The audit trail of the 2026 rebuild (the baseline, the claim ledger, the
statistical audit, the reviews and the final report) is kept in [`docs/history/`](docs/history);
it describes earlier states of the repository, not the current results.

## Licence and data reuse

The code is released under the [MIT licence](LICENSE), which allows commercial use. The data files
under `data/raw/` are not covered by it: each keeps the terms of the body that publishes it, listed
by provider in the [source register](docs/sources/register.md), and each file's source URL is in
`data/raw/manifest.csv`. DGT's crash microdata are catalogued on datos.gob.es under its legal
notice; DGT's other statistics carry no reuse licence of their own and are redistributed here as
public-sector information under Ley 37/2007 with the datos.gob.es conditions applied. INE
population is CC BY 4.0. The Ministerio de Transportes' files are reused under its legal notice,
and the CORES series as public-sector information on the datos.gob.es conditions. The Catalan file
is published on the Generalitat's open-data portal under the Llicència oberta d'ús d'informació -
Catalunya, and the Barcelona files on Open Data BCN under CC BY 4.0. The EMEF microdata are reused
under the open-data clause of the Observatori de la Mobilitat de Catalunya, and no estimate resting
on fewer than 20 sample observations is published, as the survey requires; the EMEF 2024 executive
summary is kept unchanged under its CC BY-NC-ND 4.0 licence, and Idescat's census release under
Idescat's legal notice. The EDM2018 extracts are reused under the CRTM's licence, which asks that
derived data be distributed under the same licence (Powered by CRTM). Where a provider's terms ask
for the date of last update, the register and the methodology page give it. Every published figure
is an aggregate and nothing on the site identifies a person.

The fonts are not covered by the MIT licence either. Nunito Sans and STIX Two Text, in
`src/dgt_stats/site/fonts` and `src/dgt_stats/charts/fonts`, and the subsets of STIX Two Text
embedded in the SVG figures, are under the SIL Open Font License 1.1, whose text ships beside them.
Avenir Next is not distributed: pages ask for it by name and use it where the reader's system has
it.

---

An independent analysis by Russell Howard ([RAHV-FB](https://github.com/RAHV-FB)).
