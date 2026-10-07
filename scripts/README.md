# Scripts

The command-line entry points. `fetch_ine.py` stands outside the build; the rest run in the order
below:

- `ingest.py {microdata,tables,exposure,reports,validate,all} [--years Y ...] [--force] [-v]`: the
  DGT, INE, traffic and fuel files under `data/raw/` parsed into `data/staging/dgt/`, the speed
  report transcribed, and the 482 reconciliation checks (about six minutes for `all`);
- `build_tables.py [--force]`: `data/staging/dgt/` to `data/processed/dgt_accidentes.parquet`
  (derived fields and labels);
- `model.py`: the supporting association analysis of the DGT crash records, its
  adverse-conditions sensitivity fits and the holdout, written to `reports/tables/q3_*.csv`;
- `microdata.py {inventory,build,quality,features,analyse,models,validate,sources,all}`: the
  Catalan and Barcelona layers, from the raw files to staging, processed and feature tables, then
  the descriptive tables, the source models and their rule baselines, the validation (transfer
  tests, Barcelona diagnosis, DGT microdata audit, generalisability, model decisions) and the
  generated documents; `documents` re-renders the documents from saved tables, and `organise`
  files loose downloads under `data/raw/<source>/`;
- `analyse.py {tables,figures,cards,all}`: the national result tables, every figure and its
  caption, and the cards of the two national models;
- `build_site.py`: `site/`;
- `fetch_ine.py [--from-file CSV]`: rebuilds the committed INE population extract
  (`data/raw/ine/ine_poblacion_provincias_edad_sexo.csv`) from INE table 56947, or filters an
  already downloaded copy.

Scripts are thin orchestration layers. Reusable logic belongs in `src/dgt_stats/` and is covered by
tests.
