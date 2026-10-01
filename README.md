# Road safety in Spain

[![Checks](https://github.com/RAHV-FB/dgt-stats/actions/workflows/ci.yml/badge.svg)](https://github.com/RAHV-FB/dgt-stats/actions/workflows/ci.yml)

**Live site: <https://rahv-fb.github.io/dgt-stats/>** · [Reproduce the analysis](#reproduce) ·
[Methodology](docs/methodology.md)

What changes when you stop counting road crashes and start measuring road risk? This project
takes Spain's official crash data and divides the same counts by what produced them: residents,
licence holders, registered vehicles, kilometres driven and road fuel. On each question below the
answer changes size, and on several it changes sign. It then asks what a speed law would do, with
a simulator built on what the analyses show. Everything is generated from files published by the
Dirección General de Tráfico (DGT), INE, the Ministerio de Transportes and CORES, reconciled
against the publishers' own totals by 482 checks before anything is computed, and reproducible in
five commands.

## The findings

| | Counted | Measured |
|---|---|---|
| **[2019 to 2024](https://rahv-fb.github.io/dgt-stats/trends.html)** | 2024 deaths +1.7 % on 2019 | −3.4 % per vehicle, +3.5 % per tonne of road fuel: all within an ordinary year's variation. Hospital admissions rose 11 % as a count and 13 % per unit of traffic, beyond it |
| **[The long run](https://rahv-fb.github.io/dgt-stats/long-run.html)** | 2020 deaths 24 % below trend, back on it by 2022 | Per tonne of fuel 2020 was on trend: the fall was less driving. Since then the decline has stalled: per kilometre measured on interurban roads 2023 is +5 % on the 2013–2019 trend, inside its interval; per tonne of fuel it looks +13 %, because each tonne now carries more traffic |
| **[Seasons](https://rahv-fb.github.io/dgt-stats/seasons.html)** | July deaths 1.22×, August 1.14× the average month | Per unit of petrol 1.06× and 0.98×: the summer peak is mostly traffic. Spring is safer per unit of traffic, autumn riskier |
| **[Age and sex](https://rahv-fb.github.io/dgt-stats/drivers.html)** | Drivers 75+ and men die more | 75+ crash about as often per km as drivers aged 35–54 but are killed 3.9× as often once involved; men crash 1.4× as often per licence (about their extra travel) and are killed 2.6× as often once involved |
| **[Vehicles](https://rahv-fb.github.io/dgt-stats/vehicles.html)** | A heavy truck is in a fatal crash 10× as often as a car per vehicle | 2.5× per kilometre, and 0.18 of its own occupants die per fatal crash it is in |
| **[Speed](https://rahv-fb.github.io/dgt-stats/speed.html)** | Speed recorded in 7 % of crashes, 22 % of deaths | On the same kind of road, a crash with speed recorded kills 2.0× as often (3.4× before allowing for road type): an association, with two recording biases stated |
| **[Factors](https://rahv-fb.github.io/dgt-stats/factors.html)** | DGT's recorded alcohol, distraction and drug shares | After a recording-break test: interurban alcohol 5.5 % → 8.2 % and speed 10.0 % → 6.9 % are comparable over 2014–2023; urban distraction and drugs are not |
| **[Speed laws](https://rahv-fb.github.io/dgt-stats/simulator.html)** | — | If every driver now above the limit on motorways and conventional roads kept to it, about 330 fewer people a year would die there (290–360), more than any new limit achieves; 90 → 80 km/h on conventional roads saves about 120. A validated forecasting model shows why neither would be visible in a year's death count: anything under about 180 deaths a year is not |

**What connects them.** Wherever the data split risk into how often people crash and how badly
they are hurt when they do, the difference is in the second. The national series says the same
about the past: between 1996 and 2024 deaths per tonne of road fuel fell 76 %, injury crashes per
tonne 13 % and deaths per injury crash 73 %. How hard a crash is depends on its energy and on the
body that absorbs it; speed is the energy, the lever a law reaches and the one the evidence
measures best, and in 2022 only 43 % of cars measured on Spain's conventional roads kept to 90 km/h.
Conventional roads kill 3.4× as many people per kilometre as motorways.

Two earlier analyses are kept as **supporting material**, outside the main question: a
[model of crash severity](https://rahv-fb.github.io/dgt-stats/severity.html) and a
[test of the 2006 points licence](https://rahv-fb.github.io/dgt-stats/policy.html) whose headline
did not survive its falsification tests. The site makes no causal claim from Spanish data about
policies or campaigns, and does not analyse road design or hotspots.

## The simulator

[`simulator.html`](https://rahv-fb.github.io/dgt-stats/simulator.html) lets a reader set new speed
limits, how far drivers follow them and how many speeders keep to the limit, and see deaths,
admissions to hospital, other injuries, their value and the travel time, recomputed in the browser.
It is a chain of four links, each sourced:

1. **Baseline**: deaths and injuries by road class, 2022–2024, from the reconciled microdata.
2. **Today's speeds**: car speeds measured by radar in Spain in 2022 for the EU's Baseline project
   (mean, share within the limit, 85th percentile), fitted with a log-normal that reproduces them.
3. **From a law to a mean speed**: Elvik's curve through 143 before-and-after studies of limit
   changes, or a share the reader sets; compliance lowers the mean by the expected excess over the
   limit.
4. **From speed to casualties**: the Power Model, with Elvik's 2009 meta-analytic exponents and
   their 95 % intervals, by road environment. Values of a casualty are DGT's own (2024 update).

Every published value is in [`data/raw/evidence/simulator_parameters.csv`](data/raw/evidence/simulator_parameters.csv)
with its source, table and a verbatim quote. Nothing in the chain is fitted to Spanish crash
data, which carry no speeds. The **forecasting model** behind its verdicts (`forecast.py`) is a
Poisson regression of monthly deaths on month, a four-year trend, road fuel and weekday counts,
chosen on the forecasts of 2006–2015 and scored on 2016–2024 against last year's count and
gradient-boosted trees. It beats both when the trend or the traffic moves and ties last year in
flat years; its measured error says the smallest change one year's count can show is about 15 %
of interurban deaths, and that waiting longer makes it larger. The JavaScript is a port of
`simulator.py`, and a test runs it under Node against the Python.

## Why you can believe the numbers

- **Reconciled before analysed.** 482 checks tie the crash microdata, the yearbook tables, the
  driver census and DGT's speed report to DGT's published totals: crashes and victims per year,
  deaths by province and month, driver deaths by zone, vehicles involved by type, every code
  against the dictionary, and the speed report's totals against the microdata for the same
  provinces. The microdata match the yearbook exactly, year by year
  (`src/dgt_stats/validate.py`, enforced by `tests/test_validate.py`).
- **Every rate names its denominator**, and where the denominator changes the answer the page
  shows all of them side by side.
- **Assumptions are tested, and the tests changed findings.** Road fuel was checked against the
  kilometres the Ministry measures (it drifts after 2019, which shrank the long-run excess);
  intervals were checked against each count's real year-to-year scatter (crash counts scatter 68
  times as much as chance, so the apparent fall in crashes per person is not a finding); the
  owner's age was bounded as a stand-in for the driver's. The list is on the
  [data page](https://rahv-fb.github.io/dgt-stats/data.html#assumptions-tested).
- **Models are judged on years they did not see**, against naive forecasts, and the page says
  where the simple forecast wins.
- **Recording changes are tested before trends are read.** A factor share that jumps or falls by a
  quarter in a year is treated as a change in recording, and the page compares only within the
  unbroken runs.
- **The prose cannot drift from the tables.** Every sentence on the site that contains a number
  computes it from a committed result table at build time.

How the project was re-centred on its question, pillar by pillar:
[`docs/goal_alignment_audit.md`](docs/goal_alignment_audit.md). Method by method:
[`docs/methodology.md`](docs/methodology.md).

## What the data cannot do

- **No person-level records.** The public microdata are one row per crash: no driver age, sex,
  alcohol, drug test, speed, belt or helmet. Driver age and sex come from DGT's aggregate tables;
  factors come from DGT's report as police-recorded shares; interactions such as alcohol × speed
  are out of reach.
- **Kilometres only where they are measured.** The Ministry measures interurban vehicle-km by road
  type each year (to 2023, without municipal roads); there is no urban series, no series by
  vehicle type except DGT's 2022 estimate, and no source of kilometres by sex.
- **No speeds in the crash data**, so the effect of speed on Spanish casualties is taken from
  international evidence, not estimated; and no split of urban casualties by speed limit, so the
  simulator gives urban effects per kind of street, not as a national count.
- **No road geometry or traffic volumes by section**, so no road-design analysis and no hotspot
  model.

## Reproduce

```bash
git clone https://github.com/RAHV-FB/dgt-stats.git
cd dgt-stats
python -m venv .venv && source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock          # pinned and hashed

python scripts/ingest.py all        # raw -> data/interim, 482 reconciliation checks (~6 min)
python scripts/build_tables.py      # data/interim -> data/processed
python scripts/model.py             # the severity models and their sensitivity fits (~1.5 min)
python scripts/analyse.py all       # reports/tables/*.csv and reports/figures/*.svg (~1 min)
python scripts/build_site.py        # site/
pytest                              # the test suite, the reconciliation checks among them
pytest -m slow                      # SHA-256 of every raw file against data/raw/manifest.csv
```

The test that compares the simulator's JavaScript with its Python runs when `node` is installed
and is skipped otherwise.

Raw files are tracked under `data/raw/` with their size, SHA-256 and source URL in
`data/raw/manifest.csv`; result tables and figures under `reports/` and the site's HTML, CSS and
script are committed, so the pages can be read and reviewed without rebuilding. `site/figures/`
and `site/tables/` are not committed; `scripts/build_site.py` copies them in from `reports/`, so
run it once before opening the pages locally.

Every push and pull request runs [`ci.yml`](.github/workflows/ci.yml): Ruff over `src`, `scripts`
and `tests`, then the whole sequence above from the raw files, so the checks and the tests run
against the published code rather than a prepared data layer. A push to `main` that touches the
site or its inputs runs [`pages.yml`](.github/workflows/pages.yml), which renders `site/` from the
committed tables and deploys it.

## Layout

```text
data/raw/              every source file, never edited, listed in manifest.csv; evidence/ holds
                       the simulator's register of published values
docs/                  methodology, source register, data audit, and the two audits that set
                       the project's direction
reports/tables/        result tables (CSV), committed; the site links them for download
reports/figures/       the twenty-two published figures (SVG) and their captions
scripts/               ingest · build_tables · model · analyse · build_site
src/dgt_stats/         readers (io_*), codes and labels, derived fields and validation,
                       analysis (risk_trends, seasonality, driver_risk, vehicles, factors, speed),
                       the forecasting model and the simulator (forecast, simulator, and
                       assets/simulator.js), the supporting analyses (models, policy), and output
                       (plots, figures, and the site package, one module per page)
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
CORES series are public-sector information on the same terms. The simulator's evidence register
quotes published values with attribution and redistributes none of the publications. Every
published figure is an aggregate and nothing on the site identifies a person.

---

An independent analysis by Russell Howard ([RAHV-FB](https://github.com/RAHV-FB)).
