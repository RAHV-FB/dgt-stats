# Road safety in Spain

[![Checks](https://github.com/RAHV-FB/dgt-stats/actions/workflows/ci.yml/badge.svg)](https://github.com/RAHV-FB/dgt-stats/actions/workflows/ci.yml)

**Live site: <https://rahv-fb.github.io/dgt-stats/>** · [Findings](docs/FINDINGS.md) ·
[Reproduce](#reproduce) · [Methodology](docs/methodology.md)

A statistical study of road deaths and injuries in Spain, built only from published data. It asks
how road safety has changed since 1993 and how it differs between drivers, vehicles and roads once
each count of deaths or crashes is set against a measure of who could be on the road or how much
they travel. Every number is computed by the code in this repository from the files in
[`data/raw`](data/raw) and a few values typed in from cited documents (see below).

The numbers are not repeated here, where they could drift from the data. They are in
[`docs/FINDINGS.md`](docs/FINDINGS.md) and on the site, both generated from the committed result
tables.

## Research questions and conclusions

Nothing below is causal. The national data reconcile with DGT's published totals.

1. **Has road safety improved over the long run?** Road deaths fell steeply until 2013 and have
   shown no clear trend since. A post-pandemic rise in risk is not established: it depends on
   which pre-pandemic trend deaths per tonne of fuel are compared with, and deaths per measured
   kilometre on interurban roads stayed within trend.
   [Long-run trends](https://rahv-fb.github.io/dgt-stats/long-run.html).
2. **Is summer riskier?** Deaths peak in July to September, even per tonne of fuel sold. Whether
   summer is riskier per kilometre cannot be told.
   [Seasons](https://rahv-fb.github.io/dgt-stats/seasons.html).
3. **Did the 2006 points licence save lives?** Deaths fell around its introduction. Whether the
   fall lasted depends on the trend assumed before it, and placebo Julys with no policy change
   show that the series cannot attribute a fall to the licence.
   [The 2006 points licence](https://rahv-fb.github.io/dgt-stats/policy.html).
4. **Which drivers are at higher risk?** Older drivers are the most likely to die once in an injury
   crash (counted). Per kilometre, drivers aged 18-29 are involved in injury crashes clearly more
   often than drivers aged 45-64; the comparison with the oldest drivers is not established, and
   all per-kilometre results rest on estimated distances. Men die more often than women per
   licence holder. [Drivers](https://rahv-fb.github.io/dgt-stats/drivers.html),
   [method](docs/DRIVER_AGE_EXPOSURE.md).
5. **Which vehicles?** Per kilometre, motorcyclists are in fatal crashes far more often than car
   drivers, on DGT's modelled kilometres.
   [Vehicles](https://rahv-fb.github.io/dgt-stats/vehicles.html).
6. **What goes with a deadly crash?** Crashes where the police recorded inappropriate speed are
   deadlier than others on the same kind of road (an association open to recording bias). Crash
   type and place dominate whether an injury crash is fatal.
   [Speed and other recorded factors](https://rahv-fb.github.io/dgt-stats/factors.html),
   [crash circumstances in Spain](https://rahv-fb.github.io/dgt-stats/severity.html).
7. **What do the Catalan crash records show?** Severe crashes involving a heavy vehicle are fatal
   more often. The Catalan file matches DGT's 24-hour fatal crash counts exactly in every province
   and year from 2016 to 2023. The severity model ranks crashes only modestly better than a simple
   table and was tested only within Catalonia.
   [Catalonia](https://rahv-fb.github.io/dgt-stats/catalonia.html),
   [the model](https://rahv-fb.github.io/dgt-stats/severity-models.html),
   [`docs/SEVERITY_MODEL.md`](docs/SEVERITY_MODEL.md).
8. **Who is hurt in Barcelona?** Pedestrians and motorcyclists are far more often seriously hurt or
   killed than car drivers in police-attended crashes.
   [Barcelona](https://rahv-fb.github.io/dgt-stats/barcelona.html).

Each answer, its strength and its main limit are in [`docs/FINDINGS.md`](docs/FINDINGS.md).

Two tools let readers work with the tables: the
[driver risk comparison](https://rahv-fb.github.io/dgt-stats/driver-risk.html) and the
[crash statistics explorer](https://rahv-fb.github.io/dgt-stats/crash-explorer.html).

## Data sources

Each dataset keeps its own unit of observation and role (see
[`docs/data_sources.md`](docs/data_sources.md) and [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)).
No record is linked across sources and there is no merged crash database.

| Data | Sources | Used for |
|---|---|---|
| **National** | DGT crash microdata, yearbook series and tables, driver census, kilometre estimates; INE residents; traffic and fuel series | trends, denominators and rates, province and year comparisons, the association analysis of crash severity |
| **Catalonia** | Servei Català de Trànsit, crashes with a death or serious injury, 2010-2023 | crash circumstances and the severity model |
| **Barcelona** | Guàrdia Urbana crash, person, vehicle and cause tables, 2025 | who is hurt, by road-user type; a check of involvement per kilometre by age |
| **Travel surveys** | EMEF working-day mobility survey of the Barcelona area, 2014-2024; Madrid household travel survey 2018; MOVILIA 2006 and 2007 | car-driving kilometres by driver age, the denominator of involvement per kilometre |

## What the data cannot do

- The regional crash records carry no measure of travel, so the Catalan and Barcelona analyses
  describe severity among recorded crashes, not rates per journey or kilometre. The one exception
  is the working-day check of involvement per kilometre in Barcelona.
- No crash file records vehicle speeds. The Catalan speed field is the road's posted limit.
- No national source measures kilometres by the driver's age. They are estimated from one region's
  working-day survey applied to Spain, so per-kilometre comparisons by age carry ranges across
  assumptions beside their confidence intervals.
- There are no person records nationally or in Catalonia. In Barcelona no key links a recorded
  cause to the driver or vehicle concerned.
- No record is linked between sources: they share no identifier.
- No result is a causal effect. A police-recorded factor is a judgement, not a measured cause.

## Methodological rules

- Every rate names its denominator, and the denominator is stated with what it misses.
- A model is compared with a simple table on later records it has not seen, and is kept only if it
  does better. Negative results are reported.
- Numbers on the site are computed from committed tables. Qualitative claims are guarded by tests
  that fail when the tables stop supporting them.
- Published studies may define a method but never supply an observation, a coefficient or an effect
  size.
- A few values are typed in. One comes from a document that is not archived here: the EMEF 2021
  distance report's ratio of road distance to straight-line distance for driving trips (1.45) and
  its 2021 benchmarks, which the tests use. A few come from documents archived in `data/raw`:
  Idescat's count of employed people aged 65 and over, and the EMEF 2024 executive summary's
  published figures, which only check the survey processing. Definitions such as the public-holiday
  calendars are typed too.

The full account is in [`docs/methodology.md`](docs/methodology.md).

## Reproduce

```bash
git clone https://github.com/RAHV-FB/dgt-stats.git
cd dgt-stats
python -m venv .venv && source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock          # pinned and hashed

export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1   # the fitted models need one BLAS thread

python scripts/ingest.py all          # data/raw -> data/staging/dgt, reconciliation checks (~4-5 min)
python scripts/build_tables.py        # data/processed/dgt_accidentes.parquet
python scripts/model.py               # associations in DGT crash records (~3 min)
python scripts/analyse.py tables      # national result tables, incl. the crash explorer's (~1 min)
python scripts/microdata.py build     # Catalonia and Barcelona: staging and processed tables (the five microdata.py steps take under a minute together)
python scripts/microdata.py quality
python scripts/microdata.py features
python scripts/microdata.py analyse
python scripts/microdata.py sources
python scripts/severity_model.py      # Catalan severity model and its evaluation (~5 min)
python scripts/emef.py all            # EMEF survey: car-driving distance by age (~1 min)
python scripts/exposure_risk.py all   # involvement per km by driver age and the ranges (~1-2 min)
python scripts/analyse.py figures     # SVG figures and captions (under a minute)
python scripts/build_site.py          # site/ and docs/FINDINGS.md

pytest                                # tests, including the reconciliation checks
pytest -m slow                        # raw-file checksums against data/raw/manifest.csv
```

CI runs the whole pipeline and fails if a committed document or page changes, a table's numbers
move by more than one part in a thousand, or a figure prints anything different.
`scripts/fetch_ine.py` and `scripts/fetch_edm.py` rebuild committed extracts and stand outside the
build. Details of each script are in [`scripts/README.md`](scripts/README.md).

## Layout

| Path | Contents |
|---|---|
| `src/dgt_stats/` | the package: readers, derived fields, rates, analyses, models and the site builder (`site/`) |
| `scripts/` | command-line entry points ([`scripts/README.md`](scripts/README.md)) |
| `data/raw/` | source files byte for byte, listed with checksums in `data/raw/manifest.csv` ([`data/README.md`](data/README.md)) |
| `data/staging/`, `data/processed/`, `data/features/` | rebuilt layers, not committed |
| `reports/tables/`, `reports/figures/` | committed result tables and SVG figures ([`reports/README.md`](reports/README.md)) |
| `site/` | the static site, built from the committed tables and figures |
| `docs/` | `FINDINGS.md` (generated), `methodology.md`, `data_sources.md`, `DATA_CONTRACT.md`, `DRIVER_AGE_EXPOSURE.md`, `SEVERITY_MODEL.md` |
| `tests/` | tests of the readers, the reconciliation, the analyses and the site |

## Licence and data reuse

The code is released under the [MIT licence](LICENSE), which allows commercial use. The data files
under `data/raw/` are not covered by it. Each keeps the terms of the body that publishes it, listed
by provider in [`docs/data_sources.md`](docs/data_sources.md), and each file's source URL is in
`data/raw/manifest.csv`.

- DGT's crash microdata are catalogued on datos.gob.es under its legal notice. DGT's other
  statistics carry no reuse licence of their own and are redistributed as public-sector information
  under Ley 37/2007 with the datos.gob.es conditions applied.
- INE population is CC BY 4.0.
- The Ministerio de Transportes' files are reused under its legal notice, and the CORES series as
  public-sector information on the datos.gob.es conditions.
- The Catalan file is published on the Generalitat's open-data portal under the Llicència oberta
  d'ús d'informació - Catalunya. The Barcelona files are on Open Data BCN under CC BY 4.0.
- The EMEF microdata are reused under the open-data clause of the Observatori de la Mobilitat de
  Catalunya. No estimate resting on fewer than 20 sample observations is published, as the survey
  requires. The EMEF 2024 executive summary is kept unchanged under its CC BY-NC-ND 4.0 licence,
  and Idescat's census release under Idescat's legal notice.
- The Madrid household survey extracts are reused under the CRTM's licence ("Powered by CRTM"), which asks that derived
  data be distributed under the same licence.

Every published figure is an aggregate and nothing on the site identifies a person.

The fonts are not covered by the MIT licence. Nunito Sans and STIX Two Text, in
`src/dgt_stats/site/fonts` and `src/dgt_stats/fonts`, and the subsets of STIX Two Text embedded in
the SVG figures, are under the SIL Open Font License 1.1, whose text ships beside them. Avenir Next
is not distributed: pages ask for it by name and use it where the reader's system has it.

## AI assistance

AI coding assistants were used during implementation, debugging, data-processing work and review.
The research questions, design, interpretation and responsibility are the author's.

---

An independent analysis by Russell Howard ([RAHV-FB](https://github.com/RAHV-FB)).
