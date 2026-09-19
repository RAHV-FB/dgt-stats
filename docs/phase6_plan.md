# Phase 6: policy case study

Plan date: 19 September 2026. Phase 6 of [`analytics_plan.md`](analytics_plan.md) is question Q8:
did a major policy change coincide with a measurable break in monthly road deaths? It is the seventh
of nine phases (0 to 8); after it, two remain (7 speed and context, 8 publish). Same working rules:
Python only, one commit per step on branch `phase-6`, `ruff` and `pytest` before each commit, tables
and figures committed, static HTML output, squash-merge at the end.

## 1. What the data allow

Two interventions, two designs, in the order of preference the analytics plan set:

**The points-based licence, 1 July 2006** (Ley 17/2005). The yearbook series gives deaths per month
for 384 months, January 1993 to December 2024, at 30 days and at 24 hours, for all roads, interurban
roads and urban streets. Around the intervention the series runs at 350–440 deaths a month, so a
level change of a few percent is estimable. The design is a segmented regression (interrupted time
series): a count model of monthly deaths on a linear trend, month-of-year terms, a level change at
July 2006 and a slope change after it. Three things stand in the way of a causal reading and the
page states each one:

- Other measures arrived close by: the speed-camera programme of the 2005–2008 road-safety plan, and
  the Penal Code reform on driving offences of 2 December 2007 (Ley Orgánica 15/2007). The clean
  post-period is therefore July 2006 to November 2007 (17 months); a longer window adds a second
  break at December 2007 and is reported as such.
- The 2008 recession cut traffic. The fleet series (`Tasas_Acc_Vic`, annual) enters as an offset in
  a sensitivity fit; there is no monthly traffic series.
- Deaths were already falling: the pre-trend must be shown and the level change judged against a
  placebo distribution (the same model with the break placed at every other month of the pre-period),
  not only against its own interval.

**The 90 km/h limit on conventional roads, 29 January 2019** (Real Decreto 1514/2018). The series
cannot isolate conventional roads, but the microdata can: monthly 30-day deaths by road group, 2016 to
2024, give about 58 deaths a month on conventional roads (treated) against about 42 on motorways and
dual carriageways together (not treated, same weather, same economy). The design is a
difference-in-differences interrupted series: both groups in one count model with a shared trend,
month terms, a group term, a post term and a post × conventional term, which is the estimate. The
clean post-period is February 2019 to February 2020 (13 months); the pandemic from March 2020 is
excluded from the main fit and handled with period indicators in a sensitivity fit to December 2024.
Placebo breaks at January 2017 and January 2018 check the design.

The urban 30 km/h default of May 2021 stays out: its clean pre-period is the pandemic year, so no
model on these data can say anything.

**Model choice.** Monthly deaths are counts with overdispersion and serial correlation. The main fits
are Poisson regressions with heteroskedasticity-and-autocorrelation-consistent standard errors
(Newey–West, 12 lags), which keep the estimates simple and the intervals honest; a negative-binomial
fit is the sensitivity. `statsmodels` is fine here: the design has 384 rows, not 875,000. Effects are
reported as percentage changes in the monthly level with 95 % intervals, and the slope change as an
annualised percentage. The wording follows section 8 of the analytics plan: "coincided with" by
default; "reduced" only where the pre-trend is flat or accounted for, the placebo distribution puts the
estimate in its tail and the sensitivity fits agree.

## 2. Build steps

### Step 1 — Monthly series and intervention registry (`policy.py`)
- `INTERVENTIONS`: name, date, the series or groups it applies to, pre- and post-windows, the
  confounders to mark (December 2007) and the periods to exclude (March 2020 onwards for 2019).
- `monthly_series(metric, zone)` from `series_monthly` with a continuous month index;
  `monthly_by_road_group()` from the microdata (conventional against motorway + dual carriageway);
  `fleet_offset()` interpolating the annual fleet to months.
- Tests: 384 months, no gaps, the 2006 values above; road-group months sum to the yearbook deaths.

### Step 2 — Fitting (`policy.py`)
- `segmented_fit(series, intervention, offset=None, family="poisson")`: design matrix (trend, month
  dummies, level, slope), Poisson GLM with HAC covariance, tidy coefficient table, level and slope
  changes with intervals, dispersion statistic, fitted and counterfactual series.
- `placebo_fits(series, intervention)`: the level change re-estimated with the break at every month
  of the pre-period that leaves 24 months on each side; the rank of the true estimate.
- `did_fit(panel, intervention)`: the two-group model, its post × treated estimate, and the same
  placebo at 2017 and 2018.
- `sensitivity(...)`: 24-hour deaths, interurban only, the long window with the December 2007 break,
  the fleet offset, negative binomial; one table with one row per variant.
- Tables: `q8_points_fit`, `q8_points_series`, `q8_points_placebo`, `q8_points_sensitivity`,
  `q8_speed_fit`, `q8_speed_series`, `q8_speed_placebo`, `q8_speed_sensitivity`. Registered in
  `summaries.SUMMARIES` (the fits take seconds, so `analyse.py tables` runs them).
- Tests: a synthetic series with a known level change is recovered within tolerance; the placebo
  rank on that series is 1; the DiD recovers a known treated-group change.

### Step 3 — Figures
- `plots.intervention()`: observed monthly counts, the fitted line and the dashed counterfactual,
  the intervention marked, confounder dates shaded. One for 2006 (all roads), one for 2019 (two
  panels, conventional and control, same scale).
- Placebo distributions as dot plots with the true estimate marked, one per intervention.
- Pre-trend panel: the 24 months before each intervention with the fitted trend only.

### Step 4 — Site
- `policy.html`: what an interrupted series is and what it can and cannot show, the 2006 result with
  its interval, placebo rank and sensitivity table, the 2019 result the same way, the confounder
  timeline, and a limits section. Overview card; data page definitions gain the two model
  descriptions.

### Step 5 — Docs, PR, merge
- `analytics_plan.md` phase table and Q8 row, README results and roadmap (the "evaluate one
  well-defined policy intervention" line), notebooks map, `phase6_plan.md` outcome section; PR;
  squash merge.

## 3. Verification

- The 2006 fit reproduces the raw comparison already visible in the series (July 2006 to June 2007
  against the twelve months before) once trend and season are removed, and the page prints both.
- Placebo distributions have the expected spread; the true estimate's rank is reported whatever it is.
- The 2019 control group shows no break of its own at January 2019.
- `pytest`, `ruff`, idempotent `analyse.py all` and `build_site.py`, headless screenshots at 1280 px
  and 390 px.
