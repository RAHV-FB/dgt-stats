# Statistical audit of the published claims

Tasks 21–23. Every claim the site published when the rebuild began was checked. The claims are
those listed page by page in [`DEPENDENCY_MAP.md`](DEPENDENCY_MAP.md), §1. Each was checked for
four things:

* whether its number can be reproduced;
* whether numerator and denominator cover the same people, places and period;
* whether its wording claims more than the data show;
* whether it survives the evidence added by the rebuild.

Calculation errors found along the way were corrected and given a regression test. This document
records the verdicts, the corrections and the writing rules the rewritten text follows.

## How the claims were checked

* **Reproduction.** The site prints no number typed by hand. Every figure in its prose is formatted
  from a committed table when the site is built, and qualitative words are guarded by build checks.
  For example, "about twice" fails the build outside 1.8–2.2 ([`DEPENDENCY_MAP.md`](DEPENDENCY_MAP.md),
  §4.4). Rebuilding the data layers and the site from the raw files reproduced every committed table
  and all 24 HTML files byte for byte ([`AUDIT_BASELINE.md`](AUDIT_BASELINE.md)). The repository's
  482 reconciliation checks against published DGT totals all pass.
* **Independent recounts.** Headline counts were recomputed directly from the raw files, without
  the repository's pipeline. They reproduce exactly:
  * the Catalan file: 24,478 crashes with a death or serious injury, 3,093 of them fatal;
  * Barcelona 2025: 7,741 crashes, and 15,848 people with a recorded outcome, of whom 260 (1.6%)
    were seriously or fatally injured;
  * DGT's 2024 car drivers involved and killed by age, recomputed by
    `exposure_risk.national.drivers_involved` with its own band mapping. For example, 75 and over:
    4,455 involved and 71 killed among private-car drivers, 15.9 per 1,000, as published.
* **Scope.** For each rate, the population counted in the numerator was compared with the population
  in the denominator (the next sections).
* **Wording.** The published pages were searched for causal and risk language: cause, because,
  effect, leads to, reduces or increases risk, safer, more dangerous, prevent, save. Each sentence
  found was read in context. Associations are consistently described as associations. Police-
  recorded factors are described as police judgements. Every "because" is either an accounting
  identity, such as deaths per fuel = deaths per crash × crashes per fuel, or a statement about the
  data, not about road safety. No sentence needed correcting on these grounds.

## Verdicts

The verdicts used in the table below are:

* *Stands*: correct, adequately worded, no change.
* *Restated*: correct, but changed to match the rebuilt analysis.
* *Replaced*: the estimand was wrong for the claim, and a better estimate now exists.
* *Withdrawn*: removed.
* *Reworded*: the number stands but the sentence claimed too much.

| Page | Claim (at baseline) | Verdict | Reason and action |
|---|---|---|---|
| Overview | Road deaths fell 74% from 1993 to 2013; 1,785 deaths in 2024 | Stands | Yearbook series, reconciled against the published totals |
| Overview | Deaths per injury crash fell 73% (1996–2024); injury crashes per tonne of fuel 13% | Stands | An identity of published counts; fuel is labelled a traffic proxy |
| Overview, drivers | Drivers 75+ involved in an injury crash died 3.9 times as often as drivers 35–54 (15.9 against 4.1 per 1,000) | Restated | Exposure-free and correct. The rebuilt drivers page compares every age with 45–64, the reference of the exposure analysis: 15.9 against 4.6 per 1,000 (3.4 times), private cars |
| Overview, drivers | Drivers 18–24 were involved in 6.8 times as many injury crashes per km as drivers 35–54 (2.0 under an extreme reassignment) | Replaced | The kilometres were those of cars registered to owners of each age, not those driven by drivers of that age. Young drivers drive cars registered to others, so their kilometres were understated and their rate overstated. Replaced by the driver-age estimate: 18–29 at 2.57 times the 45–64 rate (95% CI 2.28–2.86; 1.6–3.7 across methods) ([`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md)) |
| Drivers | Drivers 75+ involved 1.43 times as often per km as drivers 65–74 | Withdrawn | Same owner-age denominator. No source measures kilometres at 75+; a conditional estimate (2.06 times the 45–64 rate if people aged 75 and over drive as much less than those aged 65–74 as in Madrid in 2018) is given beside the sensitivity range (0.97–3.28); see [75+ exposure](#75-exposure-constraining-the-estimate) |
| Drivers | Men died at the wheel of a car 3.63 times as often as women per licence holder, 2022–2024 | Reworded | The ratio is for drivers aged 18 and over; the headline sentence now says so (below). The denominator counts holders of any licence class; with car (B) licence holders, the ratio for 2023–2024 rises from 3.49 to 3.57, so the published figure is about 2% conservative. This is disclosed rather than changed, because B holders by sex are not available for the whole 2014–2024 series |
| Overview | Recorded inappropriate speed: about twice the deaths per crash, adjusted for road type | Stands | An association in police records, worded as one; the adjusted ratio (2.00, 1.69–2.36) is a quasi-Poisson estimate on the report's provinces |
| Overview | Of three models, two did better on later records than a table of the same records | Replaced | The independent re-evaluation found the Catalan model's gain partly rested on a recording artefact. The model was rebuilt as the severity calculator without the artefact crashes (ROC-AUC 0.743 against 0.709 for the road × crash-type table, over eight rolling years, and 0.741 once every choice of the model was nested in that test; the original model scores 0.7475 on the same crashes); the Barcelona crash model was removed and the person model kept for research only ([`ML_MODEL_REVIEW.md`](ML_MODEL_REVIEW.md)) |
| Trends | 1,785 deaths in 2024, 1.7% more than 2019; −1.9% per resident, +3.5% per tonne of fuel; variance 1.5, 7.7 and 68 times Poisson | Stands | Published series; the variance ratios are computed around a fitted trend and labelled so |
| Long run | Joinpoint segments; deaths per tonne of fuel −76%; 2020 below its range | Stands | Turning points are described as features of the series, not as effects |
| Seasons | July 1.22 and August 1.14 times the deaths; per tonne of fuel 1.12 and 1.09; April 2020 −68% | Stands | Quasi-Poisson month effects; fuel as a proxy, stated |
| Vehicles | Heavy trucks 10.3 times a car per vehicle and 2.5 times per km; motorcycles 2.2 and 10.1 | Stands, disclosed | Crash counts include foreign-registered vehicles; DGT's kilometres include Spanish vehicles' travel abroad. The page says so. The repository holds no nationality data, so the net direction is unknown |
| Speed | 6.9% of injury crashes in 2023 with inappropriate speed recorded, 21.8% of deaths; adjusted 2.00 | Stands | "Not an estimate of causation" stated on the page |
| Recorded factors | Shares and comparable windows; 33 of 135 changes are breaks | Stands | Break rule is a code constant, quoted from it |
| Crash circumstances | DGT association model: odds ratios; ROC-AUC 0.80 on 2023–2024 | Stands, labelled research only | Coefficients describe associations in police records; the unknown-alignment level is 95.7% Catalan, disclosed ([`ML_MODEL_REVIEW.md`](ML_MODEL_REVIEW.md)) |
| Monthly deaths forecast | Model error 6.6% against 5.9% for last year's count; a 15% fall detectable four times in five | Withdrawn | Last year's count beats the model in the ordinary held-out years. The minimum detectable change came from the rejected model's errors. The page becomes a withdrawal notice. `forecast.py` no longer calls the model "the one used" |
| Policy | Points licence: −7% (−13% to −1%); 2019 limit not estimated after a failed placebo | Stands | Interrupted series with placebos; "cannot show that the licence caused the fall" is stated |
| Catalonia | 24,478 crashes, 3,093 fatal (12.6%); 19.2% interurban against 6.9% urban | Stands (recounted) | Per-resident rates now use the 1 July population (below) |
| Barcelona | 7,741 crashes; 1.6% of 15,848 people seriously or fatally injured | Stands (recounted) | |
| Severity models | Catalan model 0.79 against a table at 0.70; calibration slope 0.97; Barcelona person model 0.84 | Replaced | Single-year test, a recording artefact in the strongest predictor and a page leading with ROC-AUC. Replaced by the rolling-origin evaluation, the predicted-against-observed figure and the calculator |
| External validation | Catalan model on DGT records 0.708 against 0.712 for a DGT-trained model; provinces 0.60–0.79 | Stands, research only | Transfer tests, labelled as such; the province figure (`tr3_province_auc.svg`), drawn but never shown, is now embedded beside the prose that quotes it |
| Data sources | 482 checks pass; record counts | Stands | |
| Methodology | "Each count is divided only by a denominator that could contain it" | Reworded | Three disclosed exceptions contradict the sentence as written: the sex rates (any licence class, unlicensed and foreign drivers in the numerator), the vehicle rates (foreign vehicles) and the per-fuel interurban check (national fuel). The sentence now names them |

## The 18-and-over restriction

The restriction applies only to the comparison of men and women on the drivers page
(`driver_risk.driver_counts_by_sex`). Its 18+ row is the sum of the bands 18–24 to 75+, the cuts
that the driver tables, the driver census and the kilometre release share. The audit confirmed four
points.

* It removes drivers aged 15–17 from the numerator and from the licence-holder denominator
  together. In 2022–2024 that is 4,492 motor-vehicle drivers involved, 32 deaths and 172,433
  licence-holder-years. The restriction is therefore consistent, not a selective exclusion.
* Drivers of unknown age (about 2% of those involved) and the 120 involved aged 0–14 leave the
  numerator only. Both sexes' rates are therefore understated by about 2%. The ratio is
  unaffected unless age goes unrecorded more often for one sex.
* The table caption said "aged 18 and over", but the headline sentence quoting 3.63 did not. The
  rebuilt page states the age range in the sentence.
* In the new per-kilometre analysis, the EMEF group 16–29 is matched to drivers aged 18–29.
  Residents aged 16–17 count in the EMEF population but cannot hold a car licence, and the 41
  drivers aged 15–17 in the 2024 tables are excluded. This is documented in
  [`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md).

## Disclosed mismatches of scope

| Rate | Mismatch | Size and direction | Action |
|---|---|---|---|
| Sex: per licence holder | Numerator includes unlicensed and foreign drivers; denominator is holders of any licence class, even for car drivers | B-licence denominator: men/women death ratio 3.49 → 3.57 (2023–2024), so the published ratio is about 2% low | Disclosed, quantified here |
| Vehicles: per vehicle-km | Foreign vehicles in the crash counts; Spanish vehicles' travel abroad in the kilometres | Unknown; no nationality data | Disclosed on the page |
| Interurban deaths per tonne of fuel | Fuel is national and covers urban driving | Labelled a check, not a rate | Unchanged |
| Road class | Urban-zone crashes on State, regional or provincial roads are outside the numerator; their kilometres may be in the denominator | Rates on those networks slightly low | Disclosed in `road_class.py` and on the page |
| Residents' date | 1 July for national rates, 1 January for the Catalan and provincial per-resident rates | Rates differed by −0.2% on average, at most 1.1% | Corrected: every annual rate now divides by the 1 July population (below) |
| Driver age per km (former) | Kilometres by the owner's age | Large; reversed the comparison for young and older drivers | Replaced by driver-age exposure |

## Corrections and regression tests

| Error | Where | Correction | Test |
|---|---|---|---|
| Calibration fitted on a constant predictor raised an error | `model_review.calibration_fit` | Returns no slope when the predictor does not vary | `tests/test_model_review.py` |
| Distances of trips without a band (all years before 2021) truncated the distance distribution at the speed bound, removing the long tail of every trip: 10% too short overall and up to a third on long trips | `emef.exposure.car_driver_trips` | The bound now applies to the mean; checked against banded trips | `test_bounded_imputation_is_closest_to_the_band_based_distance` |
| INE's single-age table also carries the aggregates "85 y más" and "100 y más"; reading every row double-counted 85+ | `exposure_risk.national.single_age_population` (caught before use) | Only single years and "105 y más" are read; ages 0–105 required | `test_single_age_population_has_no_overlapping_aggregates` |
| Missing zone codes compared as missing, which turned trip flags into missing values | `emef.distance` (caught before use) | Comparisons fill missing with false | `tests/test_emef.py` (distance validation) |
| Per-resident rates for Catalonia and the provinces used 1 January | `microdata.crosssource`, `validation.generalisability` | One shared reference date, 1 July; tables and `docs/GENERALISABILITY.md` regenerated | `tests/test_population_reference.py` |
| The forecast module described the rejected model as "the one used" | `forecast.py`, `model_cards.py` | Docstring and model card follow the decision; the page is a withdrawal notice | `test_forecast_page_is_withdrawn_and_says_why` |
| A test failed, instead of skipping, when the regional data layers were absent | `tests/test_microdata_models.py` | The data-free part runs everywhere; the rest skips with a reason | the test itself |

## Orphans

At baseline, eight tables were read by no page and one figure was embedded nowhere. The figure,
`tr3_province_auc.svg`, is now shown on the external-validation page beside the range it
illustrates. Of the tables, `gen_population_context`, `ml_recording_check`, `ml_stability`,
`mq_bcn_coordinates`, `mq_bcn_null_rates` and `mq_cat_placeholders` feed generated documents
(`docs/GENERALISABILITY.md`, `docs/ML_LEAKAGE_AUDIT.md`, `docs/DATA_QUALITY_MICRODATA.md`) and the
model cards. They are kept as the record behind those documents. `ml_missingness` and
`ml_transport_reweighting` support nothing published and no page links them. They are kept in
`reports/tables/` as the record of the fits that wrote them, and are not published on the site,
which copies only the tables a page links.

## Writing rules for the rewritten text

The rewritten pages and documents follow these rules:

1. Each rate names its numerator, its denominator, its population and its period, in the sentence
   or the caption beside it.
2. "Involved" means present in an injury crash, whoever caused it. Responsibility is never inferred
   from involvement. Police-recorded factors are "recorded", not "causes".
3. An estimate is given with its 95% confidence interval when it has one. A range from alternative
   analytic choices is called a sensitivity range and is never presented as an interval.
4. A figure that depends on an assumption rather than a measurement is labelled *model-dependent*
   and is never printed as the main result. The 75+ per-kilometre rate is given only as a range.
5. Rates per resident or per licence holder describe the burden on a population. Only rates per
   kilometre describe the risk of driving, and only kilometres driven by the people counted in the
   numerator qualify.
6. Short sentences, plain words, British spelling, numbers with the precision their interval
   supports, and no adjective a table cannot back.

## The rewritten text

Task 23. The following texts were rewritten to these rules:

* the research documents in this folder;
* the drivers, models and overview pages;
* the methodology page's rates section and its tested assumptions;
* the forecast withdrawal notice;
* the README's sources, pages, limits and reproduction steps;
* the forecast model card.

Every other page was read against the rules and kept as it was, because its claims passed the
audit above. Two interpretations that the data cannot support were removed in the process. The
first was that older drivers' higher deaths once involved "reflect frailty": the records show the
outcome, not its physiological cause. The second was that the road's owner "stands in" for road
differences in the Catalan model: it was a recording artefact. The site's own checks enforce the
rules. A page fails to build if a table stops supporting a qualitative word. The tests fail if a
year or a result is typed into page code, if a heading or opening is phrased as a question, or if
a page names the withdrawn models' results.

## 75+ exposure: constraining the estimate

October 2026, after the coverage and stress tests. The question was whether the 75+ figure per
kilometre could be better constrained than the sensitivity range of 0.97–3.28 times the 45–64
rate without adding false precision. The full account, with every number and its table, is in
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

**What did not change.** The envelope, 0.97–3.28 at 75 and over and 0.66–1.63 at 65–74. No
scenario was dropped: the equal split, at odds with surveys of men's driving, stays in the range,
hatched. The 65+ range (0.85–1.75) is unchanged. Counts or shares of combinations are never used
as a probability or as weight of evidence; "403 of 405" and "most combinations" were removed.

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
  0.97–1.98, and only the part below 1.21 is reached by marked rows alone.
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
  until the pipeline reproduces them.

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
  now says the figures disagree and that the Madrid split's intervals include 1 under two of the
  three ways of counting crossing trips.
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

**What would materially improve it.** The EMEF's own aggregates for 65–74 and 75+ (or finer) with
design-based errors, and the true age × routing table, from Institut Metròpoli or the ATM, would
replace the Madrid transfer and settle the composition bound
([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md), prepared, not sent). After that: a national
all-days measure of driving by age that separates driver from passenger; the age mix of weekend
and long-distance driving; a second exact-age regional survey (the Basque Encuesta de Movilidad);
RACC km by sex and age; DGT's 2018 licence holders by age for Madrid.
