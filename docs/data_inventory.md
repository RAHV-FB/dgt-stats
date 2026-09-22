# Data inventory and audit

Audit date: 2026-09-18, extended on 19 and 20 September 2026 for the files added later and the
coding breaks found in the final review. Every source file was opened and profiled with Python
(`openpyxl`, `pandas`, `pymupdf`). This document records what each file contains, how the files
group together, what was verified, and what must be handled before analysis. It complements the
source register in [`data_sources.md`](data_sources.md). Checksums, sizes and source URLs for every
file are in [`data/raw/manifest.csv`](../data/raw/manifest.csv).

## 1. Files by category

All raw files live under `data/raw/`, grouped by role.

### A. Crash microdata (`data/raw/microdata/`, one row per injury crash)

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
| `diccionario.xlsx` | all | 38 sheets, 33 of them code lists | — | `Diccionario_Tabla_Accidentes.xlsx` |
| `metadata_2024.rdf.xml` | 2024 | DCAT record | — | datos.gob.es catalogue export |

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

### B. Official aggregate statistics (`data/raw/tables/`)

| File | Coverage | Content | Original name |
|---|---|---|---|
| `tablas_estadisticas_2024.xlsx` | 2024 | 39 tables: crashes and victims by province, autonomous community, month, weekday, hour, road type, lighting, vehicle type, driver age/sex/licence seniority, driver infractions, vehicle age | `Accidentes-con-victimas-Tablas-estadisticas-2024.xlsx` |
| `series_historicas_2024.xlsx` | 1993–2024 | 69 sheets of annual series: crashes, victims (24 h and 30 day), by month, province, sex, age, pedestrians, driver deaths by vehicle type, rates per fleet and population | `Series-Historicas-Anuario-Accidentes-2024.xlsx` |

| `tablas_estadisticas_{2020..2023}.xlsx` | 2020–2023 | Same 39–40 tables as 2024, one workbook per year, same sheet names (`TABLA 4.1.1.I`, `TABLA 4.2.U`, ...) | `Accidentes_con_victimas_Tablas_estadisticas_YYYY.xlsx` |
| `chapters/{2014..2019}/grupo_{1..8}.xls(x)` | 2014–2019 | The same yearbook split into eight chapter workbooks; chapter 4 holds driver victims by age and sex (4.1.1), drivers involved by age, sex and condition (4.2) and licence seniority (4.4), interurban and urban. 2014 is `.xls` (read with `xlrd`), 2015 uses upper-case titles without the year, 2016+ match the modern layout | `Grupo-N.-...-YYYY.xls(x)` |

A second copy of the series workbook (`...2024(1).xlsx`, byte-identical, same MD5) was removed.

### C. Exposure and denominators (`data/raw/exposure/`)

| File | Coverage | Content | Original name |
|---|---|---|---|
| `censo_conductores_2023.txt` | 2023 | 8,405 rows, pipe-delimited: province × sex × licence class × licence year → drivers. Total 27,914,572 drivers | `censo_prov_sexo_clase_antig_2023.txt` |
| `censo_conductores_2024.txt` | 2024 | 9,227 rows, total 28,142,470 drivers | `censo_prov_sexo_clase_antig_2024.txt` |
| `censo_conductores_2025.txt` | 2025 | 9,224 rows, total 28,472,636 drivers, UTF-8 BOM | `censo_prov_sexo_clase_antig_2025.txt` |
| `censo_tablas_2025.xlsx` | 2025 | 10 published tables: drivers by province/community of residence and first issue, by licence class × age, by licence class × year of issue, split by sex | `Censo-de-conductores-Tablas-estadisticas-2025.xlsx` |
| `km_itv_2022/km_recorridos_estimados_2022.xlsx` | 2022 | Estimated annual km per vehicle by vehicle type × Euro class × age band × engine size × (payload) × fuel; 6 sheets, 8,254 strata | `Km_recorridos_anuales_estimados.xlsx` (from `KM_ITV_2022.zip`) |
| `km_itv_2022/media_km_antiguedad_tipo_2022.xlsx` | 2022 | Mean annual km and fleet size by vehicle type (7) × age band (5) | `Media_km_recorridos_ antiguedad_tipo de vehículo.xlsx` |
| `km_itv_2022/metodologia.pdf` | 2014–2023 ITV | Methodology: gamma-regression (LightGBM) imputation of annualised odometer readings; explains 19–45% of variance per vehicle, valid only for aggregates | `KM_Recorridos_ITV_Parque.pdf` |

| `censo_conductores_edad_{2023,2024,2025}.txt` | 2023–2025 | Pipe-delimited: province × sex × age band (15–17, 18–20, 21–24, then five-year bands to 70–74, "Más de 74", "Se desconoce") → permits, licences and permits by class. 2023 and 2024 are Latin-1, 2025 is UTF-8 with BOM | `censo_prov_sexo_clase_edad_YYYY.txt` |
| `censo_tablas_{2014..2024}.xlsx` | 2014–2024 | Published driver-census tables; 2014–2023 include `P_6_1_1_7` (drivers by licence class × age band, plus men/women sheets), 2024 has only the province tables (age comes from the text file) | `Censo-de-conductores-Anuario-YYYY.xlsx` / `...Tablas-estadisticas-YYYY.xlsx` |
| `ine_poblacion_provincias_edad_sexo.csv` | 2002–2025 | INE table 56947 extract: residents by province × five-year age group × sex, 1 January and 1 July; 149,460 rows, rebuilt by `scripts/fetch_ine.py` | INE CSV download |
| `driving_activity_by_age.csv` | 2008, 2018, 2023 | Hand-typed survey register: ESRA2/ESRA3 Spain share of adults driving a car at least a few days a month (national only), Fundación MAPFRE driving days per week among drivers 65+ (Madrid) | typed from the reports |
| `movilia_2006.xls` | 2006 | MOVILIA 2006 daily-mobility tables (168 sheets). Tables 63–64 give trips by main mode × sex × age; the mode is "coche o moto" with **no driver/passenger split**, so it yields a car-travel intensity curve by age, not a driver share | `Movilia2006.xls` |
| `movilia_2007.xls` | 2007 | MOVILIA 2007 long-distance tables (134 sheets): trips over 50 km by mode, purpose, age and sex | `Movilia2007.xls` |
| `movilia_madrid/movilia07t0{1..5}.xls` | 2006/07 | Madrid statistical office extract of MOVILIA daily mobility (Madrid and Spain); no driver status by age | `movilia07t0N.xls` |
| `ine_ecepov_2021_55378.xlsx` | 2021 | INE ECEPOV table 55378: persons 16+ by main vehicle used to commute to work or study, by sex and age group; commuters only | INE table export |
| `ine_ehma_2008_1001{6,9}.csv` | 2008 | INE household survey: mean annual km per household vehicle by sex, age and nationality of the reference person, by fuel (10016) and by vehicle age (10019) | INE px CSV export |

The zip archive was extracted in place and the archive itself dropped.

### D. Thematic reports (`data/raw/reports/`, context, definitions, hypotheses)

| File | Pages | Content | Original name |
|---|---:|---|---|
| `dgt_factor_velocidad_2023.pdf` | 61 | Speed factor 2014–2023, 30-day data, **excludes Cataluña and País Vasco**. Speed present in 7% of injury crashes in 2023 (3% urban, 14% interurban); profiles by road type, speed limit, vehicle, driver | `INF_TEMA_4_Factor-Velocidad_v5_FINAL.pdf` |
| `dgt_personas_mayores_2023.pdf` | 82 | Road users aged 65+ in 2023: 26% of all deaths; 47.8 deaths per million vs 34.4 for under-65; collision matrices; profiles | `INF_TEMA_8_PersonasMayores_v4_FINAL_nipo.pdf` |
| `Anuario-estadistico-de-accidentes-{2015..2019}-fe-de-erratas.pdf` | — | DGT errata sheets for the 2015–2019 yearbooks; check before reconciling those years | same |
| `dgt_semana_santa_2026.pdf` | 45 | Easter 2026 interurban fatal crashes, **24-hour provisional counts**: 28 fatal crashes, 30 deaths, 17.3 million long-distance trips; series 1995–2026 | `INF_SEMANASANTA_2026_v8_FINAL.pdf` |

The ESRA reports are not archived under `data/raw/` (Vias institute offers no reproduction licence;
see the reuse terms in `data_sources.md`). They were consulted online: the ESRA3 (2023) Spain fact
sheet and main report (935 weighted respondents, 75.9 % drive at least a few days a month, main
report Table 6) at `https://www.esranet.eu/storage/minisites/esra2023countryfactsheetspain.pdf` and
`https://www.esranet.eu/storage/minisites/esra3-main-report.pdf`, and the ESRA-123 dashboard
(`https://www.esranet.eu/en/esra-123-dashboard/`) for the 2018 share (80.2 %, weighted n 906). The
two values are typed into `driving_activity_by_age.csv` with their URLs.

## 2. Crash microdata: schema and content

The 72–74 columns fall into six blocks. There are **no vehicle-level or person-level attributes**: no driver
age or sex, no alcohol or drug test result, no speed infraction, no seat-belt or helmet use, no vehicle
age, no coordinates, and no day of month.

| Block | Columns | Notes |
|---|---|---|
| Identity and time | `ID_ACCIDENTE` (2021+) / `SECUENCIAL` (2016–2020), `ANYO`, `MES`, `DIA_SEMANA`, `HORA` | Hour 0–23; no calendar day, so specific dates (holidays, campaign start dates) cannot be recovered |
| Location | `COD_PROVINCIA`, `COD_MUNICIPIO`, `ISLA`, `ZONA`, `ZONA_AGRUPADA`, `CARRETERA`, `KM`, `SENTIDO_1F`, `TITULARIDAD_VIA`, `TIPO_VIA` | Municipality is `00000` for towns under 5,000 inhabitants (12% of rows). Road name is "No inventariada" and km is null for roughly 62–65% of rows (urban crashes) |
| Crash type and severity | `TIPO_ACCIDENTE` (20 codes), `TOTAL_MU24H/HG24H/HL24H/VICTIMAS_24H`, `TOTAL_MU30DF/HG30DF/HL30DF/VICTIMAS_30DF`, `TOTAL_VEHICULOS` | Both 24-hour and 30-day counts present, so definitions can be kept separate |
| Fatalities by road-user type | `TOT_PEAT/BICI/CICLO/MOTO/TUR/FURG/CAM_MENOS3500/CAM_MAS3500/BUS/OTRO/SINESPECIF_MU24H` and `_MU30DF` | Deaths only; involvement of a vehicle type in a crash is **not** recorded. `TOT_VMP_MU30DF` (personal mobility vehicles) exists from 2020; `TOT_VMP_MU24H` only in 2020 |
| Junction and priority | `NUDO`, `NUDO_INFO`, `CARRETERA_CRUCE`, 13 `PRIORI_*` flags | `PRIORI_*` are 999 "Sin especificar" for about 60% of rows, including many junction crashes |
| Conditions | `CONDICION_NIVEL_CIRCULA`, `_FIRME`, `_ILUMINACION`, `_METEO`, `_NIEBLA`, `_VIENTO`, `VISIB_RESTRINGIDA_POR`, `ACERA`, `TRAZADO_PLANTA` | `ACERA` and `TRAZADO_PLANTA` are 998 "No aplica" for 62–87% of rows; fog and wind are null when absent. The dictionary's `.` code for "no strong wind" never occurs; strong wind is flagged in between 0.2% and 1.2% of crashes (1.1% in 2017, 1.2% in 2018, 0.5% in 2020, 0.2–0.3% in the other years) except 2021, where it is flagged in 24.6% (22,090 rows), a reporting artefact to keep out of trend comparisons |

### Missing-value states that must stay distinct

| State | Encoding in file | Example |
|---|---|---|
| Not specified / not reported | `999` | weather, priority regulation, traffic level |
| Not applicable | `998` | sidewalk on interurban road, alignment on urban street |
| Explicitly unknown | a named code: `6` in traffic level, `9` in surface, `7` in weather, `18` in visibility, `4` in alignment and direction | police attended but could not determine |
| Empty | `None` | island (usually not an island province, but also unrecorded inside them), km (not inventoried), fog and wind (absent), junction detail (not at a junction) |

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
| `TIPO_VIA = 14` ("Otro") share rises from 2.9% to 17.2%, and `TITULARIDAD_VIA = 5` ("Otra") from 1.6% to 22.0%, while `TIPO_VIA = 9` ("Calle") falls from 59.9% to 47.5% | 2016 → 2024 | coding change, almost certainly in urban reporting; road-type trends must use a collapsed grouping (motorway / dual carriageway / conventional / urban / other) and be checked year by year. `TITULARIDAD_VIA = 5` dips to 7.9% in 2021, when 14.8% of rows carry 999 instead, so its jump to 22% dates from 2023, not 2021 |
| `TIPO_VIA = 5` ("Carretera Convencional de doble calzada") falls from 6.8% to 1.8% of crashes between 2020 and 2021 while `TIPO_VIA = 6` ("Carretera Convencional de calzada única") rises from 17.9% to 21.4% and their sum stays near 23%; `TIPO_VIA = 1` ("Autopista de peaje") falls from about 1.8% to 0.4% in 2022 and 2024 while `TIPO_VIA = 2` ("Autopista libre") rises to 3.3%, with 2023 back at the earlier split and the sum stable near 3.7% | 2021, 2022, 2024 | interurban coding changes. The dual carriageway / conventional split is not comparable across 2020–2021, and the collapsed grouping does not fix it because `road_group` puts 5 in dual carriageway and 6 in conventional; the 2019 case study therefore builds its two groups from the raw codes (5 and 6 against 1, 2 and 3, `policy.py`) so that the recoding stays inside the treated group. The toll/free motorway distinction is unusable, but codes 1 and 2 are pooled into `motorway` in every use, so that group is unaffected |
| `ZONA = 4` ("Autopista o autovía urbana") falls from 0.6–0.7% of crashes in 2016–2018 to 0.1% or less from 2019 (0.4% in 2021) | 2019+ | urban motorways are coded elsewhere from 2019 (the grouped zone is unaffected); the zone level in the severity models is mostly an early-period estimate, and the page says so |
| `NUDO = 1` (at a junction) rises from 38–40% of crashes in 2016–2022 to 43.5–43.7% in 2023–2024, and `NUDO_INFO = 999` from 0.5–0.7% (2.8% in 2018) to 14.5% in 2023 and 15.1% in 2024, 72% of those rows in Barcelona and 99% in the four Catalan provinces | 2023+ | a reporting change in the junction fields, not a change on the roads; the junction term in the severity models pools both regimes and the stability check is where it would show; never read the junction share as a trend across 2022–2023 |
| `VISIB_RESTRINGIDA_POR` and `CONDICION_NIVEL_CIRCULA` swap between their explicit unknown code (18 "Se desconoce", 6 "Se desconoce") and 999 in 2021, 2023 and 2024: `VISIB_RESTRINGIDA_POR = 999` is 0.3% / 0.1% / 0.0% in 2019 / 2020 / 2022 but 14.9% / 14.0% / 14.8% in 2021 / 2023 / 2024 while code 18 drops from 28–30% to 4.8–5.6%, and `VISIB_RESTRINGIDA_POR = 17` ("Otras restricciones") jumps from 0.4% to 8.7–8.9% in the same three years; `CONDICION_NIVEL_CIRCULA = 999` is 9.5–10.2% in 2019 / 2020 / 2022 but 32.2% / 32.8% / 34.0% in 2021 / 2023 / 2024 while code 6 drops from 29–31% to 6.9–7.7%. `TITULARIDAD_VIA = 999` appears in 2021 (14.8%, 13,280 rows, all urban `ZONA 3` / `TIPO_VIA 9`) and in 28 rows of 2024 (0.03%, also all `ZONA 3`) | 2021, 2023, 2024 | one reporting batch from the four Catalan provinces (Barcelona alone is 74–79% of the `VISIB_RESTRINGIDA_POR = 999` rows in those years, Barcelona, Girona, Lleida and Tarragona together 97–100%; for `CONDICION_NIVEL_CIRCULA = 999`, which has a 10% floor everywhere, the four provinces are 65–71%), which also carries the 2021 wind flag (13,412 of the 22,090 flagged rows are the same rows); missingness is province- and year-dependent, so never run complete-case trend comparisons and never read these fields as a trend |
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

- `media_km_antiguedad_tipo_2022.xlsx` gives, for 2022 only, fleet size and mean annual km for 7 vehicle
  types × 5 age bands. Multiplying the two gives total vehicle-kilometres by type, the only vehicle-km
  denominator in the repository.
- The methodology report warns that predictions are valid in aggregate, not per vehicle, and that 2020 and
  2021 were excluded from model fitting.

## 4. What the data can and cannot support

| Question in the README | Feasible with current files? | Why |
|---|---|---|
| Crash trends, seasonality, weekday/hour patterns 1993–2024 | Yes | series workbook plus microdata |
| Severity of a crash given road type, zone, crash type, lighting, weather, surface, junction, alignment | Yes | crash-level outcome and context variables are complete enough |
| Province comparisons per population, per licensed driver, per registered vehicle | Yes, with INE population added | census files give drivers by province; fleet only national in the series |
| Vulnerable road users (pedestrians, cyclists, moped riders, motorcyclists, VMP) fatality shares and trends | Yes | `TOT_*_MU30DF` columns |
| Older road users | Partly | series has victims by age band; microdata has no age |
| Heavy vehicles and buses per vehicle-km | Only for 2022, and only occupant deaths | involvement not in microdata; km only for 2022 |
| Alcohol × speed interaction, distraction, fatigue, protective equipment | **No** | none of these variables exist in the crash-level file; speed only appears as aggregate infraction counts in `TABLA 6.1` and in the DGT report |
| Driver age, sex, licence seniority effects | Only descriptively for 2024 | aggregate `TABLA 4.x`, not linkable to crashes |
| Campaign or policy evaluation with daily resolution | **No** | no calendar day in microdata; monthly evaluation is possible |
| Road geometry, speed limits, traffic volume, coordinates | **No** | not in any file |

Vehicle-level and person-level records are the single most valuable addition and are required before any
factor-interaction work can start. They are not published for download; a data request to DGT is the route.

## 5. Organisation

- Raw files are tracked in Git under `data/raw/` (about 260 MB, 106 files) and are never edited in place.
  `data/raw/manifest.csv` records path, size, SHA-256, source URL, description and the date added for
  each file; any replacement must update the manifest entry.
- `data/interim/` and `data/processed/` stay ignored and are rebuilt from `data/raw/` by the ingestion
  scripts. Every source is converted to Parquet on first run (`openpyxl` needs about 35 seconds per
  microdata year; Parquet loads in well under a second).
- The RDF metadata file holds the official access URL, licence and issue date for 2024 and is the template
  for the manifest entries of the other years.
