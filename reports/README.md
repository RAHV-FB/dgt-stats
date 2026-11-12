# Reports

Result tables and figures, all committed. Each is rebuilt from the raw files and must match the
committed copy.

## Tables (`tables/`)

| Written by | Table families |
|---|---|
| `scripts/ingest.py validate` | `validation`, `missingness_by_year` |
| `scripts/model.py` | `q3_*` (associations with crash severity) |
| `scripts/analyse.py tables` | `risk_*` (2019 onwards), `longrun_*`, `season_*`, `drivers_*`, `q6_*` (vehicles), `speed_*`, `q9_*`, `factor_*`, `road_class_*`, `q2_*`, `q8_*` (2006), `explore_dgt_crashes` (the crash explorer) |
| `scripts/microdata.py` | `mq_*` (data quality), `cat_*` and `bcn_*` (descriptive), `ml_recording_artefacts`, `source_comparison`; `analyse` also writes `gen_coding_by_region` and `dgt_audit_*` |
| `scripts/severity_model.py` | `sev_*` (the Catalan model and its evaluation) |
| `scripts/emef.py` | `emef_*` (car-driving distance by age) |
| `scripts/exposure_risk.py` | `risk_national_*`, `risk_barcelona_*`, `risk_older_*` and the other driver-age `risk_*` tables; `risk_national_ranges` holds the ranges across assumptions |

Tables that rest on fewer than 20 survey observations are not published, as the EMEF survey
requires.

## Figures (`figures/`)

One SVG per figure, a narrow variant in `narrow/`, and `captions.json` and `titles.json`, which
record the source, period and metric of each figure. They are written by
`scripts/analyse.py figures`.

## Use

The site reads only these files. `scripts/build_site.py` copies the SVGs a page shows into
`site/figures/` and the tables a page links into `site/tables/`, so a reader can get the full
result behind a figure. A page that links a missing table stops the build. Neither copy is
committed. Every committed table is read by a page, a figure, the findings document or a test.
