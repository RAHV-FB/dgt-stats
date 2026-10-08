# Re-evaluation of the predictive models

Every model the repository fitted was refitted here with separate code
(`src/dgt_stats/model_review.py`, `src/dgt_stats/severity_model.py`), scored against a simple
benchmark on records it was not fitted on, and checked for calibration as well as ranking. The
tables are written by `python scripts/severity_calculator.py all` to `reports/tables/review_*.csv`
and `reports/tables/sev_*.csv`.

## Decisions

| Model | Target and unit | Benchmark | Model | Calibration | Decision |
|---|---|---|---|---|---|
| Catalan crash severity, original feature set (boosted trees) | fatal rather than serious; one Catalan crash with a death or serious injury | type × zone table: ROC-AUC 0.699 on 2016–2023 | 0.779 (rolling origins, 12,961 crashes, 1,627 fatal); 0.7475 on the 11,611 crashes on roads a reader can choose | slope 1.08 | **REBUILD** as the calculator model below; the original is retired from the site |
| Catalan crash severity, calculator (penalised logistic regression) | same, without the 1,840 crashes whose road owner is an artefact | road × crash type table: 0.709 | 0.739 (nested rolling origins: every choice made on earlier years; 11,611 crashes, 1,429 fatal); boosted trees on the same inputs 0.748 | slope 1.03, mean predicted 12.4% against 12.3% observed; off in three zones of provinces | **KEEP**: the public model |
| Catalan crash severity, "retrospective administrative" variant | same, adding police judgements of influence | the original model: 0.790 on 2023 | 0.796 | slope 0.91 | **REMOVE**: +0.006 from fields recorded after the event |
| Barcelona person severity (boosted trees) | serious or fatal injury; one person in a 2025 Barcelona crash | role × vehicle table: 0.780 | 0.851 (months 10–12 of 2025, 4,049 people, 58 serious or fatal) | slope 0.91 here, 0.63 in the original run | **RESEARCH ONLY** |
| Barcelona crash severity (logistic) | serious or fatal injury in the crash; one 2025 Barcelona crash | accident-type table: 0.734 | 0.737 (1,994 crashes, 58 positive) | slope 0.84 | **REMOVE**: no gain over the table |
| Catalan model on DGT-common or Barcelona-common variables | fatal rather than serious | not a predictive model | transfer tests | — | **RESEARCH ONLY**: validation instruments |
| DGT crash severity (logistic, association analysis) | a death within 30 days; one DGT injury crash, 2016–2024 | not compared | 0.801 on 2023–2024 (203,302 crashes, 3,336 fatal) | every decile within half a point | **RESEARCH ONLY**: recording artefacts (below) |
| Monthly road deaths forecast (Poisson regression) | deaths in a month, Spain | last year's count: 5.9% error in ordinary held-out years | 6.6% | — | **WITHDRAWN**: its page is a withdrawal notice (below) |

Read each row as follows. The benchmark is a table any analyst could make, scored on the same
held-out records. ROC-AUC is the chance that a randomly chosen fatal crash is ranked above a
randomly chosen non-fatal one. The calibration slope is 1 when predicted probabilities spread
exactly as far as the observed outcomes do.

## How each score was reproduced

**Catalonia.** The original design (fit 2010–2022, test 2023) was repeated with independent
pipelines. Boosted trees with the originally chosen settings scored ROC-AUC 0.788 on 2023 (0.790
published); the type × zone table 0.695 (0.695); logistic regression 0.769 (0.771). One test year
holds only 209 fatal crashes, so the evaluation was extended: each year 2016–2023 was predicted by
models fitted only on the years before it. On those 12,961 crashes the boosted trees scored 0.779
against 0.699 for the table, and the gain held in every year (smallest 2016: 0.749 against 0.655).
Calibration was good on the pooled years (slope 1.08, mean prediction within 0.4 points of the
observed 12.6%).

**A recording artefact in the strongest predictor.** The original model's most used variable was
the road's owner. On interurban conventional roads, crashes whose owner is recorded as "Altres"
(1,410) were fatal in 3.0% of cases and those whose owner is blank (430) in 53%, against 15–26% for
the named networks; "Altres" grew from 27 crashes in 2010 to about 170 a year from 2019. A field
whose blank and "other" values separate fatal from serious crashes this sharply records how a
crash was documented, not the road. The original audit classified the field as safe. Part of the
original model's advantage over its table therefore came from documentation, which no user of a
calculator can choose. The rebuilt model keeps the named networks as inputs and leaves the 1,840 artefact crashes out
of fitting and of evaluation (see [`SEVERITY_CALCULATOR.md`](SEVERITY_CALCULATOR.md)). On the
11,611 crashes of 2016–2023 on the roads a reader can choose, the original model scores ROC-AUC
0.7475, boosted trees on the calculator's inputs 0.7476 and the calculator 0.739 with every
choice nested (0.743 under the earlier design, whose choices used the test years): once the
artefact is removed, the original model has no advantage left.

**Barcelona.** The person model reproduces (0.851 here, 0.843 published; the role × vehicle table
0.780 in both), but it rests on 58 serious or fatal injuries in three months of one city's
records, its calibration slope varies between runs (0.63 to 0.91), and its Brier skill is 0.027:
its probabilities stay close to the 1.4% base rate. It ranks people better than the table, but
there is nothing a reader could do with a person-level probability from one city and year that
the descriptive table does not already show. It moves to research documentation. The crash model
adds nothing to the accident-type table (0.737 against 0.734) and is removed.

**DGT association model.** On 2023–2024 its predicted probabilities match observed shares decile
by decile, and it ranks fatal crashes with ROC-AUC 0.801. It is not a predictive tool: the
national file is filled differently by different police forces, and which circumstance fields
were left unrecorded where they apply ranks fatal crashes with ROC-AUC 0.68 on its own
(`dgt_audit_artefacts`). Its
coefficients mix road and recording. It stays a research analysis.

## Why the monthly forecast loses to last year's count

The forecast was a Poisson regression of monthly deaths on month, a linear trend, road fuel and
the number of Fridays, Saturdays and Sundays, fitted on the four years before the year predicted:
17 coefficients (an intercept and eleven month terms, the trend, road fuel and three calendar
counts) from 48 months. It was chosen on 2006–2015, when deaths fell steeply, and there
it beat last year's count easily (error 4.9% against 11.7%; last year's count was biased by −9.7%
every year). In the held-out years 2016–2019 and 2022–2024 deaths were roughly flat and the
ranking reversed: 6.6% against 5.9% (`review_forecast`).

The reason is the cost of estimating the trend. With a four-year window, the uncertainty of the
predicted annual total that comes only from estimating the coefficients averages 4.0% in the
held-out years, more than the 2.4% Poisson noise of a year's deaths. Last year's count has no
estimated coefficients, so its error is the Poisson noise of two years (3.3%) plus the year's real
change. When the trend is flat, the trend term adds variance and no information. Dropping the trend
confirms this: the same model without it errs by 4.8% in the held-out years, better than last year's
count, but by 16.9% in 2006–2015, when the trend was the signal. A longer window halves the
estimation error but extrapolates an older trend (6.8% held out, 8.1% in 2006–2015). No
specification wins in both kinds of year, and whether the next years will be flat is unknown when
the forecast is made.

The model is withdrawn as a forecast. Its page also used the model's errors to state how large a
change in deaths a before-and-after comparison can detect, and that statement depended on the
rejected model. The page is withdrawn, and the investigation is kept here.

## Predicted against observed

The public result for the retained model is its calibration on years whose data played no part
in fitting or choosing it (`reports/figures/sev1_predicted_observed.svg`,
`reports/tables/sev_calibration.csv`). The evaluation is nested
(`severity_model.nested_rolling`). For each year 2016–2023, three choices are made on the years
before it alone, by fitting on all but the last two of them and scoring those two by log loss:
the penalty (half-decades of C from 0.001 to 32, extended while the best value is at an end),
whether each input's association may differ on urban streets and interurban roads, and whether
roads through towns get the model's estimate or the average fatal share of such roads in the
province. The model is then refitted on all the years before the test year, and the table of
fatal shares by road and crash type is fitted on the same years. The choices for each year are
in `sev_choices.csv`, every grid point in `sev_penalty.csv`.

The design published before was not nested. Its penalty was chosen once, by fitting on 2010–2020
and scoring 2021–2022, two of the test years, from six values whose best (C = 0.1) was the
strongest tried. The choice of common effects, the average for roads through towns and the
intercept for each province and zone were made on the rolling scores of 2016–2023 themselves.
`sev_nested_steps.csv` replaces those choices one at a time:

| Design (2016–2023, 11,611 crashes) | ROC-AUC | Gain over the table (95% paired interval) | Calibration slope | Mean predicted (observed 12.3%) |
|---|---|---|---|---|
| Previous: penalty chosen on 2021–2022, common effects, the model on roads through towns (not nested) | 0.7425 | +0.034 (+0.023 to +0.044) | 1.10 | 12.2% |
| Penalty chosen on the years before each test year | 0.7414 | +0.032 (+0.022 to +0.042) | 1.08 | 12.2% |
| Penalty and specification chosen on earlier years | 0.7417 | +0.033 (+0.023 to +0.042) | 1.05 | 12.4% |
| Penalty, specification and through-town rule chosen on earlier years, province intercepts kept | 0.7409 | +0.032 (+0.022 to +0.042) | 1.05 | 12.3% |
| Nested: every choice, the province intercepts included, made on earlier years (published) | 0.7395 | +0.030 (+0.021 to +0.040) | 1.03 | 12.4% |

Each difference has one cause. Nesting the penalty changed four test years: in 2017 the loss on
2015–2016 fell steadily as the penalty weakened, to the edge of the grid (C = 1,000, in effect no
penalty), and that model ranked 2017 less well (0.726 against 0.731); 2018, 2021 and 2022 moved
by less than 0.004. Choosing the specification picked effects that differ by zone in six of the
eight years, which ranked the crashes about as well and brought the calibration slope closer to 1
(1.05).
The through-town rule gave such roads the average in 2016, 2022 and 2023, where the average then
predicted the test year's through-town crashes worse than the model would have (ROC-AUC on those
roads 0.54 against 0.60). Choosing the province intercepts on earlier years dropped them in one
year, 2016, which then ranked less well (0.706 against 0.716). The nested score is 0.003 below
the earlier one: the earlier choices had flattered the published result only slightly.

With every choice nested, the 11,611 crashes split into ten equal groups by predicted
probability:

| Tenth | Crashes | Fatal | Mean predicted | Observed (95% interval) |
|---|---|---|---|---|
| 1 | 1,162 | 33 | 2.8% | 2.8% (2.0–4.0) |
| 2 | 1,161 | 45 | 4.4% | 3.9% (2.9–5.1) |
| 3 | 1,161 | 56 | 5.6% | 4.8% (3.7–6.2) |
| 4 | 1,161 | 88 | 6.7% | 7.6% (6.2–9.2) |
| 5 | 1,161 | 87 | 8.2% | 7.5% (6.1–9.2) |
| 6 | 1,161 | 99 | 10.0% | 8.5% (7.1–10.3) |
| 7 | 1,161 | 131 | 12.4% | 11.3% (9.6–13.2) |
| 8 | 1,161 | 194 | 16.1% | 16.7% (14.7–19.0) |
| 9 | 1,161 | 281 | 21.9% | 24.2% (21.8–26.7) |
| 10 | 1,161 | 415 | 35.7% | 35.7% (33.0–38.5) |

In all ten groups the mean prediction lies inside the 95% interval of the observed share; in the
ninth it is 0.1 points inside the lower end. The pooled calibration slope is 1.03 and the
intercept 0.05; the mean prediction is 12.4%, against 12.3% observed. Of the fifth of crashes the
model rated most likely to be fatal, 30.0% were; of the fifth rated least likely, 3.4% (the
table: 27.4% and 4.4%). The model's probabilities can be read as estimates for groups of similar
recorded crashes, with exceptions. In 2016 it predicted 12.9% and 11.0% were fatal (9.6–12.6%).
On urban streets it predicted 7.3% against 6.6% (6.0–7.2%). By province and zone, the mean
prediction falls outside the observed interval on interurban roads in Girona (23.5% against
26.8%, 23.8–30.1%) and Tarragona (27.2% against 31.0%, 27.8–34.4%) and on urban streets in the
province of Barcelona (7.5% against 6.7%, 6.0–7.5%). Within the urban zone the model ranks
crashes less well (ROC-AUC 0.660) than on interurban roads (0.701), and on roads through towns it
does not rank them (0.544, 86 fatal crashes, partly scored with the average). The calculator
shows the average for roads through towns because the published model's own choice, made on
2022–2023, gave them the average.
