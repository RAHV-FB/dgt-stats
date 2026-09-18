# Data and evidence sources

This is the working source register. It will be expanded into machine-readable metadata during ingestion.

## Official Spanish data

### DGT en Cifras

- Provider: Dirección General de Tráfico.
- URL: https://www.dgt.es/menusecundario/dgt-en-cifras/
- Relevant collections: annual definitive injury-crash statistics, historical series, annual crash microdata, driver census, vehicle fleet and enforcement data.
- Role in project: primary source for Spanish crash, person, vehicle and exposure-related data.
- Main caution: provisional and definitive series, and 24-hour and 30-day fatality definitions, must not be mixed.

## Initial local source set

| Dataset or report | Coverage | Proposed role | Main limitation to resolve |
|---|---:|---|---|
| `Accidentes-con-victimas-Tablas-estadisticas-2024.xlsx` | 2024 | Official reconciliation totals | Aggregated tables, not crash-level observations |
| `Series-Historicas-Anuario-Accidentes-2024.xlsx` | Historical–2024 | Trend baselines | Definitions and breaks in series require review |
| `conductores_censo_*_2023/2024/2025.txt` | 2023–2025 | Licensed-driver exposure context | A licensed-driver count is not kilometres driven |
| `Censo-de-conductores-Tablas-estadisticas-2025.xlsx` | 2025 | Published driver-census controls | Aggregate dimensions may differ from raw text extracts |
| `Km_recorridos_anuales_estimados.xlsx` | To audit | Vehicle-kilometre denominator | Estimation method and uncertainty must be preserved |
| `Media_km_recorridos_ antiguedad_tipo de vehículo.xlsx` | To audit | Vehicle age/type exposure | Small cells and aggregation level require review |
| `KM_Recorridos_ITV_Parque.pdf` | Methodology | Explain annual-distance estimates | ITV selection and survivorship biases may remain |
| `INF_TEMA_4_Factor-Velocidad_v5_FINAL.pdf` | Thematic | Speed definitions and DGT context | Report evidence is contextual, not a substitute for microdata |
| `INF_TEMA_8_PersonasMayores_v4_FINAL_nipo.pdf` | 2023 | Older-road-user context | Population and exposure denominators must match |
| `INF_SEMANASANTA_2026_v8_FINAL.pdf` | Easter 2026 | Possible campaign/holiday case study | Short, seasonal and potentially provisional period |

## Research and comparison sources

- European Commission, European Road Safety Observatory, [Thematic reports](https://road-safety.transport.ec.europa.eu/european-road-safety-observatory/data-and-analysis/thematic-reports_en).
- European Commission (2024), [Main factors causing fatal crashes](https://road-safety.transport.ec.europa.eu/document/download/a7428369-8eaf-4032-806e-ea08b46028c0_en?filename=ERSO-TR-MainCauses.pdf).
- European Commission (2025), [Alcohol and drugs](https://road-safety.transport.ec.europa.eu/document/download/c1bc212c-170f-4c68-a5a4-cad17035befb_en?filename=ERSO-TR-alcohol_drugs_2026.pdf).
- European Commission (2025), [Speed and speeding](https://road-safety.transport.ec.europa.eu/document/download/9826c063-bc55-423e-84a3-24200dca3547_en?filename=ERSO-TR-speed_2026.pdf).
- European Commission (2023), [Professional drivers of trucks and buses](https://road-safety.transport.ec.europa.eu/document/download/e19cf119-eed4-4cb3-b1fd-1fd0b4554992_en?filename=Road_Safety_Thematic_Report_Professional_drivers_trucks_and_buses_2023.pdf).
- European Commission, [Facts and figures](https://road-safety.transport.ec.europa.eu/european-road-safety-observatory/data-and-analysis/facts-and-figures_en), including comparable reports and datasets for buses, HGVs, junctions, motorways, rural areas and single-vehicle crashes.

## Sources still required

- Crash-level DGT microdata and its codebook for a consistent multi-year window.
- Road network geometry, road class, junction form, curvature, lanes, median and roadside attributes.
- Posted speed limits and, where possible, observed speed distributions.
- Traffic volume or vehicle-kilometres by road, vehicle class, geography and time.
- Weather, daylight and roadworks data.
- Dated DGT campaign, enforcement and policy records.
- Population, fleet and licensed-driver denominators at matching geographic and temporal levels.

No source should enter the analytical pipeline without a stable identifier, provenance record and documented reuse terms.
