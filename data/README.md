# Data directory

Data are organised by processing stage and, within the raw layer, by publisher. Source files are
never edited in place; every later layer is rebuilt by the pipeline (`python scripts/run.py`).
Which source each raw file belongs to, which result tables read it, and which files are kept as a
record but read by no analysis, is in the [catalogue](../docs/catalogue.md#sources-list); what each
dataset may be used for, and what it may never be joined to, is in the
[data contract](../docs/sources/contract.md).

## Processing layers

| Layer | Contents | Written by | In Git |
|---|---|---|---|
| `raw/<source>/` | source files byte for byte, listed in `raw/manifest.csv` (path, size, SHA-256, source URL, description, date added, name it was downloaded as) | download; `python scripts/run.py regional.organise` for new regional files | yes |
| `staging/<source>/` | parsed files: harmonised column names and types, values unchanged | `scripts/run.py national.ingest` (`staging/dgt`), `scripts/run.py regional.build` (`staging/barcelona`, `staging/catalonia`) | no |
| `processed/` | validated tables at one documented unit of observation | `scripts/run.py national.process`, `scripts/run.py regional.build`, `scripts/run.py drivers.emef` | no |
| `features/` | model matrices: id, target, grouping key, features and a provenance record | `scripts/run.py models.features` | no |

The raw sources:

| Folder | Publisher | Files |
|---|---|---|
| `raw/dgt/microdata/` | Dirección General de Tráfico | crash microdata 2016–2024 (one row per crash with victims), code dictionary, catalogue record |
| `raw/dgt/tables/` | DGT | yearbook historical series 1993–2024, statistical tables 2014–2024 |
| `raw/dgt/census/` | DGT | driver census by class and by age (text extracts 2023–2025) and published census tables 2014–2025 |
| `raw/dgt/km_itv_2022/`, `raw/dgt/km_itv_2024/` | DGT | kilometre estimates from ITV inspections |
| `raw/dgt/reports/` | DGT | the speed-factor report 2023 (read); thematic reports and yearbook errata (PDF, kept as a record and read by no code) |
| `raw/ine/` | INE | residents by province, age and sex, and of Spain by single year of age and sex, 2002–2025 (extracts written by `scripts/tools/fetch_ine.py`); ECEPOV and EHMA survey tables (checked and not used; read by no code) |
| `raw/crtm/edm2018/` | Consorcio Regional de Transportes de Madrid (CRTM) | Madrid household travel survey 2018: respondents, car-driver trips and codebook (extracts written by `scripts/tools/fetch_edm.py`; CRTM open-data licence, "Powered by CRTM") |
| `raw/transportes/` | Ministerio de Transportes (and former Fomento) | yearbook roads chapter 2023 (vehicle-km by road type), toll-motorway traffic, MOVILIA 2006–2007 |
| `raw/comunidad_madrid/` | Comunidad de Madrid | MOVILIA 2006 extract for Madrid (files named `movilia07t0N`); read by no code |
| `raw/cores/` | CORES | monthly road fuel by product |
| `raw/catalonia/` | Servei Català de Trànsit | crashes with a death or serious injury, 2010–2023 (downloaded as `export.csv`) |
| `raw/barcelona/2025/` | Ajuntament de Barcelona, Guàrdia Urbana | six crash tables for 2025 sharing `Numero_expedient` (downloaded as `download.csv` … `download(5).csv`) |
| `raw/idescat/` | Idescat | the 2024 census release on economic activity, the source of one benchmark figure typed into the code |
| `raw/emef/<year>/` | Autoritat del Transport Metropolità (ATM), Idescat and Institut Metròpoli, published on the Observatori de la Mobilitat de Catalunya (omc.cat) | EMEF working-day mobility survey, public-use microdata 2014–2024: one trip file, one respondent file (published as `Individus` or, in 2018–2020 and 2023, `Opinió`) and one dictionary per year; the 2022 dictionary in its first and revised releases |
| `raw/compiled/` | typed by hand from publications | values from external studies and travel surveys: not data; no analysis reads them (see the data contract) |

The EMEF files were downloaded from the survey's page on omc.cat and renamed `emef_<year>_trips.csv`,
`emef_<year>_persons.csv` and `emef_<year>_dictionary.xlsx`; every one is byte-identical to the file
the page served on 7 October 2026, and its original name is in `downloaded_as`.

The regional files were renamed from their browser download names to names that say what they
hold; the original names are kept in the manifest's `downloaded_as` column. The pipeline never
relies on a file name: `src/dgt_stats/regional/files.py` identifies each file by its columns,
processes byte-identical or same-content copies once, and stops if two different files claim the
same table and year. The reproducible inventory of every file (encoding, delimiter, rows,
columns, unit, coverage, duplicates) is generated into
[`sources/raw_file_inventory.md`](../docs/sources/raw_file_inventory.md) and
`reports/tables/sources/data_inventory.csv`.

## Building the layers

```bash
python scripts/run.py national.ingest national.reconcile   # raw -> staging/dgt, 482 checks (about 6 minutes)
python scripts/run.py national.process                     # processed/dgt_accidentes.parquet
python scripts/run.py regional.build                       # staging and processed Catalonia and Barcelona
python scripts/run.py drivers.emef                         # processed/emef_*.parquet
python scripts/run.py models.features                      # features/*.parquet
```

The layers serve the sections of the project (`src/dgt_stats/catalogue.py`): the national files
feed the national and drivers sections; the Catalan and Barcelona files the regional section and
the models trained on it; the travel surveys the drivers section. No layer merges records from two
sources.

| Output | Unit | Notes |
|---|---|---|
| `processed/dgt_accidentes.parquet` | one DGT crash with victims, 2016–2024 | outcome flags, zone, road group, hour band, status companions and English labels added beside the codes |
| `processed/catalonia_severe_crashes.parquet` | one Catalan crash with a death or serious injury | surrogate `cat_crash_id`; all 58 source columns kept; parsed hour, posted speed limit only where signposted, unit-type flags |
| `processed/barcelona_accidents.parquet` | one Barcelona crash | crash table + accident type (one-to-one) + aggregated causes, vehicle-type presence and person-role counts; corrected UTM beside the source columns |
| `processed/barcelona_people.parquet` | one person record | raw victimisation kept; `serious_or_fatal` target with blanks and natural deaths left missing |
| `processed/barcelona_crash_*.parquet` | one crash | the cause and vehicle-type aggregates on their own |
| `processed/emef_persons.parquet`, `processed/emef_trips.parquet` | one EMEF respondent; one trip | the eleven survey years, 2014–2024, harmonised into one layout (`docs/drivers/emef_inventory.md`) |
| `features/*.parquet` | one observation per model | see `models/leakage_audit.md`; each file has a `.json` provenance record beside it |

Existing outputs of the national layers are skipped unless `--force` is given; the regional
staging files are rebuilt whenever a source file's SHA-256 changes. Tests that need a layer skip
themselves with a message until it has been built.

## Notes on the national files

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

The full audit of the national sources is in [`national/file_audit.md`](../docs/national/file_audit.md);
the checks that run before any analysis are listed on the data page and in
[`docs/methodology.md`](../docs/methodology.md), section 2.
