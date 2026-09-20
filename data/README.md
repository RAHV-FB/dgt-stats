# Data directory

Data are organised by processing stage. Source data must never be manually edited in place.

## Layers

- `raw/`: source downloads kept byte for byte, except `ine_poblacion_provincias_edad_sexo.csv` (an extract of INE table 56947 written by `scripts/fetch_ine.py`) and `driving_activity_by_age.csv` (hand-typed survey values); tracked in Git, with `raw/manifest.csv` listing path, size, SHA-256, source URL, description and the date added. Subfolders: `microdata/`, `tables/`, `exposure/`, `reports/`.
- `interim/`: parsed files with harmonised encodings, names and types.
- `processed/`: validated, analysis-ready tables at documented units of observation.

`interim/` and `processed/` are ignored by Git and rebuilt from `raw/`.

## Building the interim layer

```bash
python scripts/ingest.py all        # microdata, tables, exposure, reports, validate (about 6 minutes)
python scripts/ingest.py microdata --years 2024 --force
python scripts/ingest.py validate
```

| Step | Output in `interim/` | Notes |
|---|---|---|
| `microdata` | `microdata/accidentes_YYYY.parquet` (9 files) and `microdata/accidentes_all.parquet` (875,013 rows, 74 columns) | one row per injury crash; codes kept as integers, `SECUENCIAL` renamed to `ID_ACCIDENTE`, VMP death columns added as missing where a year lacks them; about 35 s per year |
| `tables` | `series_annual`, `series_monthly`, `series_province`, `series_age`, `series_sex`, `series_road_users`, `series_pedestrians`, `tables_2024_province`, `tables_2024_month`, `tables_2024_vehicles_involved`, `tables_units_by_type` (2.3, 2020–2024), `tables_victims_by_mode` (2.2, 2020–2024), `tables_driver_victims` (4.1.1, 2014–2024), `tables_drivers_involved` (4.2, 2014–2024), `tables_driver_infractions` (6.1, 2014–2024) | tidy long frames with a `source_sheet` column; `.` cells become missing; the driver tables carry a `band` column on the DGT age bands |
| `exposure` | `censo_conductores` (2023–2025 stacked), `censo_provincias_2025`, `censo_edad` (2023–2025 by province, sex and age band), `censo_edad_tablas` (published class × age totals 2014–2023), `conductores_por_edad` (2014–2025 stitched), `poblacion_ine` (INE residents 2002–2025), `km_medios_2022`, `km_estimados_2022` | census `licence_class` is the driver's highest class; `conductores_por_edad` uses the published tables to 2023 and the text files from 2024 |
| `reports` | `speed_report` | 61 of the 64 tables of the DGT speed-factor report (2014–2023, without Cataluña or País Vasco; all but the three year-on-year variation tables) transcribed from the PDF text with `pymupdf`; long format with the table's metric, zone, breakdown and a `region_scope` column on every row |
| `validate` | `reports/tables/validation.csv`, `reports/tables/missingness_by_year.csv` (both committed) | reconciliation against the yearbook and 2024 tables, key uniqueness, code domains, census cross-check, driver deaths in the yearly tables against the series (2014–2024), 2023 census by age against the published table, vehicles involved and deaths by means of transport in the yearly tables 2.3 and 2.2 against the microdata (2020–2024), the driver-infraction tables 6.1 against the drivers involved in table 4.2 within 1.5 % with one total across their blocks (2014–2024, both zones), per-year missingness (434 checks) |

Existing outputs are skipped unless `--force` is given. Tests that need the interim layer skip themselves with a message until it has been built.

## Processed layer and results

```bash
python scripts/build_tables.py      # data/processed/accidentes.parquet: interim crashes + derived fields
python scripts/model.py             # reports/tables/q3_*.csv: the severity models (about 30 seconds)
python scripts/analyse.py all       # reports/tables/q*.csv, reports/figures/*.svg, captions.json
python scripts/build_site.py        # site/*.html, site/style.css, site/figures/
```

`data/processed/accidentes.parquet` (875,013 rows, 102 columns) adds outcome flags (`fatal`, `serious`),
`zone`, `road_group`, `hour_band`, `night`, `weekend`, a `status_*` companion for every condition column
and an English `*_label` column for the code lists used on the site. The result tables, the figures
under `reports/` and the site's HTML and CSS are committed so they can be reviewed without rebuilding;
`site/figures/` is not, and `build_site.py` copies the SVGs from `reports/figures/` into it.

## Source inventory

The full audit is in [`docs/data_inventory.md`](../docs/data_inventory.md).

| Group | Files | Used for |
|---|---|---|
| Crash microdata 2016–2024 | nine yearly workbooks, the code dictionary | timing, road users, severity, the 2019 case study, monthly deaths by road type |
| Yearbook series 1993–2024 | one workbook, 69 sheets | trends, occupant deaths by vehicle, the 2006 case study |
| Statistical tables 2014–2024 | chapter workbooks to 2019, one workbook per year from 2020 | province and month totals, vehicles involved, victims by mode, drivers by age, sex and infraction |
| Driver census 2014–2025 | text extracts and published tables | licence-holder denominators by province and age |
| INE population 2002–2025 | one CSV | resident denominators by province and age |
| ITV kilometre estimates 2022 | two workbooks and the methodology note | vehicle-kilometres by type and age; the circulating fleet |
| Travel and driving surveys | MOVILIA 2006–2007, ECEPOV 2021, EHMA 2008, ESRA shares | the travel-weighted driver denominator (MOVILIA 2006 and the ESRA shares); the others are registered for context |
| DGT thematic reports | speed factor, older road users, Easter 2026 | the speed page (transcribed), definitions |

The driver-census text files use a pipe delimiter. The census-by-class files
(`censo_conductores_YYYY.txt`) carry five fields:

```text
COD_PROVINCIA | IND_SEXO | CLASE_PERMISO | DESC_ANTIG_PERMISO | NUM_CONDUCTORES
```

The 2025 file includes a UTF-8 byte-order mark, while the 2023 and 2024 files are ASCII. The
census-by-age files (`censo_conductores_edad_YYYY.txt`) carry twelve fields (`COD_PROVINCIA |
IND_SEXO | EDAD | NUM_PERMISOS | NUM_LICENCIAS | NUM_LICENCIAS_PERMISOS | NUM_PERMISOS_A …
NUM_PERMISOS_LVA`); their 2023 and 2024 files are ISO-8859-1 and the 2025 file is UTF-8 with a
byte-order mark, as encoded in `io_exposure.CENSUS_AGE_ENCODINGS`. Ingestion handles each encoding
and trims fixed-width padding from categorical values.

The checks that run before any analysis are listed on the data page and in
[`docs/methodology.md`](../docs/methodology.md), section 2.
