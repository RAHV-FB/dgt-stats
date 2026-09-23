# Road safety in Spain

[![Checks](https://github.com/RAHV-FB/dgt-stats/actions/workflows/ci.yml/badge.svg)](https://github.com/RAHV-FB/dgt-stats/actions/workflows/ci.yml)

**Live site: <https://rahv-fb.github.io/dgt-stats/>** · [Reproduce the analysis](#reproduce) ·
[Methodology](docs/methodology.md)

Four analyses of Spanish road-crash data that answer questions the published tables do not.
Everything is generated from files published by the Dirección General de Tráfico, INE, the
Ministerio de Transportes and CORES, reconciled against the publishers' own totals by 434 checks
before anything is computed, and reproducible in five commands.

## Why this exists

Spain publishes a great deal of road-safety data and very little analysis of it. DGT's yearbook
will tell you how many people died last year on each kind of road, at what hour and in which
province. It will not tell you whether older drivers are actually riskier once you know how far
they drive, or whether a policy effect survives a falsification test built for the season it
happened in. This project takes four such questions and follows each until the evidence either
holds or breaks, and says which.

## The findings

| | Finding |
|---|---|
| **[Crash severity](https://rahv-fb.github.io/dgt-stats/severity.html)** | Given that an injury crash has happened, a wet road carries **0.56×** the odds of a death of a dry one, and a junction 0.75×. Rain and wet surface are one effect split between two correlated predictors; the result survives dropping either and fitting urban and interurban roads separately. It is about severity *given* a crash, not about crashing. |
| **[Age and exposure](https://rahv-fb.github.io/dgt-stats/older-drivers.html)** | Car drivers aged 75+ are involved in injury crashes **1.02×** as often per kilometre driven as drivers aged 35–54, which is to say about as often, but are killed **3.9×** as often once involved. The apparent excess risk of older drivers is almost entirely what happens after the crash. |
| **[Vehicles per km](https://rahv-fb.github.io/dgt-stats/vehicles.html)** | A heavy truck is in a fatal crash **10.3×** as often as a car per circulating vehicle and **2.5×** per kilometre driven. Motorcycles move the other way. The denominator, not the vehicle, does most of the work. |
| **[The 2006 break](https://rahv-fb.github.io/dgt-stats/policy.html)** | Monthly deaths stepped down around the points-based licence, by **12%** under a straight pre-trend and **7%** under the pre-trend the earlier months actually prefer. Placed at July of other years the model ranks 2006 first of 15; an out-of-sample forecast ranks it only fourth. The headline did not survive the right test, and the page says so. |

One more, about the data rather than the roads: the share of drivers in an injury crash with **no
recorded speed status** jumps from 17% to 52% in 2016, so the two obvious readings of DGT's own
published speed column now move in opposite directions
([context](https://rahv-fb.github.io/dgt-stats/context.html)).

## Why you can believe the numbers

- **Reconciled before analysed.** 434 checks tie the crash microdata, the yearbook tables and the
  driver census to DGT's published totals: crashes and victims per year, deaths by province and
  month, driver deaths by zone, vehicles involved by type, every code against the dictionary. The
  microdata match the yearbook exactly, year by year. Nothing is computed until they pass
  (`src/dgt_stats/validate.py`, enforced by `tests/test_validate.py`).
- **Every rate names its denominator**, and where the denominator changes the answer the page
  shows all of them side by side rather than picking one.
- **Claims are tested, not asserted.** The severity finding is refitted eight ways; the 2006 break
  is put through calendar-matched placebos, a seasonality-free transition statistic, out-of-sample
  forecasts, a pre-trend chosen on the pre-period alone and two monthly traffic series. Results
  that failed their checks are reported as failures, in a paragraph rather than a page. The 2019
  speed-limit study is the one that failed: its control group does not survive a placebo break.
- **Uncertainty is visible** where it means something: exact Poisson intervals on rates built
  against a counted denominator, log-normal intervals on ratios, province-clustered intervals on
  the models, empirical distributions on the time series.
- **The prose cannot drift from the tables.** Every sentence on the site that contains a number
  computes it from a committed result table at build time.

Method by method, with the module that implements each: [`docs/methodology.md`](docs/methodology.md).
What the audit found and what was cut from an earlier, larger version of this site:
[`docs/refocus_audit.md`](docs/refocus_audit.md).

## What the data cannot do

- **No person-level records.** The public microdata are one row per crash: no driver age, sex,
  alcohol, drug test, speed, belt or helmet. Factor interactions such as alcohol × speed are out
  of reach, and the severity models explain outcomes from where, when and how a crash happened.
- **No road geometry or traffic volumes.** There is a road-type code but no section identifier,
  curvature, shoulder or flow, which is why the 2019 speed-limit study has no credible control.
- **Vehicle-kilometres by type exist for one year** (2022), so that comparison is a cross-section.
- **Kilometres by age are the owner's age, not the driver's**, and company-registered cars carry
  no age at all; the page brackets what that does to the comparison.

## Reproduce

```bash
git clone https://github.com/RAHV-FB/dgt-stats.git
cd dgt-stats
python -m venv .venv && source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock          # pinned and hashed

python scripts/ingest.py all        # raw -> data/interim, 434 reconciliation checks (~6 min)
python scripts/build_tables.py      # data/interim -> data/processed
python scripts/model.py             # the severity models and their sensitivity fits (~1.5 min)
python scripts/analyse.py all       # reports/tables/*.csv and reports/figures/*.svg
python scripts/build_site.py        # site/
pytest                              # the test suite, the reconciliation checks among them
pytest -m slow                      # SHA-256 of every raw file against data/raw/manifest.csv
```

Raw files are tracked under `data/raw/` with their size, SHA-256 and source URL in
`data/raw/manifest.csv`; result tables and figures under `reports/` and the site's HTML and CSS are
committed, so the pages can be read and reviewed without rebuilding. `site/figures/` and
`site/tables/` are not committed; `scripts/build_site.py` copies them in from `reports/`, so run
it once before opening the pages locally.

Every push and pull request runs [`ci.yml`](.github/workflows/ci.yml): Ruff over `src`, `scripts`
and `tests`, then the whole sequence above from the raw files, so the checks and the tests run
against the published code rather than a prepared data layer. A push to `main` that touches the
site or its inputs runs [`pages.yml`](.github/workflows/pages.yml), which renders `site/` from the
committed tables and deploys it.

## Layout

```text
data/raw/              every source file, never edited, listed in manifest.csv
docs/                  methodology, source register, data audit, the refocus audit
reports/tables/        result tables (CSV), committed; the site links them for download
reports/figures/       the eleven published figures (SVG) and their captions
scripts/               ingest · build_tables · model · analyse · build_site
src/dgt_stats/         readers (io_*), codes and labels, derived fields and validation,
                       analysis (models, driver_risk, vehicles, policy, speed), output (plots,
                       figures, site)
tests/                 data-contract, reconciliation and analysis tests
```

## How it was built

The project was developed through a reproducible, source-driven workflow. The research questions,
the choice of sources, the statistical design, the interpretation, the review and the decision to
publish each result are the author's, and so is responsibility for them. AI coding assistants,
including Claude Code, ChatGPT Work and GitHub Copilot, were used during implementation, debugging,
data-processing work and review. All published results are generated from the recorded source data
and can be independently reproduced and checked through this repository.

## Licence and data reuse

The code is released under the [MIT licence](LICENSE), which allows commercial use. The data files
under `data/raw/` are not covered by it: each keeps the terms of the body that publishes it, listed
file by file with its URL in [`docs/data_sources.md`](docs/data_sources.md). DGT's crash microdata
are catalogued on datos.gob.es under its legal notice; DGT's other statistics carry no reuse licence
of their own and are redistributed here as public-sector information under Ley 37/2007 with the
datos.gob.es conditions applied. INE population is CC BY 4.0; the Ministerio de Transportes and
CORES series are public-sector information on the same terms. Every published figure is an
aggregate and nothing on the site identifies a person.

---

An independent analysis by Russell Howard ([RAHV-FB](https://github.com/RAHV-FB)).
