# Data sources

The source register: who publishes each file under `data/raw/`, what it holds, its coverage, its
known coding breaks and the terms on which it may be reused. Paths are relative to `data/raw/`,
where files are grouped by publisher (`dgt/`, `ine/`, `transportes/`, `cores/`, `catalonia/`,
`barcelona/2025/`, `emef/`, `crtm/`, `idescat/`). `data/raw/manifest.csv` lists every file with
size, SHA-256, source URL, description, the date added and, for files filed under a new name, the
name it was downloaded as. Only files the code reads, or a published document a check compares
against, are kept. What each dataset may be joined to is in [`DATA_CONTRACT.md`](DATA_CONTRACT.md).

The DGT, INE, Ministerio de Transportes and CORES files are the national context: trends,
denominators, exposure, rates and aggregate comparisons. The EMEF and EDM2018 travel surveys
supply car-driving kilometres by driver age. The Servei Català de Trànsit file is the Catalan
crash microdata and the Guàrdia Urbana tables are the Barcelona microdata. No record is linked
across sources and there is no merged database.

## Providers

- **DGT en Cifras** (Dirección General de Tráfico, <https://www.dgt.es/menusecundario/dgt-en-cifras/>):
  yearly definitive injury-crash statistics, the historical series, the crash microdata, the driver
  census, the kilometre estimates and the speed-factor report. Provisional and definitive series,
  and 24-hour and 30-day death counts, are never mixed.
- **INE** (Instituto Nacional de Estadística): resident population by province, age and sex.
- **Ministerio de Transportes y Movilidad Sostenible**: MOVILIA 2006 and 2007 travel surveys;
  monthly traffic on the state toll-motorway network from 1990 (Boletín Estadístico Online);
  annual vehicle-kilometres and the share of heavy vehicles by type of road on the State, regional
  and provincial interurban networks, 2004-2023 (Anuario Estadístico 2023, roads chapter, table
  1.2.14).
- **CORES** (Corporación de Reservas Estratégicas de Productos Petrolíferos, which keeps Spain's
  compulsory oil stocks and publishes the official petroleum statistics under Ley 34/1998):
  monthly consumption of petroleum products from 1996.
- **Servei Català de Trànsit** (Departament d'Interior i Seguretat Pública, Generalitat de
  Catalunya): an export of the crashes in Catalonia with at least one death or serious injury,
  2010-2023, downloaded as `export.csv` from the Generalitat's open-data portal, dataset
  `rmgc-ncpb`, "Accidents de trànsit amb morts o ferits greus a Catalunya"
  (<https://analisi.transparenciacatalunya.cat/d/rmgc-ncpb>). The URL was not kept at download;
  on 8 October 2026 the file's row count and its yearly totals of deaths and serious injuries
  equalled the portal's, whose rows were last updated on 5 December 2024.
- **Ajuntament de Barcelona** (the crashes are recorded by the Guàrdia Urbana, the city police):
  six tables of the crashes the Guàrdia Urbana attended in Barcelona in 2025, with the people,
  vehicle records, crash types and recorded causes, downloaded as `download.csv` to
  `download(5).csv` from Open Data BCN, datasets `accidents-gu-bcn`, `accidents-persones-gu-bcn`,
  `accidents-vehicles-gu-bcn`, `accidents-causes-gu-bcn`, `accidents_causa_conductor_gu_bcn` and
  `accidents-tipus-gu-bcn` (<https://opendata-ajuntament.barcelona.cat/data/ca/dataset/accidents-gu-bcn>
  and its sibling pages). The URLs were not kept at download; on 8 October 2026 each file's size
  equalled that of the portal's 2025 resource (last modified 17 February 2026), whose download URL
  the manifest now gives. The portal's download route answered with a bot check, so the checksums
  could not be compared.
- **ATM, Idescat and Institut Metròpoli** (Enquesta de mobilitat en dia feiner, EMEF; published by
  the Autoritat del Transport Metropolità on the Observatori de la Mobilitat de Catalunya,
  <https://www.omc.cat/ca/w/enquesta-emef>): public-use microdata of the working-day mobility
  survey of residents aged 16 and over in the ATM planning area, 2014-2024, one trip file, one
  respondent file and one dictionary per year (`emef/<year>/`). Each file was compared byte for
  byte with the copy served by omc.cat on 7 October 2026 and matched.
- **Àrea Metropolitana de Barcelona** (RECAM, <https://recam.amb.cat>): the EMEF 2024 executive
  summary by Institut Metròpoli (`emef/2024/`), the source of the survey's technical sheet and of
  the published distance benchmarks the distance model is checked against.
- **Idescat** (Institut d'Estadística de Catalunya, <https://www.idescat.cat>): the release on the
  2024 census and economic activity (`idescat/`), the source of the count of employed people aged
  65 and over in Catalonia.
- **CRTM** (Consorcio Regional de Transportes de Madrid): the Encuesta Domiciliaria de Movilidad
  2018 (EDM2018), public microdata on the CRTM's ArcGIS open-data site.

## Reuse terms

The code in this repository is under the MIT licence (`LICENSE`). The files under `data/raw/` are
not: each keeps the terms of the body that published it, listed here as read on 19 September 2026,
and for the regional crash files on 8 October 2026. Whatever the provider, this project names the
source, keeps every file as downloaded with its checksum and date added (the `added` column of the
manifest), its edition or reference year and, where the provider's record gives one, the
publisher's date of last update (the description), publishes aggregates only, and claims no
endorsement from anyone. Some files are not downloads: `ine/ine_poblacion_provincias_edad_sexo.csv`
and `ine/ine_poblacion_edad_simple_sexo.csv` are extracts of INE tables 56947 and 56934 written by
`scripts/fetch_ine.py` (nationality total where relevant and the 1 January and 1 July periods,
columns renamed), and the files under `crtm/edm2018/` are extracts of the CRTM's EDM2018
workbooks written by `scripts/fetch_edm.py` (columns and, for trips, car-driver rows kept as
published; the manifest gives each workbook's checksum).

| Provider | Files | Terms as published | Notice |
|---|---|---|---|
| DGT, catalogued on datos.gob.es | crash microdata and dictionary (`dgt/microdata/`) | free, non-exclusive licence for commercial and non-commercial reuse: name the origin of the data, do not distort its meaning, keep the date of last update, do not suggest that the publisher endorses the reuse, keep the metadata | <https://datos.gob.es/avisolegal>, the licence named in the catalogue record of the 2024 microdata |
| DGT, from dgt.es | series, statistical tables, driver census, kilometre estimates and the speed-factor report (`dgt/tables/`, `dgt/census/`, `dgt/km_itv_2022/`, `dgt/km_itv_2024/`, `dgt/reports/`) | public-sector information within the scope of Ley 37/2007. DGT's legal notice claims the intellectual property of the portal, its graphic design and its code, states that unauthorised reproduction, distribution, commercialisation or transformation of those works other than for personal and private use is an infringement, and warns that unauthorised placement of the information the portal contains may lead to legal action; it grants no reuse licence for the statistics and names no licence at all. Redistribution of these files here therefore rests on the Ley 37/2007 regime for public-sector information, applying the datos.gob.es conditions above to every DGT file by this project's own choice; no permission has been requested from DGT | <https://www.dgt.es/contenido/aviso-legal/> |
| INE | population (`ine/ine_poblacion_provincias_edad_sexo.csv`, `ine/ine_poblacion_edad_simple_sexo.csv`) | [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/) unless a product says otherwise; processed data are cited as "Elaboración propia con datos extraídos del sitio web del INE: www.ine.es"; keep the date of last update; do not suggest that INE endorses the reuse | <https://www.ine.es/aviso_legal/> |
| Ministerio de Transportes y Movilidad Sostenible | MOVILIA 2006 and 2007 workbooks (`transportes/movilia_2006.xls`, `transportes/movilia_2007.xls`); the toll-motorway traffic series (`transportes/peaje_trafico_total.xls`); the roads chapter of the Anuario Estadístico 2023 (`transportes/anuario_carreteras_2023.pdf`) | reusable for commercial and non-commercial purposes: cite "Origen de los datos: Ministerio de Transportes y Movilidad Sostenible", keep the date of last update, do not distort the content, do not suggest endorsement, keep the metadata | <https://www.transportes.gob.es/ministerio/aviso-legal> |
| ATM (Autoritat del Transport Metropolità), on omc.cat | the EMEF microdata and dictionaries in `emef/` and the methodology report 2003-2018 (`emef/docs/emef_methodology_2003_2018.pdf`, by the IERMB, now Institut Metròpoli), kept unchanged and carrying no notice of their own | the OMC legal notice's open-data clause permits reproduction, distribution, public communication and transformation worldwide and without time limit under article 8 of Ley 37/2007, on four conditions: cite the rights holder (Consorci de l'Autoritat del Transport Metropolità de l'àrea de Barcelona), do not distort the meaning, cite the source, state the date of last update (the manifest descriptions give each file's date on omc.cat). The dictionaries add that results computed from the public-use files are the user's responsibility, not official statistics, and should be cited as "ATM, Idescat i Institut Metròpoli, <year>. Enquesta de mobilitat en dia feiner <year>. Autoritat del Transport Metropolità"; they also allow an estimate to be published only if it rests on at least 20 sample observations, and a table only if at least 60% of its cells can be (note 3 of the `Sumari` sheet), and the published tables apply that rule (`src/dgt_stats/emef/publication.py`) | <https://www.omc.cat/ca/avis-legal>, read on 7 October 2026; the `Sumari` sheet of each dictionary |
| Consorcio Regional de Transportes de Madrid (CRTM), on its ArcGIS open-data site | the EDM2018 extracts in `crtm/edm2018/` | the CRTM open-data licence permits reuse, commercial or not, on three conditions: cite the CRTM as the source, show "Powered by CRTM" with a link to www.crtm.es on any digital platform that uses the data, and distribute derived data under the same licence. The extracts keep columns and rows of the published workbooks unchanged; they and the tables derived from them are distributed under that licence, as the site's methodology page states | <https://www.crtm.es/licencia-de-uso>, the licence linked from each ArcGIS item, read on 8 October 2026 |
| Idescat (Institut d'Estadística de Catalunya) | `idescat/idescat_census_2024_activity_release.html`, the release of 8 July 2026 on the 2024 census and economic activity, kept unchanged; one count from it (67,143 employed people aged 65 and over in Catalonia) is typed into `emef/exposure.py` | Idescat's legal notice, section "Intellectual property rights", allows the information on its website to be reused provided that the source is quoted, the content is not altered or denatured and the date of the latest update is mentioned; information processed afterwards is cited as "Source: created upon the basis of Idescat's own data" (unprocessed, "Source: Idescat"); no involvement, sponsorship or support by Idescat may be suggested; Idescat may limit reuse to protect other legal interests, such as privacy or third parties' intellectual property. It names no Creative Commons or other standard licence, and cites Ley 37/2007 as amended by Ley 18/2015 | <https://www.idescat.cat/institut/web/?lang=en> (legal notice), read on 8 October 2026 |
| Àrea Metropolitana de Barcelona (AMB), on its repository RECAM (recam.amb.cat) | `emef/2024/emef_2024_executive_summary.pdf`, *Enquesta de mobilitat en dia feiner: EMEF, 2024* (Institut Metròpoli, edited by the AMB, issued 1 April 2025; <https://hdl.handle.net/20.500.14439/4922>), kept unchanged; four figures from it (the mean straight-line trip and the daily straight-line kilometres per person in three age groups) are typed into `emef/distance.py`, where they are used only to check the distance model | Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0), rights holder the Àrea Metropolitana de Barcelona, as the repository's record of the item states: the PDF may be copied and redistributed unchanged, for non-commercial purposes, with attribution and a link to the licence. The MIT licence of the code does not reach it, and a commercial reuse of the PDF goes back to the AMB | <https://creativecommons.org/licenses/by-nc-nd/4.0/>, the licence named in the item's record (`dc.rights`, `dc.rights.uri`, `dc.rights.holder`), read through the repository's API on 8 October 2026 |
| CORES | `cores/cores_consumos_pp.xlsx` | public-sector information within the scope of Ley 37/2007: CORES is a corporation of public law under the Ministerio para la Transición Ecológica and publishes these statistics as part of its statutory duty. Its site names no reuse licence, so the file is redistributed here on the same footing as the DGT statistics, applying the datos.gob.es conditions by this project's own choice: the source is named, the meaning is not distorted, the date of last update is kept (the `Actualizado el` cell of each sheet) and no endorsement is implied | <https://www.cores.es/es/estadisticas> |
| Servei Català de Trànsit, on the Generalitat's open-data portal | `catalonia/accidents_morts_ferits_greus_catalunya_2010_2023.csv` | the portal gives the licence as "See Terms of Use", linking the Llicència oberta d'ús d'informació - Catalunya: sharing, modification and reuse are free on condition that the content and its meaning are not altered, the source is cited as "Generalitat de Catalunya. Departament d'Interior i Seguretat Pública. Servei Català de Trànsit", and the date of last update is stated (5 December 2024 on the portal); sublicensing is not allowed, so the file is redistributed here under that licence and not under the code's | <https://administraciodigital.gencat.cat/ca/dades/dades-obertes/informacio-practica/llicencies/>, read on 8 October 2026; dataset metadata at <https://analisi.transparenciacatalunya.cat/d/rmgc-ncpb> |
| Ajuntament de Barcelona (Guàrdia Urbana), on Open Data BCN | the six tables in `barcelona/2025/` | Creative Commons Attribution 4.0 for each of the six datasets: reuse, commercial or not, with attribution to the Ajuntament de Barcelona, a link to the licence and a note of any changes. The files are kept unchanged here; the analysis reads them into new tables, which the site describes | <https://creativecommons.org/licenses/by/4.0/>, the licence each dataset's metadata names, read on 8 October 2026 |

### Dates of last update

The DGT (through datos.gob.es), INE, Ministerio de Transportes, OMC, Idescat and Generalitat terms
ask that the date of the data's last update be kept. The dates below are those the providers
publish, as the manifest's descriptions or the files themselves record them. Where a provider
publishes none, the date given is the download date (the manifest's `added` column), and the entry
says so. The methodology page's Reuse section gives the same dates, read from the manifest when the
page is built.

- **DGT.** The 2024 crash microdata were last updated on 5 November 2025 (datos.gob.es; the
  manifest description of `accidentes_2024.xlsx` carries the date). No date of last update is
  published for the 2016-2023 microdata files or for DGT's tables, series, census, kilometre
  releases and reports. They are dated by download only: from 18 September 2026 or earlier (the
  manifest records the first files as added "before 2026-09-18") to 8 October 2026, each file's
  date being in the manifest.
- **INE.** The population tables as downloaded carry no date of last update. The two extracts were
  written from tables downloaded on 19 September 2026 (table 56947) and 8 October 2026 (table
  56934).
- **Ministerio de Transportes y Movilidad Sostenible.** No date of last update is published with
  the files. The roads chapter of the Anuario Estadístico 2023 was created on 13 January 2025 and
  last modified on 29 January 2025, by the PDF's own metadata (`tests/test_paths.py` checks the
  manifest against them). The toll-motorway series was downloaded on 22 September 2026 and the
  MOVILIA workbooks on 19 September 2026, and are dated by download only.
- **CORES.** Every sheet of `cores/cores_consumos_pp.xlsx` states "Actualizado el 14-09-2026"
  (14 September 2026).
- **OMC (EMEF).** Each file's date on omc.cat is in its manifest description.
- **Idescat.** The census release is dated 8 July 2026.
- **AMB (EMEF 2024 executive summary).** Issued on 1 April 2025, as the repository's record
  states; its licence does not ask for a date of update.
- **Servei Català de Trànsit.** Rows last updated on the portal on 5 December 2024.
- **Ajuntament de Barcelona.** The 2025 resources were last modified on 17 February 2026.
- **CRTM.** The EDM2018 licence does not ask for a date of update; the extracts were written on 8
  October 2026 from the workbooks whose checksums the manifest gives.

## DGT crash microdata (`dgt/microdata/`)

| File | Coverage | Content |
|---|---|---|
| `accidentes_<year>.xlsx` | 2016-2024 | one row per injury crash: location, time, road, conditions, victims by severity and road-user type. 72-74 columns, two sheets each (`ACCIDENTES_YY` and a description sheet). Original names `Tabla-Accidentes-<year>.xlsx` (2016-2019) and `TABLA_ACCIDENTES_<yy>.xlsx` (2020-2024) |
| `diccionario.xlsx` | all years | code lists for the coded fields (originally `Diccionario_Tabla_Accidentes.xlsx`) |

Source: Registro Nacional de Víctimas de Accidentes de Tráfico (Orden INT/2223/2014), published on
DGT en Cifras under "Ficheros de microdatos de accidentes con víctimas". **DGT publishes only the
crash-level table**: there is no public vehicle-level or person-level file. Those tables exist in
the register and are available on request to DGT's Observatorio Nacional de Seguridad Vial. The
description sheet in the 2023 and 2024 workbooks is a stale copy of the 2022 one and must not be
used for validation. Each year's rows and 30-day victim sums reconcile exactly with the yearbook
series, and the 2024 province and month tables agree with the microdata (`reports/tables/validation.csv`,
written by `scripts/ingest.py validate`, which `ingest.py all` runs). `TOTAL_VEHICULOS` falls short of the 2024 table 2.3 by a few
dozen vehicles in 2023 and 2024 (2020-2022 are exact); the check accepts those years within 0.1%
because the microdata hold no vehicle-level rows that could locate the missing units.

The columns fall into six blocks: identity and time (`ID_ACCIDENTE`, `ANYO`, `MES`, `DIA_SEMANA`,
`HORA`; no calendar day, so specific dates cannot be recovered); location (province, municipality,
zone, road, kilometre post, owner, road type); crash type and counts of victims at 24 hours and 30
days; deaths by road-user type (deaths only: involvement of a vehicle type is not recorded);
junction and priority; and conditions (surface, lighting, weather, fog, wind, visibility, sidewalk,
alignment). There are no driver age or sex, alcohol or drug results, speed, seat-belt or helmet
use, vehicle age or coordinates. Municipality is `00000` for towns under 5,000 inhabitants and the
road name is "No inventariada" with a null kilometre post for most urban crashes
(`reports/tables/missingness_by_year.csv`).

### Missing-value states

These stay distinct (`src/dgt_stats/codes.py`):

| State | Encoding in file | Example |
|---|---|---|
| Not specified / not reported | `999` | weather, priority regulation, traffic level |
| Not applicable | `998` | sidewalk on interurban road, alignment on urban street |
| Explicitly unknown | a named code (`6` traffic level, `9` surface, `7` weather, `18` visibility, `4` alignment) | police attended but could not determine |
| Empty | `None` | island, kilometre post, fog and wind when absent, junction detail away from a junction |

Missingness also depends on the province: most fields have unrecorded shares that differ between
provinces, and the four Catalan provinces differ from the rest in several fields below.

### Coding breaks between years

Never read a share in these fields as a trend across the years named without checking it year by
year and province by province.

- `SECUENCIAL` is renamed `ID_ACCIDENTE` from 2021; identifiers restart at 1 each year, so the key is
  (`ANYO`, `ID_ACCIDENTE`). `TOT_VMP_MU30DF` exists from 2020 (earlier personal-mobility deaths are
  counted under "Otro"); `TOT_VMP_MU24H` only in 2020.
- 2016 is a separate reporting regime for the condition fields: `VISIB_RESTRINGIDA_POR = 999` falls
  from about 32% to 10% in 2017, `CONDICION_FIRME = 9` falls, and fog flags rise from under 1% to
  several percent, a rise that is Barcelona's alone (its records code fog in 33-45% of crashes a
  year from 2017). Treat 2016 as not comparable to later years.
- `CONDICION_METEO = 999` falls from about 10% in 2016-2018 to under 0.5% from 2019.
- `TIPO_VIA = 14` ("Otro") rises from 2.9% to 17.2% and `TITULARIDAD_VIA = 5` ("Otra") from 1.6% to
  22.0% between 2016 and 2024, while `TIPO_VIA = 9` ("Calle") falls from 59.9% to 47.5%: a coding
  change in the four Catalan provinces, which record no crash as a street in 2024. Use a collapsed
  road grouping; the street/other split is not comparable across 2023-2024. The toll/free
  motorway distinction (`TIPO_VIA` 1 and 2) is unusable (the toll share falls from about 2% to 0.4%
  in 2022 and 2024), so the two are always pooled.
- `TIPO_VIA = 5` (dual-carriageway conventional road) falls from 6.8% to 1.8% of crashes between 2020
  and 2021 while `TIPO_VIA = 6` rises from 17.9% to 21.4% and their sum stays near 23%: the
  dual/single carriageway split is not comparable across 2020-2021, so conventional roads are
  taken as codes 4 to 6 together.
- `ZONA = 4` (urban motorway or dual carriageway) falls from 0.6-0.7% of crashes in 2016-2018 to
  0.1% or less from 2019; the grouped zone is unaffected.
- `NUDO = 1` (at a junction) rises from 38-40% of crashes in 2016-2022 to 43.5-43.7% in 2023-2024, and
  `NUDO_INFO = 999` from under 1% to about 15%. From 2023 the four Catalan provinces code `NUDO` the
  wrong way round (their at-junction share goes from 35-42% to 62-63%, elsewhere it stays at
  37-40%; on the crashes both files hold, DGT's 2023 Catalan crashes coded at a junction match the
  Servei Català de Trànsit file's crashes between junctions). Never read the junction share as a
  trend across 2022-2023, and flip Catalan junction codes from 2023 before using them.
- `VISIB_RESTRINGIDA_POR` and `CONDICION_NIVEL_CIRCULA` swap between their explicit unknown code and
  999 in 2021, 2023 and 2024 (`VISIB_RESTRINGIDA_POR = 999` is 0.3% in 2019 but about 14-15% in those
  years, `CONDICION_NIVEL_CIRCULA = 999` about 10% against 32-34%), concentrated in the four Catalan
  provinces. `TITULARIDAD_VIA = 999` appears in 14.8% of 2021 rows (all urban `ZONA 3`). Never run
  complete-case trend comparisons on these fields.
- `CONDICION_VIENTO = 1` jumps from 0.2-1.2% in every other year to 24.6% in 2021 alone, nearly all
  of it the Catalan provinces' crashes, a reporting artefact to keep out of cross-year comparisons.
- `KM` is null in about 62% of rows in most years but 46-48% in 2019, 2020 and 2022, where a
  placeholder stands in the empty cell (1000 in 2019, 9999 in 2020 and 2022); counting the
  placeholder, the kilometre post is unrecorded in about 62% of crashes every year. The validation
  profile counts it as not observed.
- `ISLA = 0`, absent from the dictionary, appears from 2018 and grows to several hundred rows in
  2024, almost only in the Balearic and Canary provinces; it is treated as "island not specified"
  (`codes.UNDOCUMENTED_NOT_SPECIFIED`). An empty island field is not evidence of a mainland crash:
  many empty rows are in the Balearic and Canary provinces themselves.

## DGT official tables (`dgt/tables/`)

| File | Coverage | Content |
|---|---|---|
| `series_historicas_2024.xlsx` | 1993-2024 | annual series: crashes, victims (24 hours and 30 days), by month, province, sex, age, pedestrians, driver deaths by vehicle type, rates per fleet and population (originally `Series-Historicas-Anuario-Accidentes-2024.xlsx`) |
| `tablas_estadisticas_2020.xlsx` ... `_2024.xlsx` | one workbook per year | the yearbook's statistical tables with the same sheet names: province and month totals, vehicles involved by type (2.3), victims by mode (2.2), drivers by age and sex (4.1.1, 4.2), driver infractions (6.1) |
| `chapters/<2014..2019>/grupo_4`, `grupo_6` | 2014-2019 | the same tables 4.1.1, 4.2 and 6.1 for the earlier years, from the chapter workbooks of those years (chapter 4: drivers; chapter 6: infractions). 2014 is `.xls`; 2015 uses upper-case titles without the year |

## Driver census and kilometre estimates

| File | Coverage | Content |
|---|---|---|
| `dgt/census/censo_conductores_<2023..2025>.txt` | 2023-2025 | pipe-delimited: province x sex x licence class x year of issue -> drivers. Classes are each driver's single highest class and sum to the number of drivers; the 2025 workbook counts permits, a different question. 2025 is UTF-8 with a byte-order mark |
| `dgt/census/censo_conductores_edad_<2023..2025>.txt` | 2023-2025 | province x sex x age band (15-17, 18-20, 21-24, then five-year bands to 70-74, "Más de 74", "Se desconoce") -> permits and licences by class, including `NUM_PERMISOS_B`. 2023 and 2024 are Latin-1, 2025 UTF-8 with a byte-order mark |
| `dgt/census/censo_tablas_<2014..2025>.xlsx` | 2014-2025 | published census tables; 2014-2023 include drivers by licence class x age band (plus men and women sheets), 2024 has only the province tables. Province totals are read from the 2025 workbook only, so `censo_tablas_2024.xlsx` is archived but not read |
| `dgt/km_itv_2022/media_km_antiguedad_tipo_2022.xlsx` | 2022 | circulating fleet ("parque circulante": vehicles with an ITV, insurance, ownership-change, re-registration or fine record in the previous ten years) and mean annual km by vehicle type (7) and age band (5); multiplied, total vehicle-km by type |
| `dgt/km_itv_2024/km_edad_propietario_2024.xlsx` | 2024 | vehicle category x age band of the **registered owner** (and a row for vehicles in a company's name) -> vehicles, total and mean annual km. Summed over the bands it reproduces the release's own fleet and kilometres per category to within 0.1%; the reader enforces 0.5%. The owner's age is not the driver's: there are about 0.23 cars per B-permit holder at 18-24 and about 1.1 at 75 and over |
| `dgt/km_itv_2024/km_medios_tipo_2024.xlsx` | 2022-2024 | table 6 of the release: mean annual km by category for 2022, 2023 and 2024 as one series (its 2022 values equal the 2022 release's), and a 2024 detail sheet of vehicles and total km |
| `dgt/km_itv_2024/km_servicio_2024.xlsx` | 2024 | vehicle category x class of service (private; public: taxi, car hire with and without driver, driving school...) -> vehicles, total and mean annual km; the national car-km total, less taxis and ride-hailing cars |
| `dgt/km_itv_2024/km_comunidades_2024.xlsx` | 2022-2024 | table 9: mean annual km by category and the owner's autonomous community, with a 2024 detail sheet of vehicles and total km |

DGT's kilometres form one series by vehicle type only from 2022; the fleet for 2024 only, so total
kilometres for 2023 are not in the repository.

## Population, traffic and fuel

| File | Coverage | Content |
|---|---|---|
| `ine/ine_poblacion_provincias_edad_sexo.csv` | 2002-2025 | INE table 56947 extract: residents by province x five-year age group x sex, 1 January and 1 July; rebuilt by `scripts/fetch_ine.py` |
| `ine/ine_poblacion_edad_simple_sexo.csv` | 2002-2025 | INE table 56934 extract: residents of Spain by single year of age (0-104 and "105 y más", plus the overlapping aggregates "85 y más" and "100 y más") x sex; rebuilt by `scripts/fetch_ine.py --table single_age` |
| `cores/cores_consumos_pp.xlsx` | 1996-2026, monthly | CORES consumption of petroleum products in tonnes. The `Gasolinas` and `Gasoleos` sheets carry the automotive subtotals, whose sum is national road fuel, complete monthly from January 1996. Each subtotal is the sum of the product columns before it (biofuels included, checked to one part in a million) and each sheet gives the mass share of biofuel. It measures fuel sold, not distance |
| `transportes/peaje_trafico_total.xls` | 1990-2026, monthly | Boletín Estadístico Online: average daily intensity and vehicle-kilometres on the whole state toll-motorway network. The `LONGITUD` column records the network length in service, which falls as concessions expire, so the series is a traffic index, never a denominator |
| `transportes/anuario_carreteras_2023.pdf` | 2004-2023, annual | Anuario Estadístico 2023, roads chapter. Table 1.2.14: vehicle-kilometres and the share of heavy vehicles by type of road (toll motorways; autovías and free motorways; multi-lane; conventional) on the State, regional and provincial interurban networks, parsed by `io_traffic.read_road_traffic`, which requires the four types to add up to the published total (one part in ten thousand: 2009 is 0.002% short). Comparable from 2008 (new road inventory). Municipal interurban roads, up to a tenth of traffic by the Ministry's estimate, are not included, and 8.7%-11.2% of interurban deaths in the crash microdata (2016-2024) are on roads of municipal, other or unspecified owners |
| `transportes/movilia_2006.xls` | 2006 | MOVILIA 2006 daily-mobility tables: trips by main mode x sex x age (the mode is "coche o moto" with no driver/passenger split), and car trips and their duration on a weekend against a working day, by province |
| `transportes/movilia_2007.xls` | 2007 | MOVILIA 2007 long-distance tables: journeys over 50 km by age and mode (tables 13 and 18); journeys of drivers and passengers, not kilometres |

## Regional crash microdata (`catalonia/`, `barcelona/2025/`)

The regional files arrived under generic download names, kept in the manifest's `downloaded_as`
column; each was identified by its columns and filed under a descriptive name
(`src/dgt_stats/microdata/sources.py`). No record of one is linked to a record of another or of
the DGT microdata.

| File (downloaded as) | Coverage | Content |
|---|---|---|
| `catalonia/accidents_morts_ferits_greus_catalunya_2010_2023.csv` (`export.csv`) | 2010-2023, Catalonia | one row per crash with at least one death or serious injury, with place, road, conditions, victims and units involved; no slight-injury crashes and no identifier |
| `barcelona/2025/accidents_gu_bcn_2025.csv` (`download.csv`) | 2025, Barcelona city | one row per crash the Guàrdia Urbana attended: place, time, victim counts by severity and vehicles involved |
| `barcelona/2025/accidents_persones_gu_bcn_2025.csv` (`download(1).csv`) | 2025 | the people involved (drivers, passengers, pedestrians, injured or not) with age, sex, role, vehicle type and victimisation |
| `barcelona/2025/accidents_vehicles_gu_bcn_2025.csv` (`download(2).csv`) | 2025 | vehicle records (type, make, model, colour, licence class and age of licence); not shown to be one row per vehicle and with no vehicle key, so only the presence of a vehicle type in a crash is used |
| `barcelona/2025/accidents_causes_mediates_gu_bcn_2025.csv` (`download(3).csv`) | 2025 | mediate causes recorded for each crash (alcohol, speed, drugs, road surface, signals, weather, objects or animals); a single blank row means none was recorded |
| `barcelona/2025/accidents_causa_conductor_gu_bcn_2025.csv` (`download(4).csv`) | 2025 | driver-related causes recorded for each crash, with no key to the person or vehicle concerned |
| `barcelona/2025/accidents_tipus_gu_bcn_2025.csv` (`download(5).csv`) | 2025 | the type of each crash (collision, run-over, fall...), one row per crash; "Encalç", the Catalan file's term for a rear-end collision, marks almost only serious crashes |

The Catalan file holds no slight-injury crashes, so it describes severity among serious crashes,
not crash frequency; its speed field is the road's limit, not a driving speed.

## Working-day mobility survey (`emef/`)

Public-use microdata of the EMEF (Enquesta de mobilitat en dia feiner), the annual survey of the
working-day (Monday to Friday, not a public holiday) mobility of residents aged 16 and over in the
planning area of the ATM of the Barcelona area. Non-residents' trips, weekends and holidays are
outside its scope, and the trips of people who make eight or more work trips a day (drivers,
couriers, sales staff) are excluded apart from their journey to work. Every year has a respondent
file with one row per respondent, those who made no trip on the reference day included, and a trip
file whose `ID` values all appear in the respondent file.

| File (downloaded as) | Coverage | Content |
|---|---|---|
| `emef/<year>/emef_<year>_trips.csv` (`Microdades_OMC_Despl_EMEF<year>.csv` for 2014-2017 and 2024; `Microdades Ús públic_EMEF<year>_Desplaçaments.csv` for 2018-2023) | 2014-2024 | one row per trip on the reference day, keyed by respondent `ID` and trip order `ORDRE` |
| `emef/<year>/emef_<year>_persons.csv` (`..._Indivi_...` or `..._Individus.csv` for 2014-2017, 2021, 2022 and 2024; `..._Opinió.csv` for 2018-2020 and 2023) | 2014-2024 | one row per respondent, with sex, age group, residence and the weights `PESAIX` (expansion) and `PESMOS` (sample) |
| `emef/<year>/emef_<year>_dictionary.xlsx` | one per year | variable list, record layout and value labels of both files |
| `emef/2024/emef_2024_executive_summary.pdf` (`emef_2024_resum_executiu.pdf`, from recam.amb.cat) | 2024 | the executive summary: its technical sheet (sampling, calibration, fieldwork dates) and the published distance benchmarks the trip-distance estimates are checked against, typed into `emef/distance.py` |
| `emef/docs/emef_methodology_2003_2018.pdf` (`EMEF_2019_Informe_Metodologia_EMEF_2003-2018.pdf`, IERMB, July 2020) | 2003-2018 | Table 5 (page 19): the sampling strata by year, with 65-74 and 75 and over separate from 2008 to 2016 (`emef/variables.py`), and its note 5 on the difficulty of obtaining responses at 75 and over |
| `idescat/idescat_census_2024_activity_release.html` (Idescat release of 8 July 2026) | 1 January 2024, Catalonia | the census count of employed people aged 65 and over in Catalonia (67,143), typed into `emef/exposure.py` to benchmark the survey's employed share at 65 and over |

The public files merge 65-74 and 75 and over; no age group finer than 65 and over exists in them.

## Madrid household survey (`crtm/edm2018/`)

| File | Coverage | Content |
|---|---|---|
| `edm2018_individuos.csv` | 2018 | every respondent: household and person id, sex, exact age, licence, activity, reference weekday (Monday-Thursday), reason for not travelling, person weight |
| `edm2018_viajes_conductor.csv` | 2018 | every trip whose main mode is car driver (private, company or rental car), with its distance and trip weight |

Extracts of the CRTM's `EDM2018INDIVIDUOS.xlsx` and `EDM2018VIAJES.xlsx` written by
`scripts/fetch_edm.py`.

## Thematic report (`dgt/reports/`)

`dgt_factor_velocidad_2023.pdf` covers 2014-2023 without Cataluña and País Vasco. Sixty-one of its
sixty-four tables (all but the three year-on-year variation tables) are transcribed by
`io_reports.py`. Its scope totals are reconciled against the microdata by year and zone
(`speed_report_scope` in `validation.csv`), not by road type; none of its breakdowns is
republished.

## Not available

- National vehicle-level and person-level crash records (driver age and sex, alcohol and drug
  tests, speed, seat belt, helmet): DGT does not publish them for download; a request to DGT's
  Observatorio Nacional de Seguridad Vial would be needed. The Catalan file has no person or
  vehicle rows; the Barcelona person table covers one city in 2025 and its vehicle records have no
  vehicle key.
- Road geometry, traffic volumes and section-level speeds; crash coordinates in the national
  records (the Barcelona crash table has them, the Catalan file gives road and kilometre point);
  casualties by the speed limit of the road in the national records.
- Calendar days in the DGT microdata, so campaign and policy evaluation is possible by month only.
- Vehicle-kilometres by vehicle type before 2022, and monthly vehicle-kilometres on all Spanish
  roads. The two monthly series are proxies with known limits: CORES measures fuel sold, not
  distance, and its petrol/diesel mix shifts over the 2000s; the toll-motorway series measures
  distance directly but on a network whose length changes as concessions expire. The Ministry's
  annual table 1.2.14 covers interurban kilometres only, without municipal roads, and splits them
  into heavy vehicles and the rest.
- Distance driven by the driver's age for Spain as a whole. Two regional travel surveys measure it
  from their microdata: the EMEF for the Barcelona area (working days, age groups ending at 65+)
  and EDM2018 for Madrid (weekdays, exact age). MOVILIA counts trips and travel time, not
  kilometres, and does not separate drivers from passengers.
- Car-driving distance at 75 and over in the EMEF: the public files merge 65-74 and 75+.
