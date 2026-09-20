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

## 3. Outcome (19 September 2026)

All five steps are merged. What was built, with the deviations from the design above:

- `policy.py` holds the series, the intervention registry, the segmented and difference-in-
  differences fits, the placebos and the sensitivity tables; the eight `q8_*` tables are written by
  `analyse.py tables` in about six seconds. `plots.intervention()` and a highlighted variant of the
  dot plot draw the five figures. `policy.html` is the page.
- The negative-binomial sensitivity uses the dispersion from the Poisson fit (Pearson chi-square
  solved for alpha) inside a GLM rather than a maximum-likelihood negative binomial: the likelihood
  search did not converge reliably when the data are close to Poisson, and the moment version is
  deterministic.
- Results, 2006: level change −12.0 % (−17.2 to −6.4) at July 2006 against a pre-trend of −4.7 % a
  year; slope change +4.2 % a year, not distinguishable from zero; 586 deaths below the trend over
  the seventeen clean months; placebo rank 1 of 39 (the other estimates run from −8.1 % to +8.4 %).
  The estimate holds for 24-hour deaths, interurban roads, the fleet offset and the negative binomial;
  it is −7.6 % and not significant on urban streets; with the window run to December 2009 and a
  second break at the Penal Code reform it falls to −6.0 % (n.s.) while the reform takes −7.9 %.
- Results, 2019: −13.5 % (−22.4 to −3.5) on conventional roads relative to motorways and dual
  carriageways in the clean window, control change +2.5 %. The design fails its placebo: a break in
  January 2018 gives −11.7 % (−18.3 to −4.5), so the divergence predates the limit; extended through
  the pandemic the term turns to +30 %. The page makes no claim about the limit.
- The two groups were built from `road_group` (conventional against motorway and dual carriageway),
  which puts road-type code 5 ("Carretera Convencional de doble calzada") in the control group; the
  final review rebuilt them from the raw codes (5 and 6 against 1, 2 and 3) because most code 5
  crashes are coded 6 from 2021, so the estimates above are those of the phase, not of the site
  (see [`final_review.md`](final_review.md) and `methodology.md`, section 7).
- A review pass caught the covariance of the two-group model: Newey–West on the stacked panel had
  treated the control series as the continuation of the treated one. The fit now uses the panel
  form (within-group lags), which widens the 2019 intervals slightly and changes no conclusion; the
  page's conditional sentences were also aligned so that the tile, the paragraph and the reading note
  cannot disagree.
- The yearbook's zone sheets differ from its all-roads sheet by one death in four months of 1995;
  the test records it.

## 4. Verification

- The 2006 fit and the raw twelve-month comparison (−11.4 %) point the same way once the pre-trend
  (−4.7 %) is taken out, and the page prints both.
- The 2019 control group shows no break of its own at February 2019 (+2.5 %, interval includes zero).
- `pytest` (130), `ruff`, idempotent `analyse.py all` and `build_site.py`, headless screenshots at
  1280 px and 390 px with no horizontal overflow.
