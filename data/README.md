# Data directory

Data are organised by processing stage. Source data must never be manually edited in place.

## Layers

- `raw/`: byte-for-byte source downloads, tracked in Git, with `raw/manifest.csv` listing path, size, SHA-256, source URL and description. Subfolders: `microdata/`, `tables/`, `exposure/`, `reports/`.
- `interim/`: parsed files with harmonised encodings, names and types.
- `processed/`: validated, analysis-ready tables at documented units of observation.

`interim/` and `processed/` are ignored by Git and rebuilt from `raw/`. Each ingestion run should record row counts, validation outcomes and schema version alongside the manifest.

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
