# The crash-severity calculator

**Question.** Among crashes in Catalonia in which someone was killed or seriously injured, how does
the share that were fatal vary with the recorded road, conditions and crash?

The answer is a model of severity *given* a severe crash. "Fatal" is the source file's definition:
someone died within 24 hours. The file's fatal crashes equal DGT's 24-hour counts for the four
Catalan provinces in every year, and about a fifth of the crashes that DGT counts as fatal at 30
days appear in the file as serious. The data contain only crashes, so the model says nothing about
how likely a crash is to happen, how risky a road is per kilometre, or what changing a road or a
condition would do. A difference between two scenarios is an association in these records.

Code: `src/dgt_stats/severity_model.py` and `scripts/severity_calculator.py calculator`. Browser
engine: `src/dgt_stats/site/assets/severity-engine.js`; page: `severity-calculator.js`. Tests:
`tests/test_severity_engine.py` and the calculator tests in `tests/test_site_browser.py`.

## Data

Three sources could support the question.

| Source | Unit | Fatal cases | Why chosen or not |
|---|---|---|---|
| Servei Català de Trànsit, 2010–2023 | crash with a death or serious injury | 2,822 of 22,638 used | **chosen**: the population the question names, fourteen years, road, conditions and units involved recorded in every row |
| DGT crash microdata, 2016–2024 | injury crash, Spain | about 14,000 of 875,013 | not used to train: fields are blank at rates that differ by province and by outcome, and the blanks alone rank fatal crashes with ROC-AUC 0.72 ([`DGT_MICRODATA_AUDIT.md`](../DGT_MICRODATA_AUDIT.md)) |
| Guàrdia Urbana, Barcelona 2025 | person or crash | 13 deaths | far too few fatal cases for this question |

**The road owner's recording artefact.** On interurban conventional roads the owner field takes two
values that track how a crash was documented rather than the road: "Altres" (1,410 crashes, 3.0%
fatal) and blank (430 crashes, 54% fatal), against 15–26% on the named networks. "Altres" grew from
27 crashes in 2010 to about 170 a year from 2019. These 1,840 crashes are left out of fitting, of
evaluation and of every count the page shows. An earlier version kept them as two categories
used only in training; its pooled score then included them, and they made its ranking look better
than it was on the roads a reader can choose.

## Inputs

The inputs are circumstances recorded about the road and conditions before the crash, and about
the crash itself (its type and who was involved).

| Input | Levels | Default |
|---|---|---|
| Province | Barcelona, Girona, Lleida, Tarragona | Barcelona |
| Road | urban street; road through a town; motorway; dual carriageway; conventional road on the State, regional, provincial or local network; rural track; other interurban road | conventional road, regional network |
| Type of crash | pedestrian struck; head-on; side or angle; rear-end; sideswipe; ran off the road; hit an object; rider or occupant fell; other | side or angle |
| Lighting | daylight; daylight with a dark sky; dawn or dusk; night with adequate, poor or no street lighting | daylight |
| Weather | fine; light rain; heavy rain, hail or snow | fine |
| Road surface | dry; wet; slippery, flooded, icy or snowy | dry |
| Junction | between junctions; within a junction; within 50 m of one | between junctions |
| Posted speed limit | none recorded (the road's generic limit); 10–30; 40–50; 60–70; 80–90; 100–120 km/h | none recorded |
| Time of day | six bands | 10:00–13:59 |
| Road users involved | pedestrian, bicycle, moped, motorcycle, car or van, heavy vehicle, other (any combination) | car or van |
| Number involved | one, two, three, four or more (vehicles and pedestrians) | two |

**Left out.** The police's judgements of which conditions influenced the crash are left out,
because they are made after the event and fatal crashes are investigated more fully. Whether a
driver fled is left out too, since it depends on the outcome. The fog field is excluded: it is
recorded present in a tenth of urban crashes, which is not credible. The date is excluded. The
posted limit is the signposted limit where the record carries one; it is not a vehicle's speed,
and 72% of records carry none.

**Missing values.** Crashes with unspecified lighting, weather or surface (six, four and four) are
given the most common level; the posted limit's "not recorded" is a level of its own. No other
input has missing values.

## Specification

A logistic regression with:

- one intercept for each zone (urban street, road through a town, interurban road) in each
  province, Barcelona being the reference province;
- an effect for each interurban road type (a regional conventional road is the reference);
- one effect for each level of every other input, common to all zones.

That gives 58 coefficients, fitted with an L2 penalty. The intercepts are penalised hardly at all.

Two alternatives were tested on the same rolling origins (`sev_specification`, `sev_geography`):

- **Effects that differ by zone** (136 coefficients). These ranked crashes no better (ROC-AUC
  0.7425 in both cases). Their calibration slopes were 0.85 on urban streets and 0.43 on roads
  through towns, a sign of overfitting.
- **Without the province intercepts.** The estimates were too high in the province of Barcelona
  and too low in the other three, where severe crashes on interurban roads are far more often
  fatal (23–28% against 15% in 2010–2023). Fitted on three provinces and tested on the fourth,
  the model without province ranked the fourth's crashes with ROC-AUC 0.70–0.77, except in the
  province of Barcelona (0.66). There it estimated 11.7% fatal against 9.5% observed.

The penalty was chosen from six values (C = 0.1 to 30) by log loss on 2021–2022 after fitting on
2010–2020 (`sev_penalty`). The losses differ by at most 0.0005, so the choice hardly matters; the
strongest penalty, C = 0.1, was best. The final model is fitted on all 22,638 crashes. Its
covariance comes from 500 bootstrap refits of the training crashes.

## Choice of model

Three estimators were fitted on identical inputs and scored by rolling origin: each year 2016–2023
is predicted by a model fitted only on the years before it. There are 11,611 crashes on the roads
a reader can choose, 1,429 of them fatal (`sev_rolling_scores`, `sev_comparison`).

| Model | ROC-AUC (95% interval) | Brier skill | Log loss | Calibration slope | Mean predicted (observed 12.3%) |
|---|---|---|---|---|---|
| Penalised logistic regression (published) | 0.743 (0.729–0.756) | 0.099 | 0.330 | 1.10 | 12.2% |
| Gradient-boosted trees | 0.748 (0.733–0.761) | 0.102 | 0.329 | 1.08 | 12.3% |
| Fatal share of the road × crash type | 0.709 (0.694–0.723) | 0.069 | 0.342 | 1.08 | 12.2% |

The trees and the logistic regression cannot be told apart. The difference in ROC-AUC is +0.005
with a paired interval of −0.001 to +0.011, and in log loss −0.002 (−0.004 to +0.000). Both improve
clearly on the table: the logistic regression's ROC-AUC is higher by 0.034 (paired interval +0.023
to +0.044) and its log loss lower by 0.011 (0.008 to 0.015). The logistic regression is published
for three reasons:

- Every prediction is a sum of named coefficients, so the browser reproduces it exactly.
- A coefficient covariance gives an interval for any scenario, and for a comparison of two.
- Its contrasts are adjusted for every other input.

The original model (boosted trees on the original feature set, including the road owner's
artefact values) scored ROC-AUC 0.779 on all 12,961 crashes of the same years. On the 11,611
crashes on the roads a reader can choose it scores 0.7475, the same as the trees here (0.7476).
Its apparent advantage came from the artefact.

## Validation

| Check | Result |
|---|---|
| Calibration by tenth of predicted probability (`sev_calibration`) | the mean prediction lies inside the 95% interval of the observed share in nine of ten groups; in the ninth tenth the model said 21.2% and 24.5% were fatal (22.2–27.1%) |
| Calibration slope, pooled | 1.10: predictions slightly too compressed (the crashes rated most and least likely to be fatal were a little more extreme than predicted) |
| Fifths | of the fifth rated most likely to be fatal, 30.3% were; of the fifth rated least likely, 3.1%; for the table, 27.4% and 4.4% |
| Discrimination by year | ROC-AUC 0.724 (2016) to 0.770 (2018), above the table in every year |
| Calibration in the large by year | −0.18 in 2016 (11.0% observed, the lowest of the eight years); −0.09 to +0.10 in the others |
| Zones | interurban ROC-AUC 0.704, slope 1.08; urban 0.664, slope 1.17; through town 0.595, slope 0.62 |
| Barcelona city | urban streets in the city: ROC-AUC 0.665, mean predicted 7.9% against 8.5% observed; urban streets elsewhere: 0.660, 6.9% against 6.0% |
| Periods (models fitted on 2010–2016 and 2017–2023, `sev_stability`) | heavy vehicle ×1.89 and ×2.04; junction ×0.85 and ×0.79; unlit night ×1.42 and ×1.26; head-on ×1.34 and ×1.67; ran off the road ×1.20 and ×1.79; posted 40–50 km/h ×0.80 and ×1.00; heavy rain ×0.68 and ×1.07 |
| Areas (Barcelona province against the other three) | heavy vehicle ×1.93 and ×1.87; junction ×0.87 and ×0.78; posted 40–50 km/h ×0.96 and ×0.86 |

The penalty was chosen on 2021–2022, which are also test years in the rolling evaluation. 2023
played no part in any choice: there the model scores ROC-AUC 0.755 against 0.708 for the table.

The transfer tests of the original pipeline concern a different specification. Restricted to the
variables DGT records alike, a Catalan model ranked severe crashes elsewhere in Spain about as
well as a model trained there (ROC-AUC 0.708 against 0.712), but fatal crashes are commoner in the
rest of Spain (15.4% against 12.6%). The calculator's probabilities describe Catalonia; elsewhere
they are likely to be low.

## Implementation for the page

`scripts/severity_calculator.py calculator` writes `reports/models/severity_model.json`, which
holds:

- the columns and coefficients, and the lower triangle of the bootstrap covariance;
- a `model_id` (a hash of the columns and coefficients), which the page also carries, so that the
  page refuses a model file from another build;
- the input specification with labels, defaults and rules;
- the number of training crashes (and fatal ones) for each combination of zone, crash type, road
  users and number involved, the number per road and input level, and the observed fatal share
  per zone and province;
- the evaluation.

The browser engine builds the same 0/1 design vector as `severity_model.design_matrix`. It throws
on an unknown road, province or level rather than silently using the reference. It provides:

- `predict(s)`: `expit(x'b)` and its 95% interval `expit(x'b ± 1.96 √(x'Vx))`.
- `compare(a, b)`: the ratio and the difference of two scenarios' predicted fatal shares, each with
  a 95% delta-method interval from the same covariance.
- `check(s)`: the rules a scenario breaks.
  - Errors, each broken by at most one of the training records: no road user ticked; fewer
    vehicles and pedestrians than kinds of road user; a pedestrian struck without a pedestrian.
  - Warnings: a collision with one unit; a pedestrian and no vehicle; fewer than 20 recorded
    crashes of the same zone, type, users and number; fewer than 20 on the chosen road with a
    chosen level.
  - A road through a town gives no estimate. The model cannot rank crashes there (ROC-AUC 0.59,
    slope 0.62), so the page shows the observed fatal share for such roads in the chosen province.
- `similar(s)`: how many recorded crashes share the scenario's zone, crash type, road users and
  number involved, and how many of them were fatal.

The worked examples on the page (`sev_contrasts`) use the same formulae, so they and the
calculator always give the same numbers; a test requires it. `tests/test_severity_engine.py` runs
the engine under Node on several hundred scenarios: both reference crashes, every one-input change
of them, every province, and random valid scenarios. It requires:

- the design vector to be identical, and the probability, interval and comparison to agree with
  the Python reference to within 10⁻¹⁰;
- the exported coefficients to reproduce the fitted model, and every input to change the
  prediction;
- the artefact roads never to be offered, and the error rules to hold in the training records.

## What the model shows

The figures are predicted fatal shares from the final model with 95% intervals (`sev_contrasts`).
Each is for a reference crash and that crash with one circumstance changed. The raw and
standardised shares are in `sev_marginal_adjusted`. The reference crash:

- a side or angle collision between two cars or vans;
- on a regional conventional road in the province of Barcelona, between junctions;
- in daylight, fine weather and on a dry surface, between 10:00 and 13:59;
- with no posted limit recorded.

Its predicted fatal share is 10.9%.

1. **Where the crash happens.** The same crash on an urban street: 5.7% (4.8–6.7%), 0.52 times the
   interurban figure. In the other three provinces the interurban figure is higher: Girona ×1.57
   (1.40–1.77), Lleida ×1.49 (1.30–1.70), Tarragona ×1.77 (1.58–1.98). On urban streets the
   provinces differ less (×0.80 to ×1.20). Among interurban roads, State conventional roads are
   level with regional ones (×1.01, 0.91–1.13); provincial roads and dual carriageways are lower
   (×0.76 and ×0.80). Motorways cannot be told apart from regional roads (×0.93, 0.73–1.19; 223
   crashes).
2. **A heavy vehicle doubles the fatal share.** Adding a lorry or bus to the reference crash raises
   it to 21.9% (×2.01, 1.81–2.23). The association has about the same size in both periods and both
   areas (×1.87–2.04).
3. **Crash type carries less than its raw share suggests.** Head-on collisions were fatal in 24% of
   cases, against 8.7% for side collisions, but they happen mostly on interurban roads.
   Standardised to the same mix of circumstances the shares are 16.2% and 11.1%. In the model:
   - head-on ×1.51 (1.34–1.70), ran off the road ×1.50 and hit an object ×1.52 are the most
     fatal types;
   - rear-end collisions (×0.71) and sideswipes (×0.65) are the least.
   Pedestrian crashes run the other way: 10.5% raw and 13.9% standardised, because most happen on
   urban streets. The crash-type contrasts are larger in 2017–2023 than in 2010–2016 (ran off the
   road ×1.79 against ×1.20), so this ranking is less settled than the others.
4. **Night.** Against the late morning, crashes at 22:00–23:59 are associated with ×1.33
   (1.13–1.56) and at 00:00–05:59 with ×1.37 (1.18–1.59). An unlit road at night adds ×1.36
   (1.20–1.54). Most of the raw excess of unlit-night crashes (28.3% fatal against 10.6% in
   daylight) comes from where and when they happen (15.3% standardised).
5. **Junctions and rain.** Crashes within a junction are associated with ×0.83 (0.75–0.91),
   similar in both periods and both areas. Heavy rain, hail or snow goes with ×0.76 (0.60–0.97),
   but ×0.68 in 2010–2016 and ×1.07 in 2017–2023. That estimate is not stable and the page says
   so.
6. **Posted limits.** A posted 80–90 or 100–120 km/h limit goes with ×1.20 and ×1.24 against no
   posted limit; 40–50 km/h with ×0.89 (0.78–1.01), but ×0.80 in the first period and ×1.00 in the
   second. These are signs, not speeds, and the crashes that carry a recorded limit are not a random
   sample of the roads.
7. **What the model adds.** Over the fatal share of the crash's road and type, the model raises
   ROC-AUC from 0.709 to 0.743 and lowers the log loss by 0.011. The table ignores the province,
   the road users involved, the time of day, lighting, weather, surface, junction and posted limit.
   The gain is real but modest: most of what these records can tell is in the road and the type of
   crash.
8. **Where it is unreliable.** The model ranks severe crashes on urban streets only moderately
   (ROC-AUC 0.66), and on roads through towns not at all, where the page shows the average
   instead. For rare combinations (fewer than 20 similar recorded crashes) it extrapolates from its
   additive structure, and the page warns.

## Limitations

The data are the police records of severe crashes in one region. A death counts only if it came
within 24 hours, so the shares are lower than 30-day shares would be. No vehicle speeds, seat-belt
or helmet use, alcohol or drug results, or ages are recorded. A predicted fatal share describes
recorded crashes like the scenario. It is not anyone's chance of dying in a crash, because the
model conditions on someone having been killed or seriously injured. The intervals reflect the
uncertainty of the coefficients, not the differences between periods and places shown above.
