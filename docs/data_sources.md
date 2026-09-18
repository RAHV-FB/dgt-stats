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
- Population, fleet and licensed-driver denominators at matching geographic and temporal levels.

No source should enter the analytical pipeline without a stable identifier, provenance record and documented reuse terms.
