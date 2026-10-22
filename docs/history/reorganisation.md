# Reorganisation by section (October 2026)

The repository was reorganised so that it is clear, for every result, which data it comes from.
This document records the audit that led to it, what changed, and where everything moved. Like
the rest of `docs/history/`, it describes a change at a point in time; the current structure is
described in the [README](../../README.md) and mapped in [`docs/catalogue.md`](../catalogue.md).

## What the audit found

The analyses themselves were sound and reproducible: on a fresh machine every committed table and
document that the continuous-integration build regenerates came out byte for byte. The difficulty
was in how the work was organised. The same material was divided in six different ways, none of
them matching another:

| Where | How the material was divided |
|---|---|
| `src/dgt_stats/layers.py` | four "layers": national context, Catalonia, Barcelona, validation (the travel surveys in none of them) |
| `README.md` | four rows of sources: national, Catalonia, Barcelona, travel surveys |
| `docs/methodology.md` | four layers, with the travel surveys *inside* the national context |
| the site's menu | by question: Explore, Over time, Drivers vehicles and factors, Crash severity, Data and methods |
| `scripts/` | by job: `ingest`, `build_tables`, `model`, `analyse`, `microdata`, `severity_calculator`, `emef`, `exposure_risk`, `build_site` (with "model", "microdata models" and "severity_calculator" all fitting models) |
| `reports/tables/` | by prefix: research-question numbers from an early plan (`q1`–`q9`, with no `q4` or `q5`), topic words, and `risk_` used for two unrelated analyses |

Other findings:

- **Where results came from was nowhere stated in one place.** Sources were described in six
  documents (the source register, the national file audit, the raw-file inventory, the source
  comparison, the data contract and the site's sources page), but no file said which sources each
  result table was computed from, or which tables each page published.
- **A false claim.** `layers.py` said that "the site groups its pages by these layers and every
  page names its layer"; no page did.
- **Stale text.** The methodology said the notices of withdrawn analyses were kept as pages; the
  build removes them. Its description of the site's menu no longer matched the menu.
- **Two meanings of "validation".** `validation.csv` and `validate.py` held the 482 reconciliation
  checks of the national data, while the site's `validation.html` and `microdata/validation/` were
  about testing models.
- **Current and historical documents mixed.** The audit trail of the September–October rebuild
  (baseline, dependency map at `d111da8`, claim ledger, statistical audit, reviews, final and
  acceptance reports) sat in `docs/research/` beside the current research documents.
- **Unused material.** One result table (`q7_licence_share`) was written and read by nothing, its
  content superseded by another; one function parameter, two chart functions, a label map and three
  values on the site's pages were unused.
- **Raw files read by no code** (the Madrid MOVILIA extract, the ECEPOV and EHMA tables, the
  `compiled/` registers, the yearbook errata and two DGT reports) were explained in the source
  register but indistinguishable from the others when browsing `data/raw`.

## What changed

**One division, used everywhere.** Five sections, by where the data come from: national
statistics (DGT, INE, Transport, CORES), drivers (DGT's driver tables with the travel surveys),
Catalonia and Barcelona (the regional crash records), the severity model (trained on the regional
records, tested on the others) and data and methods. The code (`src/dgt_stats/<section>/`), the
pipeline stages (`scripts/run.py <section>`), the result tables (`reports/tables/<section>/`), the
documents (`docs/<section>/`), the tests (`tests/<section>/`) and the site's menu all use them.

**A catalogue.** `src/dgt_stats/catalogue.py` declares the sections, every source (each raw file
belongs to exactly one; figures typed from documents that are not archived are listed as
sources; the files kept only as a record are marked as read by no analysis) and every result
table, with the stage that writes it, the sources it is computed from and what it holds. Tables
are read and written only through `paths.table_path(name)`, which takes their folder from the
catalogue. The catalogue is written out as [`docs/catalogue.md`](../catalogue.md), which lists
every table with its sources, stage and pages, and a `README.md` in each table folder; the site
names, on every analysis page, the sources of the tables the page links, and its sources page lists
every source under the same name.
`tests/test_catalogue.py` fails if any of it falls out of step with the files.

**One command.** `scripts/run.py` runs the stages declared in `src/dgt_stats/pipeline.py`, by
section or one at a time, each in its own process; `--list` prints what each does and writes. The
logic that lived in the old scripts moved into each section's `stages.py`.

**Names that say what they hold.** The research-question tables were renamed, the national
`risk_*` tables became `trends_*`, the reconciliation checks became `reconciliation`, and three
modules were renamed for what they do: `validate` → `national.reconcile`, `models` →
`national.associations` (a supporting association analysis, not a predictive model) and
`model_review` → `models.review`; `microdata.sources` became `regional.files`.

**Documents by section,** with the rebuild's audit trail in `docs/history/` and an index in
[`docs/README.md`](../README.md).

## Finding what moved

### Commands

| Before | Now |
|---|---|
| `python scripts/ingest.py all` | `python scripts/run.py national.ingest national.reconcile` |
| `python scripts/build_tables.py` | `python scripts/run.py national.process` |
| `python scripts/model.py` | `python scripts/run.py national.associations` |
| `python scripts/analyse.py tables` | `python scripts/run.py national.results drivers.tables` |
| `python scripts/analyse.py figures` | `python scripts/run.py charts` |
| `python scripts/analyse.py cards` | `python scripts/run.py national.cards` |
| `python scripts/analyse.py withdrawn` | `python scripts/run.py national.withdrawn` |
| `python scripts/microdata.py build`, `quality`, `analyse`, `organise` | `python scripts/run.py regional.build`, `regional.quality`, `regional.analyse`, `regional.organise` |
| `python scripts/microdata.py features`, `models`, `validate`, `documents` | `python scripts/run.py models.features`, `models.fit`, `models.validate`, `models.documents` |
| `python scripts/microdata.py inventory`, `sources` | `python scripts/run.py sources.inventory`, `sources.profile` |
| `python scripts/severity_calculator.py calculator`, `review` | `python scripts/run.py models.calculator`, `models.review` |
| `python scripts/emef.py all` | `python scripts/run.py drivers.emef` |
| `python scripts/exposure_risk.py all` | `python scripts/run.py drivers.exposure` |
| `python scripts/build_site.py` | `python scripts/run.py site` |
| `python scripts/fetch_ine.py`, `fetch_edm.py`, `build_fonts.py` | `python scripts/tools/fetch_ine.py`, `fetch_edm.py`, `build_fonts.py` |

### Documents

| Before | Now |
|---|---|
| `docs/DATA_CONTRACT.md` | `docs/sources/contract.md` |
| `docs/data_sources.md` | `docs/sources/register.md` |
| `docs/RAW_FILE_INVENTORY.md` | `docs/sources/raw_file_inventory.md` |
| `docs/SOURCE_COMPARISON.md` | `docs/sources/source_comparison.md` |
| `docs/data_inventory.md` | `docs/national/file_audit.md` |
| `docs/research/DRIVER_AGE_EXPOSURE.md`, `EMEF_INVENTORY.md`, `EMEF_DATA_REQUEST.md` | `docs/drivers/driver_age_exposure.md`, `emef_inventory.md`, `emef_data_request.md` |
| `docs/DATA_QUALITY_MICRODATA.md`, `docs/BARCELONA_VEHICLE_AUDIT.md` | `docs/regional/data_quality.md`, `barcelona_vehicle_audit.md` |
| `docs/MODEL_DECISIONS.md`, `GENERALISABILITY.md`, `ML_LEAKAGE_AUDIT.md`, `DGT_MICRODATA_AUDIT.md` | `docs/models/decisions.md`, `generalisability.md`, `leakage_audit.md`, `dgt_microdata_audit.md` |
| `docs/research/ML_MODEL_REVIEW.md`, `SEVERITY_CALCULATOR.md` | `docs/models/review.md`, `severity_calculator.md` |
| `docs/models/*.md` (model cards) | `docs/models/cards/*.md` |
| `docs/research/ACCEPTANCE_REPORT.md`, `AUDIT_BASELINE.md`, `CLAIM_LEDGER.*`, `DEPENDENCY_MAP.md`, `FINAL_REPORT.md`, `STATISTICAL_AUDIT.md`, `reviews/` | `docs/history/` (lower-case names; `reviews/` keeps its file names) |

### Code

| Before | Now |
|---|---|
| `dgt_stats.codes` | `dgt_stats.national.codes` |
| `dgt_stats.crash_cells` | `dgt_stats.national.crash_cells` |
| `dgt_stats.derive` | `dgt_stats.national.derive` |
| `dgt_stats.driver_risk` | `dgt_stats.drivers.driver_risk` |
| `dgt_stats.edm2018` | `dgt_stats.drivers.edm2018` |
| `dgt_stats.emef` | `dgt_stats.drivers.emef` |
| `dgt_stats.exposure_risk` | `dgt_stats.drivers.exposure_risk` |
| `dgt_stats.factors` | `dgt_stats.national.factors` |
| `dgt_stats.features` | `dgt_stats.national.features` |
| `dgt_stats.figures` | `dgt_stats.charts.figures` |
| `dgt_stats.forecast` | `dgt_stats.national.forecast` |
| `dgt_stats.io_exposure` | `dgt_stats.national.io_exposure` |
| `dgt_stats.io_microdata` | `dgt_stats.national.io_microdata` |
| `dgt_stats.io_population` | `dgt_stats.national.io_population` |
| `dgt_stats.io_reports` | `dgt_stats.national.io_reports` |
| `dgt_stats.io_tables` | `dgt_stats.national.io_tables` |
| `dgt_stats.io_traffic` | `dgt_stats.national.io_traffic` |
| `dgt_stats.labels` | `dgt_stats.national.labels` |
| `dgt_stats.microdata` | `dgt_stats.regional` |
| `dgt_stats.microdata.charts` | `dgt_stats.charts.regional` |
| `dgt_stats.microdata.inventory` | `dgt_stats.sources.inventory` |
| `dgt_stats.microdata.ml` | `dgt_stats.models.ml` |
| `dgt_stats.microdata.sources` | `dgt_stats.regional.files` |
| `dgt_stats.microdata.validation` | `dgt_stats.models.validation` |
| `dgt_stats.model_cards` | `dgt_stats.national.model_cards` |
| `dgt_stats.model_review` | `dgt_stats.models.review` |
| `dgt_stats.models` | `dgt_stats.national.associations` |
| `dgt_stats.plots` | `dgt_stats.charts.plots` |
| `dgt_stats.policy` | `dgt_stats.national.policy` |
| `dgt_stats.risk_trends` | `dgt_stats.national.risk_trends` |
| `dgt_stats.road_class` | `dgt_stats.national.road_class` |
| `dgt_stats.seasonality` | `dgt_stats.national.seasonality` |
| `dgt_stats.severity_model` | `dgt_stats.models.severity_model` |
| `dgt_stats.source_profile` | `dgt_stats.sources.profile` |
| `dgt_stats.speed` | `dgt_stats.national.speed` |
| `dgt_stats.summaries` | `dgt_stats.national.summaries` |
| `dgt_stats.validate` | `dgt_stats.national.reconcile` |
| `dgt_stats.vehicles` | `dgt_stats.national.vehicles` |
| `dgt_stats.fonts` | `dgt_stats.charts.fonts` |
| `dgt_stats.layers` | removed: `dgt_stats.catalogue` declares the sections |

### Result tables renamed

Every table also moved from `reports/tables/` into `reports/tables/<section>/`; these changed name as well.

| Before | Now |
|---|---|
| `mq_bcn_coordinates` | `regional/bcn_quality_coordinates` |
| `mq_bcn_count_semantics` | `regional/bcn_quality_count_semantics` |
| `mq_bcn_null_rates` | `regional/bcn_quality_null_rates` |
| `mq_bcn_structure` | `regional/bcn_quality_structure` |
| `mq_cat_checks` | `regional/cat_quality_checks` |
| `mq_cat_placeholders` | `regional/cat_quality_placeholders` |
| `q1_annual_headline` | `national/longrun_headline` |
| `q2_night_share` | `national/night_share` |
| `q2_other_road_by_period` | `national/other_road_by_period` |
| `q3_adverse_composition` | `national/assoc_adverse_composition` |
| `q3_adverse_conditions` | `national/assoc_adverse_conditions` |
| `q3_adverse_exclusions` | `national/assoc_adverse_exclusions` |
| `q3_calibration` | `national/assoc_calibration` |
| `q3_groupings` | `national/assoc_groupings` |
| `q3_holdout_summary` | `national/assoc_holdout_summary` |
| `q3_junction_coding` | `national/assoc_junction_coding` |
| `q3_junction_sensitivity` | `national/assoc_junction_sensitivity` |
| `q3_location_contrasts` | `national/assoc_location_contrasts` |
| `q3_marginal_effects` | `national/assoc_marginal_effects` |
| `q3_model_coefficients` | `national/assoc_model_coefficients` |
| `q3_period_refits` | `national/assoc_period_refits` |
| `q3_profiles` | `national/assoc_profiles` |
| `q3_recording_regime` | `national/assoc_recording_regime` |
| `q3_regime_sensitivity` | `national/assoc_regime_sensitivity` |
| `q3_year_stability` | `national/assoc_year_stability` |
| `q6_rates_2022` | `national/vehicles_rates_2022` |
| `q6_summary_2022` | `national/vehicles_summary_2022` |
| `q6_van_light_truck_split` | `national/vehicles_van_light_truck_split` |
| `q6_vehicle_groups` | `national/vehicles_groups` |
| `q6_vehicle_km_2022` | `national/vehicles_km_2022` |
| `q7_company_km` | `drivers/drivers_company_km` |
| `q7_denominator_contrast` | `drivers/drivers_denominator_contrast` |
| `q7_km_by_owner_age` | `drivers/drivers_km_by_owner_age` |
| `q7_km_rates` | `drivers/drivers_km_rates` |
| `q7_km_ratio` | `drivers/drivers_km_ratio` |
| `q7_km_ratio_65_74` | `drivers/drivers_km_ratio_65_74` |
| `q7_owner_age_check` | `drivers/drivers_owner_age_check` |
| `q8_points_calendar_placebo` | `national/policy_points_calendar_placebo` |
| `q8_points_calibration` | `national/policy_points_calibration` |
| `q8_points_death_definitions` | `national/policy_points_death_definitions` |
| `q8_points_fit` | `national/policy_points_fit` |
| `q8_points_forecast` | `national/policy_points_forecast` |
| `q8_points_placebo` | `national/policy_points_placebo` |
| `q8_points_sensitivity` | `national/policy_points_sensitivity` |
| `q8_points_series` | `national/policy_points_series` |
| `q8_points_transitions` | `national/policy_points_transitions` |
| `q8_points_trend_choice` | `national/policy_points_trend_choice` |
| `q8_speed_placebo` | `national/policy_speed_placebo` |
| `q8_speed_sensitivity` | `national/policy_speed_sensitivity` |
| `q9_infraction_shares` | `national/speed_infraction_shares` |
| `risk_annual_panel` | `national/trends_annual_panel` |
| `risk_dispersion` | `national/trends_dispersion` |
| `risk_frequency_severity` | `national/trends_frequency_severity` |
| `risk_fuel_efficiency` | `national/trends_fuel_efficiency` |
| `risk_index` | `national/trends_risk_index` |
| `risk_km_crosscheck` | `national/trends_km_crosscheck` |
| `validation` | `national/reconciliation` |
| `q7_licence_share` | removed: superseded by `drivers/risk_licence_prevalence` and read by nothing |

## Verification

Everything was rebuilt from the raw files with the reorganised code (`python scripts/run.py` over
every stage of `all`, in its order) and compared, file by file, with a build of the code before the
reorganisation (`e593b6b`) on the same machine, a four-core container; the full build took 93
minutes.

- **Result tables.** 199 of the 202 tables are byte for byte the same as the earlier code's. The
  other three differ only as intended: `ml_model_decisions` and `source_comparison` give each
  model's or source's *section* where they gave its *layer*, and `data_inventory` gives the
  current path of the Barcelona vehicle audit in one description.
- **Figures and captions** are identical, and so is the calculator's exported model. The
  withdrawn forecast's six tables, which `all` does not build, were rebuilt with
  `national.withdrawn` and are identical to the committed copies.
- **Model scores that depend on the machine.** Seven model tables (`ml_geography`, `ml_variants`,
  `ml_domain_strategies`, `dgt_audit_artefacts`, `gen_calculator_transfer`, `sev_geography`,
  `sev_penalty`) came out with a few last digits different from the committed copies, and so did
  the earlier code on the same machine: refitting the models on a different processor moves them.
  The committed copies were kept. Where a regenerated document or `model_metrics.json` carries such
  numbers, only the reorganisation's own changes were applied to the committed copy (a three-way
  merge: the earlier code's output, the committed copy, the reorganised code's output).
- **The site.** Every number on every page is the same as on the pages built before the
  reorganisation; the differences are the menu, the previous and next links that follow it, the
  sources named under each page's tables, the new rows of the sources page and the names of the
  renamed downloadable tables.
- **An independent review.** Eleven reviewers read the change (references, the pipeline's
  behaviour, the entry documents, the hand-written documents, the tests, the site and the
  catalogue's entries, table by table) and three skeptics checked each of their findings. The
  confirmed ones were fixed: test paths, skip reasons and two tests that the move had left checking
  nothing; the ignore rules for the new table folders; links in generated documents; leftover
  "layer" wording; a table name the renames had changed by mistake; descriptions and sources of six
  catalogue entries; and the source names, which are now the same on the sources page as under each
  page's tables.
