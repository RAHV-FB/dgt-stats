# dgt-stats: dependency map, from raw source to published claim

Audit of the repository at commit `d111da8` (the `main` head when the rebuild began), made before any analysis was changed. Line numbers refer to that commit.

**How the map was built.**
- Every page builder in `site.PAGE_BUILDERS` (`src/dgt_stats/site/__init__.py:94`) was run into a scratch directory. During the run, `pd.read_csv`, `components.figure` and `components.downloads` were instrumented, so the table lists below show what each page actually reads at run time, not what a grep suggests.
- All 24 rebuilt HTML files are byte-identical to the committed `site/*.html`, so the committed site matches `reports/` exactly.
- A second instrumented run confirmed that the site build reads nothing under `data/`. It reads only `reports/tables/*.csv`, `reports/figures/*.svg`, `captions.json` and `titles.json`.

## 0. Pipeline and legend

**Chain.** `data/raw/**` → readers (`io_*.py`, `microdata/*.py`) → `data/staging/**` → `data/processed/**` (and `data/features/**`) → analysis functions → `reports/tables/*.csv` and `reports/figures/*.svg` → `site/<slug>.html`. The site build is `scripts/build_site.py` → `site.build()` (`site/__init__.py:170`). It also copies **all** 131 CSVs to `site/tables/` and all 40 SVGs to `site/figures/`. Both directories are gitignored and are filled by `.github/workflows/pages.yml`.

**Writer scripts (column "W" in the tables below).**
- **A** = `scripts/analyse.py:run_tables` (l.32). It loops over `summaries.SUMMARIES` (`summaries.py:220`).
- **AF** = `scripts/analyse.py:run_figures` (l.46). It calls `figures.build_all` (`figures.py:76`), which also calls `microdata/charts.py:build` (l.684).
- **M** = `scripts/model.py:main` (l.26). It writes the `q3_*` tables (l.68–85).
- **I** = `scripts/ingest.py validate` (l.45), which runs `validate.run_all` (`validate.py:565`).
- **MD:x** = `scripts/microdata.py <step>` (l.52), where x is one of `inventory`, `quality`, `analyse`, `models`, `validate` or `sources`.

**Raw-source codes (column "Raw").** The reader for each source is given with its line number.

| Code | Raw file(s) under `data/raw/` | Reader → layer |
|---|---|---|
| MICRO | `dgt/microdata/accidentes_2016…2024.xlsx` (+ `diccionario.xlsx` via `codes.py:160`) | `io_microdata.build_all` (io_microdata.py:213) → `scripts/build_tables.py:build` (l.28, `derive.add_fields` derive.py:49) → `data/processed/dgt_accidentes.parquet` |
| SER | `dgt/tables/series_historicas_2024.xlsx` | `io_tables.read_series_annual` (196), `read_series_monthly` (264), `read_series_road_users` (391) |
| TAB4 | `dgt/tables/chapters/2014–2019/grupo_4.xls(x)` + `dgt/tables/tablas_estadisticas_2020–2024.xlsx` (tables 4.1.1, 4.2) | `io_tables.read_driver_victims_all` (928), `read_drivers_involved_all` (934) |
| TAB6 | same workbooks, `grupo_6` / table 6.1, 2014–2024 | `io_tables.read_driver_infractions_all` (1086) |
| TAB2 | `dgt/tables/tablas_estadisticas_2020–2024.xlsx` (tables 2.2, 2.3) | `io_tables.read_units_by_type_all` (613), `read_victims_by_mode_all` (677) |
| CENSUS | `dgt/census/censo_tablas_2014–2023.xlsx` + `censo_conductores_edad_2024/2025.txt` | `io_exposure.licence_holders_by_age` (io_exposure.py:255) |
| CENSUS-B | `dgt/census/censo_conductores_edad_<year>.txt` (B permits) | `io_exposure.b_permit_holders_by_age` (146) |
| KM22 | `dgt/km_itv_2022/media_km_antiguedad_tipo_2022.xlsx` | `io_exposure.read_km_mean_2022` (322) |
| KM24 | `dgt/km_itv_2024/km_edad_propietario_2024.xlsx`, `km_medios_tipo_2024.xlsx` | `read_km_by_owner_age_2024` (422), `read_km_means_2024` (490) |
| INE | `ine/ine_poblacion_provincias_edad_sexo.csv` | `io_population.read_population` (19), `population_by_band` (83) |
| CORES | `cores/cores_consumos_pp.xlsx` | `io_traffic.read_cores_fuel` (123) |
| TOLL | `transportes/peaje_trafico_total.xls` | `io_traffic.read_toll_traffic` (156) |
| ROADKM | `transportes/anuario_carreteras_2023.pdf` | `io_traffic.read_road_traffic` (221) |
| SPEEDREP | `dgt/reports/dgt_factor_velocidad_2023.pdf` | `io_reports.read_speed_report` (203) |
| CAT | `catalonia/accidents_morts_ferits_greus_catalunya_2010_2023.csv` | `microdata/catalonia.py:stage` (95) / `build` (192) → `data/processed/catalonia_severe_crashes.parquet` |
| BCN | `barcelona/2025/accidents_{gu,persones,vehicles,tipus,causes_mediates,causa_conductor}_bcn_2025.csv` | `microdata/barcelona.py:stage` (217) / `build` (497) → `data/processed/barcelona_*.parquet` |
| FEAT | (derived from CAT, BCN) | `microdata/ml/features.py:build_all` (693), `build_common` (525) → `data/features/*.parquet` |
| ALL | every file under `data/raw/` + `manifest.csv` | `microdata/inventory.py:build` (265) |

## 1. Pages

**Site inventory.** 17 live pages, 3 moved pointers and 4 withdrawal notices make 24 HTML files in `site/`. Every one is written by a builder (§3). Abbreviations below: `rt` = `risk_trends.py`, `dr` = `driver_risk.py`, `md/` = `microdata/`. "(link)" marks a table that is offered only as a download link and never read for prose.

### 1.1 `index.html`, overview.py:47 `page_index`
Claims:
- "−74%": "Road deaths in Spain fell from 6,378 in 1993 to 1,680 in 2013"; "the 1,785 deaths of 2024 were more than in 2013"
- "−73%": "Deaths per injury crash fell 73% between 1996 and 2024, while injury crashes per tonne of road fuel sold fell 13%"
- "3.9×": car drivers aged 75 and over who were involved in an injury crash died "3.9 times as often as drivers aged 35–54 (15.9 against 4.1 per 1,000 involved)"
- "2.0–6.8×": drivers aged 18–24 "were involved in 6.8 times as many injury crashes per kilometre", and under an extreme reassignment "the ratio falls to 2.0"
- "2.0×": "police recorded inappropriate speed in 6.9% of injury crashes in 2023"; "about twice the deaths per crash"
- "2 of 3": of three models, "two did better on later records than a simple table of the same records"

Figures: none.

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| longrun_series, longrun_segments, longrun_efficiency | rt:long_run_series (596), long_run_segments (573), long_run_efficiency_sensitivity (635), all via `_long_run_fits` (560) / `joinpoint_search` (455) | A | SER, CORES |
| risk_index, risk_frequency_severity | rt:risk_index (242), frequency_severity (306) ← annual_outcomes / road_user_outcomes / annual_exposure (128–197) | A | SER, INE, CENSUS, CORES |
| q1_annual_headline | summaries.py:67 annual_headline | A | SER |
| q7_km_rates, q7_km_ratio, q7_km_ratio_65_74, q7_company_km, q7_owner_age_check, q7_denominator_contrast | dr:km_rates (114), km_rate_ratios (157), company_km_sensitivity (369), owner_age_check (214), denominator_contrast (429); counts from car_driver_counts (55), km from car_kilometres (95) | A | TAB4 (2024), KM24, CENSUS-B, INE |
| speed_severity, speed_severity_pooled | factors.py:speed_severity (160), speed_severity_pooled (211) ← scoped_microdata_totals (86), `_report` (104) | A | SPEEDREP, MICRO |
| ml_selected, ml_rule_comparison | md/ml/reporting.py:write_tables (172) / md/ml/rules.py:run (91) | MD:models | FEAT (CAT, BCN) |
| ml_transport_validation | md/validation/transport.py:run (814) | MD:validate | FEAT, MICRO |
| ml_outward_path | md/validation/generalisability.py:outward_path (504) via run (996) | MD:validate | earlier tables + MICRO, CAT, BCN |
| ml_model_decisions | md/validation/decisions.py:run (474) | MD:validate | committed ml_*, q3_holdout_summary, forecast_validation |
| missingness_by_year | validate.py:missingness_profile (345) via run_all (565) | I | MICRO (staging) |
| cat_frequency, bcn_person_severity_share | md/descriptive.py:catalonia_frequency (324), barcelona_person_severity (232) via write (381) | MD:analyse | CAT, BCN |

### 1.2 `trends.html`, trends.py:64 `page_trends`
Claims:
- "Spain recorded 1,785 road deaths in 2024, 1.7% more than in 2019"
- "per resident they fell 1.9%, and per tonne of road fuel sold they rose 3.5%"
- hospital admissions rose "11.0% as a count and 13.0% per tonne of road fuel"
- variance around the 2013–2019 trend: "1.5 times the pure-chance (Poisson) variance for deaths, 7.7 times for hospital admissions and 68 times for injury crashes"

Figures: `r1_risk_change` (figures.py:173 `_trend_figures`, drawn from risk_index).

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| risk_annual_panel, risk_index, risk_dispersion, risk_fuel_efficiency | rt:annual_panel (198), risk_index (242), year_to_year_dispersion (211), fuel_efficiency_sensitivity (345) | A | SER, INE, CENSUS, CORES |
| risk_km_crosscheck | rt:km_crosscheck (381) | A | KM22, KM24, CORES |
| longrun_segments | rt:long_run_segments (573) | A | SER, CORES |

### 1.3 `long-run.html`, long_run.py:60 `page_long_run`
Claims:
- "fell slowly until 2003, then by 10.9% a year for the next 10 years"
- "deaths per tonne of road fuel sold fell 76% … deaths per injury crash fell 73% and injury crashes per tonne 13%"
- "the count of deaths in 2020 was 24% lower, outside the trend's range"
- "In 2023 and 2024 deaths per tonne of fuel were 17% and 16% above their trend"
- on interurban roads, "deaths per kilometre in 2023 were 5% above their trend, within its range"

Figures (all from figures.py:208 `_long_run_figures`):
- `l1_trend_projection` and `l2_observed_over_trend`, drawn from longrun_series
- `l3_frequency_severity`, drawn from risk_frequency_severity
- `l4_km_against_fuel`, drawn from longrun_km_check and longrun_km_coverage

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| longrun_series, longrun_segments, longrun_efficiency, longrun_model_choice (link) | rt:596, 573, 635, long_run_model_choice (586) | A | SER, CORES |
| longrun_km_panel, longrun_km_check | rt:interurban_km_panel (705), km_trend_check (739) | A | ROADKM, SER (monthly), CORES |
| longrun_km_coverage | rt:interurban_network_coverage (784) | A | MICRO, SER |
| risk_annual_panel, risk_frequency_severity | rt:198, 306 | A | SER, INE, CENSUS, CORES |
| q1_annual_headline | summaries.py:67 | A | SER |
| road_class_risk | road_class.py:class_risk (183) ← crashes (134) | A | MICRO, ROADKM |

### 1.4 `seasons.html`, seasons.py:65 `page_seasons`
Claims:
- "July has 1.22 times the deaths and August 1.14 times"
- per tonne of fuel, "July and August stand at 1.12× and 1.09×"
- "In April 2020 … deaths fell 68% and road fuel sold 58%"
- in the average August, "toll-motorway traffic at 140" on the index

Figures (all from figures.py:382 `_season_figures`):
- `m1_season_profile`, drawn from season_profile_long
- `m2_month_effects`, drawn from season_month_effects
- `m3_lockdown`, drawn from season_lockdown_long

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| season_profile, season_month_effects, season_lockdown | seasonality.py:seasonal_profile (96), month_effects (133, quasi-Poisson), lockdown_months (183) ← monthly_panel (74) | A | SER (monthly), CORES, TOLL |

### 1.5 `drivers.html`, drivers.py:180 `page_drivers`
Claims:
- "in 2024, 15.9 of every 1,000 involved died within 30 days, against 4.1 per 1,000 at 35–54"
- key result "3.93×" ("95% interval 2.98–5.18")
- "drivers aged 18–24 were involved in 6.75 times as many injury crashes per kilometre as drivers aged 35–54"
- 75 and over involved "1.43 times as often as drivers aged 65–74"
- "Per licence holder, men died at the wheel of a car 3.63 times as often as women in 2022–2024"

Figures:
- `a1_killed_per_involved` (from q7_km_rates), `a4_involved_per_km` (from q7_owner_age_check) and `a2_denominator_contrast` (from q7_denominator_contrast), all from figures.py:637 `_age_figures`
- `a3_sex_ratios`, from drivers_sex_ratios with drivers_sex_rates for the caption n; figures.py:450 `_sex_figures`

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| q7_km_by_owner_age, q7_km_rates, q7_km_ratio, q7_km_ratio_65_74, q7_company_km, q7_owner_age_check, q7_breakeven_km, q7_denominator_contrast | dr:car_kilometres (95), km_rates (114), km_rate_ratios (157), company_km_sensitivity (369), owner_age_check (214), breakeven_km (297), denominator_contrast (429) | A | TAB4 (2024), KM24, CENSUS-B (2024), INE |
| q7_licence_share | summaries.py:161 licence_share_by_age | A | INE, CENSUS |
| drivers_sex_rates, drivers_sex_ratios, drivers_sex_trend | dr:sex_age_rates (553), sex_ratios (572), sex_trend (602) ← driver_counts_by_sex (517) | A | TAB4 (2014–2024), CENSUS |

### 1.6 `vehicles.html`, vehicles.py:37 `page_vehicles` (site)
Claims:
- "a heavy truck (over 3,500 kg) was involved in a fatal crash 10.3× as often as a car per vehicle on the road, and 2.5× as often per kilometre driven"
- each heavy truck "is driven 4.1× as far as a car"
- motorcycles: "2,831 km a year against 13,073 km for a car, so a rate 2.2× a car's per vehicle becomes 10.1× a car's per kilometre"

Figures: `v1_per_vehicle_vs_per_km` (figures.py:729 `_vehicle_figures`, drawn from q6_rates_2022).

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| q6_rates_2022, q6_summary_2022, q6_van_light_truck_split, q6_vehicle_groups (link), q6_vehicle_km_2022 (link) | `src/dgt_stats/vehicles.py`: rates_2022 (324), summary_2022 (391), van_light_truck_split (424), vehicle_groups_table (187), vehicle_km (249) | A | TAB2 (2022), KM22 |
| risk_km_crosscheck | rt:381 | A | KM22, KM24, CORES |

### 1.7 `speed.html`, speed.py:32 `page_speed`
Claims:
- "6.9% of injury crashes in 2023, and those crashes accounted for 21.8% of the deaths"
- "3.41 times as many deaths per crash"
- road-type adjusted: "2.00 times (95% interval 1.69–2.36)"
- urban streets: "0.73 deaths per 100 crashes", a ratio of "5.90 times"
- "1.75" on other interurban roads and "1.22" on dual carriageways

Figures:
- `f1_speed_severity`, from speed_severity_pooled (figures.py:483 `_factor_figures`)
- `c3_speed_status`, from q9_infraction_shares (figures.py:132 `_speed_status_figure`)

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| speed_severity, speed_severity_pooled | factors.py:160, 211 (quasi-Poisson adjusted row) | A | SPEEDREP, MICRO (2016–2023, report's provinces) |
| factor_changes | factors.py:factor_consistency (302) | A | SPEEDREP |
| q9_infraction_shares | speed.py:infraction_shares (29) | A | TAB6 |

### 1.8 `factors.html`, factors.py:31 `page_factors` (site)
Claims:
- "recorded alcohol rose on interurban roads from 5.5% of injury crashes in 2014 to 8.2% in 2023"
- "recorded inappropriate speed fell across all roads from 10.0% to 6.9%"
- "Of the 135 year-to-year changes, 33 are breaks or too small to test"
- break rule: "a rise of more than 25% or a fall of more than 20% … or fewer than 200 crashes". These are code constants `factors.BREAK_RATIO` and `MIN_CRASHES`, not hard-coded text.

Figures: `f2_factor_shares` (figures.py:483, drawn from factor_shares).

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| factor_shares, factor_changes, factor_windows | factors.py:factor_shares_segmented (376), factor_consistency (302), comparable_windows (337) | A | SPEEDREP |
| q9_infraction_shares | speed.py:29 | A | TAB6 |

### 1.9 `severity.html`, severity.py:90 `page_severity` (supporting page)
Claims:
- "a head-on collision had 5.66 times the odds of a death and a pedestrian struck 6.44 times"
- "0.56 times the odds of a death for wet conditions and 0.75 times at a junction"
- "875,013 injury crashes for 2016–2024, of which 1.6% had at least one death within 30 days"
- holdout "ROC-AUC 0.80 for a death and 0.69 for a death or a hospitalisation"
- road alignment "unknown": "95.7% of its 78,990 crashes are Catalan"

Figures (both from figures.py:547 `_severity_figures`):
- `s1_forest_fatal`, from q3_model_coefficients
- `s2_adverse_conditions`, from q3_adverse_conditions

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| q3_model_coefficients, q3_holdout_summary, q3_year_stability, q3_profiles, q3_adverse_conditions, q3_adverse_composition, q3_adverse_exclusions, q3_recording_regime, q3_regime_sensitivity; q3_calibration, q3_marginal_effects, q3_groupings (link) | `src/dgt_stats/models.py`: coefficient_table (327), holdout_check (456), year_stability (520), profiles (581), adverse_conditions (633), level_composition (683), level_exclusions (716), recording_regime (772), regime_sensitivity (814), marginal_effects (364); fit_severity (203); features.grouping_table (325); frame from features.model_frame (286) | M | MICRO |
| q2_other_road_by_period | summaries.py:105 | A | MICRO |
| missingness_by_year | validate.py:345 | I | MICRO |
| dgt_audit_checks | md/validation/dgt_audit.py:run (539) | MD:validate | MICRO, validation.csv, cat_vs_dgt |
| ml_selected | md/ml/reporting.py:172 | MD:models | FEAT |

### 1.10 `forecast.html`, forecast.py:180 `page_forecast` (site, supporting page)
Claims:
- in ordinary held-out years, last year's counts "an error of 5.9% of the year's deaths against 6.6%" for the model
- lockdown years: "7.3% against 19.2%"
- "a fall of 15% (264 deaths) or a rise of 17% in one year's deaths on all roads is detected four times in five"
- "The model's largest miss in the held-out years was 2022"

Figures (both from figures.py:325 `_forecast_figures`):
- `k1_forecast_check`, from forecast_backtest
- `k2_detectability`, from forecast_detectability

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| forecast_selection, forecast_validation, forecast_backtest, forecast_detectability, forecast_coefficients, forecast_horizons (link) | `src/dgt_stats/forecast.py`: model_selection (251), validation (294), backtest (310), detectability (426), coefficients (444), horizon_errors (342) ← model_panel (131) | A | SER (monthly), CORES |

The page also computes the minimum detectable rise at build time with `forecast.minimum_detectable_rise`, from the table values.

### 1.11 `policy.html`, policy.py:104 `page_policy` (supporting page)
Claims:
- "a change in deaths of −7% (95% interval −13% to −1%)"
- "−12% with a straight-line trend"
- "the largest of 15, but only narrowly, and fourth of 15 against forecasts"
- "deaths fell 11.4% across July 2006, the fourth largest fall of the 27 years"
- 2019 speed limit: a placebo break in January 2017 gives "+12%, with an interval that excludes zero", so no estimate is reported

Figures (both from figures.py:759 `_policy_figures`):
- `p1_points_series`, from q8_points_series
- `p2_july_placebos`, from q8_points_calendar_placebo

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| q8_points_fit, q8_points_sensitivity, q8_points_trend_choice, q8_points_calendar_placebo, q8_points_forecast, q8_points_transitions, q8_points_placebo (link) | `src/dgt_stats/policy.py`: points_licence_fits (856), output dict at l.979–986, via summaries `_policy_table` (summaries.py:213) | A | SER (monthly; fuel and toll sensitivity rows: CORES, TOLL) |
| q8_speed_placebo, q8_speed_sensitivity (hard-coded href at site/policy.py:367) | policy.py:speed_limit_fits (990), output l.1034–1035 | A | MICRO |

### 1.12 `catalonia.html`, regional.py:119 `page_catalonia`
Claims:
- "24,478 crashes with a death or serious injury recorded between 2010 and 2023"
- "3,093 (12.6%) were fatal"
- "19.2% on interurban roads, almost three times the 6.9% on urban streets"
- "27.8% when a heavy vehicle was involved and 28.1% at night on roads without street lighting"
- motorways "20.5%" on "only 224 crashes"

Figures:
- `cat1_fatal_by_road`, `cat2_fatal_by_speed_limit`, `cat3_fatal_by_unit` and `cat4_fatal_by_crash_type`, from cat_fatal_share
- `cat6_crashes_by_year`, from cat_frequency
- all from md/charts.py:317 `catalonia_figures`

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| cat_fatal_share, cat_frequency | md/descriptive.py:catalonia_severity (202), catalonia_frequency (324) | MD:analyse | CAT |
| cat_vs_dgt_province_year, cat_per_resident_province_year | md/crosssource.py:catalonia_vs_dgt (64), catalonia_per_resident (84) | MD:analyse | CAT, MICRO, INE |
| ml_recording_artefacts | md/ml/recording.py:audit (54) via reporting.write_tables (172) | MD:models | FEAT (CAT) |
| mq_cat_checks | md/quality.py:build (355) | MD:quality | CAT |

### 1.13 `barcelona.html`, regional.py:517 `page_barcelona`
Claims:
- "recorded 7,741 crashes in 2025"
- "Among the 15,848 people whose outcome was recorded, 1.6% were seriously or fatally injured"
- "6.5% of pedestrians and 3.3% of motorcyclists, against 3 of 4,671 car drivers (0.06%)"
- "people aged 75 and over (5.3%)"
- "Women and men differ little (1.8% and 1.6%)"

Figures:
- `bcn1_severity_by_road_user` and `bcn2_severity_by_age`, from bcn_person_severity_share
- `bcn4_crash_severity_by_type`, from bcn_crash_severity_share
- all from md/charts.py:377 `barcelona_figures`

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| bcn_person_severity_share, bcn_crash_severity_share, bcn_people_by_severity, bcn_cause_profiles, bcn_frequency (link) | md/descriptive.py:barcelona_person_severity (232), barcelona_crash_severity (252), barcelona_frequency (300; it returns both bcn_frequency and bcn_people_by_severity, see l.382), cause_profiles (338) | MD:analyse | BCN |
| mq_bcn_structure | md/quality.py:bcn_structure (51) via build (355) | MD:quality | BCN |

### 1.14 `severity-models.html`, models.py:262 `page_severity_models`
Claims:
- Catalonia model "tested once on the 1,732 crashes of 2023, of which 209 (12.1%) were fatal"
- table "ROC-AUC of 0.70"; model "0.79 (95% interval 0.76–0.82), a gain of 0.09 (0.07–0.12)"
- "11.9% predicted on average against 12.1% observed"; "calibration slope is 0.97"; in Barcelona city "a slope of 0.44"
- Barcelona person model: "58 of 4,049 people (1.4%)"; table "0.78; the model reaches 0.84 (95% interval 0.81–0.87)"
- Barcelona crash model "dropped and the table is reported instead"

Figures (all from md/charts.py:464 `model_figures`):
- `ml1_test_auc`, from ml_selected and ml_variants
- `ml2_calibration`, from ml_calibration
- `ml3_importance_catalonia_crash_severity` and `ml3_importance_barcelona_person_severity`, from ml_importance

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| ml_selected, ml_calibration, ml_importance, ml_geography, ml_feature_catalogue, ml_rare_causes, ml_recording_artefacts, ml_split_isolation (link), ml_variants (link) | md/ml/reporting.py:write_tables (172): `modelling.selected_table` (648) etc.; rare_causes (133) | MD:models | FEAT |
| ml_rule_comparison | md/ml/rules.py:run (91) | MD:models | FEAT |
| ml_subgroup_validation, ml_transport_validation | md/validation/transport.py:person_subgroups (673), run (814) | MD:validate | FEAT, MICRO |
| ml_model_decisions | decisions.py:474 | MD:validate | tables |
| bcn_crash_severity_share | descriptive.py:252 | MD:analyse | BCN |

### 1.15 `validation.html`, validation.py:188 `page_validation`
Claims:
- compare: "0.708" (Catalonia-trained model on DGT records) against "0.712" (DGT-trained model)
- tested on "the 67,971 crashes with a death or serious injury that DGT recorded elsewhere in Spain"; "(95% interval 0.702–0.712) … a difference of −0.004"
- "Fatal crashes are commoner in the test (15.4%) than in the Catalan training records (12.6%); the model's mean prediction, 14.2%"; "calibration slope is 1.10"
- "Across the 46 provinces … from 0.60 (León) to 0.79 (Zaragoza), with a median of 0.68"

Figures: `tr1_catalonia_transfer` and `tr2_dgt_transfer` (md/charts.py:596 `transport_figures`, drawn from ml_transport_validation and ml_selected).

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| ml_transport_validation, ml_transport_provinces, ml_common_feature_validation, ml_domain_shift (link) | transport.py:run (814): common_dgt (243), domain_shift (571); harmonise.validate_dgt (harmonise.py:683) | MD:validate | FEAT, MICRO, BCN |
| ml_barcelona_diagnosis_components, ml_barcelona_diagnosis_verdicts, ml_barcelona_diagnosis (link), ml_domain_strategies (link) | md/validation/diagnosis.py:run (551) | MD:validate | FEAT (CAT, BCN) |
| gen_representativeness, gen_outcomes, gen_province_rates, gen_cross_source_register, ml_outward_path | generalisability.py:representativeness (194), province_rates (220), `CROSS_SOURCE_REGISTER` (289, hand-written frame), outward_path (504), via run (996) | MD:validate | MICRO, CAT, BCN, INE |
| dgt_audit_transfer | dgt_audit.py:run (539) / transfer_checks (304) | MD:validate | MICRO + cat_vs_dgt CSV |
| cat_vs_dgt_province_year | crosssource.py:64 | MD:analyse | CAT, MICRO |
| ml_selected, ml_variants, ml_rule_comparison | reporting.py:172, rules.py:91 | MD:models | FEAT |

### 1.16 `sources.html`, sources.py:373 `page_sources`
Claims:
- "3,093 of its 24,478 crashes (12.6%) were fatal"
- Barcelona: "crashes (7,741, of which 890 record no victim) … people (17,200 records) and vehicles (16,536 records)"
- "13 people died and 247 were seriously injured, and 1,351 person records carry no severity"
- "All 482 of the repository's reconciliation checks pass" (validation.csv: 482 rows, all `passed`)
- "blank in 31% of crashes in one province and 78% in another"
- blanks-only model "ROC-AUC of 0.72 … against 0.83"

Figures: none.

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| validation | validate.py:run_checks (531) via run_all (565) | I | MICRO, SER, TAB2/4/6, CENSUS, SPEEDREP |
| data_inventory | md/inventory.py:write (361) | MD:inventory | ALL |
| dgt_audit_checks, dgt_audit_regional, dgt_audit_artefacts, dgt_audit_outcome_recording (link) | dgt_audit.py:run (539) | MD:validate | MICRO |
| source_comparison (link) | `src/dgt_stats/source_profile.py:write` (510) / build (460) | MD:sources | committed tables + MICRO, CAT, BCN processed |
| bcn_vehicle_audit_counts | md/vehicles.py:write (270), called from quality.build | MD:quality | BCN |
| mq_bcn_structure, mq_bcn_count_semantics | quality.py:51, 91 | MD:quality | BCN |
| cat_fatal_share, cat_frequency, cat_vs_dgt_province_year, bcn_people_by_severity, bcn_person_severity_share | descriptive / crosssource (as above) | MD:analyse | CAT, BCN, MICRO |
| q1_annual_headline, q6_rates_2022, risk_frequency_severity, longrun_km_panel, factor_shares | (as above) | A | SER, TAB2, KM22, ROADKM, SPEEDREP… |

### 1.17 `data.html` (Methodology), data.py:660 `page_data`
Claims:
- "14.2% of the deaths within 30 days occurred after the first 24 hours"
- "1.5 times the Poisson variance for deaths, 7.7 times for hospital admissions and 68 times for injury crashes"
- "the median circumstance field is blank in 52.8% of crashes"
- "83% of that year's “other” crashes are on urban streets, against 43% in 2016–2023"
- junction field: "blank cells fall from 61% to 48% of crashes and “not specified” rises from 1% to 15%"
- nine placeholder levels in eight Catalan fields at "at least 1.5 times as often in non-fatal crashes"

Figures: `d1_missingness` (figures.py:816 `_data_figures`, drawn from missingness_by_year).

| Result tables | Producing function(s) | W | Raw |
|---|---|---|---|
| validation, missingness_by_year | validate.py:531, 345 | I | MICRO etc. |
| risk_dispersion, longrun_segments, longrun_km_panel, longrun_km_check, longrun_fuel_bio | rt:211, 573, 705, 739, fuel_bio_share (683) | A | SER, ROADKM, CORES |
| q2_other_road_by_period, q7_owner_age_check | summaries.py:105; dr:214 | A | MICRO; TAB4, KM24, CENSUS-B |
| dgt_audit_outcome_recording, dgt_audit_regional | dgt_audit.py:outcome_recording (281), regional_recording (187) | MD:validate | MICRO |
| ml_common_features, ml_common_feature_validation | harmonise.catalogue_frame (604), validate_dgt (683) via transport.run | MD:validate | CAT, MICRO, BCN |
| ml_feature_catalogue, ml_recording_artefacts, ml_selected, ml_split_isolation, ml_rule_comparison | reporting.py:172, rules.py:91 | MD:models | FEAT |
| mq_cat_checks, mq_bcn_count_semantics | quality.py:355 | MD:quality | CAT, BCN |
| cat_frequency, cat_vs_dgt_province_year, bcn_person_severity_share | descriptive / crosssource | MD:analyse | CAT, BCN, MICRO |

## 2. Models

| Model | Code (file:function) | Training data | Target | Committed metric tables | Page(s) |
|---|---|---|---|---|---|
| DGT crash-severity association model (logistic, cluster-robust by province) | `scripts/model.py:main` (26) → `models.py:fit_severity` (203), `holdout_check` (456), `year_stability` (520), `regime_sensitivity` (814); frame `features.py:model_frame` (286) | MICRO, 875,013 injury crashes 2016–2024. The holdout fit uses 2016–2022 (671,711) and tests on 2023–2024 (203,302). | `fatal` (≥1 death ≤30 d), `serious` (death or hospitalisation) | q3_holdout_summary (AUC 0.801 / 0.693), q3_calibration, q3_year_stability, q3_regime_sensitivity, q3_model_coefficients | severity (+ s1, s2); decision row in ml_model_decisions = "KEEP as research/diagnostic model" |
| Monthly deaths forecast (Poisson GLM: month + trend + log fuel + calendar, 4-yr window); comparators: naive and boosted trees | `forecast.py`: model_panel (131), model_selection (251), validation (294), backtest (310), horizon_errors (342), detectability (426) | SER monthly 30-day deaths + CORES; selection on 2006–2015, holdout 2016–2019 + 2022–2024, pandemic 2020–2021 scored apart | monthly deaths (all, interurban, urban) | forecast_selection, forecast_validation, forecast_backtest, forecast_horizons, forecast_detectability, forecast_coefficients | forecast (+ k1, k2); decision: "REPLACE with descriptive table" (naive) |
| 2006 points-licence interrupted series (Poisson, Newey–West, piecewise trend knot by AIC) | `policy.py:points_licence_fits` (856) | SER monthly deaths Jan 2000–Nov 2007 (+ CORES, TOLL sensitivity) | monthly 30-day deaths | q8_points_fit, q8_points_sensitivity, q8_points_trend_choice, q8_points_placebo, q8_points_calendar_placebo, q8_points_forecast, q8_points_transitions | policy (+ p1, p2) |
| 2019 90 km/h difference-in-differences (Poisson ITS) | `policy.py:speed_limit_fits` (990) | MICRO 2016–2024, road codes 5–6 against 1–3 | monthly deaths `TOTAL_MU30DF` | q8_speed_placebo, q8_speed_sensitivity (negative result only) | policy |
| Long-run joinpoint (segmented log-linear, QBIC) | `risk_trends.py:joinpoint_search` (455), `_long_run_fits` (560), `km_trend_check` (739) | SER annual deaths 1993–2019 (offsets: fleet, CORES fuel); interurban km 2008–2019 (ROADKM) | annual deaths, with rate offsets | longrun_model_choice, longrun_segments, longrun_series, longrun_km_check | long-run, trends, index, data |
| Month effects (quasi-Poisson, year + month, optional log-fuel offset) | `seasonality.py:month_effects` (133) | SER monthly 2014–2024 excluding 2020–21; CORES | monthly deaths | season_month_effects | seasons (+ m2) |
| Speed-severity adjustment (quasi-Poisson, crashes as exposure, road type + year) | `factors.py:speed_severity_pooled` (211) | SPEEDREP + MICRO, 2016–2023, Spain without Catalonia and the Basque Country | deaths per crash | speed_severity_pooled ("adjusted" row) | speed, index (+ f1) |
| Catalonia crash-severity (primary: boosted trees, context set, broad geography) | `md/ml/features.py` CATALONIA_TABLE (422); `md/ml/modelling.py:run_task` (584), make_model (97), temporal_split (325); `md/ml/reporting.py:fit` (522) | FEAT ← CAT: train 2010–2020, choose on 2021–2022, test 2023 (n=1,732, 209 fatal) | `fatal` (D_GRAVETAT "Accident mortal", 24 h) vs serious | ml_selected (ROC-AUC 0.790, 0.758–0.824), ml_variants, ml_calibration, ml_importance, ml_geography, ml_stability, ml_split_isolation, ml_rule_comparison (table 0.695), ml_model_decisions = KEEP | severity-models, index, validation |
| Barcelona person-severity (boosted trees) | features.py BARCELONA_PERSON_TABLE (438); modelling.grouped_month_split (343) | FEAT ← BCN people 2025: months 1–9 with 5-fold CV grouped by crash; test months 10–12 (n=4,049, 58 positive) | `serious_or_fatal` | ml_selected (0.843, 0.813–0.874; calibration slope 0.63), ml_rule_comparison (0.780), ml_subgroup_validation; KEEP but ranking-only | severity-models |
| Barcelona crash-severity (logistic) | features.py BARCELONA_CRASH_TABLE (455) | FEAT ← BCN crashes 2025, same split (n=1,994, 58 positive) | `serious_or_fatal_crash` | ml_selected (0.737), ml_rule_comparison (table 0.734, gain +0.003, −0.039 to +0.051); REPLACE with table | severity-models |
| Harmonised Catalonia model on DGT variables (logistic) | features.py `_common_table` (489) / common_tables (508); transport.py:common_dgt (243) | FEAT ← CAT restricted to 10 DGT-compatible fields; applied to MICRO outside Catalonia (67,971 crashes) | `fatal` (24 h) | ml_selected (0.705 in-domain), ml_transport_validation, ml_transport_provinces, ml_common_feature_validation, dgt_audit_transfer | validation (+ tr1, tr2; tr3 unused) |
| Harmonised Catalonia model on Barcelona variables (boosted trees) | common_tables (508); transport.py:common_bcn (400); diagnosis.py:run (551) | FEAT ← CAT restricted to BCN-compatible fields; tested on BCN | `fatal` | ml_selected (0.681), ml_transport_validation, ml_barcelona_diagnosis*, ml_domain_strategies | validation |
| Rule baselines (smoothed lookup tables) | `md/ml/rules.py:run` (91), fit_rule / apply_rule | same splits as each model | same as the model | ml_rule_comparison | severity-models, index, data, validation |

## 3. Stale, withdrawn and orphan items

### 3.1 HTML pages in `site/`
- **No stale page.** All 24 `site/*.html` are written by `build()`:
  - 17 by `PAGE_BUILDERS`
  - 3 by `page_moved` (`site/__init__.py:115`)
  - 4 by `page_withdrawn` (`site/__init__.py:142`)
  
  `build()` deletes any HTML file that no builder wrote (`site/__init__.py:210–212`). A fresh build reproduces the committed HTML byte for byte.
- **Moved pointers** (meta-refresh + canonical; `components.py:82`):
  - `older-drivers.html` → drivers
  - `context.html` → long-run
  - `transport.html` → validation
- **Withdrawn notices** (`components.py:85–124`; noindex, no figure and no script of their own; enforced by `tests/test_withdrawn.py:78–100`): `simulator.html`, `distraction.html`, `alcohol-drugs.html`, `enforcement.html`. They were withdrawn because their results came from coefficients in external studies. `test_withdrawn.py` also checks that:
  - no code reads the evidence registers;
  - `simulator.py`, `factor_models.py`, `site/simulator.py` and `site/factor_pages.py` are gone;
  - no `simulator_*`, `factor_{deaths,…}` or `drivers_sex_travel` table remains.
  
  All four checks hold. The registers `data/raw/compiled/evidence/{simulator,factor}_parameters.csv` are still committed in `data/raw` (immutable) but are read by no code.

### 3.2 Orphan tables (131 committed CSVs, 104 read by some page, 13 more only linked)
**(a) Neither read nor linked by any page, and read by no test.** All are still copied to `site/tables/` at build time.

| Table | Writer | Used elsewhere? |
|---|---|---|
| gen_population_context | generalisability.py:population_context (255) / run (996) | only in `generalisability.document` → docs/GENERALISABILITY.md |
| ml_missingness | reporting.py:write_tables (190) | none |
| ml_recording_check | reporting.py:191 | leakage_audit → docs/ML_LEAKAGE_AUDIT.md (reporting.py:433) |
| ml_stability | reporting.py:187 | outward_path (generalisability.py:507), model cards (reporting.py:238) |
| ml_transport_reweighting | transport.py:843 | none |
| mq_bcn_coordinates, mq_bcn_null_rates, mq_cat_placeholders | quality.py:373–377 | docs/DATA_QUALITY_MICRODATA.md only |

**(b) Not read or linked by any page, but read by tests and/or used to draw a figure.** `tests/test_plots.py:350` reads every SUMMARIES table.

| Table | Writer | Role |
|---|---|---|
| q8_points_series | policy.py:980 | input of figure p1 (figures.py:761); tests/test_policy.py:225 |
| season_profile_long, season_lockdown_long | seasonality.py:119, 215 | inputs of figures m1, m3 |
| q2_night_share | summaries.py:86 | test only. docs/methodology.md:46 calls it "published as a table only", but no page links it. |
| road_class_baseline | road_class.py:145 | test only (test_withdrawn.py:54); cited by docs/methodology.md:271 |

**(c) Linked as a download only (never read for prose).**
- bcn_frequency, forecast_horizons, longrun_model_choice
- ml_barcelona_diagnosis, ml_domain_shift, ml_domain_strategies
- q3_calibration, q3_groupings, q3_marginal_effects
- q6_vehicle_groups, q6_vehicle_km_2022
- q8_points_placebo, source_comparison
- q8_speed_sensitivity, linked through a hard-coded `<a href="tables/q8_speed_sensitivity.csv">` at site/policy.py:367

**(d) Read for prose but never linked** (no download link).
- bcn_vehicle_audit_counts, longrun_fuel_bio
- ml_barcelona_diagnosis_verdicts, ml_common_features
- mq_bcn_count_semantics, mq_cat_checks
- q1_annual_headline, q2_other_road_by_period, q8_points_fit

### 3.3 Orphan figures
- `reports/figures/tr3_province_auc.svg` is written by md/charts.py:596 `transport_figures` (l.666–673, from ml_transport_provinces and gen_province_rates). It has a caption and a title, but **no page embeds it**. validation.html quotes the same province range in prose ("0.60 (León) to 0.79 (Zaragoza)").
- All other 39 SVGs are embedded. captions.json and titles.json have exactly the 40 SVG keys, with no extras.

### 3.4 Raw inputs that never reach a page
**Raw files read by no analysis code** (only inventoried by `md/inventory.py`):
- `emef/2014–2024/*` (34 files)
- `comunidad_madrid/movilia_madrid/*.xls` (5), `transportes/movilia_2006.xls`, `transportes/movilia_2007.xls`
- `ine/ine_ecepov_2021_55378.xlsx`, `ine/ine_ehma_2008_*.csv` (2)
- `compiled/driving_activity_by_age.csv`, `compiled/evidence/*` (2)
- `dgt/reports/Anuario-…-fe-de-erratas.pdf` (5), `dgt_personas_mayores_2023.pdf`, `dgt_semana_santa_2026.pdf`
- `dgt/km_itv_2022/metodologia.pdf`, `dgt/microdata/metadata_2024.rdf.xml`

The EMEF files were committed without any code reading them; their ingestion is added by this rebuild ([`EMEF_INVENTORY.md`](EMEF_INVENTORY.md)).

**Staged but consumed only by tests:**
- `km_estimados_2022` (`km_recorridos_estimados_2022.xlsx`, io_exposure.py:355)
- `series_age`, `series_sex`, `series_province`, `series_pedestrians`
- `tables_2024_vehicles_involved`

**Read only by validation (`validate.run_checks`):** the driver-census text files `censo_conductores_<year>.txt` and `censo_tablas_2025` province totals.

## 4. Notes and surprises

1. **The 18-and-over filter (drivers page only).**
   - `rates.py` has no age filter. The restriction lives in `driver_risk.py`:
     - `SEX_BANDS` (l.477) = 18-24…75+;
     - `ADULT_BAND = "18+"` (l.478) is built in `driver_counts_by_sex` (l.517–550) as the **sum of the six SEX_BANDS rows**, after `keyed.exposure_band.isin(SEX_BANDS)` (l.544) and `keyed.sex.isin(SEX_LABELS)`;
     - `sex_trend` (l.602–609) keeps only the 18+ row.
   - The site reads it at `site/drivers.py:156` (sex table, captioned "Drivers aged 18 and over by sex … Licence holders include every type of licence.") and at l.224–228 (the headline men/women ratios, including "3.63 times"). `figures.py:473` uses the same row for the a3 caption n (290,654).
   - **Why:** `agebands.py:45–50`: "15-17 exists only in the driver tables (no car licence before 18, and no owner band below 18) and is never compared". The census, the driver tables and the km release share cuts from 18 up.
   - **Effect** (recomputed from staging, 2022–2024 pooled):
     - The filter applies to numerator and denominator together. In the motor scope it drops 4,492 drivers involved aged 15–17, 32 deaths and 172,433 licence-holder-years (car scope: 123 involved, 1 death).
     - It drops from the **numerator only**: 120 involved aged 0–14, and drivers of unknown age (motor: 7,143 involved, 6 deaths; car: 4,754 involved, 2 deaths), plus unknown sex.
     - So 18+ rates per licence holder slightly understate. The docstring acknowledges about 2% (dr:520–525).
   - The page summary sentence "men died at the wheel of a car 3.63 times as often as women" does not itself say "aged 18 and over". The table caption does.
   - Separately, the four-denominator contrast starts at 25 (`CONTRAST_BANDS`, dr:47–49), because INE five-year groups cannot be cut at 18. `q7_licence_share` uses `ANALYSIS_BANDS` 15–24, which **includes** 15–17.
2. **Numerator and denominator mismatches disclosed in code.**
   - Sex rates divide drivers involved or killed (including unlicensed and foreign drivers, dr:522–525) by holders of **any** licence class, even in the car-only scope. This sits awkwardly beside data.html's "Each count is divided only by a denominator that could contain it".
   - Vehicle rates count foreign-registered vehicles in the numerator but only Spanish kilometres in the denominator (disclosed at site/vehicles.py:228).
   - Per-km age rates use the owner's age, not the driver's (dr:11–15; handled as a range via owner_age_check).
   - `km_trend_check` per-fuel: "its scope does not match the numerator" (rt:746).
   - road_class: urban-zone crashes on State, regional or provincial roads are outside the numerator while their kilometres may be in the denominator (road_class.py:36–41).
   - Residents are taken on 1 July in rt:17 and rt:182 but on 1 January in `catalonia_per_resident` (crosssource.py:97).
3. **Forecast decision against code docstring.**
   - `forecast.py:37–41` still says "so the model is the one used".
   - ml_model_decisions, docs/models/dgt_monthly_deaths_forecast.md:5 and forecast.html all say the model is **replaced by the naive forecast** for ordinary years: 5.9% against 6.6%.
   - The page still derives its minimum detectable change ("15% (264 deaths)") from the rejected model's errors. The card justifies this as "kept for … the detectable change".
4. **Hard-coded numbers in site modules: none for results.**
   - Every quoted result is formatted from a table at build time. Qualitative words are guarded by `_check` / `_require`, for example:
     - "about twice" accepts a ratio of 1.8–2.2 (overview.py:234–242);
     - "less than 0.01" is checked by `models.py:727–731` (actual gains +0.006 and +0.008);
     - the a1 alt text "rises with each older band" is checked at drivers.py:249–250.
   - Literals are limited to definitions such as "95% interval" and "0.5 is chance", and to code constants such as `factors.BREAK_RATIO`. seasons, vehicles, speed, factors and policy use local `checks`/`failed` dicts instead of `_check`.
5. **Downloads depend on a CI build.** `site/tables/` and `site/figures/` are gitignored. The committed HTML links resolve only after `scripts/build_site.py` runs (pages.yml does this). Every CSV, including the orphans in 3.2(a), is published at `site/tables/*.csv`.
6. **Order dependency.**
   - `ml_model_decisions` (MD:validate) reads `q3_holdout_summary` (M) and `forecast_validation` (A) (decisions.py:270–278, 329).
   - `dgt_audit` reads `validation.csv` (I) and `cat_vs_dgt_province_year.csv` (MD:analyse) (dgt_audit.py:122, 306).
   - So the run order is: ingest → build_tables → model → analyse tables → microdata analyse/models/validate → analyse figures.
   - CI does not refit the ML models (ci.yml comment); the `ml_*` and `gen_*` tables are committed as-is.
7. **Recording regime.** The DGT association model's "unknown alignment" level is 95.7% Catalan (severity.html). The national file is kept out of model training (sources.html: a blanks-only model reaches ROC-AUC 0.72 against 0.83). This is consistent with `dgt_audit_checks`.
