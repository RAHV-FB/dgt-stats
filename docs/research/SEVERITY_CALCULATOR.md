# The crash-severity calculator

**Question.** Given the recorded circumstances of a crash in which someone was killed or seriously
injured, what is the probability that it was fatal?

The answer is a model of severity *given* a severe crash. The data contain only crashes, so the
model says nothing about how likely a crash is to happen, how risky a road is per kilometre, or
what changing a road or a condition would do. A difference between two scenarios is an
association between modelled scenarios in these records. Code: `src/dgt_stats/severity_model.py`,
`scripts/severity_calculator.py calculator`; browser engine:
`src/dgt_stats/site/assets/severity-engine.js`; tests: `tests/test_severity_engine.py`.

## Data

Three sources could support the question.

| Source | Unit | Fatal cases | Why chosen or not |
|---|---|---|---|
| Servei Català de Trànsit, 2010–2023 | crash with a death or serious injury | 3,093 of 24,478 | **chosen**: the population the question names, fourteen years, road, conditions and units involved recorded in every row |
| DGT crash microdata, 2016–2024 | injury crash, Spain | about 14,000 of 875,013 | not used to train: fields are blank at rates that differ by province and by outcome, and the blanks alone rank fatal crashes with ROC-AUC 0.72 ([`DGT_MICRODATA_AUDIT.md`](../DGT_MICRODATA_AUDIT.md)) |
| Guàrdia Urbana, Barcelona 2025 | person or crash | 13 deaths | far too few fatal cases for this question |

## Inputs

The inputs are circumstances recorded about the road and conditions before the crash, and about
the crash itself (its type and who was involved). The calculator groups them so that a reader
can choose each one.

| Input | Levels | Default |
|---|---|---|
| Road | urban street; road through a town; motorway; dual carriageway; conventional road on the State, regional, provincial or local network; rural track; other interurban road | urban street |
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
driver fled is left out too, since it depends on the outcome. The fog field, recorded present in
a tenth of urban crashes, which is not credible, is excluded, and so are the province and the
date, which add nothing (ROC-AUC 0.7814 with them, 0.7811 without, boosted trees on 2016–2023).
The posted limit is the signposted limit where the record carries one; it is not a vehicle's
speed, and 73% of records carry none.

**The road owner's recording artefact.** On interurban conventional roads the owner field takes two
values that track how the crash was documented rather than the road: "Altres" (1,410 crashes, 3.0%
fatal) and blank (430 crashes, 54% fatal), against 15–26% on the named networks. These crashes stay
in the training data as two road categories of their own, so that they do not bias the named
networks, but no reader can choose them.

**Missing values.** Six crashes with unspecified lighting, four with unspecified weather and four
with unspecified surface are given the most common level; the posted limit's "not recorded" is a
level of its own. No other input has missing values.

## Choice of model

Three candidates were fitted on identical inputs and scored by rolling origin: each year
2016–2023 is predicted by a model fitted only on the years before it (12,961 crashes, 1,627 fatal;
`sev_rolling_scores`, `sev_comparison`).

| Model | ROC-AUC | Brier skill | Log loss | Calibration slope | Mean predicted (observed 12.6%) |
|---|---|---|---|---|---|
| Penalised logistic regression (chosen) | 0.772 (0.759–0.784) | 0.137 | 0.321 | 1.04 | 12.5% |
| Gradient-boosted trees | 0.778 (0.766–0.790) | 0.144 | 0.318 | 1.12 | 12.4% |
| Fatal share of the road × crash type | 0.745 (0.733–0.757) | 0.102 | 0.333 | 1.19 | 12.0% |

The trees rank slightly better (+0.006, paired interval +0.002 to +0.010) and have a slightly lower
log loss (−0.003). The logistic regression was chosen for four reasons:

1. Its probabilities spread as far as the outcomes do (slope 1.04 against 1.12), and probabilities
   are what the page shows.
2. Every prediction is a sum of named coefficients, so the browser reproduces it exactly.
3. A coefficient covariance gives an interval for any scenario.
4. Its contrasts are adjusted for every other input, which is the comparison Task 6 needs.

Both models improve clearly on the descriptive table (ROC-AUC +0.027, paired interval +0.019 to
+0.035; log loss −0.012).

**Specification.** Every input has an effect common to all zones and, for urban streets and
interurban roads, a deviation from it; roads through towns, with 1,180 crashes, take the common
effects. The deviations are penalised four times as hard as the common effects (in variance), and
the zone intercepts hardly at all. The penalty (C = 3) and the deviation scale (0.25) were chosen
on 2021–2022 after fitting on 2010–2020, by log loss over a grid of 15 (`sev_penalty`); the grid's
best eight settings lie within 0.0003 of each other. The final model is fitted on all 24,478
crashes, 129 coefficients (`sev_coefficients`).

## Validation

| Check | Result |
|---|---|
| Discrimination by year (each from earlier years only) | ROC-AUC 0.744 (2016) to 0.803 (2018), no trend |
| Calibration in the large by year | within ±0.09 on the log-odds scale except 2016 (−0.18: 11.3% observed, the lowest of the eight years) |
| Calibration slope by year | 0.93–1.25 |
| Zones | interurban ROC-AUC 0.766, slope 1.06; urban 0.673, slope 0.85; through-town 0.596, slope 0.53 |
| Roads a reader can choose (without the two recording categories) | ROC-AUC 0.738, slope 0.96 |
| Periods (models fitted on 2010–2016 and on 2017–2023) | heavy-vehicle involvement ×1.87 and ×2.10; junction ×0.77 and ×0.73; posted 40–50 km/h ×0.59 and ×0.67; head-on ×1.22 and ×1.79 (`sev_stability`) |
| Areas (Barcelona province against the other three) | heavy vehicle ×1.92 and ×2.01; junction ×0.61 and ×0.80; posted 40–50 km/h ×0.70 and ×0.64 |
| Uncertainty | 200 bootstrap refits of the final model; their covariance gives the page's 95% intervals |

The original pipeline's transfer tests apply to this model's domain too: a Catalan model ranked
Barcelona city's severe crashes worse than the rest of Catalonia's and was badly calibrated there
(slope 0.44), and restricted to the variables DGT records alike it ranked severe crashes elsewhere
in Spain about as well as a model trained there (ROC-AUC 0.708 against 0.712), with fatal crashes
commoner in the rest of Spain (15.4% against 12.6%). The calculator's probabilities describe
Catalonia; elsewhere they are likely to be low.

## Implementation for the page

`scripts/severity_calculator.py calculator` writes `reports/models/severity_model.json`. The file
holds the columns and coefficients, the lower triangle of the bootstrap covariance, the input
specification with labels, defaults and rules, the number of training crashes (and fatal ones)
for each combination of zone, crash type, road users and number involved, the number per zone
and input level, and the evaluation. The browser engine builds the same 0/1 design vector as
`severity_model.design_matrix` and returns:

- `predict(s)`: `expit(x'b)` and its 95% interval `expit(x'b ± 1.96 √(x'Vx))`;
- `compare(a, b)`: the ratio and the difference of two scenarios' predicted fatal shares, each
  with a 95% delta-method interval from the same covariance;
- `check(s)`: the rules a scenario breaks: errors (no road user ticked; fewer vehicles and
  pedestrians than kinds of road user; a pedestrian struck without a pedestrian), each of which
  at most one of the 24,478 records breaks, and warnings (a collision with one unit, a pedestrian
  and no vehicle, a road through a town, fewer than 20 recorded crashes of the same zone, type,
  users and number, or fewer than 20 in the zone with a chosen level);
- `similar(s)`: how many recorded crashes share the scenario's zone, crash type, road users and
  number involved, and how many of them were fatal.

`tests/test_severity_engine.py` runs the engine under Node on 302 scenarios (both reference
crashes, every one-input change of them and random valid scenarios) and requires the design
vector to be identical and the probability, interval and comparison to agree with the Python
reference to within 10⁻¹⁰. It also checks that the exported coefficients reproduce the fitted
model, that every input changes the prediction, that the recording categories are never offered,
and that the three error rules hold in the training records.

## What the model shows

The figures are predicted fatal shares from the final model with 95% bootstrap intervals
(`sev_contrasts`), for a reference crash and that crash with one circumstance changed, and the
raw against standardised shares in `sev_marginal_adjusted`. The reference is a side collision
involving a car on a regional conventional road, in daylight, fine and dry, between junctions, with
no posted limit recorded, in the late morning: 18.0% (14.9–21.6%).

1. **Where the crash happens matters most.** The same crash on an urban street has a predicted
   fatal share of 3.3% (2.4–4.5%), 0.18 times the interurban figure. Among interurban roads, State
   conventional roads are about level with regional ones (×1.09, 0.99–1.22), provincial roads and
   dual carriageways lower (×0.76 and ×0.79). Motorways cannot be told apart from regional roads
   (×0.87, 0.61–1.12; 223 crashes).
2. **A heavy vehicle doubles the fatal share.** Adding a lorry or bus to the reference crash raises
   it to 35.5% (×1.97, 1.79–2.24); on an urban street ×2.6 (2.0–3.4). The association has the
   same size in both periods and both areas (×1.87–2.10).
3. **Crash type carries less than its raw share suggests.** Head-on collisions were fatal in 25% of
   cases, against 8.9% for side collisions, but they happen mostly on interurban roads. Standardised
   to the same mix of circumstances, the shares are 13.3% and 10.6%. Running off the road (×1.55)
   and striking a pedestrian (×1.49) are the most fatal types on interurban roads; rear-end
   collisions (×0.61) and sideswipes (×0.53) the least. Pedestrian crashes run the other way:
   11.0% raw, 16.1% standardised, because most happen on urban streets. The crash-type contrasts
   are larger in 2017–2023 than in 2010–2016 (head-on ×1.79 against ×1.22), so this ranking is less
   stable than the others.
4. **Late night and darkness.** Against the late morning, crashes at 22:00–23:59 are associated
   with ×1.52 (1.23–1.82) and at 00:00–05:59 with ×1.41 (1.19–1.67). Unlit night on interurban roads
   adds ×1.22 (1.04–1.39), but most of its raw excess (28.1% fatal against 11.0% in daylight) comes
   from where and when such crashes happen (15.8% standardised), and the association weakens from
   ×1.38 in 2010–2016 to ×1.03 in 2017–2023.
5. **Posted limits.** A posted 40–50 km/h limit on an interurban road goes with a lower fatal share
   than no posted limit (×0.60, 0.50–0.70), in both periods and both areas. On urban streets a
   posted 60–70 km/h limit goes with ×3.5 (2.2–5.2). These are signs, not speeds, and the crashes
   that carry a recorded limit are not a random sample of the roads.
6. **Junctions, rain and darkness of sky.** Crashes within a junction are associated with
   ×0.75 (0.64–0.85), stable across periods. Heavy rain, hail or snow goes with a lower fatal
   share (×0.71, 0.50–0.97): among severe crashes, rain is associated with the less deadly ones.
7. **What the model adds.** Over the fatal share of the crash's road and type, the model raises
   ROC-AUC from 0.745 to 0.772 and lowers the log loss by 0.012; the table ignores the road users
   involved, the time of day, lighting, weather, surface, junction and posted limit.
8. **Where it is unreliable.** The model ranks severe crashes on urban streets only moderately
   (ROC-AUC 0.67) and on roads through towns barely at all (0.60); for rare combinations (fewer
   than 20 similar recorded crashes) it extrapolates from its additive structure. The page warns
   in both cases.

## Limitations

The data are the police records of severe crashes in one region. Severity definitions are those
of the Servei Català de Trànsit; the file does not state the time window of a death. No vehicle
speeds, seat-belt or helmet use, alcohol or drug results, or ages are recorded. A predicted fatal
share describes recorded crashes like the scenario; it is not anyone's chance of dying in a crash,
because the model conditions on someone having been killed or seriously injured.
