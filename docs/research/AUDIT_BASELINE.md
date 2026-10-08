# Audit baseline

The state of the repository before the modelling, exposure and integrity rebuild, recorded so
that every later change can be measured against it. The full source-to-claim map is in
[`DEPENDENCY_MAP.md`](DEPENDENCY_MAP.md).

## Starting point

| Item | Value |
|---|---|
| `main` head when the rebuild began | `d111da8` ("EMEF 14-16"); the last commit that changed code or results is `09feaae` ("Site Design Pass") |
| EMEF files | 33 files committed loose at the repository root (13 by `669505d`, 11 by `8ca9221` and 9 by `d111da8`); filed under `data/raw/emef/<year>/` by `e7a27d1`, which also added the revised 2022 dictionary |
| Test suite | 299 passed, 1 deselected (`-m slow`), with the national and regional data layers built (Python 3.13, the locked dependency set). Without the layers, `tests/test_microdata_models.py::test_cross_source_models_use_only_validated_or_exact_fields` fails on a missing file instead of skipping |
| Reproducibility | Rebuilding the national layers (`ingest.py all`, `build_tables.py`, `model.py`) and the regional layers (`microdata.py build quality features analyse sources`) left every committed table unchanged; rebuilding the site from the committed tables reproduced all 24 HTML files byte for byte |
| Reconciliation | all 482 checks of `validate.run_all` pass |

## How the site is built and deployed

`scripts/build_site.py` renders `site/*.html` from `reports/tables/*.csv`, `reports/figures/*.svg`
and the two caption files only; it reads nothing under `data/`. Every quoted number is formatted
from a table at build time, and qualitative wording is guarded by checks that stop the build when
a table no longer supports it. `.github/workflows/ci.yml` lints, rebuilds the national and
regional data layers from the raw files and runs `pytest` on every push and pull request; it does
not refit the regional models (about half an hour), whose tables are committed.
`.github/workflows/pages.yml` rebuilds the site from the committed tables on a push to `main` that
touches the site or its inputs and deploys it to GitHub Pages.

## Sources

| Layer | Sources | Unit | Role before the rebuild |
|---|---|---|---|
| National | DGT crash microdata 2016–2024; DGT yearbook series 1993–2024; DGT statistical tables 2014–2024; DGT driver census; DGT ITV kilometres 2022 and 2024; INE residents; CORES fuel; toll-motorway traffic; Ministry interurban vehicle-km | crash; published aggregates | trends, denominators, rates, an association model, a monthly forecast, the external test of the Catalan model |
| Catalonia | Servei Català de Trànsit, crashes with a death or serious injury, 2010–2023 | crash | crash-severity model |
| Barcelona | Guàrdia Urbana crash, person, vehicle, type and cause tables, 2025 | crash, person | person-severity model; descriptive tables |
| Mobility | EMEF 2014–2024 (respondent and trip files) | respondent, trip | none: committed but read by no code |

## What was found at baseline

These are the points the later tasks take up; each is examined in the document named.

1. **The driver-age per-kilometre rates rest on owner-age kilometres.** The drivers page divides
   DGT's car drivers involved in injury crashes (table 4.2) by DGT's 2024 ITV kilometres of cars
   registered to owners of the same age band. The page states this, adds a reassignment scenario
   and a company-car scenario, and treats the result as a range. No source in the repository
   measured kilometres by the driver's age until the EMEF files were added
   ([`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md)).
2. **Deaths once involved** (drivers killed per 1,000 drivers involved, by age) need no exposure;
   numerator and denominator come from the same DGT tables, year and population. This result is
   sound as computed.
3. **The 18-and-over restriction** applies only to the men-against-women comparison on the drivers
   page (`driver_risk.driver_counts_by_sex`). It is the sum of the bands that every source cuts
   alike (no car licence and no owner band below 18). It removes drivers aged 15–17 from numerator
   and denominator together; drivers of unknown age leave the numerator only (about 2%). The
   headline ratio sentence does not say "aged 18 and over"; the table caption does.
4. **The monthly deaths forecast** loses to last year's count in the ordinary held-out years (an
   error of 6.6% against 5.9%) and is replaced by it in the model decisions, yet `forecast.py`'s
   docstring still calls the model "the one used" and the page's minimum detectable change comes
   from the rejected model's errors ([`ML_MODEL_REVIEW.md`](ML_MODEL_REVIEW.md)).
5. **The Catalan severity model** is tested once, on 2023 (1,732 crashes, 209 fatal), with a
   calibration slope of 0.97. Its validation is careful, but the public page leads with ROC-AUC and
   permutation importance rather than predicted against observed outcomes, and there is no tool to
   use it ([`ML_MODEL_REVIEW.md`](ML_MODEL_REVIEW.md)).
6. **Orphans.** Eight result tables are read by no page, link or test (`gen_population_context`,
   `ml_missingness`, `ml_recording_check`, `ml_stability`, `ml_transport_reweighting`,
   `mq_bcn_coordinates`, `mq_bcn_null_rates`, `mq_cat_placeholders`; most feed generated
   documents), and figure `tr3_province_auc.svg` is embedded nowhere.
7. **Disclosed scope mismatches**: sex rates divide drivers (unlicensed and foreign included) by
   holders of any licence class; vehicle rates divide crashes of foreign vehicles by Spanish
   kilometres; a per-fuel check sets interurban deaths against national fuel; residents are taken
   on 1 July nationally and on 1 January for Catalonia. Each is reviewed in
   [`STATISTICAL_AUDIT.md`](STATISTICAL_AUDIT.md).
8. **The Barcelona person table** records the exact age of every driver involved, the uninjured
   included, and the date, so the city's crashes can be split by working day and matched in
   geography to EMEF trips made inside Barcelona: a check on the national design that no other
   source allows.

## Task checklist

Each task is completed, tested and committed on its own.

| Task | Subject | Output |
|---|---|---|
| 1 | Repository audit | this document, [`DEPENDENCY_MAP.md`](DEPENDENCY_MAP.md) |
| 2–3 | Re-evaluation of every model; predicted against observed | [`ML_MODEL_REVIEW.md`](ML_MODEL_REVIEW.md) |
| 4–6 | Interactive crash-severity model, its validation and its findings | [`SEVERITY_CALCULATOR.md`](SEVERITY_CALCULATOR.md) |
| 7–9 | EMEF inventory, harmonisation, access to finer ages | [`EMEF_INVENTORY.md`](EMEF_INVENTORY.md), [`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md) |
| 10–15 | Driving exposure: workday, years, weekends, Spain, 75 and over | [`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md) |
| 16–20 | Crash numerator, rates by age, quasi-induced exposure, uncertainty, conclusions | [`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md) |
| 21–23 | Audit of every public claim; corrections; rewritten text | [`STATISTICAL_AUDIT.md`](STATISTICAL_AUDIT.md) |
| 24 | Site | the drivers and models pages |
| 25 | Final review | [`FINAL_REPORT.md`](FINAL_REPORT.md) |
