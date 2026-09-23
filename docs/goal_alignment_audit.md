# Goal alignment audit

September 2026. An audit of the repository and the published site against the project's stated
goal, and a record of the changes made to close the gaps. It supersedes
[`refocus_audit.md`](refocus_audit.md) as the statement of direction; that document stays as the
record of the earlier refocus, whose corrections still stand.

## 1. The goal

> A Spain-wide road-risk analysis that explains how crash and fatality risk changes across time,
> driver groups, vehicle types and exposure, using DGT accident data combined with driver census,
> kilometres travelled and historical series.

The question it reduces to: **what changes when you stop looking at accident counts and start
measuring road risk properly?** Six pillars:

1. 2019–2024 risk trends, separating raw counts from exposure-adjusted risk.
2. Age and sex risk, from the driver census and travel or exposure proxies, not casualty counts.
3. Seasonality and mobility: whether apparent spikes and declines are changes in driving volume.
4. Speed as a severity factor, without causal attribution the data cannot support, but saying
   clearly what they suggest.
5. Alcohol, distraction and other factors, where DGT's tables are consistent enough across years.
6. Long-term structural change, distinguishing COVID-era distortion from genuine trends.

Not central unless better microdata are obtained: road-design analysis, causal claims about
campaigns, municipality-level hotspot modelling, sophisticated multivariate crash-causation models.

## 2. Status before this change

| Item | State |
|---|---|
| `main` (v1.0, `e0c16f9`) | Nine-question site (trends, timing, road users, geography, older drivers, severity, vehicles, policy, speed), 434 reconciliation checks, CI green, published on GitHub Pages |
| PR #17 (open) | "Refocus": cut the site to four analyses (severity, age against kilometres, vehicles per km, the 2006 break) plus context; added DGT's 2024 kilometres by owner age and the CORES fuel and toll-motorway traffic series; showed that the 2006 headline did not survive calendar-matched and out-of-sample tests; CI green, not merged |
| PR #18 (merged) | Relabelled the ESRA × MOVILIA older-driver denominator as an exploratory scenario; #17 then replaced it with kilometres by owner age |
| Other branches | `polish`, `dev-note`, `fix/q7-…` and the phase branches are merged history |

## 3. Audit against the goal

| Pillar | `main` | PR #17 | Verdict before this change |
|---|---|---|---|
| 1. 2019–2024 counts against risk | Trends page: 1993–2024 counts, DGT's own rates per vehicle and per resident; no 2019 base, no traffic denominator | Rates deleted; one context chart of deaths | **Missing.** The central comparison of the goal did not exist |
| 2. Age and sex | Older drivers against four denominators, one of them a synthetic ESRA × MOVILIA "travel-weighted" count; no sex analysis | Kilometres by owner age (sound); no sex analysis | **Half.** Age done well in #17; sex absent although tables 4.1.1 and 4.2 and the census carry it |
| 3. Seasonality and mobility | Month heatmap and hour × weekday grids of raw counts | Seasonality used only as an alternative explanation inside the 2006 test; the traffic series only as covariates there | **Missing as a question.** The traffic series needed were already in the repository |
| 4. Speed as a severity factor | Speed page republishing the DGT report's breakdowns and tables 6.1 shares | Only the 2016 recording discontinuity | **Missing.** No comparison of how deadly speed-related crashes are |
| 5. Alcohol, distraction, other factors | Declared out of reach ("requires person-level data") | Not addressed | **Missing, wrongly declared impossible.** The DGT report's factor table (2014–2023) was already transcribed in the interim layer |
| 6. Long-term structure and COVID | Descriptive trend page ("the fall stopped around 2013") | One context chart | **Partial.** No test of whether 2020–2024 departs from trend, in counts or per unit of traffic |
| Not central: multivariate crash models | Severity models a headline analysis | Severity the lead analysis | **Misaligned** |
| Not central: campaign or policy causation | 2006 break a headline analysis with a 12 % "coincided with" claim | 2006 break a headline analysis, correctly weakened to about 7 % | **Misaligned** |
| Not central: hotspot modelling | Province ranking page | Removed | Aligned in #17 |
| Vehicle types and exposure (in the goal statement) | Vehicles per km, 2022 | Kept | **Aligned** |

The pattern: the project had the data for every pillar (the census, the km estimates, the traffic
series and the report's factor tables were all in `data/raw/`) but had organised itself around
analyses the goal calls non-central. Neither `main` nor #17 asked the goal's question directly.

## 4. What this change does

It builds on PR #17 (merged into this branch, so its corrections and data come with it) and
re-centres the site on the goal's question. Seven analysis pages in the main navigation, one per
pillar plus vehicles; the severity model and the 2006 break in a second row labelled "supporting
analyses", each opening with a note saying why it is outside the central question.

| Pillar | Page | Method (module) | What it finds |
|---|---|---|---|
| 1 | `trends.html` | Crashes, deaths and hospitalised injured over residents, licence holders, registered vehicles and road fuel, indexed to 2019 with Poisson intervals; fuel-economy sensitivity; DGT km estimates checked against fuel (`risk_trends`) | 2024 deaths against 2019: +1.7 % as a count, −1.9 % per resident, −3.4 % per vehicle, +3.5 % per tonne of fuel, none beyond chance. Crashes fell 5–7 % per person and per vehicle, flat per unit of traffic. Hospitalised injured rose under every denominator, +5.5 % to +13 % |
| 6 | `long-run.html` | Joinpoint quasi-Poisson trends 1993–2019 for deaths, deaths per vehicle, deaths per tonne of fuel, turning points by QBIC, projected with prediction intervals (`risk_trends`) | All three find turning points near 2003 and 2011–2013: −11 % a year for a decade, then a plateau. As a count 2020 was 24 % below trend and 2022–2024 back on it. Per tonne of fuel 2020–2021 were **on** trend (the fall was traffic) and 2023–2024 were 16–17 % **above** it, outside the interval unless fuel economy improved about two points a year faster than before |
| 3 | `seasons.html` | Monthly deaths against road fuel, petrol and toll-motorway intensity; quasi-Poisson month effects with year effects, with and without a traffic offset; 2020 month by month (`seasonality`) | July 1.22× and August 1.14× the average month as counts; per unit of petrol 1.06× and 0.98×. Spring below average under every proxy; September and November above under two of three. April 2020: deaths −68 %, petrol −76 %; whether each kilometre got riskier depends on the proxy and is not claimed |
| 2 | `drivers.html` | Age: car-driver involvement per km, fatality once involved, deaths per km, 2024 (from #17). Sex: drivers involved and killed per licence-holder-year, 2022–2024, men against women, car and all motor vehicles; MOVILIA 2006 trips as a bounded travel proxy (`driver_risk`) | 75+: involvement per km 1.02× the 35–54 rate, killed once involved 3.93×. Men (car drivers): involved 1.41× per licence holder, about the size of the travel gap MOVILIA implies; killed once involved 2.57× (2.24–2.94). The excess is in what the crash does, not how often it happens |
| Vehicles | `vehicles.html` | Unchanged from #17 (`vehicles`) | Heavy truck 10.3× a car per vehicle, 2.5× per km |
| 4 | `speed.html` | Speed-related crashes and deaths from the DGT report against microdata totals for the same provinces (reconciled exactly, 48 new checks); rate ratios by road type and a quasi-Poisson model adjusted for road type and year; the 2016 recording break in tables 6.1 (`factors`, `speed`) | Speed recorded in 7 % of injury crashes and 22 % of deaths (2023). Deaths per crash 3.41× crude, **2.00× (1.69–2.36)** on the same kind of road; 5.9× on urban streets, 1.2–1.9× elsewhere. Stated as an association with two biases that cannot be measured |
| 5 | `factors.html` | Share of injury crashes with each recorded factor, 2014–2023; every year-to-year change tested against a recording-break rule; trends read only within unbroken runs (`factors`) | Interurban alcohol 5.5 % → 8.2 %, no break. Inappropriate speed 10.0 % → 6.9 %, no break. Interurban distraction stable at about 26 %. Urban distraction breaks in 2016 and 2019, urban alcohol in 2016, drugs throughout: not comparable |

Engineering added with it: three modules (`risk_trends`, `seasonality`, `factors`), sex functions
in `driver_risk`, three plot types, a reconciliation check family (`speed_report_scope`, 48 checks,
482 in all), nine figures, 22 result tables, five new pages, pointer pages for the two renamed
slugs, and tests for each method, including synthetic recoveries (joinpoint turning points, an
offset that removes a known season, the break rule).

## 5. Demoted, not deleted

- **Severity models** (`severity.html`): a multivariate model of crash outcomes is what the goal
  says not to centre. The page is kept, unchanged in substance, behind a supporting-analysis note.
- **The 2006 break** (`policy.html`): the goal rules out causal claims about campaigns. The page is
  kept because it shows why: under the right tests the headline weakened from 12 % to about 7 %
  with an out-of-sample rank of fourth of fifteen.
- **Context page**: its three parts moved to where they are used (the long-run chart, the speed
  recording break); `context.html` and `older-drivers.html` now refresh to their successors.

## 6. What the current data cannot support, and what would change that

| Wanted | Why not now | What would unlock it |
|---|---|---|
| Deaths per kilometre by year | No annual all-roads vehicle-km series; DGT's 2022 and 2024 estimates are built differently | A consistent DGT kilometre series, or the Ministerio de Transportes' annual vehicle-km on the state network (*Mapa de tráfico*) as a measured interurban denominator |
| Kilometres by sex | No Spanish source | A travel survey with driver-only kilometres by sex (a new MOVILIA wave or DGT's own survey) |
| Severity of alcohol and distraction crashes | The report gives deaths by factor for speed only | INTCF toxicology reports on killed drivers (a consistent annual series), or DGT deaths by factor |
| Whether rising recorded alcohol is behaviour or testing | Enforcement is not in the files | DGT's annual alcohol and drug test statistics |
| Factor interactions, belts, helmets, driver-level risk | Microdata are one row per crash | DGT's vehicle and person microdata, on request to the Observatorio Nacional de Seguridad Vial |
| Road design, hotspots | No geometry, coordinates or volumes | Section identifiers with traffic counts |

## 7. Decisions left to the author

- **Merge order.** This branch contains PR #17. Merging it lands #17's work too, so #17 can be
  closed after this merges (or merged first; the result is the same).
- **The ESRA × MOVILIA scenario** that PR #18 relabelled stays off the site, as in #17. MOVILIA
  2006 is used only for the male-to-female trip ratio, read as a lower bound.
- **The recording-break threshold** (25 % in one year) is a rule, not a test; every change is
  published in `factor_changes.csv` so another threshold can be applied.
