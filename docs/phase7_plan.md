# Phase 7: speed and context

Plan date: 19 September 2026. Phase 7 of [`analytics_plan.md`](analytics_plan.md) is question Q9:
how large is the speed factor and where does it concentrate? It is the eighth of nine phases (0 to
8); after it, one remains (8 publish). Same working rules: Python only, one commit per step on
branch `phase-7`, `ruff` and `pytest` before each commit, tables and figures committed, static HTML
output, squash-merge at the end.

## 1. What the data allow

Nothing in hand measures speed. The crash microdata carry no speed, no speed limit and no
infraction; the two sources that mention speed both record a police judgement, made at the scene or
in the report, that speed was "inappropriate". The chapter is therefore descriptive, as the
analytics plan reframed it, and every table says what the judgement is and how often it was not made.

| Input | Source | What it gives |
|---|---|---|
| Driver infractions | yearbook tables 6.1.I and 6.1.U, 2014–2024 (chapter workbooks to 2019, one workbook per year from 2020) | drivers involved in injury crashes by vehicle type × infraction, in three blocks: speed (infraction, driving too slowly, none, unknown), other infractions (priority, wrong side, overtaking, safety distance, other, none, unknown) and a summary (any, none, unknown); interurban and urban separately |
| The DGT speed report | `dgt_factor_velocidad_2023.pdf` (Observatorio Nacional de Seguridad Vial, March 2025) | crashes, deaths, hospitalised and non-hospitalised with the speed factor, 2014–2023, **without Cataluña or País Vasco**: by zone, road type, speed limit of the road, functional class, vehicle, engine power or size, driver age and sex, licence class, and a day × hour grid for the pooled decade; 57 tables in the annex |
| Context already on the site | trends, timing, severity and policy pages | the 2019 speed-limit case study (no claim), the severity model (no speed term), the hour × weekday grids |

Two facts shape the design:

- **The unknown share moved.** In the interurban table 6.1, "unknown" speed status covers 17 % of
  drivers in 2014 and 40–50 % from 2016 on; in the urban table it is above 50 % throughout. A share of
  drivers "with a speed infraction" over all drivers therefore falls for reasons that have nothing
  to do with speed. The page shows three series side by side: infraction, none and unknown, as
  shares of all drivers, and the infraction share among drivers whose status is known, with the
  caveat that the known ones are not a random sample.
- **The report and the tables count different things.** The report counts crashes and victims in
  which any road user was judged to have the speed factor, in fifteen of seventeen regions; the
  tables count drivers with a speed infraction, in all of Spain. The 2023 figures (5,070 crashes with
  the factor, 7 %; 3,580 interurban, 14 %; 1,490 urban, 3 %; 319 deaths) are quoted from the report
  with its exclusion in every caption and never added to the table figures.

## 2. Build steps

### Step 1 — Driver-infraction tables (`io_tables.py`, `validate.py`)
- `read_table_6_1(year, zone)` for 2014–2024: rows located by normalised label (the 2014 `.xls`
  has block headings as rows, 2015–2016 prefix the block name in the label cell, 2019 onwards are
  plain), the three blocks kept as a `block` column, vehicle columns mapped to the groups of
  `vehicles.py` (VMP appears from 2020). Interim `tables_driver_infractions`.
- One validation check: the total of every block equals the drivers involved in table 4.2 for the
  same year and zone (already ingested as `tables_drivers_involved`), so the two tables describe the
  same drivers.
- Tests: the 2024 interurban totals (4,473 speed infractions of 61,318 drivers), the 2014 layout,
  block totals equal across blocks.

### Step 2 — The speed report (`io_reports.py`, `scripts/ingest.py reports`)
- Extract the text with `pymupdf` (added to the dependencies) and parse the annex tables by their
  captions: year-by-category tables (10 values per row, labels of one or two lines, "n.d." as
  missing) and the day × hour grids (seven weekdays plus a total). Tables kept: 7 and 8 (factors,
  all roads), 9–12 (by zone), 13–15 (road type), 16–19 (speed limit), 20–23 (functional class),
  24–27 (vehicle), 36–39 (driver age and sex, crashes and driver deaths), 46–47 (licence class),
  50–51 and 54–55 (day × hour, crashes and deaths, both zones and interurban). Interim
  `speed_report.parquet`, long format: table, breakdown, category, year or weekday/hour, metric,
  value, with `region_scope = "Spain without Cataluña and País Vasco"` on every row.
- Tests pin the executive-summary numbers (5,070 crashes and 7 % in 2023; 319 deaths; 3,580 and
  1,490 by zone) and the identity that the road-type rows sum to the total in every year.

### Step 3 — Summaries (`speed.py`)
- `infraction_shares()`: by year and zone, drivers with a speed infraction, none and unknown as
  shares of all drivers, and the infraction share among known; the same by vehicle group for the
  latest year (with Wilson intervals from `rates.py`).
- `other_infractions()`: the other-infraction block for the latest year, ranked, to place speed
  among priority, safety distance and the rest.
- `report_series()`, `report_breakdowns()`, `report_day_hour()`: the parsed report tables reshaped
  for the site, with the factor share of all crashes where the report gives it.
- Tables `q9_infraction_shares`, `q9_infractions_by_vehicle`, `q9_other_infractions`,
  `q9_report_factors`, `q9_report_by_zone`, `q9_report_road_type`, `q9_report_speed_limit`,
  `q9_report_vehicle`, `q9_report_age`, `q9_report_day_hour`.

### Step 4 — Figures and site
- Figures: stacked shares of speed status by year and zone (infraction, none, unknown); the known
  share with intervals by vehicle group; the report's factor shares 2014–2023 by zone; road type and
  speed limit as small multiples or grouped bars for 2023 against 2014; the day × hour heatmap.
- `speed.html`: what "speed factor" means in each source, the driver tables with the unknown
  share in view, the report's profile (where, which road, which limit, which vehicle, who), the
  day × hour grid, a paragraph tying it to the pages that already touch speed, and a limits section
  (judgement not measurement, the exclusion, the unknown share, no exposure, drivers not crashes).
  Overview card; data page gains the report as a source and the new check.

### Step 5 — Docs, PR, merge
- `analytics_plan.md` phase table and Q9 row, README results and roadmap, `data/README.md`
  (interim table and the `reports` ingest step), notebooks map, `phase7_plan.md` outcome section;
  PR; squash merge.

## 3. Outcome (19 September 2026)

All five steps are merged. What was built, with the deviations from the design above:

- `io_tables.read_table_6_1` parses the four layouts by locating rows by label with a small state
  machine (a repeated item advances the block), `io_reports.py` transcribes all 61 annex tables of
  the speed report (the plan said 57; the PDF numbers some tables twice and three age-by-sex tables
  share one caption, so their sex is taken from the header cell glued to the first row), `speed.py`
  holds the ten `q9_*` summaries, and `speed.html` is the page. `pymupdf` joins the dependencies and
  `ingest.py reports` the CLI.
- Table 6.1 does not equal table 4.2 exactly: the totals match in 2014–2015 and sit 0.2–1.1 % below
  from 2016, so the check (44 rows, 434 in all) uses a 1.5 % tolerance and also requires one total
  across the six blocks.
- Results, driver tables: the share of drivers with no speed record jumps from 17 % (2014) to 52 %
  (2016) and stays there (52 % in 2024); the infraction share over all drivers falls from 6.7 % to
  4.3 % while the share among recorded drivers moves from 8.1 % to 9.1 % (14.3 % interurban, 5.8 %
  urban in 2024); motorcyclists 12.9 %, cars 9.0 %, bus drivers 2.8 %. Speed ranks third among the
  infractions recorded, after priority and safety distance.
- Results, the report: inappropriate speed in 5,070 injury crashes in 2023, 7 % of the total (10 %
  in 2014), 14 % interurban and 3 % urban; 319 deaths, 66 % on conventional and other interurban
  roads; 30 km/h streets carry 19 % of the crashes but 11 % of the deaths, 90 km/h roads 18 % and
  27 %; motorcycle users are 37 % of the deaths; 36 % of the crashes fall at weekends. The excluded
  regions hold 28 % of Spain's injury crashes (computed from the province table, not "a fifth").
- A review pass caught that the report's speed limit was unknown for 59 % of speed-factor crashes in
  2014 and 0.2 % in 2023, so the page now compares the 30 km/h share among crashes with a known
  limit (8 % to 19 %) instead of the raw count; that the "Total*" row of the vehicle and engine-size
  tables was being swallowed as a header (it is the count of crash-by-vehicle entries, 6,213 in
  2023); and that the reader's final groupby could hide a row assigned to two blocks, now an error
  with a test that every block's items sum to its total.

## 4. Verification

- The report's 2023 totals reproduce its own executive summary, and its road-type, speed-limit and
  day × hour rows add up to its totals.
- Table 6.1 block totals equal each other and sit within 1.5 % of table 4.2's drivers involved,
  every year and zone.
- `pytest` (137), `ruff`, idempotent `ingest.py tables reports`, `analyse.py all` and
  `build_site.py`, headless screenshots at 1280 px and 390 px with no horizontal overflow.
