# Phase 4: crash severity models

Plan date: 19 September 2026. Phase 4 of [`analytics_plan.md`](analytics_plan.md) is question Q3:
given that an injury crash happened, what makes it fatal or serious? It is the fourth of nine phases
(0 to 8); after it, four remain (5 exposure case study, 6 policy case study, 7 speed and context,
8 publish). Same working rules: Python only, one commit per step on branch `phase-4`, `ruff` and
`pytest` before each commit, tables and figures committed, static HTML output, squash-merge at the end.

## 1. What the data allow

The microdata are one row per injury crash (875,013 rows, 2016–2024) with the circumstances of the
crash and the counts of victims by severity. There are no driver, vehicle or person fields, so the
models explain severity from **where, when and how** a crash happened, not from who was involved.
Two consequences are stated up front:

- The alcohol × speed interaction in the methodology note cannot be estimated: neither factor is in
  the crash-level file. DGT's yearly tables report driver infractions only as aggregates (table 6.1).
  This phase estimates what the file supports and says so; the README roadmap line is reworded.
- A crash-level model describes the recorded crash population. It answers "which circumstances make
  a recorded injury crash more likely to kill" and nothing about the risk of crashing.

Outcomes: `fatal` (at least one death within 30 days; 1.64 % of crashes, about 14,300 events) and
`serious` (at least one death or hospitalised victim; 9.5 %). Both are binary at crash level.

Predictors, all categorical, with the missing states kept as their own level (never dropped, because
missingness is year-dependent; see the data page):

| Predictor | Source column | Levels |
|---|---|---|
| zone | `ZONA` | interurban road, urban crossing, street, urban motorway |
| road group | `road_group` | motorway, dual carriageway, conventional, urban street, other |
| crash type | `TIPO_ACCIDENTE` | grouped to 8: head-on, side or head-on/side, rear-end or multiple, run-off or overturn, pedestrian struck, fixed object or animal, fall, other |
| junction | `NUDO` | at a junction, not |
| lighting | `CONDICION_ILUMINACION` | daylight, dusk or dawn, dark with lighting, dark without lighting, not specified |
| weather | `CONDICION_METEO` | clear, cloudy, rain, other adverse, not specified |
| surface | `CONDICION_FIRME` | dry, wet, other, not specified |
| alignment | `TRAZADO_PLANTA` | straight, curve, not specified |
| time | `hour_band`, `weekend` | six bands; weekend as defined in Phase 2 |
| vehicles involved | `TOTAL_VEHICULOS` | 1, 2, 3 or more |
| year | `ANYO` | 2016 … 2024 |

Reference levels are the most common level of each predictor so that odds ratios read as "relative
to the typical crash". Province enters only through cluster-robust standard errors (52 clusters),
not as 52 dummies; a province random effect is left for later.

## 2. Build steps

### Step 1 — Model frame (`features.py`)
- `model_frame(columns=...)` builds the analysis table from `data/processed/accidentes.parquet`:
  outcome flags, grouped predictors as ordered categoricals with the reference level first, one row
  per crash, no rows dropped. Grouping maps live in one dictionary per predictor with the original
  codes listed, so the data page can print them.
- Tests: every original code maps to a group; missing markers map to the "not specified" level; row
  count equals the processed table.

### Step 2 — Fitting and diagnostics (`models.py`, `scripts/model.py`)
- `fit_severity(outcome)`: logistic regression (`statsmodels` GLM binomial, cluster-robust
  covariance by province) on the main-effects formula; returns a tidy table of terms with odds ratio,
  95 % interval, p-value and the reference level named.
- `marginal_effects()`: average marginal effect of each level on the probability of the outcome, so
  the site can say "in percentage points" as well as in odds ratios.
- `holdout_check()`: fit on 2016–2022, score 2023–2024; calibration by predicted-probability decile
  (expected versus observed), Brier score and area under the ROC curve (`scikit-learn`).
- `year_stability()`: refit per year, one table of odds ratios by year for the ten largest effects.
- `profiles()`: predicted probability of a fatal and of a serious outcome for a handful of named crash
  profiles (for example "conventional road, curve, dark without lighting, single vehicle, run-off").
- `scripts/model.py` fits everything and writes `reports/tables/q3_*.csv` (fits take a few minutes;
  the site build never refits, it reads the tables). Tests: a synthetic frame with a known odds ratio
  is recovered within tolerance; calibration deciles sum to the row count; the CLI is idempotent.

### Step 3 — Summaries and figures
- Registry entries `q3_model_fatal`, `q3_model_serious`, `q3_marginal_effects`, `q3_calibration`,
  `q3_year_stability`, `q3_profiles` (readers of the model tables, so `analyse.py` stays fast).
- `plots.forest()` (odds ratios on a log axis with interval whiskers, grouped by predictor) and
  `plots.calibration()` (expected versus observed by decile with the diagonal). Figures: forest plot
  for each outcome, calibration plot, year-stability small multiples, a predicted-probability heatmap
  of road group × lighting for the fatal outcome.

### Step 4 — Site
- `severity.html`: what the model is and is not, the two forest plots with their tables, marginal
  effects in percentage points, the profile table, calibration and stability, and the grouping maps.
  Overview card and data page updated.

### Step 5 — Docs, PR, merge
- `analytics_plan.md` phase table, README results and roadmap (the factor-interaction line reworded to
  what the data allow), `phase4_plan.md` outcome section, notebooks map; PR; squash merge.

## 3. Outcome (19 September 2026)

All five steps are merged. What was built, with the deviations from the design above:

- `features.py`, `models.py`, `scripts/model.py` are new; `summaries.py` exposes the model tables,
  `figures.py` adds forest, calibration, stability and predicted-grid figures, `site.py` adds
  `severity.html`. Eight result tables (`q3_*.csv`), five figures.
- The fit is a hand-written IRLS with a cluster-robust sandwich (`numpy`), not `statsmodels`: the
  GLM route was killed for memory on the 875,013-row design in a 16 GB container. The two agree on
  synthetic data to the third decimal; the whole script runs in about two minutes.
- Alignment code 998 (not applicable) is exactly the street zone, so it cannot be a level next to
  zone; it folds into the reference ("straight"). Levels with fewer than 500 crashes (three of them,
  with no events) merge into their reference. The other missing states remain levels.
- Results, fatal outcome: head-on collisions 5.8× and pedestrian strikes 6.4× the odds of a side
  collision; interurban roads 3.2× and urban crossings 4.2× a street; conventional, dual carriageway
  and motorway 2.0–2.4× an urban street; darkness without lighting 1.4×; 00:00–06:59 1.5×; three or
  more vehicles 1.5×; rear-end collisions 0.5×; at a junction 0.75×; wet surface 0.62×. Holdout
  (2016–2022 fit, 2023–2024 scored): AUC 0.80 for fatal, 0.69 for serious, calibrated by decile,
  Brier below the base rate for both.
- Stability: 36 of 90 year-by-term estimates leave the full model's (narrow) interval; in 2024 the
  road-type effects collapse towards 1 while the zone effects jump, matching the 2024 change in
  road-type coding recorded in the data inventory. The page says road type and zone must be read
  together.

## 4. Verification

- Odds ratios reproduce known descriptive facts already on the site: darkness without lighting and
  conventional roads raise the fatal share; urban streets and rear-end collisions lower it.
- The holdout calibration line stays close to the diagonal and the area under the curve is reported
  with its value, whatever it is.
- Per-year odds ratios move within their intervals; any level that does not (2020 is the candidate)
  is named on the page.
- `pytest`, `ruff`, idempotent `scripts/model.py` and `analyse.py all`, headless screenshots at 1280 px
  and 390 px.
