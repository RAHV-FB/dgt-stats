# Phase 3: exposure-adjusted rates, with older road users as the case study

Plan date: 2026-09-19. Phase 3 of [`analytics_plan.md`](analytics_plan.md) covers Q4 (province
rates with proper denominators) and Q7 (older road users). This document sets the design, the data
still to gather, and the build steps. Same working rules as before: Python only, one commit per step,
tables and figures committed, static HTML output, no JavaScript.

## 1. The question that drives the phase

DGT reports deaths of people aged 65 and over per million inhabitants of that age. That denominator
answers "how often does an older resident die on the road", not "how risky is it for an older person
to drive". Two things move underneath it:

- fewer people in each older cohort hold a driving licence, and the share falls steeply with age;
- among licence holders, the share who actually drive, and how often, also falls with age.

The second effect is the one that matters most and the one no DGT figure corrects for. A licence
is kept long after driving stops (renewal is cheap and many people keep it "just in case"), so
"per licence holder" still understates the risk to the people who are really on the road. Phase 3
therefore targets **active drivers** as the main denominator, and reports the same numerator against
each rung of a ladder so the reader sees how the conclusion changes:

| Rung | Denominator | Source | Years | What it measures |
|---|---|---|---|---|
| 1 | Residents in the age band | INE table 56947 (in the repo) | 2002–2025 | risk to a resident |
| 2 | Licence holders in the age band | DGT driver census by age | 2014–2025 | risk to a licensed driver (upper bound on active drivers) |
| **3** | **Active drivers in the age band** | residents × share who drive at least a few days a month, from population surveys (section 3) | survey years, interpolated | **risk to someone who drives** (headline) |
| 3b | Driving-days-weighted active drivers | rung 3 × mean driving days per week by age | survey years | risk per unit of driving, first approximation |
| 4 | Drivers involved in crashes but not responsible (induced exposure) | DGT yearly tables, drivers involved by age | 2014–2024 | relative exposure without any survey, every year |
| 5 | Kilometres driven in the age band | not published by driver age in Spain | — | stated as unavailable; rung 3b and rung 4 bracket it |

Rung 3 is the answer to the question. Rungs 2 and 4 bracket it: a licence count is an upper bound
on active drivers, and induced exposure (drivers involved in two-vehicle crashes who committed no
infraction) is a direct, yearly measure of who was really on the road, unaffected by survey
sampling. If rungs 3 and 4 tell the same story, the finding is robust.

The numerator for rungs 2–4 must be **driver** deaths (or driver involvement), not all victims: a
pedestrian aged 80 is not exposed as a driver. Driver victims by age come from DGT's yearly
statistical tables (table 4.1.1, "Edad y sexo de los conductores víctimas"); all-victim deaths by age
come from the historical series already in the repo.

## 2. What is already in hand

- **INE population** by province × five-year age group × sex, nationality total, 1 January and
  1 July, 2002–2025: `data/raw/exposure/ine_poblacion_provincias_edad_sexo.csv`, 149,460 rows,
  produced by `scripts/fetch_ine.py` from INE table 56947 (Estadística Continua de Población). The
  national 65+ figure for 1 January 2023 is 9,687,776, identical to the number in DGT's older-users
  report, so the two sources line up.
- Historical series: victims by age band 1993–2024 (`series_age`), driver deaths by vehicle type
  (`series_road_users`), province series (`series_province`).
- 2024 statistical tables: driver victims by age (4.1.1), drivers involved by age, sex and condition
  (4.2), licence seniority (4.4).
- Driver census 2023–2025 by province × sex × class × year of issue; the 2025 workbook has class × age.
- Kilometres per vehicle type and age band, 2022.

## 3. Data to gather (checklist)

Add each file under `data/raw/` in the folder shown, then run `python -m pytest tests/test_paths.py`;
it fails until the file has a row in `data/raw/manifest.csv` (path, bytes, SHA-256, source URL,
description, date). `sha256sum <file>` and `wc -c <file>` give the two numbers.

### 3.1 Share of people who actually drive, by age (rung 3) — the priority

There is no single Spanish series for this, so the plan combines the population surveys that exist.
What was checked and what each gives:

| # | Source | What it gives | Status |
|---|---|---|---|
| 1 | **ESRA3 (2023) and ESRA2 (2018)**, E-Survey of Road users' Attitudes, Spain sample 935 adults 18+ in 2023 (DGT and Fundación MAPFRE are the Spanish partners) | Question: how often did you use each transport mode in the last 12 months; "car driver at least a few days a month" is the frequent-driver definition. National 2023 value for Spain: 75.9 % of adults; the 2023 country fact sheet is at `https://www.esranet.eu/storage/minisites/esra2023countryfactsheetspain.pdf` (in the scratch notes). The **age split (18–24 … 65–74, 75+) is in the ESRA dashboard** (Power BI, linked from `https://www.esranet.eu/en/publications/esra3-publications/`), filter country = Spain, indicator = use of transport modes, split by age; the 2018 wave is in the ESRA-123 dashboard. Read the values off and type them into the CSV described below, one row per age band and wave, with the n shown. If the dashboard does not give n by age, note it. A data request to Vias institute (ESRA coordinator) is the alternative for the microdata. | to gather |
| 2 | **MOVILIA 2006/07** (Ministerio de Transportes, national travel survey, ~49,000 households) | Persons making at least one trip as car driver on an average weekday, by age band and sex; also trips per person as driver. Old, but the only Spanish travel survey with driver status by age. Excel tables from `https://www.transportes.gob.es/informacion-para-el-ciudadano/informacion-estadistica/movilidad/movilia-20062007` (the page refused the automated fetch; open it in a browser and download the "fichero Excel completo" for 2006). | to gather |
| 3 | **INE Encuesta de Hogares y Medio Ambiente 2008**, tables 10016 and 10019 | Mean kilometres per year of household cars by age of the reference person; a km-by-age curve for rung 3b/5 | to gather (px/CSV export from INEbase, links in section 3.1 notes below) |
| 4 | **Fundación MAPFRE, "Mayores de 65 años y seguridad vial"** (300 drivers aged 65+, Comunidad de Madrid, quota sample, about 2008) | Among older drivers: 55.9 % drive fewer than 3 days a week, 30.3 % 3–5 days, 13.8 % more; `https://app.mapfre.com/ccm/content/documentos/fundacion/seg-vial/investigacion/mayores-y-seguridad-vial.pdf` | read and typed into the CSV; conditional on being a driver and regional, used for rung 3b only |
| 5 | Encuesta Nacional de Salud 2011/12 and 2017, Encuesta Europea de Salud 2014/2020 | Checked the adult questionnaires: no driving or seat-belt-as-driver question, so no help | ruled out |
| 6 | INE ECEPOV 2021, table 55378 (main vehicle used to commute, by sex and age) | Commuters only, so it says little about 65+; keep as a cross-check for 25–64 | optional |
| 7 | CIS studies on road safety (they ask "¿Conduce Ud.?" with frequency, cross-tabulated by age) | Could not identify the study number from outside; if you know one, its "tabulación por edad" PDF is enough | optional |

Survey values go in one hand-typed CSV, `data/raw/exposure/driving_activity_by_age.csv` (started, with
the ESRA3 national value and the MAPFRE rows; the manifest row must be refreshed after each edit), with
columns `source, wave, question, definition, age_low, age_high, sex, share, n, url, notes`:
`share` is the fraction of residents of that age band who drive under `definition` (for example
"car driver at least a few days a month"), `n` the unweighted respondents behind it, `sex` one of
`Total`, `Men`, `Women`. Rows enter the rate tables as a multiplier with a visible uncertainty band
(binomial on n), never as a precise number. Anything that cannot be traced to a page and a question is
not entered.

Notes: EHMA 2008 tables are at `https://www.ine.es/jaxi/Tabla.htm?path=/t25/p500/2008/p10/l0/&file=10016.px&L=0`
and `...&file=10019.px&L=0` (export as CSV from the page). The DGT magazine (December 2023) states that
94 % of drivers aged 65–74 drive almost daily, without naming a survey; it is not used until the source
is found, because it contradicts item 4.

### 3.2 Required DGT files (rungs 2 and 4, driver numerators)

| # | What | Where | Folder and name |
|---|---|---|---|
| 8 | Driver census by province × sex × class × **age**, 2023, 2024, 2025 | `https://www.dgt.es/microdatos/salida/conductores/censo/2023/censo_prov_sexo_clase_edad_2023.txt` (same pattern for 2024 and 2025); listing page: DGT en Cifras → "Microdatos de censo de conductores según provincia, sexo, edad y tipo de permiso (anual)" | `exposure/censo_conductores_edad_YYYY.txt` |
| 9 | "Accidentes con víctimas – Tablas estadísticas" workbooks for **2014 to 2023** (2024 is in the repo) | DGT en Cifras → DGT en cifras resultados → search "Tablas estadísticas"; each year has its own page. 2023 is at `https://www.dgt.es/export/sites/web-DGT/.galleries/downloads/dgt-en-cifras/publicaciones/Anuario-Estadistico-de-Accidentes/Accidentes-con-victimas-Tablas-estadisticas-2023.xlsx`; earlier years sit under different paths, so take the link from each year's page | `tables/tablas_estadisticas_YYYY.xlsx` |
| 10 | "Censo de conductores – Tablas estadísticas" workbooks for **2014 to 2024** (2025 is in the repo) | 2024 is at `https://www.dgt.es/export/sites/web-DGT/.galleries/downloads/dgt-en-cifras/publicaciones/Censo-conductores-Tablas-estadisticas/Censo-de-conductores-Tablas-estadisticas-2024.xlsx`; earlier years from each year's page, or from the "Anuario Estadístico General" of that year (chapter on conductores, table class × age) | `exposure/censo_tablas_YYYY.xlsx` |

Item 9 gives driver victims by age and drivers involved by age for every year (rungs 2–4 numerators
and the rung 4 denominator). Items 8 and 10 give licence holders by age (rung 2) for 2014–2025.
Rung 4 needs, for each year, drivers involved by age split by whether they committed an infraction
(tables in the "conductores implicados" chapter); if a year's workbook lacks the infraction split,
that year uses involvement alone and is marked as such.

### 3.3 Valuable if found

| # | What | Why | Candidates |
|---|---|---|---|
| 11 | "Kilómetros anualizados recorridos por el parque móvil 2024" | refresh of the 2022 km data used in Q6 | DGT en Cifras page of that name |
| 12 | "Parque de vehículos – Tablas estadísticas 2025" (fleet by province) | Q4 per-vehicle rates | DGT en Cifras page of that name |
| 13 | Any Spanish survey reporting annual km by driver age band with its sample size | rung 5 | none found yet |

## 4. Build steps

### Step 1 — Population module
- `io_population.py`: read the INE extract; expose `population(year, reference="1 July", province=None, sex="Total")` returning five-year groups, plus `to_dgt_age_bands()` mapping to DGT's bands (0–14, 15–24, 25–34, 35–44, 45–54, 55–64, 65+; and 65–69, 70–74, 75+ for the older-driver tables). Province names carry the INE code ("28 Madrid") and are joined to DGT provinces by code.
- Interim: `data/interim/poblacion_ine.parquet`.
- Tests: national 65+ on 1 January 2023 equals 9,687,776; every province code 01–52 present; age groups sum to "Todas las edades".

### Step 2 — Driver exposure readers
- Extend `io_exposure.py`: `read_census_age_year(year)` for item 8 files; `read_census_age_workbook(year)` for the class × age tables of item 10 (2014–2025); a `licence_holders_by_age(year)` view that yields drivers per DGT age band and sex.
- Yearly statistical-table readers for item 9: `read_table_4_1_1(year)` (driver victims by age and sex, interurban and urban), `read_table_4_2(year)` (drivers involved by age, sex and condition) and the infraction-by-age table where present, header-located like `io_tables`.
- `io_activity.py`: read `driving_activity_by_age.csv`; `driving_share(year, definition)` returns the share of residents who drive per DGT age band and sex, interpolated linearly between survey waves and held flat outside them, with a low/high band from the binomial interval on n; `driving_days(age_band)` from item 4. Every output row carries the source and wave it came from.
- Tests: 2024 values equal the already-parsed 2024 workbook; totals reconcile with the series; a synthetic activity CSV interpolates and bounds as expected; an age band with no survey row yields NA, never a guess.

### Step 3 — `rates.py`
- `rate(count, exposure, per)` with exact Poisson confidence intervals; `rate_ratio()` with CIs;
  `direct_standardise()` to the 2019 population; `active_drivers(year)` = residents × driving share,
  carrying the survey band through to the rate interval; `induced_exposure_ratio(age_band)` from the
  drivers-involved tables (involved drivers with no infraction as the exposure set).
- Tests against hand-computed values, including that the rung 3 rate is never below the rung 2 rate
  for the same cell (active drivers cannot exceed licence holders; if a survey share implies more
  active drivers than licences, the cell is capped at the licence count and flagged).

### Step 4 — Summaries and figures
- **Q4 geography**: 2024 crashes, deaths and hospitalised per 100,000 residents (INE 1 July 2024)
  and per 10,000 licence holders (census 2024) by province, with CIs, ranking tables and a
  small-province caution; national rates per year 2002–2024.
- **Q7 older road users, the denominator ladder**: for each age band (35–44 … 75+) and year
  2014–2024: deaths per million residents (rung 1), driver deaths per 100,000 licence holders
  (rung 2), **driver deaths per 100,000 active drivers (rung 3, the headline, with its survey band)**,
  the driving-days-weighted variant (3b), and the induced-exposure relative risk (rung 4). One table
  and one chart show the 65+ versus 35–64 ratio under each rung side by side, so the reader sees the
  answer change with the denominator. A second table shows the three curves by age for the latest
  year: share of residents with a licence, share who drive, and share of licence holders who drive.
- Figures: province rate bars with CI whiskers; ladder chart (small multiples, one per rung, rung 3
  with a shaded band); licence-holding and driving-share curves by age on one chart; older-driver
  trend lines.

### Step 5 — Site
- Two new pages: `geography.html` and `older-users.html`; cards on the overview; data page updated
  with INE and the new DGT files; captions state denominator, reference date and CI method.

### Step 6 — Docs, tests, PR, merge
- `docs/data_inventory.md` and `docs/data_sources.md` for every new file; README roadmap tick for
  "first exposure-adjusted trend analysis"; `analytics_plan.md` phase table.

## 5. Verification

- INE totals match DGT's published population figures where both exist.
- Every survey share on the site traces to a source, wave, question and n in the activity CSV.
- Rates recompute from committed tables; CIs shrink with exposure; direct standardisation of 2019 to
  itself returns the crude rate.
- Every rate on the site names its numerator, denominator, reference date and years.
- `pytest`, `ruff`, idempotent rebuild, headless screenshots at 1280 px and 390 px.
