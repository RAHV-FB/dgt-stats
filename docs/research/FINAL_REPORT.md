# Final review and report

Task 25. This document records the final review of the rebuild (Tasks 1–24) and answers the
twenty questions of the final report. Every figure below is taken from a committed table or from
the research document named beside it; none is new. Results that are complete are kept apart from
work that waits on external data (the last section).

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
| Method A shares of car km: 16–29 / 30–44 / 45–64 / 65+ | 0.1126 / 0.2765 / 0.4774 / 0.1336 | the same, from INE's 1 July 2024 single ages | agree |
| Private-car drivers involved, 2024: 18–29 / 30–44 / 45–64 / 65+ | 21,234 / 28,775 / 35,092 / 11,425 | the same from tables 4.2 I+U; also 65–74 6,970, 75+ 4,455, aged 15–17 41, unknown age 2,234, public-service cars 1,852 | agree |
| Drivers killed, same groups | 88 / 113 / 163 / 130 | the same from table 4.1.1 | agree |
| DGT car km, all cars / less taxis and ride-hailing | 292.99 / 289.78 bn | the same | agree |
| Involvement ratio to 45–64 per km | 2.57 / 1.42 / 1 / 1.16 | 2.566 / 1.416 / 1 / 1.164; deaths 2.29 / 1.20 / 2.85 | agree |
| Barcelona working days, 2025 | 248 | 248 (50 Saturdays, 67 Sundays or holidays); working-day car drivers 652 / 981 / 1,294 / 354 and 205 of unknown age, recounted from the raw file | agree |
| Calculator calibration, 2016–2023 | 12.5% predicted, 12.6% observed | 1,616.4 predicted against 1,627 fatal of 12,961 (12.47% against 12.55%); every band inside the observed interval | agree |
| Ratio of 65+ to 45–64 km per resident | 0.41 | 0.35–0.36 with fixed band midpoints, 0.38–0.40 once the 461 unbanded trips are imputed from duration | consistent: the gap is the treatment of unbanded trips, which the sensitivity analysis already covers |

The recomputation also found errors of rounding and wording in the research documents, which were
corrected (point 15). No calculation in a committed table was found to be wrong.

### The verification checklist

| Item | How it was checked | Result |
|---|---|---|
| Raw-source reconciliation | the 482 reconciliation checks against DGT's published totals (`validate.run_all`), rerun by CI on every push; the SHA-256 of every raw file against `data/raw/manifest.csv` (`pytest -m slow`) | all pass |
| EMEF ingestion and weighting | 142 structural checks (`emef_checks.csv`): sample sizes and weighted totals equal the survey's technical tables every year; fifteen published 2024 figures reproduced to their rounding (`emef_reproduction.csv`); independent recount above | all pass |
| Car driver against passenger | code 12 (car driver) and 13 (car passenger) read from every year's dictionary and tested; a passenger stage never makes a driving trip | confirmed |
| Distance estimation | the 2021 distance report's benchmarks reproduced (8.94 against 8.9 km for a driving trip; road km per mobile person within 8% by age); the imputation of unbanded trips checked against banded trips (1.03 overall, within 10% in every year and age group) | confirmed, with the treatment of long and unbanded trips carried into the sensitivity ranges |
| Age-group handling | `age4` collapses exactly onto `age3` (tested); the 16–29 group matched to drivers aged 18–29; INE single ages summed without the file's overlapping aggregates (tested) | confirmed |
| Workday exposure | working days only in the EMEF; Barcelona's 2025 calendar of 248 working days built from the Catalan and local holidays and tested | confirmed |
| National extrapolation | Method A recomputed independently (above); Methods C and D as sensitivity and comparison | confirmed |
| Crash-numerator compatibility | private cars only, public-service cars removed from both numerator and denominator; drivers of unknown age left out of the rates and the effect stated (2.3%) | confirmed; the wording of one document corrected (point 15) |
| Uncertainty | bootstrap replicates paired with gamma draws for counts; intervals and sensitivity ranges reported separately throughout | confirmed |
| Model performance | rolling-origin scores of every model against a table of the same records (`sev_rolling_scores`, `review_*`); for the published model the evaluation is nested, every choice made on earlier years (`sev_choices`, `sev_nested_steps`) | confirmed (points 1–3) |
| Model calibration | predicted against observed in ten groups of predicted risk on years that played no part in fitting or choosing the model (`sev_calibration`), and by year, zone and province (`sev_rolling_scores`) | nine of ten groups' mean predictions inside the observed 95% interval; outside it in 2016, on urban streets, and on interurban roads in Girona and Tarragona |
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
| DGT crash severity (association model) | **Research only**: blank fields alone rank fatal crashes (ROC-AUC 0.72) |
| Monthly road deaths forecast | **Withdrawn** as a forecast: 6.6% error against 5.9% for last year's count in the ordinary held-out years; the page is a withdrawal notice |

Source: [`ML_MODEL_REVIEW.md`](ML_MODEL_REVIEW.md).

### 2. Strongest validated severity model

The penalised logistic regression behind the calculator, trained on the Servei Català de Trànsit
file (22,638 crashes with a death or serious injury, 2010–2023, 2,822 fatal; the 1,840 on
conventional roads with no named owning network are left out). It was validated by
nested rolling origin over eight years (each of 2016–2023 predicted by a model whose penalty,
specification and through-town rule were chosen, and whose coefficients were fitted, on earlier
years only; 11,611 crashes on the roads a reader can choose, 1,429 fatal), by the stability of its
contrasts across periods and areas, and by bootstrap refits. The transfer tests of the original
Catalan model, on DGT and Barcelona records, bear on its reach: its probabilities describe
Catalonia and are likely to be low elsewhere. Gradient-boosted trees rank a little better
(ROC-AUC 0.748 against 0.741) but give no interval for an estimate and cannot be read term by
term. Source: [`SEVERITY_CALCULATOR.md`](SEVERITY_CALCULATOR.md).

### 3. Model performance against baseline

| Model, nested rolling origin 2016–2023 | ROC-AUC (95% CI) | Brier skill | Log loss | Calibration slope | Mean predicted (observed 12.3%) |
|---|---|---|---|---|---|
| Calculator model | 0.741 (0.727–0.754) | 0.098 | 0.331 | 1.05 | 12.3% |
| Gradient-boosted trees | 0.748 (0.734–0.761) | 0.102 | 0.329 | 1.08 | 12.3% |
| Fatal share of road × crash type | 0.709 (0.694–0.723) | 0.069 | 0.342 | 1.08 | 12.2% |

The model improves on the table by +0.032 ROC-AUC (paired interval +0.022 to +0.042) and lowers
the log loss by 0.011. The earlier, non-nested design, whose penalty was chosen on two of the test
years and whose specification and through-town rule were decided on the test scores, gave 0.743
and +0.034. The improvement is real but modest: most of the information is in the road and the
crash type. The model ranks crashes moderately on interurban roads (0.701) and urban streets
(0.660) and not on roads through towns, where the calculator shows the province's average.

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
absolute rates but no ratio between ages. Trips without a band take the model's mean given
duration, bounded at 100 km/h. Trips combining driving with another vehicle count for half their
distance (0% and 100% tested). The method reproduces the report's benchmarks
([`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md), From distance bands to road kilometres).

### 8. Workday exposure findings

In 2022–2024 (province of Barcelona), residents aged 65 and over drove 7.87 car-driver km per
working day (95% CI 6.72–9.09), against 19.29 at 45–64 (0.41 times). Most of the difference comes
from how many older people drive at all (18.9% on the reference day, against 40.4%), not from how
far those who drive go (41.7 against 47.8 km). Older women drive far less than older men (2.95
against 14.58 km per resident). The ratio of older to middle-aged driving is nearly the same in
every part of the province (0.40–0.47). It has risen over the decade: in the metropolitan region,
which every edition covers, residents aged 65 and over drove 0.30 times as far as those aged 30–64
in 2014–2016 and 0.41 times in 2021–2024. Residents aged 65 and over account for 12.5% of the car-driver kilometres of a
working day.

### 9. National extrapolation methodology

- **A, demographic calibration**: EMEF kilometres per resident by sex and age group applied to
  INE's single-age population of Spain on 1 July 2024.
- **B, kilometre scale**: A's shares applied to DGT's 2024 car kilometres less taxis and
  ride-hailing cars (289.8 billion km); variants keep all cars (293.0) or also remove car hire and
  driving schools (278.1). B sets the level of the rates, not their ratios.
- **C, regional calibration**: A repeated with the profile of each part of the province and of the
  Madrid household travel survey of 2018.
- **D, registered owners**: DGT's kilometres by the owner's age, kept as a comparison only.

Nationally, drivers aged 65 and over account for 13.4% of car kilometres (95% CI 11.6–15.3%), more
than in the province because Spain's population is older.

### 10. Treatment of weekend and holiday driving

The EMEF covers working days. The central estimate spreads DGT's annual kilometres with the
working-day age mix. The sensitivity analysis gives non-working days the age mix of the EMEF 2023
weekend question, with 22% or 32% of annual kilometres. The 65-and-over ratio falls from 1.16 to
1.09 or 1.06, and the 18–29 ratio from 2.57 to 2.45 or 2.41. Barcelona's crashes by type of day
show the older group's weekend pattern resembling the middle-aged group's. No source measures
weekend kilometres by age, so this remains a sensitivity range.

### 11. Whether 75+ exposure was identified

No. The public EMEF files merge 65–74 and 75+; the two were sampling strata until 2016 and the
confidential records hold exact age. A request for tables has been prepared but **not sent**
([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md)). Until then the split rests on the Madrid survey
(exact ages) and three other stated assumptions, and is labelled model-dependent: drivers aged
65–74 are involved at 0.90–1.08 times the 45–64 rate per km, and drivers aged 75 and over at
1.32–2.19 times. No single 75+ rate is published.

### 12. Revised crash-involvement rates

Car drivers involved in injury crashes in Spain in 2024, per billion km driven by drivers of the
same age (Methods A and B):

| Age | Involved per bn km (95% CI) | Ratio to 45–64 (95% CI) | Sensitivity range of the ratio (regional profile) | Driver deaths, ratio to 45–64 (95% CI) |
|---|---:|---:|---:|---:|
| 18–29 | 651 (593–716) | 2.57 (2.28–2.86) | 1.64–3.65 | 2.29 (1.73–2.95) |
| 30–44 | 359 (338–380) | 1.42 (1.30–1.55) | 1.11–1.63 | 1.20 (0.92–1.53) |
| 45–64 | 254 (244–264) | 1 | | 1 |
| 65+ | 295 (260–338) | 1.16 (1.00–1.35) | 1.00–1.70 | 2.85 (2.12–3.74) |

The check matched in place and time, Barcelona's drivers in crashes with victims on the working
days of 2025 against the EMEF's driving inside the city, puts drivers aged 65 and over at 0.78–1.07
times the 45–64 rate under three denominators, and drivers aged 16–29 at 2.11–2.56 times.

Once involved, drivers aged 65 and over were killed in 11.4 of every 1,000 involvements (75+: 15.9),
against 4.6 at 45–64. Older drivers' deaths per km (2.85 times the 45–64 rate) therefore come
mostly from the outcome once a crash has happened, and only a little from more frequent
involvement (1.16 times).

### 13. Difference between old and new Figure 2

The former figure divided the same drivers by the kilometres of cars registered to owners of each
age band, with 35–54 as the reference. The new figure divides by kilometres driven by drivers of
each age, with 45–64 as the reference.

| | Young | Older |
|---|---|---|
| Former (owner's age) | 18–24: 6.75 times the 35–54 rate | 65–74: 0.71; 75+: 1.02 |
| New (driver's age) | 18–29: 2.57 times the 45–64 rate | 65+: 1.16; 65–74 0.90–1.08 and 75+ 1.32–2.19 (model-dependent) |

Young drivers largely drive cars registered to their parents, and older owners' cars are partly
driven by others. Owner kilometres therefore understated young drivers' driving and overstated
older drivers'. The young drivers' excess falls from nearly seven times to about two and a half
times. At 65–74 the rate moves from well below the middle-aged rate (0.71) to about level with it,
and at 75 and over from level (1.02) to above it. The reference groups differ (35–54 then, 45–64
now) because the survey's age groups differ from DGT's owner bands.

### 14. Main sensitivity findings

- **Regional profile** dominates: the 65+ ratio runs from 1.00 to 1.70 and the 18–29 ratio from
  1.64 to 3.65 across the five profiles, because Madrid's older residents drive less than the
  EMEF's and Barcelona city's young residents rarely drive.
- **Non-working days** move the 65+ ratio down modestly (1.06–1.16).
- **Distance treatment** (years, area, multimodal trips, unbanded trips, fixed points in bands,
  speed bound) moves the 65+ share of working-day kilometres between 10.9% and 13.1%.
- **Kilometre total** (Method B variants) changes absolute rates (65+: 292–308 per bn km) but no
  ratio.
- **75 and over**: the split assumption dominates (1.32–2.19), so only a range is given.

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
    12.0%, not 12.6%);
  - the largest calibration gap in `ML_MODEL_REVIEW.md` (2.5 points in the highest band, not 2.0
    in the 15–20% band);
  - four roundings in `DRIVER_AGE_EXPOSURE.md` (0.48, 27.6%, 0.62 and 2.45);
  - the description of how years are pooled ("equal weight" where each year counts in proportion
    to its population; the difference is below 0.001);
  - two stale figures in a code docstring (the unknown-age share in Barcelona, about 6%, and the
    mean internal trip, 4.7 km);
  - the definition behind the count of mobility professionals in `EMEF_INVENTORY.md`.

  None of these reached a page: the site formats every number from the tables when it is built.

### 16. Conclusions removed or substantially revised

- "Drivers aged 18–24 are involved in 6.8 times as many injury crashes per km as drivers aged
  35–54": **replaced** by 2.57 times at 18–29 against 45–64.
- "Drivers aged 75 and over were involved about as often per kilometre as drivers aged 35–54, and
  1.43 times as often as drivers aged 65–74": **withdrawn**. On every assumption examined, drivers
  aged 75 and over are involved more often per km than drivers aged 45–64 (1.32–2.19,
  model-dependent), and drivers aged 65–74 about as often (0.90–1.08).
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
  (new figure), the Barcelona check, the model-dependent 75+ range, deaths once involved (new
  figure), why the former figure differed, and the comparison of men and women with its age range
  in the sentence. Credits and "Powered by CRTM" link.
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

| Check | Status |
|---|---|
| Full test suite, local (Python 3.13 with the library versions of `requirements.lock`) | 359 passed, none skipped: the data, analysis, site and editorial tests, the calculator engine under Node (302 scenarios) and the eleven browser tests in Chromium |
| Raw-file hashes against the manifest (`pytest -m slow`) | passed |
| Lint and format (`ruff check`, `ruff format --check`) | clean |
| Clean rebuild of the EMEF tables, driver-age rates, figures and site from the raw files | every committed output reproduced byte for byte |
| CI on the pull request (Python 3.11, locked dependencies, national and regional layers rebuilt from the raw files, `pytest`) | passed on all five pushes of this rebuild before the review; the result for the review's own push is shown on the pull request |
| Deployment | **not yet deployed.** The Pages workflow publishes the site from `main`; the rebuilt pages go live when the pull request is merged |

The browser tests need the optional `browser` dependencies (`pip install -e .[browser]`) and skip
without them, as they do in CI, where the Node engine tests and the site tests still run.

## Completed results and pending work

**Completed and verified:** the model re-evaluation and the calculator; the EMEF inventory,
harmonisation and checks; working-day exposure by age, 2014–2024; the national rates by age with
intervals and sensitivity ranges; the Barcelona check; deaths once involved; the audit and its
corrections; the rebuilt site.

**Pending, on external data:**

- The EMEF request for car-driving tables by finer age group, including 75 and over, is prepared
  but has not been sent ([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md)). Until a reply arrives,
  every statement about drivers aged 75 and over is model-dependent and given as a range.
- The rebuilt site goes live when the pull request is merged into `main`.
