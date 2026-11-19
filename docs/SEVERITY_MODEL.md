# The Catalan severity model

A penalised logistic regression of whether a crash in Catalonia with a death or a serious injury
was fatal. Code: `src/dgt_stats/severity_model.py` (specification, selection, fitting),
`src/dgt_stats/severity_tests.py` (tests on crashes left out) and `src/dgt_stats/metrics.py`
(scores). Run with `python scripts/severity_model.py` (about five minutes on one core); it reads
the feature table written by `python scripts/microdata.py features` and writes `reports/tables/sev_*.csv`.
The results are on the site's "Crash severity model" page (`severity-models.html`); this note gives
the question, the data, the model, the evaluation and the limits.

## Question

Among crashes in which someone was killed or seriously injured, how does the share that were fatal
vary with the recorded road, conditions and crash? "Fatal" is the file's definition: someone died
within 24 hours. The file's fatal crashes equal DGT's crashes with a death within 24 hours in every
province and year (`cat_vs_dgt_province_year`). The model is of severity given a severe crash. It
cannot say how likely a crash is, because the file holds only crashes, and its differences between
scenarios are associations in these records, not the effect of changing a road or a condition.

## Data

The Servei Català de Trànsit file of crashes with a death or serious injury, 2010-2023
(24,478 crashes, 3,093 fatal), staged and processed by `scripts/microdata.py build` and turned into
the feature table `data/features/catalonia_crash_severity.parquet` by `scripts/microdata.py features`.

**Crashes left out.** Crashes on conventional roads whose owner network is recorded as "other"
(1,410 crashes, 3% fatal) or left blank (430 crashes, 53% fatal) are not used: 1,840 crashes in all.
The named networks (State, regional, provincial, local) have fatal shares of 15-26%. A blank owner is
far commoner on fatal records and "other" on non-fatal ones, so the field records how a crash was
documented, not the road (`ml_recording_artefacts`, `sev_population`). The model and its tests
therefore describe 22,638 crashes (2,822 fatal) on roads with a named owning network or of another
type. With the 1,840 crashes the overall fatal share would be 12.6% instead of 12.5%, and the
interurban share 19.2% instead of 20.0%.

**Inputs.** Zone (urban street, road through a town, interurban road) and, for interurban roads,
the type of road and the owning network; crash type; lighting; weather; road surface; junction;
posted speed limit (the signposted limit, never a vehicle's speed); time of day in six bands; the
road users involved (pedestrian, bicycle, moped, motorcycle, car or van, heavy vehicle, other) and
the number of units; and province. The police's judgements of what influenced the crash, whether a
driver fled, the date and the fog and wind fields are not used.

## Model

A logistic regression with one barely penalised intercept per zone and province, an effect for each
interurban road type, and an effect for each other input, either common to all zones or allowed to
differ on urban streets and on interurban roads. Every other coefficient takes one L2 penalty.

Four choices are made on data, always from the crashes a fit is allowed to see: the penalty C (a
grid of half-decades extended until the best value lies inside it); whether effects are common
or differ by zone; whether roads through towns get the model's estimate or the average fatal
share of such roads in the province; and whether each province has its own intercepts. For a set
of training years the rule is to fit on all but the last two and score those two by log loss.

Intervals come from 500 refits on crashes resampled with replacement; each is
`expit(x'b +- 1.96 sqrt(x'Vx))` or its delta-method extension to a ratio of two scenarios.

## Evaluation

**Nested rolling origin.** Each year 2016-2023 is predicted by a model whose four choices were
made, and whose coefficients were fitted, on the years before it. The published model is chosen
by the same rule on all years and refitted on all of them. The benchmark is a table of the fatal
share of each road and crash type, shrunk towards the overall share and fitted on the same years;
gradient-boosted trees on the same inputs are a second comparator.

**Tests on crashes left out** (`severity_tests.py`, `sev_tests`): the last year from the years
before it; each province left out in turn (the specification without province intercepts); and
Barcelona city from the rest of Catalonia. Each sits beside the same choices fitted and
cross-validated inside the test crashes, and beside the table fitted on the training crashes. No
other source records the inputs, so there is no test outside the Catalan file.

## Results

- **Contrasts** (`sev_contrasts`, `sev_stability`, `sev_coefficients`). From a reference crash (a
  side or angle collision between two cars on a regional road, in daylight, dry, between
  junctions) a heavy vehicle involved goes with about twice the fatal share (ratio 2.0; 95%
  interval 1.7-2.2), the largest increase of any single input. Some other contrasts do not keep
  their direction when the model is refitted on 2010-2016 and on 2017-2023 separately.
- **Ranking** (`sev_rolling_scores`, `sev_comparison`). Over the 11,611 crashes of 2016-2023 the
  ROC-AUC is 0.74, against 0.71 for the table (difference 0.02-0.04, 95% interval), ahead in
  each year. Within a kind of road it is lower: 0.70 on interurban roads, 0.66 on urban streets and
  0.55 on roads through towns, where it does not beat the table (0.58). Gradient-boosted trees
  reach 0.75, a little better, but give no interval for an estimate.
- **Calibration** (`sev_calibration`). Pooled, the mean estimate (12.4%) is close to the observed
  share (12.3%) and the calibration slope is 1.03. By province and kind of road the mean estimate
  falls outside the observed interval in some cells, and on urban streets outside Barcelona city
  the estimates run high.
- **Tests on crashes left out** (`sev_tests`, `sev_geography`). In every test the model ranks the
  held-out crashes above the table. Its estimate of the fatal share misses for some provinces left
  out, and fitted without Barcelona city it puts the city's fatal share too low.

## Limits

- Associations in police records between a modelled scenario and a fatal outcome among severe
  crashes. A smaller share in heavy rain or at a junction does not make those crashes safer.
- A moderate ranking: it separates fatal from non-fatal severe crashes better than the table but
  not sharply, and not at all on roads through towns.
- Estimates for a province or a kind of road can be off; the model has been tested only within
  Catalonia and should not be used for another place.
- The 1,840 crashes with an outcome-dependent road-owner field are excluded, so the results do
  not describe crashes on conventional roads whose owner is "other" or blank.
- "Fatal" is a death within 24 hours; Spain's official figures count deaths within 30 days.
