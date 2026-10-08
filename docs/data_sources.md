# Data and evidence sources

The source register, as of the published site (October 2026). Paths are relative to `data/raw/`,
where the files are grouped by the body that publishes them (`dgt/`, `ine/`, `transportes/`,
`cores/`, `comunidad_madrid/`, `catalonia/`, `barcelona/2025/`, `emef/`) and the values typed by hand from
publications sit apart in `compiled/`. Every file is listed with size, SHA-256, source URL,
description, the date added and, for the regional files, the name it was downloaded under in
`data/raw/manifest.csv`; the generated [`RAW_FILE_INVENTORY.md`](RAW_FILE_INVENTORY.md) lists every
file with its format, rows and unit of observation, the audit of what each supports is in
[`data_inventory.md`](data_inventory.md), and what each dataset may be joined to is in
[`DATA_CONTRACT.md`](DATA_CONTRACT.md). The page column names where the file's numbers appear on
the site; the overview, which repeats headline numbers from the other pages, is listed only for the
road-class split, which no other page shows.

Each file read by the code serves one of the four layers declared in `src/dgt_stats/layers.py`. The
DGT, INE, Ministerio de Transportes and CORES files are the national context: trends, denominators,
exposure, rates and aggregate comparisons (the deaths forecast that also used them was withdrawn).
The EMEF and EDM2018 travel surveys supply car-driving kilometres by driver age to the same
layer's rates. The Servei Català de Trànsit file
is the Catalan crash microdata: the crash-severity model and its temporal and geographic
validation. The Guàrdia Urbana tables are the Barcelona microdata: crash and person analysis and
the person-severity model. The validation layer adds no file: it harmonises variables and tests
models on these files' real records, and never creates observations. No record is linked across
sources and there is no merged database. The DGT crash microdata do not train a predictive model
([`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md)); the DGT severity regression is a supporting
association analysis. MOVILIA 2006 table 64 is read for one sensitivity test of the national
driver-age rates (the age mix of weekend car trips). The other MOVILIA files, the ECEPOV and EHMA
survey files and the `compiled/` registers are read by no code: no analysis or page uses them, and
the only code that opens them is the generated inventory, which opens every file under `data/raw/`
to count its rows.

## Providers

- **DGT en Cifras** (Dirección General de Tráfico, <https://www.dgt.es/menusecundario/dgt-en-cifras/>):
  yearly definitive injury-crash statistics, the historical series, the crash microdata, the driver
  census, the kilometre estimates and the thematic reports. Provisional and definitive series, and
  24-hour and 30-day death counts, are never mixed.
- **INE** (Instituto Nacional de Estadística): resident population by province, age and sex; the
  2021 ECEPOV commuting extract; two extracts of the 2008 EHMA household survey (kilometres per
  household vehicle).
- **Ministerio de Transportes y Movilidad Sostenible**: MOVILIA 2006 and 2007 travel surveys;
  monthly traffic on the state toll-motorway network from 1990 (Boletín Estadístico Online);
  annual vehicle-kilometres and the share of heavy vehicles by type of road on the State, regional
  and provincial interurban networks, 2004–2023 (Anuario Estadístico 2023, roads chapter, table
  1.2.14).
- **CORES** (Corporación de Reservas Estratégicas de Productos Petrolíferos, the body that
  keeps Spain's compulsory oil stocks and publishes the official petroleum statistics under
  Ley 34/1998): monthly consumption of petroleum products from 1996.
- **Servei Català de Trànsit** (Departament d'Interior i Seguretat Pública, Generalitat de
  Catalunya): an export of the crashes in Catalonia with at least one death or serious injury,
  2010–2023 (`catalonia/`), downloaded as `export.csv` from the Generalitat's open-data portal,
  dataset `rmgc-ncpb`, "Accidents de trànsit amb morts o ferits greus a Catalunya"
  (<https://analisi.transparenciacatalunya.cat/d/rmgc-ncpb>). The URL was not kept at download;
  on 8 October 2026 the file's row count (24,478) and its yearly totals of deaths and serious
  injuries for 2010–2023 equalled the portal's, whose rows were last updated on 5 December 2024.
- **Ajuntament de Barcelona** (the crashes are recorded by the Guàrdia Urbana, the city police):
  six tables of the crashes the Guàrdia Urbana attended in Barcelona in 2025, with the people,
  vehicle records, crash types and recorded causes (`barcelona/2025/`), downloaded as
  `download.csv` to `download(5).csv` from Open Data BCN, datasets `accidents-gu-bcn`,
  `accidents-persones-gu-bcn`, `accidents-vehicles-gu-bcn`, `accidents-causes-gu-bcn`,
  `accidents_causa_conductor_gu_bcn` and `accidents-tipus-gu-bcn`
  (<https://opendata-ajuntament.barcelona.cat/data/ca/dataset/accidents-gu-bcn> and its sibling
  pages). The URLs were not kept at download; on 8 October 2026 each file's size equalled that of
  the portal's 2025 resource (last modified 17 February 2026), whose download URL the manifest now
  gives. The portal's download route answered with a bot check, so the checksums could not be
  compared.
- **ATM, Idescat and Institut Metròpoli** (Enquesta de mobilitat en dia feiner, EMEF; published by
  the Autoritat del Transport Metropolità on the Observatori de la Mobilitat de Catalunya,
  <https://www.omc.cat/ca/w/enquesta-emef>): public-use microdata of the working-day mobility
  survey of residents aged 16 and over in the ATM planning area (SIMMB), 2014–2024, one trip file,
  one respondent file and one dictionary per year (`emef/<year>/`). Each file was compared byte for
  byte with the copy served by omc.cat on 7 October 2026 and matched.
- **ESRA** (E-Survey of Road users' Attitudes, coordinated by Vias institute): the national shares
  of adults who drive, 2018 and 2023, consulted online (section on thematic reports below) and
  typed into `compiled/driving_activity_by_age.csv`, which no code reads; none of its publications
  is archived here.
- **Fundación MAPFRE** ("Mayores de 65 años y seguridad vial"): driving-frequency shares among
  Madrid drivers aged 65+, quoted by URL in `compiled/driving_activity_by_age.csv`; the report PDF
  is not archived under `data/raw/`, so those three rows cannot be checked from the repository, and
  no code reads them. Its reuse terms are in the table below.

## Reuse terms

The code in this repository is under the MIT licence (`LICENSE`). The files under `data/raw/` are
not: each keeps the terms of the body that published it, listed here as read on 19 September 2026,
and for the regional crash files on 8 October 2026. Whatever the provider, this project names the
source, keeps every file as downloaded with
its checksum and date added (the `added` column of the manifest), its edition or reference year
and, where the provider's record gives one, the publisher's date of last update (the description),
publishes aggregates only, and claims no endorsement from anyone. Eight files under `data/raw/`
are not downloads: `ine/ine_poblacion_provincias_edad_sexo.csv` and
`ine/ine_poblacion_edad_simple_sexo.csv` are extracts of INE tables 56947 and 56934 written by
`scripts/fetch_ine.py` (nationality total where relevant and the 1 January and 1 July periods,
columns renamed); the three files under `crtm/edm2018/` are extracts of the CRTM's EDM2018
workbooks written by `scripts/fetch_edm.py` (columns and, for trips, car-driver rows kept as
published; the manifest gives each workbook's checksum); and the three files under `compiled/`
are hand-typed from the publications they cite.

| Provider | Files | Terms as published | Notice |
|---|---|---|---|
| DGT, catalogued on datos.gob.es | crash microdata and dictionary (`dgt/microdata/`) | free, non-exclusive licence for commercial and non-commercial reuse: name the origin of the data, do not distort its meaning, keep the date of last update, do not suggest that the publisher endorses the reuse, keep the metadata | <https://datos.gob.es/avisolegal>, the licence named in `dgt/microdata/metadata_2024.rdf.xml` |
| DGT, from dgt.es | series, statistical tables, driver census, kilometre estimates, thematic reports and errata (`dgt/tables/`, `dgt/census/`, `dgt/km_itv_2022/`, `dgt/km_itv_2024/`, `dgt/reports/`) | public-sector information within the scope of Ley 37/2007. DGT's legal notice claims the intellectual property of the portal, its graphic design and its code, states that unauthorised reproduction, distribution, commercialisation or transformation of those works other than for personal and private use is an infringement, and warns that unauthorised placement of the information the portal contains may lead to legal action; it grants no reuse licence for the statistics and names no licence at all. Redistribution of these files here therefore rests on the Ley 37/2007 regime for public-sector information, applying the datos.gob.es conditions above to every DGT file by this project's own choice; no permission has been requested from DGT | <https://www.dgt.es/contenido/aviso-legal/> |
| INE | population (`ine/ine_poblacion_provincias_edad_sexo.csv`, `ine/ine_poblacion_edad_simple_sexo.csv`), ECEPOV 2021 and EHMA 2008 (`ine/`) | Creative Commons Attribution 4.0 unless a product says otherwise; processed data are cited as "Elaboración propia con datos extraídos del sitio web del INE: www.ine.es"; keep the date of last update; do not suggest that INE endorses the reuse | <https://www.ine.es/aviso_legal/> |
| Ministerio de Transportes y Movilidad Sostenible | MOVILIA 2006 and 2007 workbooks (`transportes/movilia_2006.xls`, `transportes/movilia_2007.xls`); the toll-motorway traffic series (`transportes/peaje_trafico_total.xls`); the roads chapter of the Anuario Estadístico 2023 (`transportes/anuario_carreteras_2023.pdf`) | reusable for commercial and non-commercial purposes: cite "Origen de los datos: Ministerio de Transportes y Movilidad Sostenible", keep the date of last update, do not distort the content, do not suggest endorsement, keep the metadata | <https://www.transportes.gob.es/ministerio/aviso-legal> |
| Comunidad de Madrid, Instituto de Estadística | five MOVILIA 2006 tables for Madrid (`comunidad_madrid/movilia_madrid/`) | copying and distribution allowed provided the pages are not used directly for commercial purposes, the source is cited, the content is neither altered nor its meaning distorted, and no sponsorship is implied. These five files carry a condition the code licence does not; a commercial reuse of them goes back to the provider | <https://www.madrid.org/iestadis/fijas/otros/avisolegal.htm> |
| ATM (Autoritat del Transport Metropolità), on omc.cat | the EMEF microdata and dictionaries in `emef/` | the OMC legal notice's open-data clause permits reproduction, distribution, public communication and transformation worldwide and without time limit under article 8 of Ley 37/2007, on four conditions: cite the rights holder (Consorci de l'Autoritat del Transport Metropolità de l'àrea de Barcelona), do not distort the meaning, cite the source, state the date of last update (the manifest descriptions give each file's date on omc.cat). The dictionaries add that results computed from the public-use files are the user's responsibility, not official statistics, and should be cited as "ATM, Idescat i Institut Metròpoli, <year>. Enquesta de mobilitat en dia feiner <year>. Autoritat del Transport Metropolità"; they also ask that no estimate resting on fewer than 20 sample observations be published | <https://www.omc.cat/ca/avis-legal>, read on 7 October 2026; the `Sumari` sheet of each dictionary |
| Consorcio Regional de Transportes de Madrid (CRTM), on its ArcGIS open-data site | the EDM2018 extracts in `crtm/edm2018/` | the CRTM open-data licence permits reuse, commercial or not, on three conditions: cite the CRTM as the source, show "Powered by CRTM" with a link to www.crtm.es on any digital platform that uses the data, and distribute derived data under the same licence. The extracts keep columns and rows of the published workbooks unchanged; they and the tables derived from them (`reports/tables/edm_*.csv`, and the Madrid profiles in `risk_*.csv`) are distributed under that licence, as the site's methodology page states | <https://www.crtm.es/licencia-de-uso>, the licence linked from each ArcGIS item, read on 8 October 2026 |
| Fundación MAPFRE | none archived; three driving-frequency rows typed into `compiled/driving_activity_by_age.csv` | a private foundation, not a public body, so the Ley 37/2007 regime applied to the DGT files does not reach it: the report offers no reuse licence and none was requested. The three shares (0.559 / 0.303 / 0.138 of Madrid drivers aged 65+, n 300, year inferred) are short quotations with attribution to "Mayores de 65 años y seguridad vial" and its URL; the PDF is not archived here and no code reads them | <https://app.mapfre.com/ccm/content/documentos/fundacion/seg-vial/investigacion/mayores-y-seguridad-vial.pdf>; the foundation's site publishes no reuse notice, only a privacy policy (<https://www.fundacionmapfre.org/politica-privacidad/>), as read on 22 September 2026 |
| CORES | `cores/cores_consumos_pp.xlsx` | public-sector information within the scope of Ley 37/2007: CORES is a corporation of public law under the Ministerio para la Transición Ecológica and publishes these statistics as part of its statutory duty. Its site names no reuse licence, so the file is redistributed here on the same footing as the DGT statistics, applying the datos.gob.es conditions by this project's own choice: the source is named, the meaning is not distorted, the date of last update is kept (the `Actualizado el` cell of each sheet) and no endorsement is implied | <https://www.cores.es/es/estadisticas> |
| Servei Català de Trànsit, on the Generalitat's open-data portal | `catalonia/accidents_morts_ferits_greus_catalunya_2010_2023.csv` | the portal gives the licence as "See Terms of Use", linking the Llicència oberta d'ús d'informació - Catalunya: sharing, modification and reuse are free on condition that the content and its meaning are not altered, the source is cited as "Generalitat de Catalunya. Departament d'Interior i Seguretat Pública. Servei Català de Trànsit", and the date of last update is stated (5 December 2024 on the portal); sublicensing is not allowed, so the file is redistributed here under that licence and not under the code's | <https://administraciodigital.gencat.cat/ca/dades/dades-obertes/informacio-practica/llicencies/>, read on 8 October 2026; dataset metadata at <https://analisi.transparenciacatalunya.cat/d/rmgc-ncpb> |
| Ajuntament de Barcelona (Guàrdia Urbana), on Open Data BCN | the six tables in `barcelona/2025/` | Creative Commons Attribution 4.0 for each of the six datasets: reuse, commercial or not, with attribution to the Ajuntament de Barcelona, a link to the licence and a note of any changes. The files are kept unchanged here; the analysis reads them into new tables, which the site describes | <https://creativecommons.org/licenses/by/4.0/>, the licence each dataset's metadata names, read on 8 October 2026 |
| ESRA (Vias institute and partner institutes) | none archived; two national shares typed into `compiled/driving_activity_by_age.csv` | no reuse licence is offered: the Vias disclaimer linked from the ESRA site footer claims intellectual rights over its contents for Vias institute "or entitled third parties", and no reproduction permission is stated in the reports or was requested, so nothing of theirs is redistributed here. The two shares are short quotations with attribution: the 2023 share (75.9 %, weighted n 935) from the ESRA3 main report, Table 6, and the Spain country fact sheet; the 2018 share (80.2 %, weighted n 906) from the ESRA-123 online dashboard, which publishes no downloadable table | <https://www.esranet.eu/en/publications/>, <https://www.vias.be/en/disclaimer> |
| Register of the withdrawn speed-law simulator (`compiled/evidence/simulator_parameters.csv`) | compiled by this project; read by no code | the values are quoted with attribution from their publications (TØI report 1034/2009; Trafikksikkerhetshåndboken, TØI for Statens vegvesen; European Commission, Baseline KPI Speeding; BOE; DGT); no publication is redistributed, and each row names its source, location and URL | the URLs in the file |
| Register of the withdrawn factor models (`compiled/evidence/factor_parameters.csv`) | compiled by this project; read by no code | the values are quoted with attribution from their publications (DGT's yearly Principales cifras and its 2024 errata; the INTCF toxicology reports of the Ministerio de Justicia; DGT's EDAP 2024 roadside survey; the EU DRUID final report; Dingus et al. 2016, PNAS; the EU Baseline KPI reports; ESRA3; Trafikksikkerhetshåndboken; Novoa et al. 2010; Bergen et al. 2014; Zhu et al. 2021; Ferdinand et al. 2014); no publication is redistributed, and each row names its source, location and URL | the URLs in the file |

## DGT crash microdata (`dgt/microdata/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `accidentes_2016.xlsx` … `accidentes_2024.xlsx` | 2016–2024, 875,013 injury crashes | the crash table: location, time, road, conditions, victims by severity and road-user type. National context and the external test domain of the transfer tests; it trains no predictive model ([`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md)) | speed (scoped totals), long run (deaths outside the measured networks), road class (overview split), associations in DGT records (supporting), 2006 break (supporting: the fits of the 2019 speed-limit study, linked as a negative result), Catalonia (province-year comparison), how far the results reach (test domain), four layers of data (audit), data |
| `diccionario.xlsx` | all years | code lists for the 33 coded fields | the pages that use the microdata (labels), data (code checks) |
| `metadata_2024.rdf.xml` | 2024 | official access URL, licence and issue date | manifest template |

datos.gob.es gives 5 November 2025 as the last update of the 2024 microdata (the `dct:modified` of
the `dcat:Dataset` in `metadata_2024.rdf.xml`, which equals its `dct:issued`; the enclosing
`dcat:CatalogRecord` carries its own, later `dct:modified`, 2026-05-26, for the catalogue entry; the
manifest description of `accidentes_2024.xlsx` carries the dataset date); no last-update date is
published in the records held for 2016–2023, and the record gives the dictionary no date of its own.

## DGT official tables (`dgt/tables/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `series_historicas_2024.xlsx` | 1993–2024, 69 sheets | crashes and victims by year, month, province, sex, age, pedestrians, drivers and passengers by vehicle, fleet and rates | 2019–2024, long run, seasons, 2006 break (supporting), data (checks); formerly the withdrawn monthly deaths forecast |
| `tablas_estadisticas_2020.xlsx` … `_2024.xlsx` | one workbook per year | province and month totals (validation), vehicles involved by type (2.3), victims by mode (2.2), drivers by age and sex (4.1.1, 4.2), driver infractions (6.1) | data (checks), vehicles, age and sex, speed, factors |
| `chapters/2014/grupo_1.xls` … `chapters/2019/grupo_8.xlsx` | 2014–2019, eight chapters a year | the same tables 4.1.1, 4.2 and 6.1 for the earlier years | age and sex, speed, factors |

## Exposure and denominators

| File | Coverage | Role | Page |
|---|---|---|---|
| `dgt/census/censo_conductores_{2023,2024,2025}.txt` | 2023–2025 | licence holders by province, sex, class and seniority | data (check) |
| `dgt/census/censo_conductores_edad_{2023,2024,2025}.txt` | 2023–2025 | licence holders by province, sex and age band; the `NUM_PERMISOS_B` column (holders of a B, car, permit) gives the 2024 car-licence population of the owner-age check and the denominator contrast | 2019–2024, age and sex, data (owner-age check) |
| `dgt/census/censo_tablas_2014.xlsx` … `dgt/census/censo_tablas_2025.xlsx` | 2014–2025 | published census tables: class by age 2014–2023 (the 2024 workbook has no class-by-age sheet and the 2025 ones are left unused so the 2024–2025 segment keeps a single source); province totals from the 2025 workbook only, so `censo_tablas_2024.xlsx` is archived but read by no script | 2019–2024, age and sex, data (checks) |
| `ine/ine_poblacion_provincias_edad_sexo.csv` | 2002–2025 | residents by province, five-year age group and sex, 1 January and 1 July | 2019–2024, age and sex, Catalonia and how far the results reach (severe crashes per resident by province) |
| `dgt/km_itv_2022/media_km_antiguedad_tipo_2022.xlsx` | 2022 | circulating fleet ("parque circulante": vehicles with an ITV, insurance, ownership-change, re-registration or fine record in the previous ten years) and mean annual km by vehicle type and age | vehicles, 2019–2024 (DGT's kilometre series beside fuel; its 2022 means equal table 6's) |
| `dgt/km_itv_2022/km_recorridos_estimados_2022.xlsx` | 2022 | km per vehicle by stratum (type, Euro class, age, engine, fuel) | parsed; not on the site |
| `dgt/km_itv_2024/km_edad_propietario_2024.xlsx` | 2024 | vehicles, total and mean annual km by vehicle category **and by the age band of the registered owner**; the denominator of the former driver-age figure, now the comparison Method D and one assumption of the 75-and-over split, never a driver-age denominator | drivers (former figure, Method D) |
| `dgt/km_itv_2024/km_medios_tipo_2024.xlsx` | 2022–2024 | the release's table 6, mean annual km by category for 2022, 2023 and 2024 as one series (its 2022 values equal the 2022 release's), and the 2024 detail sheet of vehicles and total km, used to reconcile the owner-age table against the published fleet; set beside fuel and deaths on the 2019–2024 page | age and sex (check), 2019–2024 |
| `dgt/km_itv_2024/km_servicio_2024.xlsx` | 2024 | vehicles and total and mean annual km by category and class of service (private; public: taxi, car hire with and without driver, driving school...): the national car-km total of the driver-age rates, less taxis and ride-hailing cars | drivers (driver-age exposure, Method B) |
| `dgt/km_itv_2024/km_comunidades_2024.xlsx` | 2024 | the release's table 9: mean annual km by category and the owner's autonomous community, with vehicles and total km in the 2024 detail sheet; read for the scale comparison of Catalonia and Madrid | drivers (driver-age exposure, text) |
| `ine/ine_poblacion_edad_simple_sexo.csv` | 2002–2025 | residents of Spain by single year of age and sex, 1 January and 1 July (INE table 56934, extract written by `scripts/fetch_ine.py --table single_age`), so that age groups can start at 16, 30, 45 and 65 without splitting a five-year group | drivers (driver-age exposure, Method A) |
| `crtm/edm2018/edm2018_individuos.csv`, `crtm/edm2018/edm2018_viajes_conductor.csv`, `crtm/edm2018/edm2018_codebook.csv` | 2018 | Madrid household travel survey (EDM2018): every respondent with exact age, sex, licence and person weight; every trip whose main mode is car driver with its distance; the codebook. Extracts of the CRTM workbooks written by `scripts/fetch_edm.py`. The age profile of car driving above 65, and a regional alternative to the EMEF profile | drivers (75 and over; Method C) |
| `cores/cores_consumos_pp.xlsx` | 1996–2026, monthly | national consumption of petroleum products; the automotive petrol and diesel subtotals, added together, are road fuel, the road-traffic exposure proxy, annual and monthly (petrol alone is shown only as a traffic index); each sheet also publishes the mass share of biofuel blended into its subtotal | 2019–2024, long run, seasons (deaths per tonne of road fuel), data (biofuel check), 2006 break (fuel covariate); formerly a predictor of the withdrawn monthly deaths forecast, which used each forecast month's own fuel sales |
| `transportes/peaje_trafico_total.xls` | 1990–2026, monthly | average daily intensity and vehicle-kilometres on the state toll-motorway network: a traffic index, never a denominator. The 2006 break uses the intensity, because the network's vehicle-kilometres step up with its length in July 2006 | seasons (traffic index), 2006 break (intensity covariate) |
| `transportes/anuario_carreteras_2023.pdf` | 2004–2023, annual | Ministerio de Transportes, Anuario Estadístico 2023, chapter on roads; table 1.2.14 gives vehicle-kilometres measured on the State, regional and provincial interurban networks by type of road (toll motorways; autovías and free motorways; multi-lane; conventional), each with its share of heavy vehicles, parsed by `io_traffic.read_road_traffic`, which requires the four types to add up to the published total. Comparable from 2008 (new road inventory); municipal interurban roads, up to a tenth of traffic by the Ministry's estimate, are not included, and the crash microdata record 8.7%–11.2% of interurban deaths, 2016–2024, on roads of municipal, other or unspecified owners, outside these networks (`longrun_km_coverage`) | long run (per measured km), 2019–2024 (the kilometre check), road class (owners 1–3; overview split), data (assumptions tested) |
| `dgt/km_itv_2022/metodologia.pdf` | 2014–2023 ITV | how the kilometres are modelled; the definition of the circulating fleet (Anexo III) and the category definitions that settle the heavy-truck mapping | vehicles (limits) |
| `transportes/movilia_2006.xls` | 2006 | table 64, trips by main mode × sex × age. Once the basis of the retired travel-weighted age denominator, which it could not support (its car-or-motorcycle column counts passengers as well as drivers and its top band is 65+). Read again for one sensitivity test of the national driver-age rates: the age mix of car trips on an average weekend day (sheet T64-5), which weights the weekend kilometres (`exposure_risk/national.py`, `movilia_weekend_weights`) | Drivers (sensitivity range) |
| `transportes/movilia_2007.xls`, `comunidad_madrid/movilia_madrid/*.xls` | 2006–2007 | long-distance and Madrid extracts, inspected; not read by any code | none |
| `ine/ine_ecepov_2021_55378.xlsx` | 2021 | commuters by main vehicle, sex and age | registered and checked in the audit; not read by the code and not on the site |
| `ine/ine_ehma_2008_10016.csv`, `ine/ine_ehma_2008_10019.csv` | 2008 | household km per vehicle by fuel and vehicle age | registered and checked in the audit; not read by the code and not on the site |

## Regional crash microdata (`catalonia/`, `barcelona/2025/`)

The regional files arrived under generic download names, kept in the manifest's `downloaded_as`
column; each was identified by its columns and filed under a descriptive name
(`src/dgt_stats/microdata/sources.py`). Their source URLs were not kept at download; the manifest
now gives the portal resource each was identified with (providers above). What each may be joined
to, and the checks on its keys and definitions, are in
[`DATA_CONTRACT.md`](DATA_CONTRACT.md); how each source came to exist is generated in
[`SOURCE_COMPARISON.md`](SOURCE_COMPARISON.md). No record of one is linked to a record of another
or of the DGT microdata.

| File (downloaded as) | Coverage | Role | Page |
|---|---|---|---|
| `catalonia/accidents_morts_ferits_greus_catalunya_2010_2023.csv` (`export.csv`) | 2010–2023, Catalonia, 24,478 crashes | Servei Català de Trànsit: one row per crash with at least one death or serious injury, with place, road, conditions, victims and units involved; no slight-injury crashes and no identifier. The Catalan crash-microdata layer: the crash-severity model, its temporal and geographic validation, and the training domain of the transfer tests | Catalonia, severity models, how far the results reach, four layers of data |
| `barcelona/2025/accidents_gu_bcn_2025.csv` (`download.csv`) | 2025, Barcelona city, 7,741 crashes | Guàrdia Urbana: one row per crash it attended, with place, time, victim counts by severity and vehicles involved; the crash table of the Barcelona layer | Barcelona, severity models (crash severity), how far the results reach, four layers of data |
| `barcelona/2025/accidents_persones_gu_bcn_2025.csv` (`download(1).csv`) | 2025, 17,200 person records | the people involved (drivers, passengers, pedestrians, injured or not) with age, sex, role, vehicle type and victimisation; the unit of the person-severity model | Barcelona, severity models (person severity), how far the results reach, four layers of data, drivers (car drivers per km on working days, with the EMEF) |
| `barcelona/2025/accidents_vehicles_gu_bcn_2025.csv` (`download(2).csv`) | 2025, 16,536 vehicle records | vehicle records (type, make, model, colour, licence class and age of licence); not shown to be one row per vehicle and with no vehicle key, so only the presence of a vehicle type in a crash is used ([`BARCELONA_VEHICLE_AUDIT.md`](BARCELONA_VEHICLE_AUDIT.md)) | Barcelona (vehicle audit), severity models (vehicle-type presence) |
| `barcelona/2025/accidents_causes_mediates_gu_bcn_2025.csv` (`download(3).csv`) | 2025, 7,749 rows | mediate causes recorded for each crash (alcohol, speed, drugs, road surface, signals, weather, objects or animals); a single blank row means none was recorded | Barcelona (recorded causes), severity models (retrospective set only) |
| `barcelona/2025/accidents_causa_conductor_gu_bcn_2025.csv` (`download(4).csv`) | 2025, 8,072 rows | driver-related causes recorded for each crash, with no key to the person or vehicle concerned, so they stay at crash level | Barcelona (recorded causes), severity models (retrospective set only) |
| `barcelona/2025/accidents_tipus_gu_bcn_2025.csv` (`download(5).csv`) | 2025, 7,741 rows | the type of each crash (collision, run-over, fall...), one row per crash; "Encalç", the Catalan file's term for a rear-end collision, marks almost only serious crashes; the descriptive tables count it as a rear-end collision (`microdata/descriptive.py`), while the source models used the field as recorded | Barcelona, severity models (crash type) |

## Working-day mobility survey (`emef/`)

Public-use microdata of the EMEF (Enquesta de mobilitat en dia feiner), the annual survey of the
working-day (Monday to Friday, not a public holiday) mobility of residents aged 16 and over in the
planning area of the ATM of the Barcelona area. Non-residents' trips, weekends and holidays are
outside its scope, and the trips of people who make eight or more work trips a day (drivers,
couriers, sales staff) are excluded apart from their journey to work. Every year has a respondent
file with one row per respondent, those who made no trip on the reference day included, and a trip
file whose `ID` values all appear in the respondent file.

| File (downloaded as) | Coverage | Role |
|---|---|---|
| `emef/<year>/emef_<year>_trips.csv` (`Microdades_OMC_Despl_EMEF<year>.csv` for 2014–2017 and 2024; `Microdades Ús públic_EMEF<year>_Desplaçaments.csv` for 2018–2023) | 2014–2024, 32,334–45,552 trips a year | one row per trip on the reference day, keyed by respondent `ID` and trip order `ORDRE` |
| `emef/<year>/emef_<year>_persons.csv` (`..._Indivi_...` or `..._Individus.csv` for 2014–2017, 2021, 2022 and 2024; `..._Opinió.csv` for 2018–2020 and 2023) | 2014–2024, 9,461–11,420 respondents a year | one row per respondent, with sex, age group, residence, the opinion module and the weights `PESAIX` (expansion) and `PESMOS` (sample) |
| `emef/<year>/emef_<year>_dictionary.xlsx` | one per year | variable list, record layout and value labels of both files |
| `emef/2022/emef_2022_dictionary_revised.xlsx` | 2022 | the dictionary the OMC page links today: identical to the first release except for the trip-file value-label sheet |
| `emef/2024/emef_2024_executive_summary.pdf` (`emef_2024_resum_executiu.pdf`, from recam.amb.cat) | 2024 | the survey's published executive summary: its technical sheet (sampling, calibration, fieldwork dates) and the published benchmarks the trip-distance estimates are checked against (mean straight-line trip 4.7 km; daily straight-line km per person by age), typed into `emef/distance.py` |
| `idescat/idescat_census_2024_activity_release.html` (Idescat release of 8 July 2026) | 1 January 2024, Catalonia | the census count of employed people aged 65 and over in Catalonia (67,143), typed into `emef/exposure.py` to benchmark the survey's employed share at 65 and over, one choice in the drivers' sensitivity range |

How the eleven years were read, harmonised and checked, and what they cannot show (no age group
finer than 65 and over), is set out in
[`research/EMEF_INVENTORY.md`](research/EMEF_INVENTORY.md).

## Compiled registers (`compiled/`)

Three files hold values typed by hand from publications, each row with its source. They are not
source data: external studies may define a variable or a method in this project but never supply
an observation, a coefficient or an effect size, so **no code reads them** (`tests/test_withdrawn.py`
checks that for the two evidence registers). They are kept, unmodified and hashed, as the record
of what was searched and of what the withdrawn analyses used: the speed-law simulator, the
distraction and alcohol-and-drug models and the enforcement comparison were withdrawn because
their results came from external-study coefficients, and their pages are now withdrawal notices.

| File | Content | Page |
|---|---|---|
| `compiled/driving_activity_by_age.csv` | 2008, 2018, 2023: hand-typed survey register of ESRA national shares of adults who drive (Spain) and three Fundación MAPFRE rows on driving days per week among Madrid drivers 65+. Kept as the record of what was searched; no code reads it. The survey-based driving denominator it fed was withdrawn, and driving by age is now measured from the EMEF and EDM2018 microdata | none |
| `compiled/evidence/simulator_parameters.csv` | the register of the withdrawn speed-law simulator, 33 rows, one per published value it used with its source, the table or page, the URL and a verbatim quote: Elvik (2009, TØI report 1034/2009, table S1) Power Model exponents by road environment; the limit-to-mean-speed curve of the Norwegian road-safety handbook (Trafikksikkerhetshåndboken, chapter 3.11, figure 3.11.2); free-flow car speeds measured in Spain in 2022 for the EU Baseline project (KPI Speeding report, tables 9–11 and 12a, and for autovías the Annex 1 text introducing tables 12a–12c); the legal limits (Reglamento General de Circulación art. 48; Real Decreto 970/2020 art. 50); DGT's 2024 values of preventing a death, a serious and a slight injury (Universidad de Murcia for DGT) | none (withdrawal notice) |
| `compiled/evidence/factor_parameters.csv` | the register of the withdrawn distraction and alcohol-and-drug models and enforcement comparison, 112 rows: DGT's fatal crashes with each concurrent factor, all roads and interurban roads, 2022–2024 (Tabla 50 of the yearly Principales cifras, with the 2024 errata), and injury crashes with distraction and alcohol (2024); the INTCF toxicology of drivers killed in 2023 and 2024 (blood alcohol bands, drugs, alcohol with drugs, medicines); the drugs the police detected in 2023; the EU DRUID project's relative risks of serious injury or death by blood alcohol and by drug; the crash risks of distraction from the SHRP 2 naturalistic driving study (Dingus et al. 2016); roadside prevalence of alcohol, drugs and handheld phones (EDAP 2024, Baseline KPI reports, ESRA3); the Guardia Civil's breath and drug tests (2023 and 2024) and DGT's speed fines (2024); the deaths in 2024 crashes in which a driver's alcohol was recorded, and how many of them were those drivers; the risk of phone use by crash severity (Trafikksikkerhetshåndboken chapter 8.14); and 17 published evaluations of enforcement (Trafikksikkerhetshåndboken chapters 8.1, 8.2, 8.7, 8.14 and 8.15; Novoa et al. 2010; Bergen et al. 2014; Zhu et al. 2021; Ferdinand et al. 2014) | none (withdrawal notices) |

None of the publications is archived here: the TØI report and the handbook carry the
institute's copyright, the Baseline report is the European Commission's, and the registers only
quote the numbers with attribution, as with the ESRA shares below. The DGT reports on the value of
a casualty are public-sector information and are cited rather than copied.

## Thematic reports (`dgt/reports/`)

| File | Coverage | Role | Page |
|---|---|---|---|
| `dgt_factor_velocidad_2023.pdf` | 2014–2023, without Cataluña or País Vasco | 61 of its 64 tables (all but the three year-on-year variation tables; Tablas 50–61 are its Anexo I), transcribed by `io_reports.py`. Its scope totals (Tablas 1–3), speed-related crashes and deaths by road type, and crashes by concurrent factor are inputs to analyses; its scope totals are reconciled against the microdata by year and zone (`speed_report_scope`), not by road type; none of its breakdowns is republished | speed, factors |
| `dgt_personas_mayores_2023.pdf` | 2023 | the per-inhabitant framing for older road users that the age-and-sex page's four denominators test; no figure from it is reproduced, and the page does not cite it | none (context) |
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

- National vehicle-level and person-level crash records (driver age and sex, alcohol and drug
  tests, speed, seat belt, helmet): DGT does not publish them for download; a request to DGT's
  Observatorio Nacional de Seguridad Vial would be needed. The Catalan file has no person or
  vehicle rows; the Barcelona person table covers one city in 2025 and its vehicle records have no
  vehicle key.
- Road geometry, traffic volumes and section-level speeds; crash coordinates in the national
  records (the Barcelona crash table has them, the Catalan file gives road and kilometre point).
- A dated register of campaigns and enforcement periods.
- Vehicle-kilometres **by vehicle type** before 2022. DGT's 2024 release gives mean kilometres by
  category for 2022–2024 as one series, but the fleet for 2024 only, so total kilometres for 2023
  are not in the repository; the vehicles page pairs the crash tables with the kilometres for 2022
  only. The Ministry's table 1.2.14 splits
  interurban traffic only into heavy vehicles, as one group, and the rest.
- Distance driven by the **driver's** age **for Spain as a whole**. Two regional travel surveys
  measure it from their microdata: the EMEF for the Barcelona area (working days, age groups
  ending at 65+) and EDM2018 for Madrid (weekdays, exact age). The national rates transfer their
  age profiles to Spain's population (`research/DRIVER_AGE_EXPOSURE.md`). DGT's 2024 kilometre
  release gives the **owner's** age band and is kept as a comparison. MOVILIA 2006/2007 count
  trips and travel time, not kilometres, and do not separate drivers from passengers; INE's EHMA
  2008 gives mean annual kilometres per household vehicle by the age of the household's reference
  person, in four bands that stop at 65+; ESRA gives a national share of adults who drive with no
  age split. Each was checked and is registered above.
- Car-driving distance at 75 and over in the EMEF. The public files merge 65–74 and 75+; the
  confidential records hold exact age, and a request for tables is prepared but not sent
  (`research/EMEF_DATA_REQUEST.md`).
- Monthly vehicle-kilometres on all Spanish roads, and annual urban vehicle-kilometres. The two
  monthly series registered above are proxies with known limits: CORES measures fuel sold, not
  distance, and its petrol/diesel mix shifts over the 2000s; the toll-motorway series measures
  distance directly but on 1,400–2,500 km of motorway whose length changes as concessions expire.
  The Ministry's annual table 1.2.14 measures interurban kilometres only, without municipal roads.
- Measured speeds by road type before and after a Spanish limit change (the 2019 change to 90 km/h
  on conventional roads, the 2011 temporary 110 km/h on motorways): no published before-and-after
  measurement was found, and the crash records carry no speeds.
- Casualties by the speed limit of the road or street in DGT's national records. The Catalan file
  records a posted limit only where `D_LIMIT_VELOCITAT` is "Senyal velocitat"; otherwise its speed
  field is a code, not a limit.
