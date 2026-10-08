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
| DGT crash microdata, 2016–2024 | injury crash, Spain | about 14,000 of 875,013 | not used to train: fields are blank at rates that differ by province and by outcome, and the fields left unrecorded where they apply rank fatal crashes on their own with ROC-AUC 0.68 (`dgt_audit_artefacts.csv`, deaths within 30 days; [`DGT_MICRODATA_AUDIT.md`](../DGT_MICRODATA_AUDIT.md)) |
| Guàrdia Urbana, Barcelona 2025 | person or crash | 13 deaths | far too few fatal cases for this question |

**The road owner's recording artefact.** On interurban conventional roads the owner field takes two
values that track how a crash was documented rather than the road: "Altres" (1,410 crashes, 3.0%
fatal) and blank (430 crashes, 53% fatal), against 15–26% on the named networks. "Altres" grew from
27 crashes in 2010 to about 170 a year from 2019. These 1,840 crashes are left out of fitting, of
evaluation and of every count and average the page shows (`sev_population`). The estimates and
tests therefore describe crashes on roads with a named owning network or of another type. The
crashes left out were fatal in 14.7% of cases, so with them the fatal share of all crashes would
be 12.6% rather than 12.5%, and of interurban crashes 19.2% rather than 20.0%. The calculator's
comparison figures say that they are averages over the fitted crashes. An earlier version kept
the artefact roads as two categories used only in training; its pooled score then included them,
and they made its ranking look better than it was on the roads a reader can choose.

## Inputs

The inputs are circumstances recorded about the road and conditions before the crash, and about
the crash itself (its type and who was involved).

| Input | Levels | Default |
|---|---|---|
| Province | Barcelona, Girona, Lleida, Tarragona | Barcelona |
| Road | urban street; road through a town; motorway; dual carriageway; conventional road on the State, regional, provincial or local network; rural track; other interurban road | conventional road, regional network |
| Type of crash | pedestrian struck; head-on; side or angle; rear-end; sideswipe; ran off the road; hit an object; rider or occupant fell; other | side or angle |
| Lighting | daylight; daylight, overcast; dawn or dusk; night with adequate, poor or no street lighting | daylight |
| Weather | fine; light rain; heavy rain, hail or snow | fine |
| Road surface | dry; wet; slippery, flooded, icy or snowy | dry |
| Junction | between junctions; within a junction; within 50 m of one | between junctions |
| Posted speed limit | none recorded (the road's generic limit); 10–30; 40–50; 60–70; 80–90; 100–120 km/h | none recorded |
| Time of day | six bands | 10:00–13:59 |
| Road users involved | pedestrian, bicycle, moped, motorcycle, car or van, heavy vehicle, other (any combination) | car or van |
| Number involved | one, two, three, four or more (vehicles and pedestrians) | two |

The lighting value "De dia, dia fosc" is labelled "daylight, overcast", as on the Catalonia page.

**Left out.** The police's judgements of which conditions influenced the crash are left out,
because they are made after the event and fatal crashes are investigated more fully. Whether a
driver fled is left out too, since it depends on the outcome. The fog field is excluded: it is
recorded present in a tenth of urban crashes, which is not credible. The date is excluded. The
posted limit is the signposted limit where the record carries one; it is not a vehicle's speed,
and 72% of records carry none.

**Missing values.** Crashes with unspecified lighting, weather or surface (six, four and four) are
given the most common level; the posted limit's "not recorded" is a level of its own. No other
input has missing values.

## Specification and the choices made on data

A logistic regression with:

- one intercept for each zone (urban street, road through a town, interurban road) in each
  province, Barcelona being the reference province;
- an effect for each interurban road type (a regional conventional road is the reference);
- one effect for each level of every other input, either common to all zones ("common", 58
  coefficients) or with an additional departure on urban streets and on interurban roads
  ("by zone", 136 coefficients).

Every coefficient but the intercepts takes the same L2 penalty; the intercepts are penalised
hardly at all. Three choices are made on data, always by the same rule (`severity_model.select`):
fit on all but the last two years of the crashes the choice may use, score those two years by
log loss, and keep the best.

- **The penalty.** C runs over half-decades from 0.001 to 32. While the best value is at either
  end, the grid is extended by a half-decade on that side, up to C = 0.0001 or 1,000, so the
  chosen value has a worse one on each side. The earlier grid (0.1 to 30) stopped at its best
  value, C = 0.1, where the validation loss was still falling.
- **The specification**: common or by zone, whichever has the lower validation loss at its own
  best penalty.
- **Roads through towns**: the model's estimate, or the average fatal share of such roads in the
  province, whichever has the lower log loss on the validation years' crashes on such roads.

**The published model** follows the rule on all the years: fitted on 2010–2021 and scored on
2022–2023, the by-zone specification (validation log loss 0.3321) beat the common one (0.3334),
with C = 0.1, inside the grid; on the 198 through-town crashes of 2022–2023 (26 fatal), the
average (0.4006) beat the model (0.4043). It is then fitted on all 22,638 crashes of 2010–2023.
Its covariance comes from 500 bootstrap refits of the training crashes. This changed the
published model: the earlier one had common effects (58 coefficients); the choices of penalty and
through-town rule are unchanged (C = 0.1, the average).

## Evaluation: nested rolling origin

Each year 2016–2023 is predicted by a model whose three choices were made on the years before it
alone, by the rule above, and whose coefficients were then fitted on all the years before it.
For 2016 the choices are made by fitting on 2010–2013 and scoring 2014–2015; for 2023, by fitting
on 2010–2020 and scoring 2021–2022. The table of fatal shares by road and crash type is fitted on
the same years. No choice sees the year it predicts. The file ends in 2023, so no later year is
left for a further test. Gradient-boosted trees on the same inputs, with fixed settings, are
fitted on the same years for comparison. The choices, year by year (`sev_choices`, with every
grid point in `sev_penalty`):

| Test year | Choices made on | Specification | C | Roads through towns |
|---|---|---|---|---|
| 2016 | 2010–2013, scored on 2014–2015 | by zone | 0.1 | average |
| 2017 | 2010–2014, scored on 2015–2016 | common | 1,000 (the grid's weak end: the loss had stopped changing, so in effect unpenalised) | model |
| 2018 | 2010–2015, scored on 2016–2017 | common | 0.32 | model |
| 2019 | 2010–2016, scored on 2017–2018 | by zone | 0.1 | model |
| 2020 | 2010–2017, scored on 2018–2019 | by zone | 0.032 | model |
| 2021 | 2010–2018, scored on 2019–2020 | by zone | 0.01 | model |
| 2022 | 2010–2019, scored on 2020–2021 | by zone | 0.1 | average |
| 2023 | 2010–2020, scored on 2021–2022 | by zone | 0.1 | average |

There are 11,611 crashes on the roads a reader can choose, 1,429 of them fatal
(`sev_rolling_scores`, `sev_comparison`, `sev_calibration`).

| Model (nested rolling origin, 2016–2023) | ROC-AUC (95% interval) | Brier skill | Log loss | Calibration slope | Mean predicted (observed 12.3%) |
|---|---|---|---|---|---|
| Penalised logistic regression (published) | 0.741 (0.727–0.754) | 0.098 | 0.331 | 1.05 | 12.3% |
| Gradient-boosted trees | 0.748 (0.734–0.761) | 0.102 | 0.329 | 1.08 | 12.3% |
| Fatal share of the road × crash type | 0.709 (0.694–0.723) | 0.069 | 0.342 | 1.08 | 12.2% |

The logistic regression's ROC-AUC is higher than the table's by 0.032 (paired bootstrap interval
+0.022 to +0.042) and its log loss lower by 0.011 (0.008 to 0.014). The trees rank a little
better than the logistic regression: +0.007 in ROC-AUC (+0.001 to +0.012) and −0.002 in log loss
(−0.004 to −0.000). The logistic regression is published for three reasons:

- Every prediction is a sum of named coefficients, so the browser reproduces it exactly.
- A coefficient covariance gives an interval for any scenario, and for a comparison of two.
- Its contrasts are adjusted for every other input.

**What nesting changed** (`sev_nested_steps`). The figures published before (ROC-AUC 0.7425,
gain over the table +0.034, slope 1.10) were not nested: the penalty was chosen on 2021–2022,
which are test years, and the specification and the through-town rule were decided on the
2016–2023 rolling scores, 2023 included. Replacing those choices one at a time:

| Design | ROC-AUC | Gain over the table (95% paired interval) | Calibration slope |
|---|---|---|---|
| Previous (not nested) | 0.7425 | +0.034 (+0.023 to +0.044) | 1.10 |
| Penalty nested | 0.7414 | +0.032 (+0.022 to +0.042) | 1.08 |
| Penalty and specification nested | 0.7417 | +0.033 (+0.023 to +0.042) | 1.05 |
| Every choice nested (published) | 0.7409 | +0.032 (+0.022 to +0.042) | 1.05 |

Nesting the penalty changed four years; most of the fall is 2017, where the unpenalised model
chosen on 2015–2016 ranked 2017 less well (0.726 against 0.731). The by-zone specification, chosen
in six of the eight years, ranked about as well and brought the slope closer to 1. The average on
roads through towns, chosen in 2016, 2022 and 2023, predicted those years' through-town crashes
less well than the model would have. The original model (boosted trees on the original feature
set, including the road owner's artefact values) scored ROC-AUC 0.779 on all 12,961 crashes of
the same years. On the 11,611 crashes on the roads a reader can choose it scores 0.7475, the same
as the trees here (0.7476). Its apparent advantage came from the artefact.

## Validation

All figures are from the nested evaluation unless marked.

| Check | Result |
|---|---|
| Calibration by tenth of predicted probability (`sev_calibration`) | the mean prediction lies inside the 95% interval of the observed share in nine of ten groups; in the ninth tenth the model said 21.8% and 24.7% were fatal (22.3–27.3%) |
| Calibration slope and intercept, pooled | 1.05 and 0.07: the crashes rated most and least likely to be fatal were a little more extreme than predicted |
| Fifths | of the fifth rated most likely to be fatal, 30.2% were; of the fifth rated least likely, 3.4%; for the table, 27.4% and 4.4% |
| Discrimination by year | ROC-AUC 0.716 (2016) to 0.769 (2018), above the table in every year |
| Calibration by year | in 2016 the model predicted 12.9% and 11.0% were fatal (9.6–12.6%), outside the interval; in every other year the mean prediction lies inside the observed interval |
| Zones | interurban ROC-AUC 0.701, slope 1.02, 19.9% predicted against 21.0% (19.8–22.2%); urban 0.660, slope 0.92, 7.3% against 6.6% (6.0–7.2%), too high; through town 0.544, scored with the average in three of the eight years |
| Provinces and zones (`sev_rolling_scores`, "province and zone") | outside the observed interval on interurban roads in Girona (23.5% against 26.8%, 23.8–30.1%) and Tarragona (27.2% against 31.0%, 27.8–34.4%), and on urban streets in the province of Barcelona (7.5% against 6.7%, 6.0–7.5%); inside it in the other nine zones of provinces |
| Barcelona city | urban streets in the city: ROC-AUC 0.658, mean predicted 8.1% against 8.5% observed; urban streets elsewhere: 0.661, 7.1% against 6.0% |
| A province left out (`sev_geography`; no province terms, choices made on the other three) | ROC-AUC 0.68 (Barcelona) to 0.77 (Tarragona). Mean estimate against observed: Barcelona 11.2% against 9.5% (9.1–10.0%), too high; Girona 14.3% against 17.2% (15.9–18.5%), too low; Lleida 16.4% against 17.6% (16.1–19.2%), inside; Tarragona 14.3% against 17.0% (15.7–18.3%), too low |
| Barcelona city's urban streets from the rest of Catalonia's | ROC-AUC 0.656; 5.9% predicted against 9.9% (8.8–11.0%) |
| Periods (models fitted on 2010–2016 and 2017–2023, `sev_stability`) | heavy vehicle ×1.86 and ×2.07; junction ×0.76 and ×0.76; head-on ×1.23 and ×1.74; ran off the road ×1.17 and ×1.95; unlit night ×1.43 and ×1.20; posted 40–50 km/h ×0.62 and ×0.77; heavy rain ×0.63 and ×1.12. Of the eleven changes in the page's table, seven have 95% intervals on the same side of 1 in both periods; ran off the road, 00:00–05:59, an unlit road at night and heavy rain do not |
| Areas (Barcelona province against the other three) | heavy vehicle ×1.81 and ×1.93; junction ×0.69 and ×0.81; posted 40–50 km/h ×0.75 and ×0.66 |

The site's earlier wording, that the estimates could be read "roughly at face value" and that they
missed only in the province of Barcelona, did not hold: the provinces left out and three zones of
provinces in the nested test miss their observed intervals, so the page lists them.

The transfer tests of the original pipeline concern a different specification. Restricted to the
variables DGT records alike, a Catalan model ranked severe crashes elsewhere in Spain nearly as
well as a model trained there (ROC-AUC 0.710 against 0.721), but fatal crashes are commoner in the
rest of Spain (15.4% against 12.6%). The calculator's probabilities describe Catalonia; elsewhere
they are likely to be low.

## Implementation for the page

`scripts/severity_calculator.py calculator` writes `reports/models/severity_model.json`, which
holds:

- the columns and coefficients, and the lower triangle of the bootstrap covariance;
- a `model_id` (a hash of the columns and coefficients), which the page also carries, so that the
  page refuses a model file from another build;
- the published choices (`choice`: specification, C, the through-town rule and the years they
  were made on);
- the input specification with labels, defaults and rules;
- the number of training crashes (and fatal ones) for each combination of zone, crash type, road
  users and number involved, the number per road and input level, and the observed fatal share
  per zone and province with its count and Wilson 95% interval (`zone_average`, `zone_counts`);
- the number of crashes left out for the road-owner artefact, and how many were fatal;
- the nested evaluation.

The browser engine builds the same 0/1 design vector as `severity_model.design_matrix`,
including the by-zone columns (`urban:…`, `interurban:…`). It throws on an unknown road, province
or level rather than silently using the reference. It provides:

- `predict(s)`: `expit(x'b)` and its 95% interval `expit(x'b ± 1.96 √(x'Vx))`.
- `compare(a, b)`: the ratio and the difference of two scenarios' predicted fatal shares, each with
  a 95% delta-method interval from the same covariance.
- `check(s)`: the rules a scenario breaks.
  - Errors, each broken by at most one of the training records: no road user ticked; fewer
    vehicles and pedestrians than kinds of road user; a pedestrian struck without a pedestrian.
  - Warnings: a collision with one unit; a pedestrian and no vehicle; fewer than 20 recorded
    crashes of the same zone, type, users and number; fewer than 20 on the chosen road with a
    chosen level.
  - A road through a town gives no estimate when the published choice gives such roads the
    average (it does): the page shows the observed fatal share for such roads in the chosen
    province with its count and 95% interval (Lleida: 16 of 103).
- `similar(s)`: how many recorded crashes share the scenario's zone, crash type, road users and
  number involved, and how many of them were fatal.

The page says, beside every estimate, that it is a share of crashes already recorded with a death
or serious injury, not the chance of a crash or of a death on a journey. Its comparison figures
are labelled as shares of the crashes the model was fitted on, with their counts, and the
paragraph above the calculator says that those crashes leave out the 1,840 on roads with no named
owning network.

The worked examples on the page (`sev_contrasts`) use the same formulae, so they and the
calculator always give the same numbers; a test requires it. `tests/test_severity_engine.py` runs
the engine under Node on more than 300 random valid scenarios and every edge case (every road in
every province, every level of every input on three roads, the boundaries of the rules). It
requires:

- the design vector to be identical, and the probability and interval to agree with the Python
  reference to within 10⁻¹² and with an independent computation from the exported column names,
  coefficients and covariance alone to within 10⁻¹⁰; the comparison to agree to within 10⁻¹⁰;
- the exported model to be the one the published choices give, and every input to change the
  prediction;
- the artefact roads never to be offered, the error rules to hold in the training records, and
  the through-town rule to follow the published choice;
- the calculator's text to frame the estimate as a conditional share.

## What the model shows

The figures are predicted fatal shares from the final model with 95% intervals (`sev_contrasts`).
Each is for a reference crash and that crash with one circumstance changed. The raw and
standardised shares are in `sev_marginal_adjusted`. The reference crash:

- a side or angle collision between two cars or vans;
- on a regional conventional road in the province of Barcelona, between junctions;
- in daylight, fine weather and on a dry surface, between 10:00 and 13:59;
- with no posted limit recorded.

Its predicted fatal share is 13.4%. Because the published model lets each input's association
differ on urban streets and interurban roads, the same change can go with different ratios on the
two kinds of road; the figures below are for the interurban reference crash unless marked.

1. **Where the crash happens.** The same crash on an urban street: 3.7% (2.9–4.7%), 0.27 times the
   interurban figure. In the other three provinces the interurban figure is higher: Girona ×1.49
   (1.33–1.68), Lleida ×1.41 (1.24–1.60), Tarragona ×1.66 (1.49–1.86). On urban streets the
   provinces differ less (×0.79 to ×1.19). Among interurban roads, State conventional roads are
   level with regional ones (×1.02, 0.92–1.13); provincial roads (×0.78) and local roads (×0.74)
   are lower, dual carriageways about level (×0.85, 0.71–1.02). Motorways cannot be told apart from
   regional roads (×0.95, 0.75–1.20; 223 crashes).
2. **A heavy vehicle doubles the fatal share.** Adding a lorry or bus to the reference crash raises
   it to 26.5% (×1.98, 1.75–2.24); on the urban reference crash ×2.55 (2.08–3.12). The association has about the same size in both periods and both areas (×1.81–2.07).
3. **Crash type carries less than its raw share suggests.** Head-on collisions were fatal in 24% of
   cases, against 8.7% for side collisions, but they happen mostly on interurban roads.
   Standardised to the same mix of circumstances the shares are 13.6% and 11.1%. On interurban
   roads:
   - pedestrian struck ×1.50 (1.24–1.81), ran off the road ×1.47 (1.23–1.75) and head-on ×1.40
     (1.22–1.62) are the most fatal types;
   - rear-end collisions (×0.63) and sideswipes (×0.55) are the least.
   On urban streets a head-on collision is not distinguishable from a side collision (×0.93,
   0.68–1.26), while running off the road (×1.97) and hitting an object (×2.08) are higher.
   Pedestrian crashes are 10.5% fatal raw and 16.0% standardised, because most happen on urban
   streets. The crash-type contrasts are larger in 2017–2023 than in 2010–2016 (ran off the road
   ×1.95 against ×1.17), so this ranking is less settled than the others.
4. **Night.** Against the late morning, crashes at 22:00–23:59 on interurban roads are associated
   with ×1.41 (1.16–1.72) and at 00:00–05:59 with ×1.29 (1.07–1.57). An unlit road at night adds
   ×1.33 (1.15–1.53). Most of the raw excess of unlit-night crashes (28.3% fatal against 10.6% in
   daylight) comes from where and when they happen (15.7% standardised).
5. **Junctions and rain.** On interurban roads, crashes within a junction are associated with
   ×0.76 (0.65–0.88); on urban streets a junction makes no difference (×1.00, 0.86–1.16). Heavy
   rain, hail or snow goes with ×0.73 (0.54–0.99) on interurban roads. but ×0.63 in 2010–2016 and ×1.12 in 2017–2023. That estimate is not stable and the page says so. The junction association is the same in both periods (×0.76).
6. **Posted limits.** On interurban roads, a posted 80–90 or 100–120 km/h limit goes with ×1.10
   and ×1.18 against no posted limit, and 40–50 km/h with ×0.66 (0.56–0.77); on urban streets a
   posted 40–50 km/h limit goes with ×1.54 (1.25–1.91) and 60–70 km/h with ×2.61. These are signs,
   not speeds, and the crashes that carry a recorded limit are not a random sample of the roads.
7. **What the model adds.** Over the fatal share of the crash's road and type, the model raises
   ROC-AUC from 0.709 to 0.741 on the nested test and lowers the log loss by 0.011. The table
   ignores the province, the road users involved, the time of day, lighting, weather, surface,
   junction and posted limit. The gain is real but modest: most of what these records can tell is
   in the road and the type of crash.
8. **Where it is unreliable.** The model ranks severe crashes on urban streets only moderately
   (ROC-AUC 0.66) and estimates them a little high; on interurban roads in Girona and Tarragona its
   estimates were low; on roads through towns the page shows the average instead. For rare
   combinations (fewer than 20 similar recorded crashes) it extrapolates from its additive
   structure, and the page warns.

## Limitations

The data are the police records of severe crashes in one region, on roads with a named owning
network or of another type. A death counts only if it came within 24 hours, so the shares are
lower than 30-day shares would be. No vehicle speeds, seat-belt or helmet use, alcohol or drug
results, or ages are recorded. A predicted fatal share describes recorded crashes like the
scenario. It is not anyone's chance of dying in a crash, because the model conditions on someone
having been killed or seriously injured. The intervals reflect the uncertainty of the
coefficients, not the differences between periods and places shown above, nor the uncertainty of
the choices of penalty, specification and through-town rule.
