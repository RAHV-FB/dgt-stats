# Data and evidence sources

The source register, as of the published site (September 2026). Paths are relative to `data/raw/`;
every file is listed with size, SHA-256, source URL, description and the date added in
`data/raw/manifest.csv`, and the audit of what each supports is in
[`data_inventory.md`](data_inventory.md). The page column names where the file's numbers appear on
the site.

## Providers

- **DGT en Cifras** (Dirección General de Tráfico, <https://www.dgt.es/menusecundario/dgt-en-cifras/>):
  yearly definitive injury-crash statistics, the historical series, the crash microdata, the driver
  census, the kilometre estimates and the thematic reports. Provisional and definitive series, and
  24-hour and 30-day death counts, are never mixed.
- **INE** (Instituto Nacional de Estadística): resident population by province, age and sex; the
  2021 ECEPOV commuting extract; the 2008 household mobility survey extracts.
- **Ministerio de Transportes y Movilidad Sostenible**: MOVILIA 2006 and 2007 travel surveys;
  monthly traffic on the state toll-motorway network from 1990 (Boletín Estadístico Online).
- **CORES** (Corporación de Reservas Estratégicas de Productos Petrolíferos, the body that
  keeps Spain's compulsory oil stocks and publishes the official petroleum statistics under
  Ley 34/1998): monthly consumption of petroleum products from 1996.
- **ESRA** (E-Survey of Road users' Attitudes, coordinated by Vias institute): the national shares
  of adults who drive, 2018 and 2023, consulted online (section on thematic reports below); none of
  its publications is archived here.
- **Fundación MAPFRE** ("Mayores de 65 años y seguridad vial"): driving-frequency shares among
  Madrid drivers aged 65+, quoted by URL in `driving_activity_by_age.csv`; the report PDF is not
  archived under `data/raw/`, so those three rows cannot be checked from the repository, and no
  page uses them. Its reuse terms are in the table below.
- **European Road Safety Observatory**: context only, cited in the README; nothing from it enters a
  table.

## Reuse terms

The code in this repository is under the MIT licence (`LICENSE`). The files under `data/raw/` are
not: each keeps the terms of the body that published it, listed here as read on 19 September 2026.
Whatever the provider, this project names the source, keeps every file as downloaded with its
checksum and date added (the `added` column of the manifest), its edition or reference year and,
where the provider's record gives one, the publisher's date of last update (the description),
publishes aggregates only, and claims no endorsement from anyone. Two files under `data/raw/` are
not downloads: `ine_poblacion_provincias_edad_sexo.csv` is an extract of INE table 56947 written by
`scripts/fetch_ine.py` (nationality total and the 1 January and 1 July periods, columns renamed),
and `driving_activity_by_age.csv` is hand-typed from the surveys it cites.

| Provider | Files | Terms as published | Notice |
|---|---|---|---|
| DGT, catalogued on datos.gob.es | crash microdata and dictionary (`microdata/`) | free, non-exclusive licence for commercial and non-commercial reuse: name the origin of the data, do not distort its meaning, keep the date of last update, do not suggest that the publisher endorses the reuse, keep the metadata | <https://datos.gob.es/avisolegal>, the licence named in `metadata_2024.rdf.xml` |
| DGT, from dgt.es | series, statistical tables, driver census, kilometre estimates, thematic reports (`tables/`, `exposure/`, `reports/dgt_*.pdf`, errata) | public-sector information within the scope of Ley 37/2007. DGT's legal notice claims the intellectual property of the portal, its graphic design and its code, states that unauthorised reproduction, distribution, commercialisation or transformation of those works other than for personal and private use is an infringement, and warns that unauthorised placement of the information the portal contains may lead to legal action; it grants no reuse licence for the statistics and names no licence at all. Redistribution of these files here therefore rests on the Ley 37/2007 regime for public-sector information, applying the datos.gob.es conditions above to every DGT file by this project's own choice; no permission has been requested from DGT | <https://www.dgt.es/contenido/aviso-legal/> |
| INE | population (`ine_poblacion_provincias_edad_sexo.csv`), ECEPOV 2021, EHMA 2008 | Creative Commons Attribution 4.0 unless a product says otherwise; processed data are cited as "Elaboración propia con datos extraídos del sitio web del INE: www.ine.es"; keep the date of last update; do not suggest that INE endorses the reuse | <https://www.ine.es/aviso_legal/> |
| Ministerio de Transportes y Movilidad Sostenible | MOVILIA 2006 and 2007 workbooks; the toll-motorway traffic series (`exposure/traffic/peaje_trafico_total.xls`) | reusable for commercial and non-commercial purposes: cite "Origen de los datos: Ministerio de Transportes y Movilidad Sostenible", keep the date of last update, do not distort the content, do not suggest endorsement, keep the metadata | <https://www.transportes.gob.es/ministerio/aviso-legal> |
| Comunidad de Madrid, Instituto de Estadística | five MOVILIA 2006 tables for Madrid (`exposure/movilia_madrid/`) | copying and distribution allowed provided the pages are not used directly for commercial purposes, the source is cited, the content is neither altered nor its meaning distorted, and no sponsorship is implied. These five files carry a condition the code licence does not; a commercial reuse of them goes back to the provider | <https://www.madrid.org/iestadis/fijas/otros/avisolegal.htm> |
| Fundación MAPFRE | none archived; three driving-frequency rows typed into `exposure/driving_activity_by_age.csv` | a private foundation, not a public body, so the Ley 37/2007 regime applied to the DGT files does not reach it: the report offers no reuse licence and none was requested. The three shares (0.559 / 0.303 / 0.138 of Madrid drivers aged 65+, n 300, year inferred) are short quotations with attribution to "Mayores de 65 años y seguridad vial" and its URL; the PDF is not archived here and no page reads them (only the ESRA rows are read, `io_activity.py`) | <https://app.mapfre.com/ccm/content/documentos/fundacion/seg-vial/investigacion/mayores-y-seguridad-vial.pdf>; the foundation's site publishes no reuse notice, only a privacy policy (<https://www.fundacionmapfre.org/politica-privacidad/>), as read on 22 September 2026 |
| CORES | `exposure/traffic/cores_consumos_pp.xlsx` | public-sector information within the scope of Ley 37/2007: CORES is a corporation of public law under the Ministerio para la Transición Ecológica and publishes these statistics as part of its statutory duty. Its site names no reuse licence, so the file is redistributed here on the same footing as the DGT statistics, applying the datos.gob.es conditions by this project's own choice: the source is named, the meaning is not distorted, the date of last update is kept (the `Actualizado el` cell of each sheet) and no endorsement is implied | <https://www.cores.es/es/estadisticas> |
| ESRA (Vias institute and partner institutes) | none archived; two national shares typed into `exposure/driving_activity_by_age.csv` | no reuse licence is offered: the Vias disclaimer linked from the ESRA site footer claims intellectual rights over its contents for Vias institute "or entitled third parties", and no reproduction permission is stated in the reports or was requested, so nothing of theirs is redistributed here. The two shares are short quotations with attribution: the 2023 share (75.9 %, weighted n 935) from the ESRA3 main report, Table 6, and the Spain country fact sheet; the 2018 share (80.2 %, weighted n 906) from the ESRA-123 online dashboard, which publishes no downloadable table | <https://www.esranet.eu/en/publications/>, <https://www.vias.be/en/disclaimer> |

## Crash microdata (`microdata/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `accidentes_2016.xlsx` … `accidentes_2024.xlsx` | 2016–2024, 875,013 injury crashes | the crash table: location, time, road, conditions, victims by severity and road-user type | timing, road users, severity, policy (2019), data |
| `diccionario.xlsx` | all years | code lists for the 33 coded fields | every page (labels), data |
| `metadata_2024.rdf.xml` | 2024 | official access URL, licence and issue date | manifest template |

datos.gob.es gives 5 November 2025 as the last update of the 2024 microdata (the `dct:modified` of
the `dcat:Dataset` in `metadata_2024.rdf.xml`, which equals its `dct:issued`; the enclosing
`dcat:CatalogRecord` carries its own, later `dct:modified`, 2026-05-26, for the catalogue entry; the
manifest description of `accidentes_2024.xlsx` carries the dataset date); no last-update date is
published in the records held for 2016–2023, and the record gives the dictionary no date of its own.

## Official tables (`tables/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `series_historicas_2024.xlsx` | 1993–2024, 69 sheets | crashes and victims by year, month, province, sex, age, pedestrians, drivers and passengers by vehicle, fleet and rates | 2019–2024 risk, long run, seasons, vehicles, 2006 break (supporting) |
| `tablas_estadisticas_2020.xlsx` … `_2024.xlsx` | one workbook per year | province and month totals (validation), vehicles involved by type (2.3), victims by mode (2.2), drivers by age and sex (4.1.1, 4.2), driver infractions (6.1) | data (checks), vehicles, age and sex, speed |
| `chapters/2014/grupo_1.xls` … `chapters/2019/grupo_8.xlsx` | 2014–2019, eight chapters a year | the same tables 4.1.1, 4.2 and 6.1 for the earlier years | age and sex, speed |

## Exposure and denominators (`exposure/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `censo_conductores_{2023,2024,2025}.txt` | 2023–2025 | licence holders by province, sex, class and seniority | data (check) |
| `censo_conductores_edad_{2023,2024,2025}.txt` | 2023–2025 | licence holders by province, sex and age band | 2019–2024 risk, age and sex |
| `censo_tablas_2014.xlsx` … `censo_tablas_2025.xlsx` | 2014–2025 | published census tables: class by age 2014–2023 (the 2024 workbook has no class-by-age sheet and the 2025 ones are left unused so the 2024–2025 segment keeps a single source); province totals from the 2025 workbook only, so `censo_tablas_2024.xlsx` is archived but read by no script | 2019–2024 risk, age and sex, data (checks) |
| `ine_poblacion_provincias_edad_sexo.csv` | 2002–2025 | residents by province, five-year age group and sex, 1 January and 1 July | 2019–2024 risk, age and sex |
| `km_itv_2022/media_km_antiguedad_tipo_2022.xlsx` | 2022 | circulating fleet ("parque circulante": vehicles with an ITV, insurance, ownership-change, re-registration or fine record in the previous ten years) and mean annual km by vehicle type and age | vehicles |
| `km_itv_2022/km_recorridos_estimados_2022.xlsx` | 2022 | km per vehicle by stratum (type, Euro class, age, engine, fuel) | parsed; not on the site |
| `km_itv_2024/km_edad_propietario_2024.xlsx` | 2024 | vehicles, total and mean annual km by vehicle category **and by the age band of the registered owner**; the denominator of the age-and-exposure analysis | age and sex |
| `km_itv_2024/km_medios_tipo_2024.xlsx` | 2024 | vehicles and mean annual km by category (the release's table 6), used to reconcile the owner-age table against the published fleet, and compared with fuel on the 2019–2024 page | age and sex (check), 2019–2024 |
| `traffic/cores_consumos_pp.xlsx` | 1996–2026, monthly | national consumption of petroleum products; the automotive petrol and diesel subtotals are the road-traffic exposure proxy, annual and monthly | 2019–2024, long run, seasons, 2006 break |
| `traffic/peaje_trafico_total.xls` | 1990–2026, monthly | average daily intensity and vehicle-kilometres on the state toll-motorway network | seasons (intensity), 2006 break |
| `km_itv_2022/metodologia.pdf` | 2014–2023 ITV | how the kilometres are modelled; the definition of the circulating fleet (Anexo III) and the category definitions that settle the heavy-truck mapping | vehicles (limits) |
| `driving_activity_by_age.csv` | 2008, 2018, 2023 | hand-typed survey register: ESRA national shares of adults who drive (Spain) and three Fundación MAPFRE rows on driving days per week among Madrid drivers 65+. Registered and kept as the record of what was searched; **no page reads them any more**, since DGT's 2024 kilometres by owner age replaced the survey-based driving denominator | none |
| `movilia_2006.xls` | 2006 | table 64, trips by main mode × sex × age. Once the basis of the retired travel-weighted age denominator, which it could not support (its car-or-motorcycle column counts passengers as well as drivers and its top band is 65+). Now used only for the male-to-female trip ratio by age, read as a lower bound on the travel gap between the sexes | age and sex (bracket) |
| `movilia_2007.xls`, `movilia_madrid/*.xls` | 2006–2007 | long-distance and Madrid extracts, inspected; not read by any script | none |
| `ine_ecepov_2021_55378.xlsx` | 2021 | commuters by main vehicle, sex and age | registered and checked in the audit; not read by the code and not on the site |
| `ine_ehma_2008_10016.csv`, `ine_ehma_2008_10019.csv` | 2008 | household km per vehicle by fuel and vehicle age | registered and checked in the audit; not read by the code and not on the site |

## Thematic reports (`reports/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `dgt_factor_velocidad_2023.pdf` | 2014–2023, without Cataluña or País Vasco | 61 of its 64 tables (all but the three year-on-year variation tables; Tablas 50–61 are its Anexo I), transcribed by `io_reports.py`. Its scope totals (Tablas 1–3), speed-related crashes and deaths by road type, and crashes by concurrent factor are inputs to analyses; its scope totals are reconciled against the microdata (`speed_report_scope`); none of its breakdowns is republished | speed, factors |
| `dgt_personas_mayores_2023.pdf` | 2023 | the per-inhabitant framing for older road users that the age-and-sex page reinterprets against four denominators; none of its figures is reproduced | age and sex (context) |
| `dgt_semana_santa_2026.pdf` | Easter 2026 | provisional holiday figures; not used | none |
| `Anuario-estadistico-de-accidentes-201{5,6,7,8,9}-fe-de-erratas.pdf` | 2015–2019 | errata to the yearbooks, checked when the series and the tables disagreed | none (consulted by hand while reconciling 2015–2019; no number on the site) |

The ESRA reports behind the driving-activity shares are not archived, because Vias institute offers
no reproduction licence (reuse terms above). They were consulted online: the ESRA3 main report
(<https://www.esranet.eu/storage/minisites/esra3-main-report.pdf>, Table 6) and the Spain country
fact sheet (<https://www.esranet.eu/storage/minisites/esra2023countryfactsheetspain.pdf>) give the
2023 share of 75.9 % (weighted n 935); the ESRA-123 dashboard
(<https://www.esranet.eu/en/esra-123-dashboard/>) gives the 2018 share of 80.2 % (weighted n 906),
which appears in no downloadable table. The ESRA3 methodology report and thematic report no. 5
(young and ageing drivers, both at <https://www.esranet.eu/en/publications/>) were consulted at the
same time; nothing from them enters a table.

## Not available

- Vehicle-level and person-level crash records (driver age and sex, alcohol and drug tests, speed,
  seat belt, helmet): not published for download; a request to DGT's Observatorio Nacional de
  Seguridad Vial would be needed.
- Road geometry, coordinates, traffic volumes and section-level speeds.
- A dated register of campaigns and enforcement periods.
- Vehicle-kilometres **by vehicle type** for any year other than 2022; DGT's 2024 release gives
  them by owner age and by category but the vehicles page needs the type × involvement pairing
  that only the 2022 release supports at that level of detail.
- Distance driven by the **driver's** age. DGT's 2024 kilometre release is the closest Spanish
  source and gives the **owner's** age band. MOVILIA 2006/2007 count trips and travel time, not
  kilometres, and do not separate drivers from passengers; INE's EHMA 2008 gives mean annual
  kilometres per household vehicle by the age of the household's reference person, in four
  bands that stop at 65+, and is sixteen years older than the crash counts; ESRA gives a
  national share of adults who drive with no age split. Each was checked and is registered
  above; the DGT owner-age table is the one used, and the page states what it is.
- Monthly vehicle-kilometres on all Spanish roads. The two monthly series registered above are
  proxies with known limits: CORES measures fuel sold, not distance, and its petrol/diesel mix
  shifts over the 2000s; the toll-motorway series measures distance directly but on 1,400–2,500
  km of motorway whose length changes as concessions expire.
