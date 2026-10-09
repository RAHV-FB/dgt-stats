# Scripts

The command-line entry points. `fetch_ine.py`, `fetch_edm.py` and `build_fonts.py` stand outside
the build; the rest run in the order below:

- `ingest.py {microdata,tables,exposure,reports,validate,all} [--years Y ...] [--force] [-v]`: the
  DGT, INE, traffic and fuel files under `data/raw/` parsed into `data/staging/dgt/`, the speed
  report transcribed, and the 482 reconciliation checks (about six minutes for `all`);
- `build_tables.py [--force]`: `data/staging/dgt/` to `data/processed/dgt_accidentes.parquet`
  (derived fields and labels);
- `model.py`: the supporting association analysis of the DGT crash records, its
  adverse-conditions and junction-coding sensitivity fits and the holdout, written to
  `reports/tables/q3_*.csv` (about fifteen minutes), and the crash explorer's counts by year,
  region, road type and crash type (`reports/tables/explore_dgt_crashes.csv`);
- `microdata.py {inventory,build,quality,features,analyse,models,validate,sources,all}`: the
  Catalan and Barcelona layers, from the raw files to staging, processed and feature tables, then
  the descriptive tables, the source models and their rule baselines, the validation (transfer
  tests, Barcelona diagnosis, DGT microdata audit, generalisability, model decisions) and the
  generated documents; `documents` re-renders the documents from saved tables, and `organise`
  files loose downloads under `data/raw/<source>/`;
- `severity_calculator.py {review,calculator,all}`: the independent re-evaluation of every model
  (`reports/tables/review_*.csv`) and the crash-severity calculator model: its nested
  rolling-origin evaluation, in which every year's penalty, specification and through-town rule
  are chosen on earlier years only, its validation tables (`sev_*.csv`) and its export for the
  browser (`reports/models/severity_model.json`; about twenty minutes for `calculator`);
- `emef.py {build,validate,exposure,all}`: the EMEF 2014–2024 microdata read, harmonised and
  checked, the published figures and the distance report reproduced, and working-day car-driving
  exposure by age (`emef_*.csv`);
- `exposure_risk.py {barcelona,madrid,national,all}`: the Barcelona working-day design, the Madrid
  survey's age profile, the national exposure methods, the share of DGT's car kilometres the
  survey covers and the age-mix scenarios for the rest, and car drivers involved per kilometre by
  age (`risk_*.csv`, `edm_*.csv`);
- `analyse.py {tables,figures,cards,all}`: the national result tables, every figure and its
  caption, and the cards of the two national models;
- `build_site.py`: `site/`;
- `build_fonts.py <source font directory>`: stands outside the build too; it cuts the committed
  font subsets (the site's web fonts and the charts' serif) from the open fonts in the
  google/fonts repository, and is needed only to change the character set or update a font;
- `fetch_ine.py [--table provinces|single_age] [--from-file CSV]`: rebuilds the committed INE
  population extracts (`data/raw/ine/ine_poblacion_provincias_edad_sexo.csv` from table 56947,
  `data/raw/ine/ine_poblacion_edad_simple_sexo.csv` from table 56934), or filters an already
  downloaded copy;
- `fetch_edm.py [--from-dir DIR]`: rebuilds the committed extracts of the Madrid household travel
  survey 2018 (`data/raw/crtm/edm2018/`) from the CRTM's workbooks.

Scripts are thin orchestration layers. Reusable logic belongs in `src/dgt_stats/` and is covered by
tests.
