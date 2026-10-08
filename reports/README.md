# Reports

Result tables, figures and captions, all committed and rebuilt from the raw files by:

- `scripts/ingest.py validate`: `validation.csv` and `missingness_by_year.csv`;
- `scripts/model.py`: the `q3_*` tables (the supporting association analysis of DGT records);
- `scripts/microdata.py`: the regional and validation tables, `data_inventory` (inventory),
  `mq_*` (quality), `cat_*` and `bcn_*` (descriptive), `ml_*` (source models, rule baselines,
  transfer tests, diagnosis, outward path and model decisions), `dgt_audit_*` (DGT microdata
  audit), `gen_*` (representativeness and cross-source register) and `source_comparison`;
- `scripts/severity_calculator.py`: the model review (`review_*`) and the calculator's model
  (`sev_*`);
- `scripts/emef.py`: the EMEF checks and car-driving exposure by age (`emef_*`), under the survey's
  rule that no estimate resting on fewer than 20 sample observations is published;
- `scripts/exposure_risk.py`: car drivers involved per kilometre by age (`risk_national_*`,
  `risk_barcelona_*`, `risk_older_*` and the other driver-age `risk_*` tables) and the Madrid
  survey's age profile (`edm_*`);
- `scripts/analyse.py all`: every other national table (`risk_*` 2019–2024, `longrun_*`,
  `season_*`, `drivers_*` and `q7_*` age and sex, `q6_*` vehicles, `speed_*` and `q9_*` speed,
  `factor_*`, `road_class_*`, `q1_*`, `q2_*` and the supporting `q8_*` 2006 tables), the SVG
  figures and `figures/captions.json`;
- `scripts/analyse.py withdrawn`: the `forecast_*` tables of the withdrawn monthly deaths
  forecast, the record behind its model card and the model review; no page reads or links them.

- `tables/`: the result tables;
- `figures/`: one SVG per figure and `captions.json`, which records the source, period and metric
  definition of each figure and the n where one applies.

The site reads only these files: `scripts/build_site.py` copies into `site/figures/` the SVGs a
page shows and into `site/tables/` the tables a page links as a download, so a reader can get the
full result behind a figure without leaving the page. A table no page links (a withdrawn
analysis's record, such as `forecast_*.csv` and `review_forecast.csv`, or a check behind a
generated document) stays here and is not published, and a page that links a missing table stops
the build. Neither copy is committed.
