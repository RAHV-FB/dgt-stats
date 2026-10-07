# Data inventory and audit

Audit date: 2026-09-18, extended on 19, 20 and 22 September 2026 for the files added later, the
coding breaks found in review and the exposure sources added then, and in October 2026 for the
Ministry's kilometres by type of road, the move to one raw folder per publisher and the regional
crash files (section 1 F). Every national source file was opened and profiled with Python
(`openpyxl`, `pandas`, `pymupdf`). This document records what each file contains, how the files
group together, what was verified, and what must be handled before analysis. It complements the
source register in [`data_sources.md`](data_sources.md); what each dataset may be used for, and
what it may never be joined to, is in [`DATA_CONTRACT.md`](DATA_CONTRACT.md). Checksums, sizes,
source URLs and download names for every file are in
[`data/raw/manifest.csv`](../data/raw/manifest.csv). The complete machine-generated inventory of
every raw file (encoding, delimiter, rows, columns, unit of observation, coverage, duplicates) is
[`RAW_FILE_INVENTORY.md`](RAW_FILE_INVENTORY.md), written by `python scripts/microdata.py
inventory`; this document is the hand-written audit beside it and does not repeat its counts.

## 1. Files by category

All raw files live under `data/raw/<source>/`, one folder per publisher: `dgt/`, `ine/`,
`transportes/`, `cores/`, `comunidad_madrid/`, `catalonia/` and `barcelona/2025/`, plus
`compiled/` for registers typed by hand ([`data/README.md`](../data/README.md)). This section
groups them by role. Each table gives a file relative to the folder in its section heading, or to
`data/raw/` where the column says so.

### A. Crash microdata (`data/raw/dgt/microdata/`, one row per injury crash)

| File | Year | Rows | Columns | Original DGT name |
|---|---:|---:|---:|---|
| `accidentes_2016.xlsx` | 2016 | 102,362 | 72 | `Tabla-Accidentes-2016.xlsx` |
| `accidentes_2017.xlsx` | 2017 | 102,233 | 72 | `Tabla-Accidentes-2017.xlsx` |
| `accidentes_2018.xlsx` | 2018 | 102,299 | 72 | `Tabla-Accidentes-2018.xlsx` |
| `accidentes_2019.xlsx` | 2019 | 104,080 | 72 | `Tabla-Accidentes-2019.xlsx` |
| `accidentes_2020.xlsx` | 2020 | 72,959 | 74 | `TABLA_ACCIDENTES_20.xlsx` |
| `accidentes_2021.xlsx` | 2021 | 89,862 | 73 | `TABLA_ACCIDENTES_21.xlsx` |
| `accidentes_2022.xlsx` | 2022 | 97,916 | 73 | `TABLA_ACCIDENTES_22.xlsx` |
| `accidentes_2023.xlsx` | 2023 | 101,306 | 73 | `TABLA_ACCIDENTES_23.XLSX` |
| `accidentes_2024.xlsx` | 2024 | 101,996 | 73 | `TABLA_ACCIDENTES_24.XLSX` |
| `diccionario.xlsx` | all | 38 sheets, 33 of them code lists | n/a | `Diccionario_Tabla_Accidentes.xlsx` |
| `metadata_2024.rdf.xml` | 2024 | DCAT record | n/a | datos.gob.es catalogue export |

- Source: Registro Nacional de Víctimas de Accidentes de Tráfico (Orden INT/2223/2014), published on
  DGT en Cifras under "Ficheros de microdatos de accidentes con víctimas". Licence: datos.gob.es aviso
  legal. The 2020–2023 files are served from the `24h/` directory of dgt.es, the 2016–2019 and 2024
  files from `publicaciones/Ficheros_microdatos_de_accidentalidad_con_victimas/` (see manifest).
- **DGT publishes only the crash-level table.** The download pages for 2019 through 2024 each list one
  accident workbook and the dictionary; there is no public vehicle-level or person-level file. Those
  tables exist in the register and are available on request to DGT's Observatorio Nacional de Seguridad
  Vial, or in aggregated form through the "Panel de datos de siniestralidad" application.
- Each workbook has two sheets: `ACCIDENTES_YY` (data) and a description sheet. The description sheet in
  the 2023 and 2024 files is a stale copy of the 2022 one (it names `TABLA_ACCIDENTES_22.xlsx` and
  97,916 records), so it must not be used for validation.

### B. Official aggregate statistics (`data/raw/dgt/tables/`)

| File | Coverage | Content | Original name |
|---|---|---|---|
| `tablas_estadisticas_2024.xlsx` | 2024 | 39 tables: crashes and victims by province, autonomous community, month, weekday, hour, road type, lighting, vehicle type, driver age/sex/licence seniority, driver infractions, vehicle age | `Accidentes-con-victimas-Tablas-estadisticas-2024.xlsx` |
| `series_historicas_2024.xlsx` | 1993–2024 | 69 sheets of annual series: crashes, victims (24 h and 30 day), by month, province, sex, age, pedestrians, driver deaths by vehicle type, rates per fleet and population | `Series-Historicas-Anuario-Accidentes-2024.xlsx` |
| `tablas_estadisticas_{2020..2023}.xlsx` | 2020–2023 | Same 39–40 tables as 2024, one workbook per year, same sheet names (`TABLA 4.1.1.I`, `TABLA 4.2.U`, ...) | `Accidentes_con_victimas_Tablas_estadisticas_YYYY.xlsx` |
| `chapters/{2014..2019}/grupo_{1..8}.xls(x)` | 2014–2019 | The same yearbook split into eight chapter workbooks; chapter 4 holds driver victims by age and sex (4.1.1), drivers involved by age, sex and condition (4.2) and licence seniority (4.4), interurban and urban. 2014 is `.xls` (read with `xlrd`), 2015 uses upper-case titles without the year, 2016+ match the modern layout | `Grupo-N.-...-YYYY.xls(x)` |

A second copy of the series workbook (`...2024(1).xlsx`, byte-identical, same MD5) was removed.

### C. Exposure and denominators (several publisher folders)

| File (under `data/raw/`) | Coverage | Content | Original name |
|---|---|---|---|
| `dgt/census/censo_conductores_2023.txt` | 2023 | 8,405 rows, pipe-delimited: province × sex × licence class × licence year → drivers. Total 27,914,572 drivers | `censo_prov_sexo_clase_antig_2023.txt` |
| `dgt/census/censo_conductores_2024.txt` | 2024 | 9,227 rows, total 28,142,470 drivers | `censo_prov_sexo_clase_antig_2024.txt` |
| `dgt/census/censo_conductores_2025.txt` | 2025 | 9,224 rows, total 28,472,636 drivers, UTF-8 BOM | `censo_prov_sexo_clase_antig_2025.txt` |
| `dgt/census/censo_tablas_2025.xlsx` | 2025 | 10 published tables: drivers by province/community of residence and first issue, by licence class × age, by licence class × year of issue, split by sex | `Censo-de-conductores-Tablas-estadisticas-2025.xlsx` |
| `dgt/census/censo_conductores_edad_{2023,2024,2025}.txt` | 2023–2025 | Pipe-delimited: province × sex × age band (15–17, 18–20, 21–24, then five-year bands to 70–74, "Más de 74", "Se desconoce") → permits, licences and permits by class, including `NUM_PERMISOS_B` (B-permit holders, used for the 2024 owner-age check). 2023 and 2024 are Latin-1, 2025 is UTF-8 with BOM | `censo_prov_sexo_clase_edad_YYYY.txt` |
| `dgt/census/censo_tablas_{2014..2024}.xlsx` | 2014–2024 | Published driver-census tables; 2014–2023 include `P_6_1_1_7` (drivers by licence class × age band, plus men/women sheets), 2024 has only the province tables (age comes from the text file) | `Censo-de-conductores-Anuario-YYYY.xlsx` / `...Tablas-estadisticas-YYYY.xlsx` |
| `dgt/km_itv_2022/km_recorridos_estimados_2022.xlsx` | 2022 | Estimated annual km per vehicle by vehicle type × Euro class × age band × engine size × (payload) × fuel; 6 sheets, 8,254 strata | `Km_recorridos_anuales_estimados.xlsx` (from `KM_ITV_2022.zip`) |
| `dgt/km_itv_2022/media_km_antiguedad_tipo_2022.xlsx` | 2022 | Mean annual km and fleet size by vehicle type (7) × age band (5) | `Media_km_recorridos_ antiguedad_tipo de vehículo.xlsx` |
| `dgt/km_itv_2022/metodologia.pdf` | 2014–2023 ITV | Methodology: gamma-regression (LightGBM) imputation of annualised odometer readings; explains 19–45% of variance per vehicle, valid only for aggregates. Documentation; not read by code | `KM_Recorridos_ITV_Parque.pdf` |
| `dgt/km_itv_2024/km_edad_propietario_2024.xlsx` | 2024 | 115 rows: vehicle category (8) × owner age band (18–20, 21–24, then five-year bands to 70–74, 75+, plus "Vehículo a nombre de empresa") → vehicles, total annual km, mean annual km. The only file in the repository that gives distance driven by a person's age for the whole circulating fleet (the 2008 INE household survey below does so for a sample). The age is the **registered owner's**, not the driver's, and it does not hold as a stand-in for the driver's at either end (section 3) | `KM_Edad_Propietario.xlsx` (from `KM_Recorridos_2024_Material_Adicional.zip`) |
| `dgt/km_itv_2024/km_medios_tipo_2024.xlsx` | 2022–2024 | The same release's table 6: vehicles and mean annual km by category, with a 2024 detail sheet. Used to check the owner-age table against the published fleet and, beside the 2022 table, to show that DGT's two kilometre releases cannot be chained (`risk_km_crosscheck.csv`) | `TAB_06-KM_Medios.xlsx` (same zip) |
| `cores/cores_consumos_pp.xlsx` | 1996–2026 | CORES monthly consumption of petroleum products, tonnes, 8 sheets. The `Gasolinas` and `Gasoleos` sheets carry `Subtotal gasolinas auto` and `Subtotal gasóleos auto`; their sum is national road-fuel consumption, complete monthly from January 1996. Each subtotal is the sum of the product columns before it (bioethanol, biodiesel and blends included), and each sheet gives the mass share of biofuel in its subtotal (`% biocomb. en gasolinas`, `% biocomb. en gasóleos`) | `consumos-pp.xlsx` |
| `transportes/peaje_trafico_total.xls` | 1990–2026 | Ministerio de Transportes, Boletín Estadístico Online: annual and monthly average daily intensity and vehicle-kilometres on the whole state toll-motorway network. Complete monthly from January 1990; the `LONGITUD` column records the network length in service, which falls as concessions expire. A traffic index and a covariate, never a denominator (section 3) | `06010000.XLS` |
| `transportes/anuario_carreteras_2023.pdf` | 2004–2023 | Ministerio de Transportes, Anuario Estadístico 2023, roads chapter (13 pages). Table 1.2.14: vehicle-kilometres and the share of heavy vehicles by type of road (toll motorways; autovías and free motorways; multi-lane; conventional) on the State, regional and provincial interurban networks; see section 3 | `carreteras_2023.pdf` |
| `ine/ine_poblacion_provincias_edad_sexo.csv` | 2002–2025 | INE table 56947 extract: residents by province × five-year age group × sex, 1 January and 1 July; 149,460 rows, rebuilt by `scripts/fetch_ine.py` | INE CSV download |
| `transportes/movilia_2006.xls` | 2006 | MOVILIA 2006 daily-mobility tables (168 sheets). Tables 63–64 give trips by main mode × sex × age; the mode is "coche o moto" with **no driver/passenger split**, so it yields a car-travel intensity curve by age, not a driver share. Not read by any code: the sex travel bracket built from it was withdrawn | `Movilia2006.xls` |
| `transportes/movilia_2007.xls` | 2007 | MOVILIA 2007 long-distance tables (134 sheets): trips over 50 km by mode, purpose, age and sex. Not read by any code | `Movilia2007.xls` |
| `comunidad_madrid/movilia_madrid/movilia07t0{1..5}.xls` | 2006/07 | Madrid statistical office extract of MOVILIA daily mobility (Madrid and Spain); no driver status by age. Not read by any code | `movilia07t0N.xls` |
| `ine/ine_ecepov_2021_55378.xlsx` | 2021 | INE ECEPOV table 55378: persons 16+ by main vehicle used to commute to work or study, by sex and age group; commuters only. Not read by any code | INE table export |
| `ine/ine_ehma_2008_1001{6,9}.csv` | 2008 | INE household survey: mean annual km per household vehicle by sex, age and nationality of the reference person, by fuel (10016) and by vehicle age (10019). Not read by any code | INE px CSV export |

The zip archives were extracted in place and the archives themselves dropped. The survey register
`driving_activity_by_age.csv` now sits in `compiled/` (section E).

### D. Thematic reports (`data/raw/dgt/reports/`, context and definitions)

| File | Pages | Content | Original name |
|---|---:|---|---|
| `dgt_factor_velocidad_2023.pdf` | 61 | Speed factor 2014–2023, 30-day data, **excludes Cataluña and País Vasco**. Speed present in 7% of injury crashes in 2023 (3% urban, 14% interurban); profiles by road type, speed limit, vehicle, driver | `INF_TEMA_4_Factor-Velocidad_v5_FINAL.pdf` |
| `dgt_personas_mayores_2023.pdf` | 82 | Road users aged 65+ in 2023: 26% of all deaths; 47.8 deaths per million vs 34.4 for under-65; collision matrices; profiles | `INF_TEMA_8_PersonasMayores_v4_FINAL_nipo.pdf` |
| `Anuario-estadistico-de-accidentes-{2015..2019}-fe-de-erratas.pdf` | n/a | DGT errata sheets for the 2015–2019 yearbooks; check before reconciling those years | same |
| `dgt_semana_santa_2026.pdf` | 45 | Easter 2026 interurban fatal crashes, **24-hour provisional counts**: 28 fatal crashes, 30 deaths, 17.3 million long-distance trips; series 1995–2026 | `INF_SEMANASANTA_2026_v8_FINAL.pdf` |

Only the speed report is read by code (`io_reports.py`), for the speed comparison and the factor
tables (section 4); no code reads the other reports.

The ESRA reports are not archived under `data/raw/` (Vias institute offers no reproduction licence;
see the reuse terms in `data_sources.md`). They were consulted online: the ESRA3 (2023) Spain fact
sheet and main report (935 weighted respondents, 75.9 % drive at least a few days a month, main
report Table 6) at `https://www.esranet.eu/storage/minisites/esra2023countryfactsheetspain.pdf` and
`https://www.esranet.eu/storage/minisites/esra3-main-report.pdf`, and the ESRA-123 dashboard
(`https://www.esranet.eu/en/esra-123-dashboard/`) for the 2018 share (80.2 %, weighted n 906). The
two values are typed into `compiled/driving_activity_by_age.csv` with their URLs; no code reads
that file.

### E. Registers typed by hand (`data/raw/compiled/`, not read by any code)

| File | Rows | Content | Original name |
|---|---:|---|---|
| `driving_activity_by_age.csv` | 5 | Survey register, 2008, 2018 and 2023: ESRA2/ESRA3 Spain share of adults driving a car at least a few days a month (national only), Fundación MAPFRE driving days per week among drivers 65+ (Madrid). Its reader (`io_activity.py`) was deleted; no code reads it | typed from the reports |
| `evidence/simulator_parameters.csv` | 33 | Register of the published values the speed-law simulator used: Power Model exponents, the response of mean speed to a new limit, car speeds measured in Spain in 2022, the legal limits and DGT's values of a casualty, each with its source, its place in the source, the URL and a verbatim quote. The simulator was **withdrawn**; no code reads the file (section 3) | compiled by this project |
| `evidence/factor_parameters.csv` | 112 | Register of the published values the distraction and alcohol-and-drug models and the enforcement comparison used: DGT's police record of factors in fatal crashes, the toxicology of killed drivers, measured crash risks, roadside prevalence and 17 published evaluations of enforcement, each with its source, its place in the source, the URL and a verbatim quote. Those analyses were **withdrawn**; no code reads the file | compiled by this project |

These files hold values typed from publications, not observations, and no result of the project
rests on them ([`DATA_CONTRACT.md`](DATA_CONTRACT.md)).

### F. Regional crash microdata (`data/raw/catalonia/`, `data/raw/barcelona/2025/`, added October 2026)

| File (under `data/raw/`) | Coverage | Unit of observation | Downloaded as |
|---|---|---|---|
| `catalonia/accidents_morts_ferits_greus_catalunya_2010_2023.csv` | 2010–2023, Catalonia | one crash with at least one death or serious injury (no source identifier) | `export.csv` |
| `barcelona/2025/accidents_gu_bcn_2025.csv` | 2025, Barcelona city | one crash (`Numero_expedient`): place, time, victims by severity, vehicles involved | `download.csv` |
| `barcelona/2025/accidents_persones_gu_bcn_2025.csv` | 2025, Barcelona city | one person record in a crash: age, sex, role, associated vehicle type, victimisation | `download(1).csv` |
| `barcelona/2025/accidents_vehicles_gu_bcn_2025.csv` | 2025, Barcelona city | one vehicle record (not shown to be one vehicle) | `download(2).csv` |
| `barcelona/2025/accidents_causes_mediates_gu_bcn_2025.csv` | 2025, Barcelona city | one recorded mediate cause of a crash | `download(3).csv` |
| `barcelona/2025/accidents_causa_conductor_gu_bcn_2025.csv` | 2025, Barcelona city | one recorded driver-related cause of a crash (no person or vehicle key) | `download(4).csv` |
| `barcelona/2025/accidents_tipus_gu_bcn_2025.csv` | 2025, Barcelona city | one crash: the type of crash | `download(5).csv` |

- Publishers: Servei Català de Trànsit (the Catalan file, an export) and the Ajuntament de
  Barcelona's Guàrdia Urbana (six tables sharing `Numero_expedient`). The source URL was not
  recorded at download; the files were renamed to say what they hold and the manifest keeps the
  browser download name in `downloaded_as`.
- Roles (`src/dgt_stats/layers.py`): the Catalan file is the crash microdata layer (the
  crash-severity model and its temporal and geographic validation); the Barcelona files are the
  rich microdata layer (crash and person analysis, the person-severity model). Neither is merged
  with the other or linked to DGT records; they meet the national layer only at province and year
  aggregates and in held-out transfer tests, which create no observations.
- The Catalan file holds no slight-injury crashes, so it describes severity among serious crashes,
  not crash frequency; its speed field is the road's limit, not a driving speed.
- Rows, columns and encodings are in [`RAW_FILE_INVENTORY.md`](RAW_FILE_INVENTORY.md); keys,
  cardinality and placeholders in [`DATA_QUALITY_MICRODATA.md`](DATA_QUALITY_MICRODATA.md); the
  audit of the Barcelona vehicle table, whose rows are not shown to be one per vehicle, in
  [`BARCELONA_VEHICLE_AUDIT.md`](BARCELONA_VEHICLE_AUDIT.md). Sections 2 and 3 below cover the
  national files only.

## 2. DGT crash microdata: schema and content

The 72–74 columns fall into six blocks. There are **no vehicle-level or person-level attributes**: no driver
age or sex, no alcohol or drug test result, no speed infraction, no seat-belt or helmet use, no vehicle
age, no coordinates, and no day of month.

| Block | Columns | Notes |
|---|---|---|
| Identity and time | `ID_ACCIDENTE` (2021+) / `SECUENCIAL` (2016–2020), `ANYO`, `MES`, `DIA_SEMANA`, `HORA` | Hour 0–23; no calendar day, so specific dates (holidays, campaign start dates) cannot be recovered |
| Location | `COD_PROVINCIA`, `COD_MUNICIPIO`, `ISLA`, `ZONA`, `ZONA_AGRUPADA`, `CARRETERA`, `KM`, `SENTIDO_1F`, `TITULARIDAD_VIA`, `TIPO_VIA` | Municipality is `00000` for towns under 5,000 inhabitants (11–13% of rows a year, `missingness_by_year.csv`). Road name is "No inventariada" and km is null for roughly 62–65% of rows (urban crashes) |
| Crash type and severity | `TIPO_ACCIDENTE` (20 codes), `TOTAL_MU24H/HG24H/HL24H/VICTIMAS_24H`, `TOTAL_MU30DF/HG30DF/HL30DF/VICTIMAS_30DF`, `TOTAL_VEHICULOS` | Both 24-hour and 30-day counts present, so definitions can be kept separate |
| Fatalities by road-user type | `TOT_PEAT/BICI/CICLO/MOTO/TUR/FURG/CAM_MENOS3500/CAM_MAS3500/BUS/OTRO/SINESPECIF_MU24H` and `_MU30DF` | Deaths only; involvement of a vehicle type in a crash is **not** recorded. `TOT_VMP_MU30DF` (personal mobility vehicles) exists from 2020; `TOT_VMP_MU24H` only in 2020 |
| Junction and priority | `NUDO`, `NUDO_INFO`, `CARRETERA_CRUCE`, 13 `PRIORI_*` flags | `PRIORI_*` are 999 "Sin especificar" for 59–69% of rows a year (`missingness_by_year.csv`), including many junction crashes |
| Conditions | `CONDICION_NIVEL_CIRCULA`, `_FIRME`, `_ILUMINACION`, `_METEO`, `_NIEBLA`, `_VIENTO`, `VISIB_RESTRINGIDA_POR`, `ACERA`, `TRAZADO_PLANTA` | `ACERA` and `TRAZADO_PLANTA` are 998 "No aplica" for 61–88% of rows (`missingness_by_year.csv`); fog and wind are null when absent. The dictionary's `.` code for "no strong wind" never occurs; strong wind is flagged in between 0.2% and 1.2% of crashes (1.1% in 2017, 1.2% in 2018, 0.5% in 2020, 0.2–0.3% in the other years) except 2021, where it is flagged in 24.6% (22,090 rows), a reporting artefact to keep out of trend comparisons |

### Missing-value states that must stay distinct

| State | Encoding in file | Example |
|---|---|---|
| Not specified / not reported | `999` | weather, priority regulation, traffic level |
| Not applicable | `998` | sidewalk on interurban road, alignment on urban street |
| Explicitly unknown | a named code: `6` in traffic level, `9` in surface, `7` in weather, `18` in visibility, `4` in alignment and direction | police attended but could not determine |
| Empty | `None` | island (usually not an island province, but also unrecorded inside them), km (not inventoried), fog and wind (absent), junction detail (not at a junction) |

Missingness also depends on the province. Road alignment "unknown" is recorded for 78,990 crashes
in 2016–2024, 75,624 of them in the four Catalan provinces (`q3_recording_regime.csv`), and most
candidate fields have unrecorded shares that differ between provinces by more than the audit's
limit ([`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md), check 6).

## 3. Verification results

### Microdata reconciles exactly with the published yearbook

Row counts and 30-day victim sums of each yearly file were compared with `series_historicas_2024.xlsx`
sheets `Acc_Vict` and `Vict_I-U`. All nine years match to the unit.

| Year | Crashes (file rows) | Deaths 30 d | Hospitalised 30 d | Non-hospitalised 30 d | Deaths 24 h |
|---:|---:|---:|---:|---:|---:|
| 2016 | 102,362 | 1,810 | 9,755 | 130,635 | 1,551 |
| 2017 | 102,233 | 1,830 | 9,546 | 129,616 | 1,590 |
| 2018 | 102,299 | 1,806 | 8,935 | 129,674 | 1,556 |
| 2019 | 104,080 | 1,755 | 8,613 | 130,745 | 1,496 |
| 2020 | 72,959 | 1,370 | 6,681 | 87,881 | 1,187 |
| 2021 | 89,862 | 1,533 | 7,784 | 110,378 | 1,311 |
| 2022 | 97,916 | 1,746 | 8,502 | 119,328 | 1,504 |
| 2023 | 101,306 | 1,806 | 9,265 | 124,266 | 1,539 |
| 2024 | 101,996 | 1,785 | 9,561 | 125,084 | 1,522 |

Additional checks on 2024: province totals in `TABLA 1.1` and monthly totals in `TABLA 3.1` sum to the same
101,996 crashes and 1,785 deaths. `TOTAL_VEHICULOS` sums to 176,332 versus 176,398 implied by `TABLA 2.3`
(190,508 units minus 14,110 pedestrians), a difference of 66; the 2023 table is 48 vehicles above the
microdata in the same way and 2020–2022 are exact, so the reconciliation check (`table_2_3_vehicles`)
accepts those two years within its 0.1% tolerance: the microdata carry no vehicle-level rows that could
locate the missing units.

No duplicate identifiers were found in any year.

### Schema drift between years

| Change | Years | Handling |
|---|---|---|
| `SECUENCIAL` renamed to `ID_ACCIDENTE` | 2021+ | rename on load; ids restart at 1 each year, so the key must be `(ANYO, ID_ACCIDENTE)` |
| `TOT_VMP_MU30DF` added | 2020+ | add as null for 2016–2019 (VMP deaths were counted under "Otro") |
| `TOT_VMP_MU24H` present | 2020 only | drop or keep as null elsewhere; 24-hour VMP deaths are not needed |
| `TIPO_VIA = 14` ("Otro") share rises from 2.9% to 17.2%, and `TITULARIDAD_VIA = 5` ("Otra") from 1.6% to 22.0%, while `TIPO_VIA = 9` ("Calle") falls from 59.9% to 47.5% | 2016 → 2024 | a coding change in the four Catalan provinces: in 2024 they record no crash as a street (code 9) and most as code 14, and from 2023 most of their crashes carry owner code 5, while both shares stay flat in the other provinces. Road-type trends must use a collapsed grouping (motorway / dual carriageway / conventional / urban / other) and be checked year by year; the street / other split is not comparable across 2023–2024. `TITULARIDAD_VIA = 5` is 7.9% in 2021, when 14.8% of rows carry 999 instead, and back near its earlier level in 2022, so its jump to 22% dates from 2023 |
| `TIPO_VIA = 5` ("Carretera Convencional de doble calzada") falls from 6.8% to 1.8% of crashes between 2020 and 2021 while `TIPO_VIA = 6` ("Carretera Convencional de calzada única") rises from 17.9% to 21.4% and their sum stays near 23%; `TIPO_VIA = 1` ("Autopista de peaje") falls from about 2% to 0.4% in 2022 and 2024 while `TIPO_VIA = 2` ("Autopista libre") rises to 3.3%, with 2023 back at the earlier split and the sum stable near 3.7% | 2021, 2022, 2024 | interurban coding changes. The dual carriageway / conventional split is not comparable across 2020–2021, and the collapsed grouping does not fix it because `road_group` puts 5 in dual carriageway and 6 in conventional; the 2019 speed-limit study (computed but not published, as it fails its own placebo) therefore builds its two groups from the raw codes (5 and 6 against 1, 2 and 3, `policy.py`) so that the recoding stays inside the treated group, and the severity regressions (`features.py`) and `road_class.py` take conventional roads from the road-type code itself, codes 4 to 6 together, so the recoding stays inside one level. The toll/free motorway distinction is unusable, but codes 1 and 2 are pooled in every use (as `motorway` in `road_group` and in the severity regressions, as autopistas in `road_class.py`), so no group splits them |
| `ZONA = 4` ("Autopista o autovía urbana") falls from 0.6–0.7% of crashes in 2016–2018 to 0.1% or less from 2019 (0.4% in 2021) | 2019+ | the code is almost unused from 2019 (the grouped zone is unaffected); the zone level in the DGT severity regressions is mostly an early-period estimate, and the page says so |
| `NUDO = 1` (at a junction) rises from 38–40% of crashes in 2016–2022 to 43.5–43.7% in 2023–2024, and `NUDO_INFO = 999` from 0.5–0.7% (2.8% in 2018) to 14.5% in 2023 and 15.1% in 2024, 72% of those rows in Barcelona and 99% in the four Catalan provinces | 2023+ | a change in how the junction fields are recorded: the rise in `NUDO = 1` is in the four Catalan provinces only, and the share elsewhere stays flat; the junction term in the DGT severity regressions pools both regimes and the stability check is where it would show; never read the junction share as a trend across 2022–2023 |
| `VISIB_RESTRINGIDA_POR` and `CONDICION_NIVEL_CIRCULA` swap between their explicit unknown code (18 "Se desconoce", 6 "Se desconoce") and 999 in 2021, 2023 and 2024: `VISIB_RESTRINGIDA_POR = 999` is 0.3% / 0.1% / 0.0% in 2019 / 2020 / 2022 but 14.9% / 14.0% / 14.8% in 2021 / 2023 / 2024 while code 18 drops from 28–30% to 4.8–5.6%, and `VISIB_RESTRINGIDA_POR = 17` ("Otras restricciones") jumps from 0.4% to 8.7–8.9% in the same three years; `CONDICION_NIVEL_CIRCULA = 999` is 9.5–10.2% in 2019 / 2020 / 2022 but 32.2% / 32.8% / 34.0% in 2021 / 2023 / 2024 while code 6 drops from 29–31% to 6.9–7.7%. `TITULARIDAD_VIA = 999` appears in 2021 (14.8%, 13,280 rows, all urban `ZONA 3` / `TIPO_VIA 9`) and in 28 rows of 2024 (0.03%, also all `ZONA 3`) | 2021, 2023, 2024 | concentrated in the four Catalan provinces (Barcelona alone is 74–79% of the `VISIB_RESTRINGIDA_POR = 999` rows in those years, Barcelona, Girona, Lleida and Tarragona together 97–100%; for `CONDICION_NIVEL_CIRCULA = 999`, which has a 10% floor everywhere, the four provinces are 65–71%); 13,412 of the 22,090 rows flagged for strong wind in 2021 are also `VISIB_RESTRINGIDA_POR = 999` rows; missingness is province- and year-dependent, so never run complete-case trend comparisons and never read these fields as a trend |
| `CONDICION_METEO = 999` falls from 10.0–10.4% in 2016–2018 to 0.0–0.5% from 2019 on | 2018 → 2019 | missingness is year-dependent; never run complete-case trend comparisons |
| `VISIB_RESTRINGIDA_POR = 999` falls 32.3% → 10.2% while code 1 ("Buena visibilidad") rises 29.8% → 50.8%; `CONDICION_FIRME = 9` falls 5.5% → 2.7%; `CONDICION_NIEBLA` is flagged in 0.6% → 7.3% of crashes | 2016 → 2017 | 2016 is a separate reporting regime for the condition fields; treat 2016 as not comparable to later years |
| `KM` null share 62% in most years but 46–48% in 2019, 2020 and 2022, where a placeholder stands in the empty cell's place (1000 in 2019, 9999 in 2020 and 2022) | 2019, 2020, 2022 | counting the placeholder, the km post is unrecorded in about 62% of crashes in every year; `validate.missingness_profile` counts it as not observed, so the profile shows no improvement where there was none. Investigate before using km-post analyses |
| `ISLA = 0`, absent from the dictionary, appears from 2018 (7 rows) and grows to 605 rows in 2024, almost only in the Balearic and Canary provinces | 2018+ | treated as "island not specified" (`codes.UNDOCUMENTED_CODES`); an empty island field usually means the crash was not in an island province, but 11,430 empty rows are in the Balearic and Canary provinces themselves (376 in 2016 rising to 2,371 in 2024), so empty is not evidence of a mainland crash |
| `CONDICION_VIENTO = 1` share jumps from 0.2–1.2% in every other year (1.1–1.2% in 2017 and 2018) to 24.6% in 2021 only | 2021 | reporting artefact; exclude the wind flag from cross-year comparisons |

### Driver census text files

- Columns `COD_PROVINCIA | IND_SEXO | CLASE_PERMISO | DESC_ANTIG_PERMISO | NUM_CONDUCTORES`, values
  padded with spaces; sex coded `V`/`M`; 52 provinces; no duplicate keys.
- `CLASE_PERMISO` is the driver's single (highest) class: classes sum to the total number of drivers
  (about 28 million), whereas the 2025 workbook counts permits (27.6 million class B permits alone).
  The two sources answer different questions and must not be mixed.
- `DESC_ANTIG_PERMISO` is the year of issue from 2014 to the census year plus `Anterior_2014`.

### Kilometre estimates

- `dgt/km_itv_2022/media_km_antiguedad_tipo_2022.xlsx` gives, for 2022 only, fleet size and mean
  annual km for 7 vehicle types × 5 age bands. Multiplying the two gives total vehicle-kilometres by type, the vehicles
  page's denominator. The other vehicle-km in the repository are DGT's 2024 estimates by owner age
  and by category, the Ministry's measured interurban kilometres by type of road and the monthly
  toll-motorway series.
- The methodology report warns that predictions are valid in aggregate, not per vehicle, and that 2020 and
  2021 were excluded from model fitting.
- `dgt/km_itv_2024/km_edad_propietario_2024.xlsx` gives the same estimate broken down by the
  owner's age band. Summed over the bands it reproduces the release's own published fleet and
  kilometres per category to within 0.1 % for every category; the residual is the vehicles whose
  owner's age DGT could not classify, and the reader enforces a 0.5 % tolerance. Cars registered to
  companies are a row of their own (2,176,619 vehicles, 40.4 bn km in 2024) and carry no age.
- The age in that table is the registered owner's. Checked against B-permit holders by age
  (`NUM_PERMISOS_B` in the 2024 census text file), it does not hold as a stand-in for the driver's
  at either end: there are 0.46 cars per B-permit holder at 18–34 and 1.14 at 75+
  (`q7_owner_age_check.csv`). Per-km ratios by age are therefore published as ranges, from a
  transfer scenario to the published ratio, and deaths per driver involved, which need no
  kilometres, are given beside them ([`methodology.md`](methodology.md), section 7).

### Monthly traffic series

- CORES's automotive subtotals are complete monthly from January 1996 with no gaps. They measure
  fuel **sold**, not distance, and no series in the repository measures kilometres per tonne on all
  roads, so the fuel level cannot be checked against distance; `fuel_efficiency_sensitivity` only
  shows what hypothetical drifts would do to the per-fuel change and supports no conclusion. Of the
  monthly series, road fuel is the only one divided into deaths; petrol alone is shown beside
  deaths as a traffic index only. Seasonal peak: July.
- The reader checks that each automotive subtotal equals the sum of its product columns, bioethanol,
  biodiesel and blends included, to one part in a million in every month, so a tonne of road fuel
  counts the biofuel blended into it. CORES publishes the mass share of that biofuel: 6.6 % of road
  fuel in 2019, 7.8 % in 2023 and 7.1 % in 2024 (`longrun_fuel_bio.csv`). Biofuel carries less
  energy per tonne than the petrol and diesel it replaces, so a rise in its share lowers kilometres
  per tonne slightly; it cannot explain the rise in interurban kilometres per tonne of road fuel
  after 2019 (below).
- The toll-motorway series measures vehicle-kilometres and average daily intensity directly, but
  on a network whose length in service changes as concessions open and expire: 2,362 km at the end
  of 2019, 1,894 km in 2020, 1,416 km from 2022. Seasonal peak: August, sharper than CORES's. The
  seasonal profiles of road fuel and toll vehicle-km correlate at about 0.75 over 2000–2007. The
  series is never a denominator: the seasons page shows its intensity beside deaths as a traffic
  index, and the 2006 case study uses the intensity as a covariate.

### Measured interurban kilometres (added October 2026)

- `transportes/anuario_carreteras_2023.pdf`, the roads chapter of the Ministerio de Transportes'
  2023 statistical yearbook (13 pages, printed from the Ministry's own workbook in January 2025).
  Table 1.2.14 gives vehicle-kilometres on the State, regional and provincial interurban networks
  by type of road, 2004–2023, with the share of heavy vehicles on each, from each network's
  traffic-count plan. All twenty years parse; the four road types add up to the published total in
  every year but 2009, where the published row is 5 million vehicle-km (0.002 %) short, so the
  reader allows one part in ten thousand. Footnote 3 marks 2008 as not comparable with 2007 (new
  road inventory), so trend fits start in 2008. Footnote 1 puts the municipal interurban roads it
  leaves out at up to 10 % of traffic; in the crash microdata, 8.7 % to 11.2 % of interurban deaths
  in 2016–2024 are on roads whose owner is municipal, other or not specified (`TITULARIDAD_VIA` 4,
  5 or 999; `longrun_km_coverage.csv`). Toll motorway kilometres fall after 2019 and autovía
  kilometres rise while the toll network's length in service falls (above), so deaths per
  kilometre by road class pool the two, and the class rates count only crashes on roads of owners
  1 to 3 (State, autonomous community, provincial council), the networks the kilometres cover
  (`road_class.py`).
- Against road fuel, as a diagnostic only: kilometres on this network per tonne of all road fuel
  (`km_per_tonne` in `longrun_km_panel.csv`) grew 0.5 % a year over 2011–2019 (8,410 to 8,740 km
  per tonne), the span of the national per-fuel trend's last segment, and 1.9 % a year over
  2019–2023 (to 9,420). The ratio sets the interurban kilometres of the State, regional and
  provincial networks against fuel sold for all roads, so it is neither fuel economy nor a test of
  the fuel proxy: it also moves when traffic shifts between towns and interurban roads, and with
  the mix of freight.

### Evidence registers (added October 2026; not read, analyses withdrawn)

- `compiled/evidence/simulator_parameters.csv` (33 rows) and
  `compiled/evidence/factor_parameters.csv` (112 rows) hold values read in external publications,
  each with the table or page, the URL and a verbatim quote. They fed the speed-law simulator, the
  distraction and alcohol-and-drug models and the enforcement comparison, all three **withdrawn**
  because their results came from external-study coefficients: external studies may define
  variables or methods but never supply observations, coefficients or effect sizes
  ([`DATA_CONTRACT.md`](DATA_CONTRACT.md)). The files stay in `data/raw/`, which is never edited,
  as a record; no code reads them, and `tests/test_withdrawn.py` checks that none does.
- How they were compiled, kept as a record only: the Baseline speed figures were read in the
  report's tables 9–11 and 12a and, for autovías, the Annex 1 text introducing tables 12a–12c
  (p. 42); the Elvik exponents in table S1 of TØI report 1034/2009; the response curve in figure
  3.11.2 of the handbook; the limits in the consolidated text of the Reglamento General de
  Circulación and Real Decreto 970/2020 in the BOE; DGT's values in the two 2024 Universidad de
  Murcia reports; DGT's Tabla 50 counts in the 2022, 2023 and 2024 reports and the 2024 errata;
  the toxicology in the INTCF reports for 2023 and 2024; the DRUID risks in its final report; the
  distraction risks in Dingus et al. (2016); and the enforcement evaluations in the Norwegian
  handbook's chapters and the abstracts or full texts of four papers.

## 4. What the data can and cannot support

| Question | Feasible with current files? | Why |
|---|---|---|
| Crash trends, seasonality, weekday/hour patterns 1993–2024 | Yes | series workbook plus microdata |
| Severity of a crash given road type, zone, crash type, lighting, weather, surface, junction, alignment, in the DGT records | As an association only | the outcome and context variables are complete enough for a supporting association analysis ([`methodology.md`](methodology.md), section 13), with the recording levels flagged (`is_nuisance`) and a refit without the four Catalan provinces; the fields are recorded differently across provinces, so the DGT crash microdata do not train a predictive model ([`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md)) |
| Severity among crashes with a death or serious injury, Catalonia 2010–2023 | Yes, within Catalonia | the Catalan file trains the crash-severity model; it holds no slight-injury crashes, so it says nothing about crash frequency. How far each model's evidence reaches is in [`MODEL_DECISIONS.md`](MODEL_DECISIONS.md) and [`GENERALISABILITY.md`](GENERALISABILITY.md) |
| Person-level severity and recorded causes, Barcelona 2025 | Yes, for one city and one year | the Guàrdia Urbana crash, person and cause tables, which share `Numero_expedient`; a cause is what the police recorded, not an established cause |
| Province comparisons per resident, per licensed driver, per registered vehicle | Per resident and per licence holder, yes; per registered vehicle, only for Spain as a whole | INE residents and the census files give population and drivers by province; the fleet is only national in the series |
| Vulnerable road users (pedestrians, cyclists, moped riders, motorcyclists, VMP) fatality shares and trends | Yes | `TOT_*_MU30DF` columns |
| Older road users, per unit of driving | Partly, for 2024 | DGT's 2024 kilometre release gives km by the **registered owner's** age band; the driver tables give car-driver deaths and involvements by age. The owner's age does not hold as a stand-in for the driver's at either end (section 3), so per-km ratios are ranges; deaths per driver involved need no kilometres. Earlier years have no age-specific kilometres |
| Heavy vehicles and buses per vehicle-km | Only for 2022, and only occupant deaths | involvement not in microdata; km by vehicle type only for 2022 (the Ministry's table 1.2.14 gives only the share of heavy vehicles on interurban roads, as one group) |
| Alcohol, distraction, drugs, speed and illegal manoeuvres as recorded concurrent factors, year to year | Partly | DGT's speed report counts injury crashes with each factor, 2014–2023, for Spain without Cataluña and País Vasco; comparable only within runs of years without a recording break (urban distraction breaks in 2016 and 2019, urban alcohol in 2016, drugs throughout); deaths by factor are published for speed only |
| Speed as a severity factor | Yes, as an association | the speed report's speed-related crashes and deaths by road type against microdata totals for the same provinces. The microdata restricted to the report's provinces reproduce its totals by year and zone exactly (`speed_report_scope`); the report gives no totals by road type, so the mapping of the microdata to its road types is not reconciled |
| Alcohol × speed interaction, fatigue, protective equipment | **No** | none of these variables exist in the DGT crash-level file, and the report gives no cross-tabulation of factors |
| Driver age and sex risk | Yes, per licence holder and per driver involved, 2014–2024; per km of cars registered to owners of each age, 2024 only, as ranges | aggregate tables 4.1.1 and 4.2 with the driver census; no file gives kilometres by sex, so the sex comparison is per licence holder (any class) and per driver involved |
| Campaign or policy evaluation with daily resolution | Not for Spain | no calendar day in the DGT microdata, so only monthly evaluation is possible; the Catalan and Barcelona files carry dates for their own areas |
| Annual and monthly exposure for risk trends and seasonality | Partly | CORES road fuel (all roads, but tonnes, not km) is the only monthly series divided into deaths; no series measures kilometres per tonne on all roads. Petrol alone and toll-motorway intensity are shown beside deaths as traffic indices, never as denominators. On the State, regional and provincial interurban networks the Ministry measures annual vehicle-km, 2004–2023 (comparable from 2008, without urban or municipal roads); DGT's 2022 and 2024 kilometre estimates cannot be chained |
| The 2019 conventional-road speed limit | **No** | the aggregate two-group design fails its own placebo, and section identifiers, limits, speeds and volumes are not published |
| Deaths per kilometre by year and road class | Yes, interurban only: in total 2008–2023, by road class 2016–2023 | the Ministry's measured vehicle-km (table 1.2.14) run from 2004, are comparable from 2008 and cover only the State, regional and provincial networks. Against the yearbook series' interurban deaths they give the total for 2008–2023, with 8.7 % to 11.2 % of interurban deaths in 2016–2024 on roads the kilometres leave out (`longrun_km_coverage.csv`). By road class (autopistas and autovías together, conventional roads) the deaths come from the crash microdata, which start in 2016, so only 2016–2023 have both, and the class rates are restricted to roads of owners 1 to 3, the networks the kilometres cover (`road_class.py`). No urban kilometres |
| Road geometry, speed limits, traffic volume, coordinates | Not for Spain | the DGT file records only the police's category for alignment and traffic level, with no speed limit, measured volume or coordinates; the Catalan file records the road's speed limit (not a driving speed) and the Barcelona crash table carries coordinates, for their own areas only; no file measures traffic volume at a crash site |

For Spain as a whole, vehicle-level and person-level records would be the most useful addition and
are required before any factor-interaction work on national data can start. DGT does not publish
them for download; a data request to DGT is the route. The Barcelona files hold person and vehicle
records for one city and one year (section 1 F) and do not stand in for national records.

## 5. Organisation

- Raw files are tracked in Git under `data/raw/<source>/`, one folder per publisher
  ([`data/README.md`](../data/README.md)), and are never edited in place. `data/raw/manifest.csv`
  records path, size, SHA-256, source URL, description, the date added and, for renamed downloads,
  the name the file was downloaded as; any replacement must update the manifest entry, and
  `tests/test_paths.py` checks the checksums. The file count, sizes and any file missing from the
  manifest are reported in the generated [`RAW_FILE_INVENTORY.md`](RAW_FILE_INVENTORY.md).
- `data/staging/<source>/`, `data/processed/` and `data/features/` are ignored by Git and rebuilt
  from `data/raw/` by the scripts. `scripts/ingest.py` parses the national DGT files into Parquet
  under `data/staging/dgt/` on first run (`openpyxl` needs about 35 seconds per microdata year;
  Parquet loads in well under a second).
- The RDF metadata file (`dgt/microdata/metadata_2024.rdf.xml`) holds the official access URL,
  licence and issue date for 2024 and is the template for the manifest entries of the other years.
