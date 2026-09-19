# Data and evidence sources

This is the working source register. It will be expanded into machine-readable metadata during ingestion.

## Official Spanish data

### DGT en Cifras

- Provider: Dirección General de Tráfico.
- URL: https://www.dgt.es/menusecundario/dgt-en-cifras/
- Relevant collections: annual definitive injury-crash statistics, historical series, annual crash microdata, driver census, vehicle fleet and enforcement data.
- Role in project: primary source for Spanish crash, person, vehicle and exposure-related data.
- Main caution: provisional and definitive series, and 24-hour and 30-day fatality definitions, must not be mixed.

## Local source set

Paths are relative to `data/raw/`. Crash microdata for 2016–2024 (`microdata/accidentes_YYYY.xlsx`) and its dictionary are catalogued in [`data_inventory.md`](data_inventory.md).

| Dataset or report | Coverage | Proposed role | Main limitation to resolve |
|---|---:|---|---|
| `tables/tablas_estadisticas_2024.xlsx` | 2024 | Official reconciliation totals | Aggregated tables, not crash-level observations |
| `tables/series_historicas_2024.xlsx` | 1993–2024 | Trend baselines | Definitions and breaks in series require review |
| `exposure/censo_conductores_{2023,2024,2025}.txt` | 2023–2025 | Licensed-driver exposure context | A licensed-driver count is not kilometres driven |
| `exposure/censo_tablas_2025.xlsx` | 2025 | Published driver-census controls | Aggregate dimensions may differ from raw text extracts |
| `exposure/km_itv_2022/km_recorridos_estimados_2022.xlsx` | 2022 | Vehicle-kilometre denominator | Estimation method and uncertainty must be preserved |
| `exposure/km_itv_2022/media_km_antiguedad_tipo_2022.xlsx` | 2022 | Vehicle age/type exposure | Small cells and aggregation level require review |
| `exposure/km_itv_2022/metodologia.pdf` | Methodology | Explain annual-distance estimates | ITV selection and survivorship biases may remain |
| `reports/dgt_factor_velocidad_2023.pdf` | 2014–2023 | Speed definitions and DGT context | Report evidence is contextual, not a substitute for microdata |
| `reports/dgt_personas_mayores_2023.pdf` | 2023 | Older-road-user context | Population and exposure denominators must match |
| `reports/dgt_semana_santa_2026.pdf` | Easter 2026 | Possible campaign/holiday case study | Short, seasonal and potentially provisional period |
| `exposure/ine_poblacion_provincias_edad_sexo.csv` | 2002–2025 | Population denominators by province, five-year age group and sex (INE table 56947, nationality total, 1 January and 1 July) | Extract, not the full INE file; rebuilt by `scripts/fetch_ine.py` |
| `exposure/driving_activity_by_age.csv` | 2008, 2023 | Share of residents who drive, and driving frequency among older drivers, by age band and survey wave (ESRA3 Spain 2023; Fundación MAPFRE older-driver survey) | Hand-typed from published reports; every row carries its question, n and URL; age split from the ESRA dashboard still to be added |
| `tables/tablas_estadisticas_{2020..2023}.xlsx`, `tables/chapters/{2014..2019}/grupo_{1..8}.xls(x)` | 2014–2023 | Driver victims and drivers involved by age and sex for every year (rungs 2–4 of the Phase 3 ladder) | Layout differs by year (chapter workbooks, `.xls` in 2014, title wording in 2015) |
| `exposure/censo_conductores_edad_{2023,2024,2025}.txt` | 2023–2025 | Licence holders by province, sex and age band | Encoding differs by year (Latin-1 to 2024, UTF-8 BOM in 2025) |
| `exposure/censo_tablas_{2014..2024}.xlsx` | 2014–2024 | Licence holders by class × age band for 2014–2023 (table P.6.1.1.7) | 2024 workbook lacks the age table; use the text file |
| `exposure/movilia_2006.xls`, `exposure/movilia_2007.xls`, `exposure/movilia_madrid/*.xls` | 2006–2007 | Car-travel intensity by age and sex (trips by main mode) | Mode is "coche o moto" without a driver/passenger split; old |
| `exposure/ine_ecepov_2021_55378.xlsx` | 2021 | Commuting mode by sex and age, sensitivity check | Commuters only; says little about 65+ |
| `exposure/ine_ehma_2008_1001{6,9}.csv` | 2008 | Mean km per household vehicle by reference-person age | Household vehicle, not driver; old |
| `reports/esra*.pdf`, `reports/Anuario-estadistico-de-accidentes-*-fe-de-erratas.pdf` | 2015–2023 | ESRA Spain benchmarks; yearbook errata | ESRA age split not public |

## Research and comparison sources

- European Commission, European Road Safety Observatory, [Thematic reports](https://road-safety.transport.ec.europa.eu/european-road-safety-observatory/data-and-analysis/thematic-reports_en).
- European Commission (2024), [Main factors causing fatal crashes](https://road-safety.transport.ec.europa.eu/document/download/a7428369-8eaf-4032-806e-ea08b46028c0_en?filename=ERSO-TR-MainCauses.pdf).
- European Commission (2025), [Alcohol and drugs](https://road-safety.transport.ec.europa.eu/document/download/c1bc212c-170f-4c68-a5a4-cad17035befb_en?filename=ERSO-TR-alcohol_drugs_2026.pdf).
- European Commission (2025), [Speed and speeding](https://road-safety.transport.ec.europa.eu/document/download/9826c063-bc55-423e-84a3-24200dca3547_en?filename=ERSO-TR-speed_2026.pdf).
- European Commission (2023), [Professional drivers of trucks and buses](https://road-safety.transport.ec.europa.eu/document/download/e19cf119-eed4-4cb3-b1fd-1fd0b4554992_en?filename=Road_Safety_Thematic_Report_Professional_drivers_trucks_and_buses_2023.pdf).
- European Commission, [Facts and figures](https://road-safety.transport.ec.europa.eu/european-road-safety-observatory/data-and-analysis/facts-and-figures_en), including comparable reports and datasets for buses, HGVs, junctions, motorways, rural areas and single-vehicle crashes.

## Sources still required

- Vehicle-level and person-level DGT microdata (not published for download; request to DGT).
- Road network geometry, road class, junction form, curvature, lanes, median and roadside attributes.
- Posted speed limits and, where possible, observed speed distributions.
- Traffic volume or vehicle-kilometres by road, vehicle class, geography and time.
- Weather, daylight and roadworks data.
- Dated DGT campaign, enforcement and policy records.
- Fleet denominators by province (Parque de vehículos tables).
- Share of people who drive by age band, Spain: the ESRA dashboard does not expose it and no other national survey asks it (see `phase3_plan.md`).

No source should enter the analytical pipeline without a stable identifier, provenance record and documented reuse terms.
