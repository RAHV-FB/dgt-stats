# Reports

Everything the pipeline publishes, committed so that the results can be read and reviewed without
rebuilding:

- `tables/<section>/`: the result tables (CSV), one folder per section of the project
  (`national`, `drivers`, `regional`, `models`, `sources`). Each folder's `README.md` lists every
  table in it, what it holds, the sources it is computed from, the stage that writes it and the
  site page that links it. Which folder a table belongs to is declared in
  `src/dgt_stats/catalogue.py`, and code reads and writes tables only through
  `dgt_stats.paths.table_path`, so a table cannot be written outside its folder or under a name the
  catalogue does not know.
- `figures/`: one SVG per figure, `captions.json` (the source, period and metric of each figure and
  the n where one applies) and `titles.json`; `figures/narrow/` holds the same figures drawn for a
  phone's column. Written by `python scripts/run.py charts`.
- `models/severity_model.json`: the crash-severity calculator's model, exported for the browser by
  `python scripts/run.py models.calculator`.

The site reads only these files: `python scripts/run.py site` copies into `site/figures/` the SVGs a
page shows and into `site/tables/` the tables a page links as a download. A table no page links (a
withdrawn analysis's record, such as `forecast_*.csv` and `review_forecast.csv`, or a check behind a
generated document) stays here and is not published, and a page that links a missing table stops
the build. Neither copy is committed.
