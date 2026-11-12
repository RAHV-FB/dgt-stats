# Findings

This study covers road deaths and injuries in Spain from 1993 to 2024, police crash records for
Catalonia (2010–2023) and Barcelona (2025), and the kilometres driven by drivers of each age. Every
result is descriptive or an association in recorded data, not a causal effect. The pages with the
full evidence are on the [site](https://rahv-fb.github.io/dgt-stats/); definitions, checks and
technical notes are in the [methodology](https://rahv-fb.github.io/dgt-stats/data.html).

Strength: **Strong** is counted, or an interval far from no effect that survives the checks run.
**Moderate** is clear on the central assumptions and open to a stated alternative. **Weak** is
suggestive. **Not established** means the data cannot tell.

## 1. How have road deaths changed since 1993?

Deaths fell steeply to 2013 and have not clearly changed since.

- **Strong.** Deaths within 30 days fell by about three quarters between 1993 and 2013, from 6,378
  to 1,680. The steepest fall was 2003–2013, −10.9% a year (95% interval −11.6% to −10.3%).
- **Strong.** There is no clear trend after 2013: fitted alone, the change for 2013–2019 is +1.2% a
  year (−0.2% to +2.7%), and 2024 had 1,785 deaths.
- **Moderate.** Deaths per tonne of road fuel sold fell by 76% between 1996 and 2024. Whether
  crashes became rarer or less deadly depends on the denominator: per injury crash the fall is
  mostly in deaths per crash (crashes per tonne fell 13%); per person admitted to hospital,
  admissions per tonne fell to 21% while deaths per admission did not fall.
- **Not established.** A post-pandemic rise in risk. Per tonne of fuel, 2023 and 2024 are 16% and
  14% above the trend of 2011–2019, outside its range, but 8% above a trend started in 2013 and
  inside its range. Deaths per measured interurban kilometre in 2023 are 5% above trend, inside its
  range.
- **Weak.** Hospital admissions per tonne of road fuel in 2024 are 13% above 2019, beyond ordinary
  year-to-year variation (interval +1.6% to +25.6%). This depends on how completely admissions are
  recorded, and fuel sold is not kilometres driven.
- **Not established.** A change since 2019. Deaths in 2024 are 1.7% above 2019, within the variation
  between ordinary years (0.92–1.13 as a ratio).

Main limit: traffic is measured by fuel sold and, from 2008, by kilometres on the measured
interurban roads; neither measures all travel.

## 2. Which roads are deadliest per kilometre?

Conventional roads, much more than motorways and autovías.

- **Strong.** Per measured kilometre, deaths on conventional interurban roads were 3.04 to 3.84
  times those on motorways and autovías in each year of 2016–2023; in 2023, 3.45 times (95% interval
  3.03–3.92).

Main limit: the measured network covers the state and regional interurban roads only, so urban
streets and local roads are not compared.

## 3. When in the year are deaths highest?

In summer, and not only because more fuel is sold then.

- **Moderate.** Deaths in July, August and September exceed the average month even per tonne of road
  fuel sold: July 1.12 times (95% interval 1.06–1.18), August 1.09 (1.03–1.15).
- **Moderate.** In April 2020, deaths fell 68% against the 2017–2019 average for the month and road
  fuel sold fell 58%.

Main limit: road fuel sold is the only traffic series available by month, so whether summer is
riskier per kilometre driven cannot be told.

## 4. Did the 2006 points licence cut deaths?

Deaths fell around its introduction, but the series cannot show that the licence caused the fall or
that it lasted.

- **Weak.** Under the preferred trend, which bends once, the model puts a step at July 2006 at −7.1%
  (95% interval −13.2% to −0.5%); averaged over the 17 months from it the change is −2.5% (−7.8% to
  +3.2%).
- **Weak.** A straight-line trend gives a larger step, −12%, and a lasting fall, −9.5% on average
  (−14.3% to −4.5%), but fits the earlier months worse, by about 7 points of QAIC.
- **Not established.** That the licence caused the fall. The placebo count and the recalibrated
  interval are for the straight-line specification, whose July 2006 step is −9.8%: 6 of 14 placebo
  Julys with no policy change also have an interval that excludes zero, so the model's intervals are
  too narrow; the interval recalibrated on the placebos runs from −21.2% to +3.2%, which includes no
  change.

Main limit: one national monthly series, a long downward trend and no comparison group.

## 5. Which drivers are at higher risk?

Older drivers are the most likely to die once in a crash. Per kilometre, drivers aged 18–29 are
clearly more often in one than drivers aged 45–64; the comparison with drivers aged 75 and over is
not established.

- **Strong.** Once in an injury crash, car drivers aged 75 and over died 3.4 times as often as
  drivers aged 45–64 in 2024 (95% interval 2.6–4.5). This is counted, not estimated.
- **Moderate.** Per kilometre driven, drivers aged 18–29 were involved in injury crashes about 2.7
  times as often as drivers aged 45–64 (sampling interval 2.5–2.9; range across assumptions
  1.5–3.6). Drivers aged 30–44 were modestly above (about 1.2 times; range 1.1–1.7).
- **Not established.** Drivers aged 65–74 cannot be told apart from 45–64 per kilometre (about 1.1
  times; range 0.7–1.6), and the result for 75 and over (range 0.9–3.1) rests on a split of the
  survey's 65-and-over group that the data cannot check.
- **Strong.** Men were killed 3.6 times as often as women per B-licence holder (2023–2024; 95%
  interval 3.0–4.2).
- **Moderate.** Per kilometre, men are not shown to be involved in injury crashes more often (0.91
  times women's; range 0.60–1.23), but are killed 2.6 times as often (range 1.7–3.6).

Main limit: no national source counts kilometres by the driver's age, so the kilometres are
estimated from regional surveys (the EMEF in the Barcelona area and Madrid's 2018 survey) and the
per-kilometre results rest on them.

## 6. Which vehicles are in the most fatal crashes?

Per kilometre, motorcycles; per vehicle on the road, buses and heavy trucks.

- **Strong.** Per kilometre in 2022, motorcycles were in fatal crashes 10.1 times as often as cars
  (39.5–47.8 against 4.1–4.5 per billion km, 95% intervals; the intervals cover the crash counts
  only, and the rate rests on DGT's modelled kilometres), mostly because they are in more crashes.
- **Moderate.** Heavy trucks are in fewer injury crashes per kilometre than cars (0.42 times), but
  the share that are fatal is 5.9 times a car's. Deaths per vehicle in a fatal crash average 0.18
  for a truck's own occupants, so most of those killed were outside the truck.

Main limit: the kilometres are DGT's modelled estimates for one year, valid for groups of vehicles,
and the intervals cover the crash counts only.

## 7. How do speed and the other recorded factors relate to deaths?

Crashes recorded with inappropriate speed are deadlier.

- **Moderate.** Crashes in which the police recorded inappropriate speed had 2.0 times the deaths
  per crash of other crashes on the same kind of road (2016–2023; 95% interval 1.7–2.4), from 1.2
  times on dual carriageways to 5.9 times on urban streets.
- **Weak.** On interurban roads the share of crashes with inappropriate speed recorded was flat to
  2020 (18.6% in 2014, 18.5% in 2020) and fell to 14.4% in 2022. On all roads it fell from 10.0% in
  2014 to 6.9% in 2023, partly because crashes shifted to urban streets, where speed is rarely
  recorded. A change in recording practice is not excluded, so the series is not read as a change in
  behaviour.

Main limit: the factor is the police's judgement, recorded more or less often over time and by
place, so the association is open to recording bias; the report excludes Catalonia and the Basque
Country.

## 8. What goes with a death in Spain's injury crashes?

The kind of crash and where it happens, much more than the weather or the light.

- **Moderate.** Crash type and place dominate whether an injury crash is fatal. Against the
  reference crash, a pedestrian struck has odds 6.3 times as high (95% interval 5.2–7.5), a head-on
  collision 5.5 (5.0–6.1). By place, the highest contrast with an urban street is an urban crossing
  on a conventional road, 8.8 (6.5–11.7).

Main limit: the records hold only crashes with victims and the circumstances the police code, so the
odds ratios are associations conditional on a crash, with recording that differs by region.

## 9. Which severe crashes in Catalonia were fatal?

Those on interurban roads, involving heavy vehicles and in head-on collisions.

- **Strong.** Of 24,478 crashes with a death or serious injury in Catalonia (2010–2023), 12.6% were
  fatal. The fatal share was 19.2% on interurban roads and 6.9% on urban streets, 27.8% with a heavy
  vehicle involved and 25.0% in head-on collisions (the highest of any kind of crash).
- **Moderate.** With the other recorded circumstances held equal, the model puts the fatal share 2.0
  times as high with a heavy vehicle involved (95% interval 1.7–2.2). The interval covers
  coefficient uncertainty only, and the model was tested only within Catalonia.
- **Strong.** The Catalan file's fatal crashes equal DGT's crashes with a death within 24 hours in
  all 32 province-years of 2016–2023.
- **Moderate.** On the crashes of 2016–2023, each predicted from earlier years, the model ranks
  fatal crashes better than a table of fatal shares by road and crash type (ROC-AUC 0.74 against
  0.71), but not on roads through towns (0.55 against 0.58).

Main limit: the model was tested only within Catalonia; its inputs are recorded in no other source,
and a fatal crash there means a death within 24 hours.

## 10. Who is seriously hurt in Barcelona's crashes (2025)?

Pedestrians, motorcyclists and the oldest.

- **Strong.** Of 15,848 people with a recorded outcome in 2025, 1.6% were seriously injured or
  killed. Pedestrians (6.5%) and motorcyclists (3.3%) were far more often so than car drivers (3 of
  4,671, 0.06%).
- **Moderate.** People aged 75 and over had the highest share by age (5.3%, 95% interval 3.8% to
  7.5%).

Main limit: one year, shares of people in the crashes the city police attended, not rates per
journey or per kilometre.

## 11. How far can the data be trusted?

As counts, well; as measures of causes or of kilometres by age, only as far as the limits above
allow.

- **Strong.** The national files reconcile with DGT's published totals: all 473 reconciliation
  checks pass.

Main limit: the police records code circumstances unevenly across years and regions (the
[methodology](methodology.md) lists the coding breaks). The study would gain most from kilometres
driven by age on a national basis, from a measure of exposure for the regional records and from
exact age above 65 in the EMEF.
