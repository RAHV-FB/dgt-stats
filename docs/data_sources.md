# Data and evidence sources

The source register, as of the published site (September 2026). Paths are relative to `data/raw/`;
every file is listed with size, SHA-256, source URL and description in `data/raw/manifest.csv`, and
the audit of what each supports is in [`data_inventory.md`](data_inventory.md). The page column names
where the file's numbers appear on the site.

## Providers

- **DGT en Cifras** (Dirección General de Tráfico, <https://www.dgt.es/menusecundario/dgt-en-cifras/>):
  yearly definitive injury-crash statistics, the historical series, the crash microdata, the driver
  census, the kilometre estimates and the thematic reports. Provisional and definitive series, and
  24-hour and 30-day death counts, are never mixed.
- **INE** (Instituto Nacional de Estadística): resident population by province, age and sex; the
  2021 ECEPOV commuting extract; the 2008 household mobility survey extracts.
- **Ministerio de Transportes**: MOVILIA 2006 and 2007 travel surveys.
- **ESRA** (E-Survey of Road users' Attitudes): national shares of adults who drive, 2018 and 2023.
- **European Road Safety Observatory**: context only, cited in the README; nothing from it enters a
  table.

## Reuse terms

The code in this repository is under the MIT licence (`LICENSE`). The files under `data/raw/` are
not: each keeps the terms of the body that published it, listed here as read on 19 September 2026.
Whatever the provider, this project names the source, keeps every file as downloaded with its
checksum and download date (the `added` column of the manifest) and its edition or reference year
(the description), publishes aggregates only, and claims no endorsement from anyone.

| Provider | Files | Terms as published | Notice |
|---|---|---|---|
| DGT, catalogued on datos.gob.es | crash microdata and dictionary (`microdata/`) | free, non-exclusive licence for commercial and non-commercial reuse: name the origin of the data, do not distort its meaning, keep the date of last update, do not suggest that the publisher endorses the reuse, keep the metadata | <https://datos.gob.es/avisolegal>, the licence named in `metadata_2024.rdf.xml` |
| DGT, from dgt.es | series, statistical tables, driver census, kilometre estimates, thematic reports (`tables/`, `exposure/`, `reports/dgt_*.pdf`, errata) | public-sector information within the scope of Ley 37/2007. DGT's legal notice claims the portal's design and code and sets no separate conditions for its statistics; this project applies the datos.gob.es conditions above to every DGT file | <https://www.dgt.es/contenido/aviso-legal/> |
| INE | population (`ine_poblacion_provincias_edad_sexo.csv`), ECEPOV 2021, EHMA 2008 | Creative Commons Attribution 4.0 unless a product says otherwise; processed data are cited as "Elaboración propia con datos extraídos del sitio web del INE: www.ine.es"; keep the date of last update; do not suggest that INE endorses the reuse | <https://www.ine.es/aviso_legal/> |
| Ministerio de Transportes y Movilidad Sostenible | MOVILIA 2006 and 2007 workbooks | reusable for commercial and non-commercial purposes: cite "Origen de los datos: Ministerio de Transportes y Movilidad Sostenible", keep the date of last update, do not distort the content, do not suggest endorsement, keep the metadata | <https://www.transportes.gob.es/ministerio/aviso-legal> |
| Comunidad de Madrid, Instituto de Estadística | five MOVILIA 2006 tables for Madrid (`exposure/movilia_madrid/`) | copying and distribution allowed provided the pages are not used directly for commercial purposes, the source is cited, the content is not altered and no sponsorship is implied. These five files carry a condition the code licence does not; a commercial reuse of them goes back to the provider | <https://www.madrid.org/iestadis/fijas/otros/avisolegal.htm> |
| ESRA (Vias institute and partner institutes) | four published reports (`reports/esra*.pdf`) | public reports; no reuse licence is stated on the site. The two national shares used are quotations attributed to the reports; the PDFs are kept unaltered, with URL and checksum, so the quotation can be checked | <https://www.esranet.eu/en/publications/> |

## Crash microdata (`microdata/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `accidentes_2016.xlsx` … `accidentes_2024.xlsx` | 2016–2024, 875,013 injury crashes | the crash table: location, time, road, conditions, victims by severity and road-user type | timing, road users, severity, policy (2019), vehicles (occupant deaths), data |
| `diccionario.xlsx` | all years | code lists for the 33 coded fields | every page (labels), data |
| `metadata_2024.rdf.xml` | 2024 | official access URL, licence and issue date | manifest template |

## Official tables (`tables/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `series_historicas_2024.xlsx` | 1993–2024, 69 sheets | crashes and victims by year, month, province, sex, age, pedestrians, drivers and passengers by vehicle, fleet and rates | trends, road users, geography, older drivers, vehicles, policy (2006) |
| `tablas_estadisticas_2020.xlsx` … `_2024.xlsx` | one workbook per year | province and month totals (validation), vehicles involved by type (2.3), victims by mode (2.2), drivers by age and sex (4.1.1, 4.2), driver infractions (6.1) | data (checks), vehicles, older drivers, speed |
| `chapters/2014/grupo_1.xls` … `chapters/2019/grupo_8.xlsx` | 2014–2019, eight chapters a year | the same tables 4.1.1, 4.2 and 6.1 for the earlier years | older drivers, speed |

## Exposure and denominators (`exposure/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `censo_conductores_{2023,2024,2025}.txt` | 2023–2025 | licence holders by province, sex, class and seniority | geography, data (check) |
| `censo_conductores_edad_{2023,2024,2025}.txt` | 2023–2025 | licence holders by province, sex and age band | older drivers |
| `censo_tablas_2014.xlsx` … `censo_tablas_2025.xlsx` | 2014–2025 | published census tables: class by age (2014–2023), province totals | older drivers, data (checks) |
| `ine_poblacion_provincias_edad_sexo.csv` | 2002–2025 | residents by province, five-year age group and sex, 1 January and 1 July | geography, older drivers |
| `km_itv_2022/media_km_antiguedad_tipo_2022.xlsx` | 2022 | fleet and mean annual km by vehicle type and age | vehicles |
| `km_itv_2022/km_recorridos_estimados_2022.xlsx` | 2022 | km per vehicle by stratum (type, Euro class, age, engine, fuel) | parsed; not on the site |
| `km_itv_2022/metodologia.pdf` | 2014–2023 ITV | how the kilometres are modelled; the category definitions that settle the heavy-truck mapping | vehicles (limits) |
| `driving_activity_by_age.csv` | 2018, 2023 | ESRA national shares of adults who drive (Spain), transcribed | older drivers |
| `movilia_2006.xls`, `movilia_2007.xls`, `movilia_madrid/*.xls` | 2006–2007 | trips by mode, purpose, sex and age (car-travel profile by age) | older drivers |
| `ine_ecepov_2021_55378.xlsx` | 2021 | commuters by main vehicle, sex and age | parsed for context; not on the site |
| `ine_ehma_2008_10016.csv`, `ine_ehma_2008_10019.csv` | 2008 | household km per vehicle by fuel and vehicle age | parsed for context; not on the site |

## Thematic reports (`reports/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `dgt_factor_velocidad_2023.pdf` | 2014–2023, without Cataluña or País Vasco | the 61 annex tables, transcribed by `io_reports.py` | speed |
| `dgt_personas_mayores_2023.pdf` | 2023 | the older-road-user figures the older-drivers page reproduces and reinterprets | older drivers (context) |
| `dgt_semana_santa_2026.pdf` | Easter 2026 | provisional holiday figures; not used | none |
| `Anuario-estadistico-de-accidentes-201{5,6,7,8,9}-fe-de-erratas.pdf` | 2015–2019 | errata to the yearbooks, checked when the series and the tables disagreed | data (context) |
| `esra3-main-report.pdf`, `esra3-methodology-report.pdf`, `esra2023countryfactsheetspain.pdf`, `esra2023thematicreportno5youngandagingdrivers.pdf` | 2018, 2023 | the source of the driving-activity shares | older drivers (context) |

## Not available

- Vehicle-level and person-level crash records (driver age and sex, alcohol and drug tests, speed,
  seat belt, helmet): not published for download; a request to DGT's Observatorio Nacional de
  Seguridad Vial would be needed.
- Road geometry, coordinates, traffic volumes and section-level speeds.
- A dated register of campaigns and enforcement periods.
- Vehicle-kilometres for any year other than 2022.
