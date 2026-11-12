# Scripts

The command-line entry points. They run in this order. `fetch_ine.py` and `fetch_edm.py` stand
outside the build.

- `ingest.py {microdata,tables,exposure,reports,validate,all} [--years Y ...] [--force] [-v]`: the
  DGT, INE, traffic and fuel files under `data/raw/` parsed into `data/staging/dgt/`, and the
  reconciliation against DGT's published totals (about 4-5 minutes for `all`).
- `build_tables.py [--force]`: `data/staging/dgt/` to `data/processed/dgt_accidentes.parquet`
  (derived fields and labels).
- `model.py`: the associations between recorded circumstances and crash severity in DGT's crash
  records, with their sensitivity fits and holdout (`q3_*` tables; about three minutes).
- `analyse.py {tables,figures,all}`: the national result tables, including the crash explorer's
  table (`explore_dgt_crashes`; about a minute), and the SVG figures with their captions (under a
  minute). `tables` needs only the processed layer; `figures` also needs the regional tables from
  `microdata.py` and `severity_model.py`.
- `microdata.py {build,quality,features,analyse,sources}`: the Catalan and Barcelona layers. `build`
  makes staging and processed tables from the raw files, `quality` the data-quality checks,
  `features` the model matrices, `analyse` the descriptive tables and DGT's coding tables, and `sources` the comparison of the
  Catalan file with DGT's counts (the steps take under a minute together).
- `severity_model.py`: the Catalan penalised logistic model, its nested rolling-origin evaluation
  against a simple table, and the tests within Catalonia (`sev_*` tables; about five minutes).
- `emef.py {build,exposure,all}`: the EMEF 2014-2024 survey read and harmonised, and working-day
  car-driving distance by age (`emef_*` tables). Its checks against the published figures run as
  tests.
- `exposure_risk.py {barcelona,madrid,national,all}`: the exposure methods and car drivers involved
  per kilometre by driver age, with the ranges across assumptions (`risk_*`, `edm_*` tables).
- `build_site.py`: `site/` and `docs/FINDINGS.md`, from the committed tables and figures.
- `compare_reports.py`: after the pipeline, checks the rebuilt tables and figures against the
  committed ones: no file new or missing, every table number within one part in a thousand, and
  everything a figure prints identical (CI runs it; documents are compared byte for byte).
- `fetch_ine.py [--table provinces|single_age] [--from-file CSV]`: rebuilds the committed INE
  population extracts in `data/raw/ine/`, or filters an already downloaded copy.
- `fetch_edm.py [--from-dir DIR]`: rebuilds the committed extracts of the Madrid household travel
  survey 2018 in `data/raw/crtm/edm2018/` from the CRTM's workbooks.

Scripts are thin. Reusable logic is in `src/dgt_stats/` and covered by tests. Set `OMP_NUM_THREADS=1`,
`OPENBLAS_NUM_THREADS=1` and `MKL_NUM_THREADS=1` for the fitting steps.
