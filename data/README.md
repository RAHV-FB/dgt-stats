# Data directory

Data are organised by processing stage. Source data must never be manually edited in place.

## Layers

- `raw/`: byte-for-byte source downloads.
- `interim/`: parsed files with harmonised encodings, names and types.
- `processed/`: validated, analysis-ready tables at documented units of observation.

The contents of these folders are ignored by Git. Each ingestion run should record the source URL, provider, release date, download date, file checksum, file size, row count and schema version.

## Seed source inventory

| Source group | Files currently available | Intended use |
|---|---|---|
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
