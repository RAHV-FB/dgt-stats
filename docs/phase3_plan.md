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

Update 19 September 2026, after the data collection round: everything in section 3.2 is in the repo
(driver census by age 2023–2025, census workbooks 2014–2024, yearly crash tables 2014–2023), plus
MOVILIA 2006/07, INE ECEPOV 2021 and INE EHMA 2008. The ESRA age split is **not obtainable** from the
public dashboard (only national totals: 80.2 % in 2018, 75.9 % in 2023), and MOVILIA's published
tables report the mode "coche o moto" without a driver/passenger split. Consequences for rung 3:

- Rung 3 cannot be built as "residents × survey share who drive by age" from public data alone.
  It becomes **rung 3 (bounded)**: the age shape of active driving is taken from the DGT
  induced-exposure measure (rung 4, yearly, from tables 4.2), scaled so that the national active-driver
  total matches the ESRA national share in 2018 and 2023 (interpolated between, held flat outside).
  MOVILIA 2006 trips by "coche o moto" per resident by age and sex is the historical cross-check on
  that age shape. The result carries the ESRA binomial band and is labelled as a calibrated estimate.
- Rung 2 (licence holders) and rung 4 (observed drivers) are reported separately and never merged
  into one unlabelled exposure measure.
- If an ESRA age cross-tab is obtained later (data request to Vias institute), it drops straight into
  `driving_activity_by_age.csv` and rung 3 switches to the direct definition without code changes
  beyond the reader.

Originally in hand before the collection round:

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
| 1 | **ESRA3 (2023) and ESRA2 (2018)**, E-Survey of Road users' Attitudes, Spain sample 935 adults 18+ in 2023 (DGT and Fundación MAPFRE are the Spanish partners) | Question: how often did you use each transport mode in the last 12 months; "car driver at least a few days a month" is the frequent-driver definition. National 2023 value for Spain: 75.9 % of adults; the 2023 country fact sheet is at `https://www.esranet.eu/storage/minisites/esra2023countryfactsheetspain.pdf` (in the scratch notes). The **age split (18–24 … 65–74, 75+) is in the ESRA dashboard** (Power BI, linked from `https://www.esranet.eu/en/publications/esra3-publications/`), filter country = Spain, indicator = use of transport modes, split by age; the 2018 wave is in the ESRA-123 dashboard. The dashboard was checked: it exposes the Spain national totals only (2018: 80.2 %, n 906 weighted; 2023: 75.9 %, n 935 weighted), both typed into the CSV. A data request to Vias institute (ESRA coordinator) is the only route to the age split. | national values in the CSV; age split unavailable |
| 2 | **MOVILIA 2006/07** (Ministerio de Transportes, national travel survey, ~49,000 households) | Persons making at least one trip as car driver on an average weekday, by age band and sex; also trips per person as driver. Old, but the only Spanish travel survey with driver status by age. In the repo as `movilia_2006.xls` and `movilia_2007.xls`. Checked: tables 63–64 give trips by main mode × sex × age, but the mode is "coche o moto" with no driver/passenger split, so it is a car-travel intensity curve by age, not a driver share. | in the repo; weaker than hoped |
| 3 | **INE Encuesta de Hogares y Medio Ambiente 2008**, tables 10016 and 10019 | Mean kilometres per year of household cars by age of the reference person; a km-by-age curve for rung 3b/5 | in the repo (`ine_ehma_2008_10016.csv`, `ine_ehma_2008_10019.csv`) |
| 4 | **Fundación MAPFRE, "Mayores de 65 años y seguridad vial"** (300 drivers aged 65+, Comunidad de Madrid, quota sample, about 2008) | Among older drivers: 55.9 % drive fewer than 3 days a week, 30.3 % 3–5 days, 13.8 % more; `https://app.mapfre.com/ccm/content/documentos/fundacion/seg-vial/investigacion/mayores-y-seguridad-vial.pdf` | read and typed into the CSV; conditional on being a driver and regional, used for rung 3b only |
| 5 | Encuesta Nacional de Salud 2011/12 and 2017, Encuesta Europea de Salud 2014/2020 | Checked the adult questionnaires: no driving or seat-belt-as-driver question, so no help | ruled out |
| 6 | INE ECEPOV 2021, table 55378 (main vehicle used to commute, by sex and age) | Commuters only, so it says little about 65+; keep as a cross-check for 25–64 | in the repo (`ine_ecepov_2021_55378.xlsx`) |
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
| 8 | Driver census by province × sex × class × **age**, 2023, 2024, 2025 (in the repo) | `https://www.dgt.es/microdatos/salida/conductores/censo/2023/censo_prov_sexo_clase_edad_2023.txt` (same pattern for 2024 and 2025); listing page: DGT en Cifras → "Microdatos de censo de conductores según provincia, sexo, edad y tipo de permiso (anual)" | `exposure/censo_conductores_edad_YYYY.txt` |
| 9 | "Accidentes con víctimas – Tablas estadísticas" workbooks for **2014 to 2023** (in the repo: 2020–2023 as yearly workbooks, 2014–2019 as chapter workbooks under `tables/chapters/`) | DGT en Cifras → DGT en cifras resultados → search "Tablas estadísticas"; each year has its own page. 2023 is at `https://www.dgt.es/export/sites/web-DGT/.galleries/downloads/dgt-en-cifras/publicaciones/Anuario-Estadistico-de-Accidentes/Accidentes-con-victimas-Tablas-estadisticas-2023.xlsx`; earlier years sit under different paths, so take the link from each year's page | `tables/tablas_estadisticas_YYYY.xlsx` |
| 10 | "Censo de conductores – Tablas estadísticas" workbooks for **2014 to 2024** (in the repo; 2024 has no age table, the age text file covers it) | 2024 is at `https://www.dgt.es/export/sites/web-DGT/.galleries/downloads/dgt-en-cifras/publicaciones/Censo-conductores-Tablas-estadisticas/Censo-de-conductores-Tablas-estadisticas-2024.xlsx`; earlier years from each year's page, or from the "Anuario Estadístico General" of that year (chapter on conductores, table class × age) | `exposure/censo_tablas_YYYY.xlsx` |

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

## 4. Build steps (final design, 19 September 2026)

Branch `phase-3`, one commit per step, `ruff` and `pytest` before each commit, squash-merge to `main`
at the end. Analysis age bands are 15–24, 25–34, 35–44, 45–54, 55–64, 65–74 and 75+, with 65–69 and
70–74 kept for the older-driver tables; every source band must nest inside exactly one analysis band
(`agebands.py` raises otherwise, so nothing is split silently).

### Step 1 — Age bands and population
- `agebands.py`: band definitions, `parse_age_label()` for every DGT, INE and MOVILIA label
  ("De 15 a 17 años", "Más de 74 años", "Hasta 14 años", "65 y más años", "0\\14 años"), `band_for()`.
- `io_population.py`: the INE extract as a tidy frame (province code, sex, five-year group, reference
  date, year); `population_by_band()`, `population_by_province()`; interim `poblacion_ine.parquet`.
- Tests: national 65+ on 1 January 2023 = 9,687,776; provinces sum to the national total; five-year
  groups sum to "Todas las edades"; label parsing; straddling bands raise.

### Step 2 — Licence holders by age
- `io_exposure.read_census_age_year()` (text files 2023–2025; Latin-1 to 2024, UTF-8 BOM in 2025;
  permits, licences and their sum per province × sex × band) and `read_census_age_tables()` (workbook
  sheets P.6.1.1.7 / P.6.1.2.7 / P.6.1.3.7 for 2014–2023: the "TOTAL GENERAL" row to 2020, the
  "Total censo" row from 2021). `licence_holders_by_age()` stitches 2014–2022 from the workbooks and
  2023–2025 from the text files, by sex and fine band, with the source named per row.
- Tests: text-file totals equal the published census totals (27,914,572 / 28,142,470 / 28,472,636);
  the 2023 workbook equals the 2023 text file band by band.

### Step 3 — Driver tables 2014–2024, MOVILIA, checks
- `io_tables.read_table_4_1_1(year)` (driver victims by fine age band × sex × vehicle type, killed /
  hospitalised / not hospitalised, interurban and urban) and `read_table_4_2(year)` (drivers involved
  by fine band × sex × vehicle type). Layout differences handled: 2014 `.xls` read through `xlrd`,
  sheet names without the "TABLA" prefix, sex codes V/M/Desconocido, per-age "Total" rows in the
  first column, "No especificada"; 2015 titles in upper case and labels with line breaks.
- `io_activity.py`: the survey register and MOVILIA 2006 table 64 (trips by main mode × sex × age,
  average weekday) with trips per resident from the 2006 population.
- New validation checks: driver deaths from tables 4.1.1 (interurban + urban) equal the yearbook
  series of driver deaths for every year 2014–2024; the 2023 census workbook equals the text file.
- `scripts/ingest.py` builds the new interim tables; tests on totals and layouts.

### Step 4 — `rates.py`
- Exact Poisson intervals (`scipy.stats.chi2`), `rate_ratio()` with log-normal intervals,
  `direct_standardise()`, `active_driver_share()` (ESRA national share interpolated between waves ×
  MOVILIA car-travel age profile, capped at the licence-holding share; low/high from the ESRA
  binomial interval). Tests against hand-computed values.

### Step 5 — Summaries
- Q4: `province_rates()` for 2024 (crashes, deaths, hospitalised per 100,000 residents on 1 July 2024
  and per 10,000 licence holders, with intervals and ranks; small-province caution) and
  `national_rates_by_year()` (deaths per 100,000 residents 2002–2024, per 10,000 licence holders
  2014–2024).
- Q7: `driver_ladder()` (year × band: residents, licence holders, active-driver estimate, drivers
  involved, driver deaths; deaths per million residents, per 100,000 licence holders, per 100,000
  active drivers, involvement per 10,000 licence holders, deaths per 1,000 involved drivers),
  `ladder_ratio()` (65+ and 75+ against 35–64 under each denominator), `licence_share_by_age()`,
  `victims_by_age_rates()` (all victims per million residents by band, 2002–2024, from the series)
  and `movilia_car_travel()`.
- Provinces are joined by code: the INE name carries it, the DGT dictionary maps codes to the names
  used in table 1.1.

### Step 6 — Figures
- `plots.dot_interval()` (ranked dots with interval whiskers) and an optional shaded band in
  `line_series()`. Figures: province death rates with intervals; national rates over time; the
  ladder (65+ / 35–64 ratio by year, one line per denominator); licence-holding and active-driver
  shares by band; driver death rates by band over time; involvement versus fatality-given-involvement.

### Step 7 — Site
- `geography.html` and `older-users.html`, cards on the overview, data page updated, every rate
  captioned with numerator, denominator, reference date and interval method.

### Step 8 — Docs, PR, merge
- Inventory, sources, README roadmap and results, analytics plan phase table; PR; squash merge.

## 5. Outcome (19 September 2026)

All eight steps are merged. What was built, with the deviations from the design above:

- `agebands.py`, `io_population.py`, `io_activity.py`, `rates.py` are new; `io_exposure.py` and
  `io_tables.py` gained the census-by-age and driver-table readers; `summaries.py`, `figures.py` and
  `site.py` gained Q4 and Q7. Seven result tables (`q4_*.csv`, `q7_*.csv`), seven figures and the
  pages `geography.html` and `older-drivers.html`.
- The licence series uses the published class × age tables up to 2023 and the text files from 2024
  (not 2023 as planned): the 2023 text file differs from the 2023 tables by up to 1.1 % in some bands,
  so one publication type is kept for as long as it exists; the gap is a validation check (2 %
  tolerance, 15 rows) rather than an assertion.
- Rung 3 is named **travel-weighted drivers** on the site and in the code (not "active drivers"):
  spreading the ESRA share by the MOVILIA car-trip profile weights people by how much they travel by
  car, which is an exposure weight rather than a head count of drivers. Because MOVILIA counts
  passengers, the estimate overstates older people's driving and understates their per-driver rate,
  so the true per-driver ratio is at or above the travel-weighted one. The site says so.
- Rung 4 is presented as two measures rather than a quasi-induced-exposure risk: drivers involved in
  injury crashes per 10,000 licence holders (crash involvement) and driver deaths per 1,000 drivers
  involved (fatality given involvement). No yearly table splits involved drivers by fault and age.
- The reconciliation is exact: driver deaths from tables 4.1.1 equal the yearbook series for every
  year 2014–2024 and both zones (33 checks). 325 checks in all, none failing.
- 2024 result, drivers aged 75+ against 35–64: 0.74 per resident, 1.55 per licence holder, 2.8 per
  travel-weighted driver, 2.95 per driver involved; involvement per licence holder 0.53.

Still open: an ESRA age cross-tab (data request to Vias institute) would turn rung 3 into a direct
measure; kilometres by driver age remain unpublished.

## 6. Verification

- INE totals match DGT's published population figures where both exist.
- Every survey share on the site traces to a source, wave, question and n in the activity CSV.
- Rates recompute from committed tables; CIs shrink with exposure; direct standardisation of 2019 to
  itself returns the crude rate.
- Every rate on the site names its numerator, denominator, reference date and years.
- `pytest`, `ruff`, idempotent rebuild, headless screenshots at 1280 px and 390 px.
