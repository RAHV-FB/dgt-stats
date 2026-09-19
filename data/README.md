# Data directory

Data are organised by processing stage. Source data must never be manually edited in place.

## Layers

- `raw/`: byte-for-byte source downloads, tracked in Git, with `raw/manifest.csv` listing path, size, SHA-256, source URL and description. Subfolders: `microdata/`, `tables/`, `exposure/`, `reports/`.
- `interim/`: parsed files with harmonised encodings, names and types.
- `processed/`: validated, analysis-ready tables at documented units of observation.

`interim/` and `processed/` are ignored by Git and rebuilt from `raw/`.

## Building the interim layer

```bash
python scripts/ingest.py all        # microdata, tables, exposure, validate (about 6 minutes)
python scripts/ingest.py microdata --years 2024 --force
python scripts/ingest.py validate
```

| Step | Output in `interim/` | Notes |
|---|---|---|
| `microdata` | `microdata/accidentes_YYYY.parquet` (9 files) and `microdata/accidentes_all.parquet` (875,013 rows, 74 columns) | one row per injury crash; codes kept as integers, `SECUENCIAL` renamed to `ID_ACCIDENTE`, VMP death columns added as missing where a year lacks them; about 35 s per year |
| `tables` | `series_annual`, `series_monthly`, `series_province`, `series_age`, `series_sex`, `series_road_users`, `series_pedestrians`, `tables_2024_province`, `tables_2024_month`, `tables_2024_units`, `tables_2024_vehicles_involved` | tidy long frames with a `source_sheet` column; `.` cells become missing |
| `exposure` | `censo_conductores` (2023–2025 stacked), `censo_provincias_2025`, `km_medios_2022`, `km_estimados_2022` | census `licence_class` is the driver's highest class |
| `validate` | `reports/tables/validation.csv`, `reports/tables/missingness_by_year.csv` (both committed) | reconciliation against the yearbook and 2024 tables, key uniqueness, code domains, census cross-check, per-year missingness |

Existing outputs are skipped unless `--force` is given. Tests that need the interim layer skip themselves with a message until it has been built.

## Source inventory

The full audit is in [`docs/data_inventory.md`](../docs/data_inventory.md).

| Source group | Files currently available | Intended use |
|---|---|---|
| Crash microdata | `microdata/accidentes_2016.xlsx` … `accidentes_2024.xlsx`, dictionary | Crash-level analysis, severity models |
| Driver census | Pipe-delimited files for 2023, 2024 and 2025; 2025 statistical workbook | Exposure context by province, sex, licence class and licence seniority |
| Injury crashes | 2024 DGT statistical tables | Official totals and validation controls |
| Historical series | DGT accident-yearbook series through 2024 | Long-run trends by area, severity, sex, age and road-user role |
| Distance travelled | Annual kilometre estimates by vehicle type; mean kilometres by vehicle age/type; ITV/fleet methodology report | Exposure-adjusted rates |
| Thematic reports | Speed, older road users and Easter 2026 mortality reports | Definitions, context and hypothesis development |

The driver-census text files use a pipe delimiter. Their observed fields are:

```text
COD_PROVINCIA | IND_SEXO | CLASE_PERMISO | DESC_ANTIG_PERMISO | NUM_CONDUCTORES
```

The 2025 file includes a UTF-8 byte-order mark, while the 2023 and 2024 files are ASCII. Ingestion must handle both encodings and trim fixed-width padding from categorical values.

## Required validation before analysis

1. Establish the unit of observation for every table.
2. Preserve original identifiers and raw labels.
3. Reconcile annual totals against the published DGT tables.
4. Check duplicate keys, missing values, impossible dates and category drift.
5. Confirm whether injury outcomes use 24-hour or 30-day definitions.
6. Document breaks in series and changes in data collection.
7. Keep `unknown`, `not tested`, `not applicable` and `no` as separate states.
