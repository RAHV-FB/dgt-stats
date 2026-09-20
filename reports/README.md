# Reports

Result tables, figures and captions, all committed and rebuilt by `scripts/model.py` (the `q3_*`
tables), `scripts/analyse.py all` (the other `q*.csv`, the SVG figures and `figures/captions.json`)
and `scripts/ingest.py validate` (`validation.csv` and `missingness_by_year.csv`).

- `tables/`: the `q*.csv` result tables, plus `validation.csv` and `missingness_by_year.csv`;
- `figures/`: one SVG per figure and `captions.json`, which records the source, period and metric
  definition of each figure and the n where one applies; the SVGs are copied into `site/figures/`
  at build time.

The site reads only these files.
