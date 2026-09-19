# Phase 5: vehicles per kilometre driven

Plan date: 19 September 2026. Phase 5 of [`analytics_plan.md`](analytics_plan.md) is question Q6:
how dangerous are heavy vehicles and buses per kilometre driven, compared with cars, vans and
motorcycles? It is the sixth of nine phases (0 to 8); after it, three remain (6 policy case study,
7 speed and context, 8 publish). Same working rules: Python only, one commit per step on branch
`phase-5`, `ruff` and `pytest` before each commit, tables and figures committed, static HTML output,
squash-merge at the end.

## 1. What the data allow

The plan of 18 September assumed involvement by vehicle type existed only for 2024 and that Q6 would
have to lean on occupant deaths from the microdata. Phase 3 added the yearbook workbooks for 2020–2023,
and each carries the same two tables as 2024, so the case study can be built entirely on 2022, the
year of the kilometre estimates:

| Input | Source | What it gives for 2022 |
|---|---|---|
| Vehicle-kilometres | `km_itv_2022/media_km_antiguedad_tipo_2022.xlsx` (already parsed as `km_medios_2022`) | fleet size and mean annual km for 7 vehicle types × 5 age bands; fleet × mean km = vehicle-km |
| Involvement | `tablas_estadisticas_2022.xlsx`, TABLA 2.3 | vehicles of each of 22 types involved in injury crashes and in fatal crashes, by zone |
| Occupant victims | `tablas_estadisticas_2022.xlsx`, TABLA 2.2 | drivers and passengers killed, hospitalised and not hospitalised, per vehicle type and zone |
| Occupant deaths, long run | series `Cond-Pasj_MU_I-U` (1993–2024) and microdata `TOT_*_MU30DF` (2016–2024) | the same 30-day occupant deaths by vehicle group; the two agree exactly in 2022 |
| Registered fleet | series `Tasas_Acc_Vic` | national fleet total (35.7 million in 2022) to state how much of it the km table covers |

Three limits are stated on the page and drive the design:

- **Involvement is only in the yearbook tables**, never in the microdata, so nothing below the level of
  vehicle type × zone × severity is possible (no hour, road type or crash type by vehicle).
- **The kilometre estimates are modelled**, not measured: annualised ITV odometer readings imputed to the
  fleet (the methodology report gives 19–45 % explained variance per vehicle and says the figures are
  valid for aggregates only). They exist for one year and for seven types; buses, heavy trucks and
  light trucks are separate, but tractors, quadricycles and "other" have no denominator.
- **Rates per kilometre and per vehicle answer different questions.** A heavy truck drives about ten
  times the kilometres of a car, so ranking by registered vehicle and ranking by vehicle-km disagree;
  both are shown, with the kilometres per vehicle that explain the gap.

The type mapping between the km table and the yearbook tables (kept in one dictionary so the page can
print it): car = "Turismo sin remolque" + "con remolque" + "de SP hasta 9 plazas"; van = "Furgoneta";
light truck (≤ 3,500 kg) = the two "Camión <=3.500 kg" rows; heavy truck (> 3,500 kg) = the two
"Camión >3.500 kg" rows + "Tractocamión" + "Vehículo articulado"; bus = "Autobús (no escolar)" +
"Autobús escolar"; motorcycle and moped map one to one. Pedestrians, bicycles, VMP, machinery,
quadricycles, rail and unknown are listed as "no kilometre denominator".

Measures, each for 2022 and each with an exact Poisson interval (`rates.poisson_interval`):

| Measure | Numerator | Denominator |
|---|---|---|
| Involvement in injury crashes | vehicles of the type involved (TABLA 2.3) | billion vehicle-km; 100,000 registered vehicles |
| Involvement in fatal crashes | vehicles of the type involved in 30-day fatal crashes (TABLA 2.3) | same |
| Occupant deaths | drivers and passengers of the type killed within 30 days (TABLA 2.2) | same |
| Occupant death share | occupant deaths ÷ vehicles involved in fatal crashes | (a ratio, not a rate: how often the fatal crash a vehicle is in kills its own occupants) |

The last row is what separates heavy vehicles from the rest: a heavy truck in a fatal crash rarely loses
its own occupants, so its occupant-death rate is low while its fatal-crash involvement per kilometre is
not.

## 2. Build steps

### Step 1 — Ingest the vehicle tables for 2020–2024 (`io_tables.py`, `validate.py`)
- Generalise `read_table_2_3(year)` to the five workbooks (same layout in all) and add
  `read_table_2_2(year)`, which reads the single interurban + urban sheet of 2020–2022 and the split
  `2.2.I` / `2.2.U` sheets of 2023–2024 into one tidy frame (`unit_type`, `zone`, `role` in driver,
  passenger, pedestrian, `metric` in involved, victims, deaths_30d, hospitalised_30d,
  non_hospitalised_30d). Interim outputs `tables_units_by_type` and `tables_victims_by_mode`, both with
  a `year` column; the 2024-only outputs keep their names.
- Two validation checks: TABLA 2.3 vehicle totals against the microdata `TOTAL_VEHICULOS` sum per year
  (2024 is known to differ by 66 vehicles, so the tolerance is 0.1 %), and TABLA 2.2 occupant deaths per
  vehicle group against the microdata `TOT_*_MU30DF` sums for 2020–2024 (exact).
- Tests: the 2022 totals in the parsed frames (183,078 vehicles, 2,940 in fatal crashes; 1,273 deaths
  on interurban roads, 1,746 in all) and the checks passing; a synthetic-sheet test for the two 2.2
  layouts.

### Step 2 — Vehicle-km rates (`vehicle_km.py`, `summaries.py`)
- `VEHICLE_GROUPS`: the mapping above with English labels, plus the "no denominator" list.
- `vehicle_km_2022()`: fleet, mean km and vehicle-km per group (summed over age bands) with the share
  of the fleet and of the kilometres; coverage of the national fleet stated as a number.
- `rates_2022()`: one row per group and measure with count, denominator, rate and interval, per
  billion km and per 100,000 vehicles, for all zones and split interurban / urban (the km cannot be
  split by zone, so the zone rows share the denominator and say so).
- `km_by_age_2022()`: mean km and fleet by group × age band, to show where the kilometres sit.
- `occupant_deaths_series()`: 1993–2024 occupant deaths by group from the series (light trucks and
  vans are one column there), indexed to 2013 so the groups are comparable.
- Tables: `q6_vehicle_km_2022.csv`, `q6_rates_2022.csv`, `q6_km_by_age_2022.csv`,
  `q6_occupant_deaths_series.csv`, `q6_involvement_by_year.csv` (2020–2024 counts, for context only),
  `q6_vehicle_groups.csv`. Tests: rates recompute from their columns; intervals contain the rate; the
  group sums equal the table totals minus the excluded rows.

### Step 3 — Figures
- Dot plot with interval whiskers of the three rates per billion km, groups ordered by fatal-crash
  involvement, log axis (rates span two orders of magnitude between buses and motorcycles).
- Paired dot plot: rank per 100,000 vehicles against rank per billion km, with lines joining the same
  group, to show which groups move.
- Heatmap of mean annual km by group × age band.
- Small multiples of occupant deaths 1993–2024 by group, indexed to 2013.

### Step 4 — Site
- `vehicles.html` ("Vehicles per kilometre"): tiles (share of fleet, of kilometres and of fatal-crash
  involvements for heavy trucks), the rates table and figure, the per-vehicle versus per-km comparison,
  the occupant-death share, kilometres by age, the long-run series, the group mapping, and a limits
  section written from the three points above. Overview card; data page gains the two checks.

### Step 5 — Docs, PR, merge
- `analytics_plan.md` phase table and the Q6 row (2022 involvement is available, so the 2024 caveat
  goes), README results and roadmap, `data/README.md` interim table, notebooks map,
  `phase5_plan.md` outcome section; PR; squash merge.

## 3. Outcome (19 September 2026)

All five steps are merged. What was built, with the deviations from the design above:

- `vehicles.py` (not `vehicle_km.py`) holds the group mapping and the Q6 summaries; `io_tables.py`
  reads tables 2.3 and 2.2 for 2020–2024 (`tables_units_by_type`, `tables_victims_by_mode`);
  `validate.py` gains two checks (390 in all): vehicles involved within 0.1 % of the microdata (exact
  in 2020–2022, 48 and 66 vehicles short in 2023 and 2024) and occupant deaths by group equal to the
  microdata death columns in every year. Seven `q6_*` tables, four figures, `vehicles.html`.
- **Six rate groups, not seven.** Taken separately, trucks up to 3,500 kg showed a fifth of the van
  rate: the crash record codes most light commercial vehicles as "Furgoneta" while the register
  splits them, so only the sum has the same meaning in numerator and denominator. Vans and light
  trucks are one group on the page, as they are in the series.
- Results, 2022: per billion km, motorcycles are in a fatal crash 43.5 times, mopeds 20.7, buses
  15.7, heavy trucks 10.7, vans and light trucks 4.5, cars 4.3. Per 100,000 registered vehicles the
  order is buses 73, heavy trucks 58, motorcycles 12, vans and light trucks 6.6, cars 5.6, mopeds 3.6;
  a heavy truck drives 53,600 km a year against 13,100 for a car. Occupant deaths per fatal-crash
  involvement: motorcycles 0.93, mopeds 0.92, cars 0.52, vans and light trucks 0.35, buses 0.31,
  heavy trucks 0.18. The seven km-table types cover 91 % of the registered fleet.
- The verification item comparing a fleet-wide rate with `Tasas_Acc_Vic` was dropped: the yearbook
  rate counts all deaths per registered vehicle of every kind, which is not the quantity any row of
  this page estimates. The reconciliation is the two validation checks instead.

## 4. Verification

- Occupant deaths from TABLA 2.2 equal the microdata and the series for every group and year.
- `pytest` (122), `ruff`, idempotent `ingest.py tables`, `analyse.py all` and `build_site.py`,
  headless screenshots at 1280 px and 390 px with no horizontal overflow.
