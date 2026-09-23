# Scripts

The command-line entry points. `fetch_ine.py` stands outside the build; the rest run in the order
below:

- `ingest.py {microdata,tables,exposure,reports,validate,all} [--years Y ...] [--force] [-v]`: raw
  files to `data/interim/`, the speed report transcribed, and the 482 reconciliation checks (about
  six minutes for `all`);
- `build_tables.py [--force]`: `data/interim/` to `data/processed/` (derived fields and labels);
- `model.py`: the severity models, their adverse-conditions sensitivity fits and the holdout,
  written to `reports/tables/q3_*.csv` (about a minute and a half);
- `analyse.py {tables,figures,all}`: the other result tables, the figures and their captions;
- `build_site.py`: `site/`;
- `fetch_ine.py [--from-file CSV]`: rebuilds the committed INE population extract
  (`data/raw/exposure/ine_poblacion_provincias_edad_sexo.csv`) from INE table 56947, or filters an
  already downloaded copy.

Scripts are thin orchestration layers. Reusable logic belongs in `src/dgt_stats/` and is covered by
tests.
