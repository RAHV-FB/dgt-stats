# Reports

Result tables, figures and captions, all committed and rebuilt from the raw files by:

- `scripts/ingest.py validate`: `validation.csv` and `missingness_by_year.csv`;
- `scripts/model.py`: the `q3_*` tables (the supporting association analysis of DGT records);
- `scripts/microdata.py`: the regional and validation tables, `data_inventory` (inventory),
  `mq_*` (quality), `cat_*` and `bcn_*` (descriptive), `ml_*` (source models, rule baselines,
  transfer tests, diagnosis, outward path and model decisions), `dgt_audit_*` (DGT microdata
  audit), `gen_*` (representativeness and cross-source register) and `source_comparison`;
- `scripts/analyse.py all`: every other national table (`risk_*` 2019–2024, `longrun_*`,
  `season_*`, `drivers_*` and `q7_*` age and sex, `q6_*` vehicles, `speed_*` and `q9_*` speed,
  `factor_*`, `forecast_*`, `road_class_*`, `q1_*`, `q2_*` and the supporting `q8_*` 2006
  tables), the SVG figures and `figures/captions.json`.

- `tables/`: the result tables;
- `figures/`: one SVG per figure and `captions.json`, which records the source, period and metric
  definition of each figure and the n where one applies.

The site reads only these files: `scripts/build_site.py` copies the SVGs into `site/figures/` and
every `tables/*.csv` into `site/tables/`, where the pages link them as downloads, so a reader can
get the full result behind any figure without leaving the page. Neither copy is committed.
