# Reports

Result tables, figures and captions, all committed and rebuilt by `scripts/model.py` (the `q3_*`
tables), `scripts/analyse.py all` (the other `q*.csv`, the SVG figures and `figures/captions.json`)
and `scripts/ingest.py validate` (`validation.csv` and `missingness_by_year.csv`).

- `tables/`: the `q*.csv` result tables, plus `validation.csv` and `missingness_by_year.csv`;
- `figures/`: one SVG per figure and `captions.json`, which records the source, period and metric
  definition of each figure and the n where one applies.

The site reads only these files: `scripts/build_site.py` copies the SVGs into `site/figures/` and
every `tables/*.csv` into `site/tables/`, where the pages link them as downloads, so a reader can
get the full result behind any figure without leaving the page. Neither copy is committed.
