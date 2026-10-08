# Final review and report

Task 25. This document records the final review of the rebuild (Tasks 1–24) and answers the
twenty questions of the final report. Every figure below is taken from a committed table or from
the research document named beside it; none is new. Results that are complete are kept apart from
work that waits on external data (the last section).

The final audit that followed this review changed several results: the distance corrections
moved the per-km ratios (18–29 from 2.57 to 2.53, 65 and over from 1.16 to 1.19), the coverage of
DGT's kilometres widened their sensitivity ranges, the 75+ figures were constrained, the method
fixes of October 2026 (the Madrid profile standardised to Spain's older population, the licence
split counted one way, DGT's owner-age kilometres made a bound, and every sampling interval
printed to the precision its Monte Carlo error supports) moved the ends of those ranges, and the
severity model was re-evaluated with every choice nested. The figures below are the current ones;
where a first-published or later superseded figure differed, it is given and labelled as such. The
acceptance report of that audit is [`ACCEPTANCE_REPORT.md`](ACCEPTANCE_REPORT.md).

The work is on the branch `cl/inspiring-wozniak-uqpemm`, in pull request
[RAHV-FB/dgt-stats#25](https://github.com/RAHV-FB/dgt-stats/pull/25). The site at
<https://rahv-fb.github.io/dgt-stats/> is published from `main`, so it shows the rebuilt pages only
once that pull request is merged.

## How the review was done

The review did not assume that earlier calculations were correct. It had three parts.

1. **A clean rebuild.** The EMEF tables (`scripts/emef.py all`), the driver-age rates
   (`scripts/exposure_risk.py all`), every figure (`scripts/analyse.py figures`) and the site
   (`scripts/build_site.py`) were regenerated from the raw files. Every committed table, figure and
   page was reproduced byte for byte; `git status` showed no change. CI rebuilds the national and
   regional data layers from the raw files on every push, and passed on every push before this
   review.
2. **An independent recomputation.** The headline quantities were recomputed directly from the raw
   files with separate code that does not call the repository's package (next section).
3. **A reading of every document and page against the results.** This found statements that the
   rebuild had made stale. They are listed under point 15 and were corrected.

### Independent recomputation

The scripts read the raw files directly; the package's source was read only to learn file
layouts and definitions.

| Quantity | Committed | Recomputed | Verdict |
|---|---|---|---|
| EMEF weighted population 16+, 2022 / 2023 / 2024 | 4,853,758 / 4,927,771 / 5,019,771 | the same; the technical documents' universes | agree |
| Share of residents who drove on the day, 2022–2024: 16–29 / 30–44 / 45–64 / 65+ | 19.8 / 37.2 / 40.4 / 18.9% | the same, and every sex × age cell to four decimals | agree |
| Car-driver trips per resident, same groups | 0.571 / 1.197 / 1.296 / 0.551 | the same | agree |
| Car driver against passenger | codes 12 and 13 | the dictionaries' labels "Cotxe com a conductor/a" and "Cotxe com a acompanyant"; 129 trips with both stages | agree |
| Method A shares of car km: 16–29 / 30–44 / 45–64 / 65+, as first published (now 0.1139 / 0.2787 / 0.4770 / 0.1304) | 0.1126 / 0.2765 / 0.4774 / 0.1336 | the same, from INE's 1 July 2024 single ages | agree |
| Private-car drivers involved, 2024: 18–29 / 30–44 / 45–64 / 65+ | 21,234 / 28,775 / 35,092 / 11,425 | the same from tables 4.2 I+U; also 65–74 6,970, 75+ 4,455, aged 15–17 41, unknown age 2,234, public-service cars 1,852 | agree |
| Drivers killed, same groups | 88 / 113 / 163 / 130 | the same from table 4.1.1 | agree |
| DGT car km, all cars / less taxis and ride-hailing | 292.99 / 289.78 bn | the same | agree |
| Involvement ratio to 45–64 per km, as first published (now 2.53 / 1.40 / 1 / 1.19 after the final audit's distance corrections) | 2.57 / 1.42 / 1 / 1.16 | 2.566 / 1.416 / 1 / 1.164; deaths 2.29 / 1.20 / 2.85 | agree |
| Barcelona working days, 2025 | 248 | 248 (50 Saturdays, 67 Sundays or holidays); working-day car drivers 652 / 981 / 1,294 / 354 and 205 of unknown age, recounted from the raw file | agree |
| Calculator calibration, 2016–2023, as first published (now 12.4% against 12.3% on the 11,611 crashes on choosable roads, nested, all 10 groups inside) | 12.5% predicted, 12.6% observed | 1,616.4 predicted against 1,627 fatal of 12,961 (12.47% against 12.55%); every band inside the observed interval | agree |
| Ratio of 65+ to 45–64 km per resident, as first published (now 0.40) | 0.41 | 0.35–0.36 with fixed band midpoints, 0.38–0.40 once the 461 unbanded trips are imputed from duration | consistent: the gap is the treatment of unbanded trips, which the sensitivity analysis already covers |

The recomputation also found errors of rounding and wording in the research documents, which were
corrected (point 15). No calculation in a committed table was found to be wrong.

### The verification checklist

| Item | How it was checked | Result |
|---|---|---|
| Raw-source reconciliation | the 482 reconciliation checks against DGT's published totals (`validate.run_all`), rerun by CI on every push; the SHA-256 of every raw file against `data/raw/manifest.csv` (`pytest -m slow`) | all pass |
| EMEF ingestion and weighting | 154 structural checks (`emef_checks.csv`; 142 when first published): sample sizes and weighted totals equal the survey's technical tables every year; fifteen published 2024 figures reproduced to their rounding (`emef_reproduction.csv`); independent recount above | all pass |
| Car driver against passenger | code 12 (car driver) and 13 (car passenger) read from every year's dictionary and tested; a passenger stage never makes a driving trip | confirmed |
| Distance estimation | the 2021 distance report's benchmarks reproduced (8.95 against 8.9 km for a driving trip, 8.94 as first published; road km per mobile person within 8% by age); the duration-only treatment of unbanded trips checked against banded trips under 100 km (1.05 times the band-based total overall, within 14% in every duration class up to two hours, 1.82 times at 120–180 minutes; as first published, with the bound at 100 km/h and an earlier version of the check, 1.03 overall and within 10% in every year and age group) | confirmed up to two hours; the treatment of long and unbanded trips is carried into the sensitivity ranges |
| Age-group handling | `age4` collapses exactly onto `age3` (tested); the 16–29 group matched to drivers aged 18–29; INE single ages summed without the file's overlapping aggregates (tested) | confirmed |
| Workday exposure | working days only in the EMEF; Barcelona's 2025 calendar of 248 working days built from the Catalan and local holidays and tested | confirmed |
| National extrapolation | Method A recomputed independently (above); Methods C and D as sensitivity and comparison | confirmed |
| Crash-numerator compatibility | private cars only, public-service cars removed from both numerator and denominator; drivers of unknown age left out of the rates and the effect stated (2.3%) | confirmed; the wording of one document corrected (point 15) |
| Uncertainty | bootstrap replicates crossed with gamma draws of the counts (50 per replicate for the national and Barcelona rates since October 2026, one per replicate when first published); the Monte Carlo error of every interval end estimated, and the ends printed to the precision it supports; intervals and sensitivity ranges reported separately throughout | confirmed |
| Model performance | rolling-origin scores of every model against a table of the same records (`sev_rolling_scores`, `review_*`); for the published model the evaluation is nested, every choice made on earlier years (`sev_choices`, `sev_nested_steps`) | confirmed (points 1–3) |
| Model calibration | predicted against observed in ten groups of predicted risk on years that played no part in fitting or choosing the model (`sev_calibration`), and by year, zone and province (`sev_rolling_scores`) | all ten groups' mean predictions inside the observed 95% interval (nine of ten before the province intercepts were nested); outside it in 2016, on urban streets, and on interurban roads in Girona and Tarragona |
| Frontend inference | the browser engine against the Python model on 302 scenarios under Node, and on 120 scenarios in Chromium on the built page, to 10⁻¹⁰; the comparison of two crashes against `compare_exported` | agree |
| Website conclusions | every number in page prose is formatted from a table at build time; qualitative words are guarded by build checks; tests fail on a number or year typed into page code | the build and the tests pass |

## The twenty points

### 1. Models retained, rebuilt and removed

| Model | Decision |
|---|---|
| Catalan crash severity, original boosted trees | **Rebuilt** as the calculator model; the original is retired from the site |
| Catalan crash severity, calculator (penalised logistic regression) | **Kept**: the public model |
| Catalan "retrospective administrative" variant | **Removed**: its gain (+0.006 ROC-AUC) came from fields recorded after the event |
| Barcelona crash severity (logistic) | **Removed**: no gain over a table of accident type (0.737 against 0.734) |
| Barcelona person severity (boosted trees) | **Research only**: 58 serious or fatal cases in the test months |
| Catalan model on DGT- or Barcelona-common variables | **Research only**: transfer tests |
| DGT crash severity (association model) | **Research only**: the fields left unrecorded where they apply rank fatal crashes on their own (ROC-AUC 0.68; 0.72 as first published, before cells that do not apply were set aside) |
| Monthly road deaths forecast | **Withdrawn** as a forecast: 6.6% error against 5.9% for last year's count in the ordinary held-out years; the page is a withdrawal notice |

Source: [`ML_MODEL_REVIEW.md`](ML_MODEL_REVIEW.md).

### 2. Strongest validated severity model

The penalised logistic regression behind the calculator, trained on the Servei Català de Trànsit
file (22,638 crashes with a death or serious injury, 2010–2023, 2,822 fatal; the 1,840 on
conventional roads with no named owning network are left out). It was validated by
nested rolling origin over eight years (each of 2016–2023 predicted by a model whose penalty,
specification, through-town rule and province intercepts were chosen, and whose coefficients were
fitted, on earlier
years only; 11,611 crashes on the roads a reader can choose, 1,429 fatal), by the stability of its
contrasts across periods and areas, and by bootstrap refits. The transfer tests of the original
Catalan model, on DGT and Barcelona records, bear on its reach: its probabilities describe
Catalonia and are likely to be low elsewhere. Gradient-boosted trees rank a little better
(ROC-AUC 0.748 against 0.739) but give no interval for an estimate and cannot be read term by
term. Source: [`SEVERITY_CALCULATOR.md`](SEVERITY_CALCULATOR.md).

### 3. Model performance against baseline

| Model, nested rolling origin 2016–2023 | ROC-AUC (95% CI) | Brier skill | Log loss | Calibration slope | Mean predicted (observed 12.3%) |
|---|---|---|---|---|---|
| Calculator model | 0.739 (0.725–0.753) | 0.096 | 0.331 | 1.03 | 12.4% |
| Gradient-boosted trees | 0.748 (0.734–0.761) | 0.102 | 0.329 | 1.08 | 12.3% |
| Fatal share of road × crash type | 0.709 (0.694–0.723) | 0.069 | 0.342 | 1.08 | 12.2% |

The model improves on the table by +0.030 ROC-AUC (paired interval +0.021 to +0.040) and lowers
the log loss by 0.010. The earlier, non-nested design, whose penalty was chosen on two of the test
years and whose specification, through-town rule and province intercepts were decided on the test
scores, gave 0.743 and +0.034; nesting all but the province intercepts gave 0.741 and +0.032
(slope 1.05, nine of the ten calibration groups inside the observed interval). As first
published, on all 12,961 crashes of 2016–2023 with the road-owner artefact and without nesting,
the figures were 0.772 against 0.745 for the table (+0.027), slope 1.04, 12.5% predicted against
12.6% observed; all are superseded. The improvement is real but modest: most of the information
is in the road and the crash type. The model ranks crashes moderately on interurban roads (0.697)
and urban streets (0.660) and not on roads through towns, where the calculator shows the
province's average.

### 4. EMEF years successfully imported

All eleven years, 2014–2024: 110,819 respondents and 418,716 trips, each year's respondent file,
trip file and dictionary (and the revised 2022 dictionary). Every year passes all of its checks.
Source: [`EMEF_INVENTORY.md`](EMEF_INVENTORY.md).

### 5. Missing or unusable EMEF files

No file is missing or unusable. The limits are in the content of the public files:

- No year publishes exact age or separates 65–74 from 75 and over.
- No distance variable before 2021; distances for 2014–2020 are modelled from duration.
- 2020 was surveyed under COVID-19 restrictions; it is reported but left out of every pooled
  estimate.
- 2017 has no reported trip count per respondent, so one check cannot run that year.
- The usual-driving question changed scale in 2021, and in 2020 asked only about use before the
  pandemic; the car licence was asked only in 2016.
- Two dictionaries contradict their files (2015 age column, 2024 respondent columns); the files
  were followed and the renamed 2024 columns verified against the trip file.

### 6. Harmonised mobility variables

Weight (`PESAIX`), car-driver trip (stage code 12), passenger (13), multimodal trips, other
vehicles (van and lorry, motorcycle, moped), people without trips, age group (`age3` in every year,
`age4` from 2019), sex, area of residence (zones 1–5 and comarca, renumbered in 2017), straight-line
distance band (from 2021), duration, usual frequency of driving, car licence (2016) and the
missing-value codes. Each rule was checked against every year's dictionary and the codes present
in the file ([`EMEF_INVENTORY.md`](EMEF_INVENTORY.md), Harmonisation).

### 7. Driver-distance methodology

Straight-line distance is modelled as log-normal given the trip's duration, its type and the
respondent's age group and year, fitted by maximum likelihood with interval censoring so that the
model never contradicts a band. Each trip takes the mean of the fitted distribution truncated to
its band. The EMEF 2021 distance report's ratio of road to straight-line distance for driving
trips (12.9 / 8.9 km = 1.45) converts it to road kilometres; as a common factor it changes
absolute rates, and the ratios between ages only slightly, because trips without a band are
bounded by a door-to-door speed whatever the ratio. Trips without a band take the model's mean
given duration, bounded at 80 km/h door to door (100 km/h as first published; bounds of 60 and
100 km/h, durations capped at four hours, the unbounded mean and leaving the trips out are
tested). Trips combining driving with another vehicle count for half their distance (0% and 100%
tested). The method reproduces the report's benchmarks
([`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md), From distance bands to road kilometres).

### 8. Workday exposure findings

In 2022–2024 (province of Barcelona), residents aged 65 and over drove 7.52 car-driver km per
working day (95% CI 6.50–8.59), against 18.86 at 45–64 (0.40 times). Most of the difference comes
from how many older people drive at all (18.9% on the reference day, against 40.4%), not from how
far those who drive go (39.9 against 46.7 km). Older women drive far less than older men (2.90
against 13.81 km per resident). The ratio of older to middle-aged driving is nearly the same in
every part of the province (0.39–0.47). It has risen over the decade: in the metropolitan region,
which every edition covers, residents aged 65 and over drove 0.29 times as far as those aged 30–64
in 2014–2016 and 0.40 times in 2021–2024. Residents aged 65 and over account for 12.2% of the
car-driver kilometres of a working day. (As first published, before the final audit corrected the
distances of unbanded trips: 7.87 against 19.29 km, 0.41, 41.7 against 47.8 km, 2.95 and 14.58,
0.40–0.47, 0.30 to 0.41 and 12.5%.)

### 9. National extrapolation methodology

- **A, demographic calibration**: EMEF kilometres per resident by sex and age group applied to
  INE's single-age population of Spain on 1 July 2024.
- **B, kilometre scale**: A's shares applied to DGT's 2024 car kilometres less taxis and
  ride-hailing cars (289.8 billion km); variants keep all cars (293.0) or also remove car hire and
  driving schools (278.1). B sets the level of the rates, not their ratios.
- **C, regional calibration**: A repeated with the profile of each part of the province and of the
  Madrid household travel survey of 2018.
- **D, registered owners**: DGT's kilometres by the owner's age, kept as a comparison only.

Nationally, drivers aged 65 and over account for 13.0% of car kilometres (95% CI 11.5–14.8%; first
published 13.4%, 11.6–15.3%), more than in the province because Spain's population is older.

### 10. Treatment of weekend and holiday driving

The EMEF covers working days. The central estimate spreads DGT's annual kilometres with the
working-day age mix. The sensitivity analysis gives non-working days, with 22% or 32% of annual
kilometres, one of two age mixes: the EMEF 2023 weekend question (a proxy) and MOVILIA 2006's car
trips on a weekend day against a working day. The 65-and-over ratio falls from 1.19 to 1.11 or
1.08 with the first and to 1.09 or 1.05 with the second, and the 18–29 ratio from 2.53 to 2.38–2.47
(first published, with the EMEF proxy only: from 1.16 to 1.09 or 1.06, and from 2.57 to 2.45 or
2.41). The coverage scenarios apply the same mixes to all the kilometres the survey does not
cover (point 14). Barcelona's crashes by type of day
show the older group's weekend pattern resembling the middle-aged group's. No source measures
weekend kilometres by age, so this remains a sensitivity range.

### 11. Whether 75+ exposure was identified

Not directly. The public EMEF files merge 65–74 and 75+; the two were sampling strata until 2016
and the confidential records hold exact age. A request for tables has been prepared but **not
sent** ([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md)). The figure first published here (65–74 at
0.90–1.08 and 75+ at 1.32–2.19, with no single 75+ rate) has since been replaced: the drivers page
now gives a conditional estimate for 75 and over (2.06 times the 45–64 rate if people aged 75 and
over drive as much less than those aged 65–74 as in Madrid in 2018; 95% sampling interval
1.6–2.6, whose second decimal is within Monte Carlo error) beside the sensitivity range
(0.97–3.20; 0.97–3.28 before the October 2026 method fixes). See
[75+ exposure: constraining the estimate](#75-exposure-constraining-the-estimate).

### 12. Revised crash-involvement rates

Car drivers involved in injury crashes in Spain in 2024, per billion km driven by drivers of the
same age (Methods A and B; `risk_national_rates.csv`, kilometre total less taxis and
ride-hailing). Interval ends are printed to the precision their Monte Carlo errors support: one
decimal for the ratios, whole numbers or tens for the rates.

| Age | Involved per bn km (95% CI) | Ratio to 45–64 (95% CI) | Sensitivity range of the ratio (every alternative) | Driver deaths, ratio to 45–64 (95% CI) |
|---|---:|---:|---:|---:|
| 18–29 | 643 (590–700) | 2.53 (2.2–2.8) | 1.49–3.63 | 2.26 (1.7–3.0) |
| 30–44 | 356 (340–380) | 1.40 (1.3–1.5) | 1.12–1.72 | 1.19 (0.9–1.5) |
| 45–64 | 254 (245–264) | 1 | | 1 |
| 65+ | 302 (270–340) | 1.19 (1.0–1.4) | 0.85–1.82 | 2.92 (2.3–3.9) |

As first published, before the final audit corrected the distances of unbanded trips and added
the age mix of the kilometres the survey's working days do not cover, the ratios were 2.57
(2.28–2.86), 1.42 and 1.16 (1.00–1.35), and the regional profiles alone gave the ranges (18–29
1.64–3.65, 65+ 1.00–1.70). After that audit and before the October 2026 method fixes (the Madrid
profile standardised to Spain's older population, DGT's owner-age kilometres made a bound, 50
count draws per survey replicate), this table gave the ranges as 1.49–3.75 and 0.85–1.75 and the
intervals to two decimals (2.25–2.82, 1.30–1.53 and 1.03–1.36; deaths 1.71–2.92, 0.91–1.51 and
2.21–3.82; the rates 587–707, 337–375 and 267–341), a precision their Monte Carlo errors do not
support; those figures are superseded.

The check on Barcelona's drivers in crashes with victims on the working days of 2025, against the
EMEF's driving inside the city, puts drivers aged 65 and over at 0.80–1.11 times the 45–64 rate
under three denominators, and drivers aged 18–29 at 2.14–2.61 times (first published 0.78–1.07
and 2.11–2.56).

Once involved, drivers aged 65 and over were killed in 11.4 of every 1,000 involvements (75+: 15.9),
against 4.6 at 45–64. Older drivers' deaths per km (2.92 times the 45–64 rate) therefore come
mostly from the outcome once a crash has happened, and only a little from more frequent
involvement (1.19 times).

### 13. Difference between old and new Figure 2

The former figure divided the same drivers by the kilometres of cars registered to owners of each
age band, with 35–54 as the reference. The new figure divides by kilometres driven by drivers of
each age, with 45–64 as the reference.

| | Young | Older |
|---|---|---|
| Former (owner's age) | 18–24: 6.75 times the 35–54 rate | 65–74: 0.71; 75+: 1.02 |
| New (driver's age) | 18–29: 2.53 times the 45–64 rate (first published 2.57) | 65+: 1.19 (first published 1.16); 65–74 and 75+ as first published: 0.90–1.08 and 1.32–2.19 (superseded: see below) |

Young drivers largely drive cars registered to their parents, and older owners' cars are partly
driven by others. Owner kilometres therefore understated young drivers' driving and overstated
older drivers'. The young drivers' excess falls from nearly seven times to about two and a half
times. At 65–74 the rate moves from well below the middle-aged rate (0.71) to about level with it.
The reference groups differ (35–54 then, 45–64 now) because the survey's age groups differ from
DGT's owner bands.

*Superseded for 65–74 and 75 and over (October 2026).* The first-published sentence said that at
75 and over the rate moved "from level (1.02) to above it". The 75+ figures are now a sensitivity
range of 0.97–3.20 (65–74: 0.67–1.70; 0.97–3.28 and 0.66–1.63 before the October 2026 method
fixes) and, on its stated Madrid condition, a conditional estimate
of 2.06 (95% sampling interval 1.6–2.6; 65–74 0.94, 0.8–1.1). Below about 1.2 the range is reached
only with equal km per licence holder, at odds with Spanish surveys of men's driving, and the
lowest other combination, 1.21, has a sampling interval of 0.9–1.8, so these data cannot show
that drivers aged 75 and over are involved more often per km whatever the assumption, nor by how
much. See [75+ exposure: constraining the estimate](#75-exposure-constraining-the-estimate).

### 14. Main sensitivity findings

- **Regional profile** dominates: the 65+ ratio runs from 0.99 to 1.74 and the 18–29 ratio from
  1.64 to 3.63 across the five profiles, because Madrid's older residents drive less than the
  EMEF's and Barcelona city's young residents rarely drive (the Madrid profile's 1.74 is
  standardised to Spain's older population; 1.65 before October 2026). Combined with other age
  mixes for the kilometres the survey's working days do not cover (about half of DGT's total),
  they give the sensitivity ranges, 0.85–1.82 at 65 and over and 1.49–3.63 at 18–29, whose top is
  Barcelona city's profile alone (before the October 2026 method fixes, when DGT's owner-age
  kilometres still counted as a credible mix: 0.85–1.75 and 1.49–3.75; first published, regional
  profile alone: 1.00–1.70 and 1.64–3.65).
- **Non-working days** move the 65+ ratio down modestly (1.05–1.11; first published 1.06–1.16).
- **Distance treatment** (years, area, multimodal trips, unbanded trips, fixed points in bands,
  speed bound) moves the 65+ share of kilometres between 11.0% and 13.8% (first published 10.9%
  and 13.1%).
- **Kilometre total** (Method B variants) changes absolute rates (65+: 299–315 per bn km; first
  published 292–308) but no ratio.
- **75 and over** (superseded, October 2026): first published as "the split assumption dominates
  (1.32–2.19), so only a range is given". Now the four splits give 1.36–2.09 under the central
  structure and, with every other choice, the sensitivity range 0.97–3.20; one at a time, the
  regional profile (1.71–3.01) and the split (1.36–2.09) move the figure most, then, about
  equally, the trip-distance conversion (1.95–2.43) and the age mix of the unexplained km
  (1.82–2.27) (`risk_older_decomposition.csv`). Before the October 2026 method fixes the four
  splits gave 1.36–2.24, the range was 0.97–3.28, the regional profile gave 1.71–2.85 and the age
  mix of the unexplained km 1.73–2.27; those figures are superseded. The Madrid split is
  published as a conditional estimate, 2.06 (95% sampling interval 1.6–2.6), beside the range.

### 15. Corrected statistical errors

From the audit ([`STATISTICAL_AUDIT.md`](STATISTICAL_AUDIT.md)), each with a regression test:

- Distances of unbanded trips truncated the distance distribution at the speed bound, making them
  10% too short overall and up to a third too short on long trips; the bound now applies to the mean.
- INE's single-age table also carries aggregate rows ("85 y más", "100 y más"); reading every row
  double-counted 85 and over (caught before use).
- Missing zone codes turned trip flags into missing values (caught before use).
- Per-resident rates for Catalonia and its provinces used the 1 January population while national
  rates used 1 July; every annual rate now uses 1 July.
- A calibration fit on a constant predictor raised an error.
- The forecast module still called the rejected model "the one used".
- A test failed instead of skipping when the regional data were absent.

Found in this final review and corrected:

- `DRIVER_AGE_EXPOSURE.md` said drivers of unknown age were "allocated in proportion for absolute
  rates", while the rates shown leave them out (allocation is a separate column). The text now
  says what the table does.
- `docs/methodology.md` still described the owner-age kilometres as the driver-age denominator and
  the forecast as a live supporting analysis; `docs/data_sources.md`, `docs/data_inventory.md` and
  `docs/DATA_CONTRACT.md` said the same in places. They now describe the travel-survey exposure,
  the withdrawn forecast and the calculator.
- The site's shared-number module kept a reader for the former owner-age figures that no page used
  any more; it was removed.
- The independent recomputation found, and the documents now correct:
  - the mean predictions of the trees and of the table in `SEVERITY_CALCULATOR.md` (12.4% and
    12.0%, not 12.6%, on the evaluation published then; on the nested evaluation that replaced it
    they are 12.3% and 12.2%);
  - the largest calibration gap in `ML_MODEL_REVIEW.md` (2.5 points in the highest band, not 2.0
    in the 15–20% band, on the evaluation published then; the document now gives the nested
    evaluation by tenth, whose largest gap is 2.3 points, in the ninth tenth);
  - four roundings in `DRIVER_AGE_EXPOSURE.md` (0.48, 27.6%, 0.62 and 2.45);
  - the description of how years are pooled ("equal weight" where each year counts in proportion
    to its population; the difference is below 0.001);
  - two stale figures in a code docstring (the unknown-age share in Barcelona, about 6%, and the
    mean internal trip, 4.7 km);
  - the definition behind the count of mobility professionals in `EMEF_INVENTORY.md`.

  None of these reached a page: the site formats every number from the tables when it is built.

### 16. Conclusions removed or substantially revised

- "Drivers aged 18–24 are involved in 6.8 times as many injury crashes per km as drivers aged
  35–54": **replaced** by 2.53 times at 18–29 against 45–64 (first published 2.57).
- "Drivers aged 75 and over were involved about as often per kilometre as drivers aged 35–54, and
  1.43 times as often as drivers aged 65–74": **withdrawn**. The replacement first published here,
  "on every assumption examined, drivers aged 75 and over are involved more often per km than
  drivers aged 45–64 (1.32–2.19)", is itself **superseded** (October 2026): the sensitivity range is
  0.97–3.20 (0.97–3.28 before the October 2026 method fixes) and two combinations are at or below 1
  (0.975 and 0.989), so a higher rate per km is not shown whatever the assumption. On the Madrid
  condition the conditional estimate is 2.06 (95% sampling interval 1.6–2.6); drivers aged 65–74
  are at 0.94 (0.8–1.1) on that condition and 0.67–1.70 across the range (0.66–1.63 before those
  fixes).
- Drivers aged 65–74 at 0.71 times the middle-aged rate per km (owner kilometres): **revised** to
  about level.
- The kilometres young drivers "would have to drive" to match the middle-aged rate, computed from
  owner kilometres: **withdrawn** with the owner-age figure.
- The monthly deaths forecast and the minimum detectable change computed from its errors:
  **withdrawn**.
- "Of three models, two did better than a table": **replaced** by the re-evaluation; the public
  model is the calculator, and the page leads with predicted against observed outcomes.
- The road owner "standing in" for road differences in the Catalan model: **removed** as a
  recording artefact.
- "Each count is divided only by a denominator that could contain it": **reworded** to name its
  three disclosed exceptions.
- Men's deaths at the wheel 3.63 times women's per licence holder: **reworded** to say "aged 18 and
  over" in the sentence; the figure is about 2% conservative against car-licence holders.

### 17. New data sources

- **EMEF 2014–2024** (ATM, Idescat, Institut Metròpoli): committed by the repository owner as loose
  files, filed under `data/raw/emef/`, and read for the first time.
- **Madrid household travel survey 2018** (EDM2018, CRTM): respondents with exact age and car-driver
  trips with distance, under the CRTM licence (cite the CRTM, show "Powered by CRTM", share derived
  data under the same licence).
- **INE population by single year of age and sex** (table 56934), 1 January and 1 July, 2002–2025.
- **DGT 2024 kilometres by class of service and by autonomous community** (two tables of the 2024
  kilometre release).
- Values used as method parameters, each cited in the code: the EMEF 2021 distance report's
  road-to-straight-line ratios, and the 2025 Catalan holiday calendar (Ordre EMT/85/2024) with
  Barcelona's two local holidays.

### 18. Remaining evidence gaps

- Car-driving kilometres at 75 and over: the EMEF's confidential ages (request prepared, not sent)
  or a national survey with exact ages.
- Car-driving kilometres by driver age for Spain as a whole: every national rate transfers a
  regional profile, which is the largest source of uncertainty for the youngest and oldest groups.
- Weekend and holiday kilometres by age.
- Responsibility: quasi-induced exposure needs driver-level crash records with age and fault,
  which no public source provides.
- A national working-day design: DGT publishes no cross-tabulation of driver age by day of the week.
- Severity: no speeds, protective equipment, alcohol results or ages in the Catalan file; the
  model describes Catalonia and is likely to understate fatal shares elsewhere in Spain.

### 19. Website changes

- **Drivers page** rebuilt: involvement per km by driver age with intervals and sensitivity ranges
  (new figure), the Barcelona check, the 75+ section (counted measures, the conditional estimate
  with its sampling interval beside the sensitivity range, and Figure 3 on what moves it; it
  replaced the first-published "model-dependent 75+ range" in October 2026), deaths once involved
  (new figure), why the former figure differed, and the comparison of men and women with its age
  range in the sentence. Credits and "Powered by CRTM" link.
- **Models page** rebuilt: it leads with predicted against observed outcomes, then discrimination,
  what the model shows, the interactive calculator (probability, 95% interval, the number of
  similar recorded crashes, warnings, and a comparison of two crashes), and every model the
  project fitted with its decision.
- **Forecast page** withdrawn and replaced by a notice that says why.
- **Front page** findings updated to the new drivers and models results; the external-validation
  page now shows the province figure it quotes; the methodology page's rates and tested
  assumptions rewritten.
- The calculator works with the keyboard, announces its results, fits a phone's width and, without
  scripting, leaves a table of worked examples.

### 20. Final test and deployment status

The final status is the one measured at the end of the work, on the final commit: the test counts,
the raw-file hashes, lint and format, the clean rebuild, CI and deployment are recorded in
[`ACCEPTANCE_REPORT.md`](ACCEPTANCE_REPORT.md), with the commit they were measured on. They are
not repeated here, where they could drift. The table names each check and gives only the earlier
measurements, labelled with when they were taken; none of them is the final status.

| Check | Earlier measurements (superseded by the acceptance report) |
|---|---|
| Full test suite, local (Python 3.13 with the library versions of `requirements.lock`) | 359 passed, none skipped, when this review was first written; 547 passed, none skipped, at 3af96b3, during the final audit |
| Raw-file hashes against the manifest (`pytest -m slow`) | passed when this review was first written |
| Lint and format (`ruff check`, `ruff format --check`) | clean when this review was first written |
| Clean rebuild of the EMEF tables, driver-age rates, figures and site from the raw files | every committed output reproduced byte for byte when this review was first written |
| CI on the pull request (Python 3.11, locked dependencies, national and regional layers rebuilt from the raw files, `pytest`) | passed on all five pushes of the rebuild before this review; the result for each later push is shown on the pull request |
| Deployment | not deployed by this work: the Pages workflow publishes the site from `main`, so the rebuilt pages go live only when the pull request is merged |

The browser tests need the optional `browser` dependencies (`pip install -e .[browser]`) and skip
without them locally. CI runs them in a job of its own (`browser` in `.github/workflows/ci.yml`),
with `REQUIRE_BROWSER=1` so that they cannot skip.

## Completed results and pending work

**Completed and verified:** the model re-evaluation and the calculator; the EMEF inventory,
harmonisation and checks; working-day exposure by age, 2014–2024; the national rates by age with
intervals and sensitivity ranges; the Barcelona check; deaths once involved; the audit and its
corrections; the rebuilt site.

**Pending, on external data:**

- The EMEF request for car-driving tables by finer age group, including 75 and over, is prepared
  but has not been sent ([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md)). Until a reply arrives,
  the figure per kilometre at 75 and over is a conditional estimate beside the sensitivity range.
- The rebuilt site goes live when the pull request is merged into `main`.

## 75+ exposure: constraining the estimate

October 2026, after the coverage and stress tests. The question was whether the 75+ figure per
kilometre could be better constrained than the sensitivity range, then 0.97–3.28 times the 45–64
rate (0.97–3.20 since the method fixes recorded later in this section), without adding false
precision. The full account, with every number and its table, is in
[`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md#ages-75-and-over).

**What was examined.** The CRTM Encuesta Sintética de Movilidad 2024 (ages 14–80 only, one 65–80
band, driver and passenger merged, no km tables and no microdata: not usable for the split); the
EMEF's historical 65–74 and 75+ strata (2008–2016, never tabulated) and the P1b questionnaire
routing, which identifies retirees aged 75 and over and matches INE's population share in 2014
and roughly in 2016; Fundació RACC's *Mayores al volante* (2013), driving days per licence holder
by age; EMQ 2006 through Fundació RACC/CED (2011); INE's EET 2009–10 and 2002–03 time-use
surveys; Madrid's EDM2004; and national travel surveys of the Netherlands, England and Germany.
None of them measures km at 75 and over for Spain, so none replaces the split; they are used as
validation, context or, for RACC and the routing, to build one split and one bound.

**What changed.**

* The Madrid split (EDM2018 km per resident, by sex) is published as a conditional estimate,
  2.06 times the 45–64 rate, always with its condition ("if people aged 75 and over drive as much
  less than those aged 65–74 as in Madrid in 2018"). It is the one split that uses km measured by
  exact age without a bridge between two definitions of a licence holder.
* Its 95% sampling interval crosses all 300 EMEF replicates with all 300 EDM2018 replicates and
  is 1.63–2.64 in the table. The earlier 1.78–2.35 held the Madrid ratio fixed and was too narrow.
  The Monte Carlo errors of its ends are 0.019 and 0.033 (pigeonhole bootstrap; the batch figures
  first reported, 0.006 and 0.010, ignored the replicates the blocks share), so the pages print
  it to one decimal, 1.6–2.6.
* A fourth split, an upper limit for men from RACC's driving days with women equal, gives 1.69.
* The marking rule now uses men's implied km per licence holder (marks exactly the equal split,
  for any threshold in (0.68, 1]); the 65–74 ≥ 45–64 rule became a diagnostic.
* A bound for too few people aged 75 and over in the EMEF's 65+ sample, from the routing, is a
  new variant inside the range (up to 2.28).
* The range has a one-at-a-time decomposition, descriptive Shapley shares (documents only),
  sampling intervals at its ends, and Barcelona intervals.
* Figure 1 of the drivers page shows four layers, kept apart: observed counts, the conditional
  estimate (hollow diamond), its sampling interval, and the sensitivity range with the part
  reached only by the equal split hatched. A new Figure 3 shows what moves the 75+ figure.

**What did not change in that step.** The envelope, then 0.97–3.28 at 75 and over and 0.66–1.63
at 65–74 (0.97–3.20 and 0.67–1.70 since the method fixes recorded below). No scenario was
dropped: the equal split, at odds with surveys of men's driving, stays in the range, hatched. The
65+ range was unchanged by that step (then 0.85–1.75; 0.85–1.82 since those fixes). Counts or
shares of combinations are never used as a probability or as weight of evidence; "403 of 405"
and "most combinations" were removed.

**The guard.** The pages choose between three wordings from the tables. The lowest combination
not at odds with men's driving is 1.21, above the 45–64 rate, but its 95% sampling interval is
0.9–1.8, which reaches it (Monte Carlo errors 0.017 and 0.040; the guard refuses to choose a
wording when an end lies within three of them of 1). The intermediate wording is printed: among
those combinations every one puts drivers aged 75 and over above the 45–64 rate, but at the lowest
sampling error alone could bring them down to it, so these data cannot show that drivers aged 75
and over are involved more often per kilometre whatever the assumption, nor by how much.

**The critiques, accepted and rejected.**

* Accepted: drop the 65–74 ≥ 45–64 rule as a marking rule (algebraically ratio_65_74 ≤ 0.715,
  so it set the 65–74 edge by construction; its evidence is working-day only; it does not change
  the lowest unmarked 75+ value at threshold 1).
* Accepted: replace a single permuted pairing of EMEF and EDM replicates with the full cross.
* Accepted: hatching instead of a faded band (a faded band read as "less probable" and failed
  contrast), and a hollow diamond instead of a filled one, which could not be told from the dots
  on a phone.
* Rejected: marking that the equal split's whole span lies in the hatched part; its rows span
  0.97–2.05 (0.97–1.98 before the October 2026 method fixes), and only the part below 1.21 is
  reached by marked rows alone.
* Rejected: dating the RACC survey 2012; the fieldwork dates are not stated and the 2012–2013
  fieldwork belongs to another survey (RACE–Liberty), so "published in 2013" is used.
* Rejected: showing no interval for the RACC and equal splits; all four rows show one, and the
  table caption says which sources each includes and that the RACC constant is fixed.
* Rejected: a by-sex or pooled marking rule (a by-sex rule would mark the Madrid split on women's
  evidence that does not exclude 1; a pooled rule depends on the sex mix).
* Rejected: a pooled uncertainty interval merging sampling and structural spread, percentiles of
  the scenarios, model averaging over splits, or narrowing the range to the unmarked span; each
  would turn assumption counts into probabilities or rest on a rule adopted after seeing results.
* Not added, documented: women at 0.5 in the RACC split (about 1.83), and the exploratory crossed
  envelopes (0.92–3.53; 0.78–3.59; an unmarked minimum of about 1.15), which stay off the site
  until the pipeline reproduces them. The crossed envelopes were computed before the October 2026
  method fixes and have not been recomputed, so their ends are not current figures.

**The final audit (October 2026).** An independent audit of this section found the following,
and each was corrected:

* The Monte Carlo errors of the joint intervals were understated several times by a batch method
  whose blocks share replicates. A pigeonhole bootstrap now estimates them (Madrid split at 75 and
  over: 0.019 and 0.033), the pages print the ends to the precision these support (one decimal),
  and no wording rests on an end within three of them of 1. The interval values did not change.
* Figure 3 labelled the age mix of the unexplained km "Km outside working days", which reads as
  including the weekends of a separate bar. Its bars are now named by the assumption they change,
  its title says the bars show how the estimate changes, and its caption says the top bar spans
  every combination tested, not every possible one.
* The key 75+ sentence, "a higher rate per kilometre is not established under every assumption",
  could be read as "established under none". It now reads "these data cannot show that drivers
  aged 75 and over are involved more often per kilometre whatever the assumption, nor by how
  much", and the drivers page's opening was shortened, with the detail moved to the 75+ section.
* The Barcelona check blamed its inconclusiveness on wide intervals, although some exclude 1. It
  now says the figures disagree. Of the Madrid split's three intervals, one includes 1, one lies
  above it and one ends within its Monte Carlo error of 1 (0.999, standard error 0.012), and the
  page says that last end could fall on either side rather than counting it; the page's count of
  intervals that include 1 is classified with the same three-standard-error margin as the
  conditional estimate.
* The table of possible biases left out the women's implied km per licence holder under the
  Madrid split (1.08), which points higher. It is now listed (exploratory: +1% to +17%).
* The licence trend at 75 and over was labelled as B licences; it is the any-class series, and
  the cohort update (1.88) is now computed in the pipeline.
* The questionnaire filter and the sampling strata were cited from sources not in the
  repository. The 2014–2016 and 2022–2023 questionnaires and the methodology report 2003–2018 are
  now archived in `data/raw/emef/` with manifest rows.
* Points 13, 14, 16 and 19 of the final report and two claim-ledger rows still gave the
  first-published 75+ range as a finding; they are marked superseded.

Not changed: text in the charts falls to about 10–11 px at some phone and tablet widths (360 px,
and 641–767 px, where the wide chart is shown). That follows from the figure scales and the
breakpoint shared by every chart on the site, not from these figures, and is left to a site-wide
change.

**The method fixes (October 2026).** A later independent review found three faults of method, and
each was corrected (the full account is in the change log of
[`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md#change-log)):

* The Madrid profile's 65+ km per resident was Madrid's own 65+ mean, although Madrid's residents
  aged 65 and over are younger than Spain's. It is now standardised to Spain's older population
  from the survey's exact ages, which raises the Madrid profile's 65+ ratio from 1.65 to 1.74.
* The licence split divided by the survey's self-reported licence holders and so counted the fall
  in licence holding at 75 and over twice. It now carries Madrid's km per DGT licence holder to
  Spain's DGT licence holders: 2.09 at 75 and over, against 2.24 before.
* DGT's kilometres by the owner's age were counted as a credible age mix for the unexplained km.
  They are now a bound, reported with their values and left out of the ranges, and their 84 rows
  left the 75+ table (460 rows, 544 before). The national, Barcelona and men-against-women
  intervals now cross each survey replicate with 50 count draws, and every interval is printed to
  the precision its Monte Carlo error supports.

The ranges moved: 18–29 from 1.49–3.75 to 1.49–3.63, 65 and over from 0.85–1.75 to 0.85–1.82,
65–74 from 0.66–1.63 to 0.67–1.70 and 75 and over from 0.97–3.28 to 0.97–3.20. The conditional
estimate, 2.06 (1.6–2.6), and the lowest combination not at odds with men's driving, 1.21
(0.9–1.8), did not change.

**What would materially improve it.** The EMEF's own aggregates for 65–74 and 75+ (or finer) with
design-based errors, and the true age × routing table, from Institut Metròpoli or the ATM, would
replace the Madrid transfer and settle the composition bound
([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md), prepared, not sent). After that: a national
all-days measure of driving by age that separates driver from passenger; the age mix of weekend
and long-distance driving; a second exact-age regional survey (the Basque Encuesta de Movilidad);
RACC km by sex and age; DGT's 2018 licence holders by age for Madrid.
