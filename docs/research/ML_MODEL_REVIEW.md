# Re-evaluation of the predictive models

Every model the repository fitted was refitted here with separate code
(`src/dgt_stats/model_review.py`, `src/dgt_stats/severity_model.py`), scored against a simple
benchmark on records it was not fitted on, and checked for calibration as well as ranking. The
tables are written by `python scripts/severity_calculator.py all` to `reports/tables/review_*.csv`
and `reports/tables/sev_*.csv`.

## Decisions

| Model | Target and unit | Benchmark | Model | Calibration | Decision |
|---|---|---|---|---|---|
| Catalan crash severity, original feature set (boosted trees) | fatal rather than serious; one Catalan crash with a death or serious injury | type × zone table: ROC-AUC 0.699 on 2016–2023 | 0.779 (rolling origins, 12,961 crashes, 1,627 fatal) | slope 1.08 | **REBUILD** as the calculator model below; the original is retired from the site |
| Catalan crash severity, calculator (penalised logistic regression) | same | road × crash type table: 0.745 | 0.772 | slope 1.04, mean predicted 12.5% against 12.6% observed | **KEEP**: the public model |
| Catalan crash severity, "retrospective administrative" variant | same, adding police judgements of influence | the original model: 0.790 on 2023 | 0.796 | slope 0.91 | **REMOVE**: +0.006 from fields recorded after the event |
| Barcelona person severity (boosted trees) | serious or fatal injury; one person in a 2025 Barcelona crash | role × vehicle table: 0.780 | 0.851 (months 10–12 of 2025, 4,049 people, 58 serious or fatal) | slope 0.91 here, 0.63 in the original run | **RESEARCH ONLY** |
| Barcelona crash severity (logistic) | serious or fatal injury in the crash; one 2025 Barcelona crash | accident-type table: 0.734 | 0.737 (1,994 crashes, 58 positive) | slope 0.84 | **REMOVE**: no gain over the table |
| Catalan model on DGT-common or Barcelona-common variables | fatal rather than serious | not a predictive model | transfer tests | — | **RESEARCH ONLY**: validation instruments |
| DGT crash severity (logistic, association analysis) | a death within 30 days; one DGT injury crash, 2016–2024 | not compared | 0.801 on 2023–2024 (203,302 crashes, 3,336 fatal) | every decile within half a point | **RESEARCH ONLY**: recording artefacts (below) |
| Monthly road deaths forecast (Poisson regression) | deaths in a month, Spain | last year's count: 5.9% error in ordinary held-out years | 6.6% | — | **REMOVE** as a forecast (below) |

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
(1,410) were fatal in 3.0% of cases and those whose owner is blank (430) in 54%, against 15–26% for
the named networks; "Altres" grew from 27 crashes in 2010 to about 170 a year from 2019. A field
whose blank and "other" values separate fatal from serious crashes this sharply records how a
crash was documented, not the road. The original audit classified the field as safe. Part of the
original model's advantage over its table therefore came from documentation, which no user of a
calculator can choose. The rebuilt model keeps the named networks as inputs and absorbs the two
artefact values in categories used only in training (see
[`SEVERITY_CALCULATOR.md`](SEVERITY_CALCULATOR.md)); on the road categories a reader can choose,
its held-out ROC-AUC is 0.738.

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
were left blank ranks fatal crashes with ROC-AUC 0.72 on its own (`dgt_audit_checks`). Its
coefficients mix road and recording. It stays a research analysis.

## Why the monthly forecast loses to last year's count

The forecast was a Poisson regression of monthly deaths on month, a linear trend, road fuel and
the number of Fridays, Saturdays and Sundays, fitted on the four years before the year predicted:
16 coefficients from 48 months. It was chosen on 2006–2015, when deaths fell steeply, and there
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

The model is removed as a forecast. Its page also used the model's errors to state how large a
change in deaths a before-and-after comparison can detect, and that statement depended on the
rejected model. The page is withdrawn, and the investigation is kept here.

## Predicted against observed

The public result for the retained model is its calibration on years it was not fitted on
(`reports/figures/sev1_predicted_observed.svg`, `reports/tables/sev_calibration.csv`). Each year
2016–2023 is predicted by the model fitted on the years before it, and the 12,961 crashes are
grouped into eight bands of predicted probability:

| Predicted band | Crashes | Fatal | Mean predicted | Observed (95% interval) |
|---|---|---|---|---|
| under 3% | 1,459 | 29 | 2.1% | 2.0% (1.4–2.8) |
| 3–6% | 3,493 | 145 | 4.5% | 4.2% (3.5–4.9) |
| 6–10% | 2,524 | 193 | 7.8% | 7.6% (6.7–8.7) |
| 10–15% | 1,887 | 231 | 12.2% | 12.2% (10.8–13.8) |
| 15–20% | 1,101 | 214 | 17.4% | 19.4% (17.2–21.9) |
| 20–30% | 1,414 | 340 | 24.3% | 24.0% (21.9–26.3) |
| 30–45% | 701 | 254 | 35.9% | 36.2% (32.8–39.9) |
| 45% and over | 382 | 221 | 55.4% | 57.9% (52.8–62.7) |

In every band the mean prediction lies inside the 95% interval of the observed share; the largest
gaps are 2.5 points in the highest band and 2.0 points in the 15–20% band. The model separates crashes that were almost never fatal (2% in
the lowest band) from crashes that were fatal more often than not (58% in the highest), and its
probabilities can be read as estimates for groups of similar recorded crashes. It does not follow
that every individual prediction is precise: within the urban zone the model ranks crashes much
less well (ROC-AUC 0.673) than on interurban roads (0.766), and on roads through towns it barely
ranks them at all (0.596, 86 fatal crashes), which the calculator says when such a road is chosen.
