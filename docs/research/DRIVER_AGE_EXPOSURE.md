# Car-driving exposure by driver age

This document estimates how far people of each age drive a car, and then how often drivers of
each age are involved in injury crashes per kilometre driven (Tasks 10–20). The primary source of
exposure is the EMEF working-day mobility survey, 2014–2024
([`EMEF_INVENTORY.md`](EMEF_INVENTORY.md)), with the Madrid household travel survey of 2018 for
ages above 65. The code is `src/dgt_stats/emef/` (kilometres from distance bands, exposure
estimates, intervals and sensitivity analyses), `src/dgt_stats/edm2018.py` (the Madrid survey) and
`src/dgt_stats/exposure_risk/` (the Barcelona design, the national methods and the rates).
`python scripts/emef.py validate exposure` writes the `reports/tables/emef_*.csv` tables cited
here, and `python scripts/exposure_risk.py all` writes the `risk_*.csv` and `edm_*.csv` tables.

The Madrid survey data are © Consorcio Regional de Transportes de Madrid, reused under its
open-data licence. Powered by CRTM (<https://www.crtm.es>).

## What is measured

The unit is the **car-driver kilometre on a working day** by a resident aged 16 or over of the
survey area. A car-driver trip is a trip with at least one stage driven as a car driver. A
respondent "drove" if they made at least one such trip on their reference day, which is the
working day before the interview. Every rate per resident divides by all residents of the group,
including those who made no trip. Weekends, public holidays, non-residents and the in-work driving
of mobility professionals are outside the survey; later sections address weekends and the
national scale.

Each estimate is shown with a **95% confidence interval** from a rescaling bootstrap of
respondents within strata of year and comarca (300 replicates). These intervals describe sampling
error only. **Sensitivity ranges**, reported separately, describe how much an estimate moves under
other defensible analytic choices. The public files carry no sampling units, so any clustering in
the fieldwork is not reflected, and the intervals may be somewhat too narrow.

## From distance bands to road kilometres

The public files give each trip's straight-line distance only from 2021, and only in seven bands:
0–0.5, 0.5–2, 2–5, 5–10, 10–50, 50–100 and 100 km or more. Two steps turn a band into road
kilometres.

**1. Placing each trip within its band.** Straight-line distance is modelled as log-normal given
the trip's duration, whether it stays within one municipality, whether it leaves the survey area,
whether it touches Barcelona city, the respondent's age group and the year. The spread of the
distribution depends on duration. The model is fitted by maximum likelihood with interval
censoring: each trip contributes the probability of its observed band, so the model never
contradicts a band. A trip's distance is then the mean of the fitted distribution truncated to
its band. A 15-minute trip in the 10–50 km band is therefore placed near 10 km and a 50-minute one
much further, and the open band receives a mean set by the durations of its trips rather than by
an arbitrary cap.

**2. Converting straight-line distance to road distance.** The EMEF 2021 distance report computed
both the straight-line and the road distance (Google Distance Matrix) of every trip with
coordinates. Driving trips averaged 8.9 km in a straight line and 12.9 km by road, a ratio of 1.45.
That ratio is applied to every trip. Because it multiplies every age group alike, it changes
absolute rates per kilometre but not the ratio of one age group's rate to another's.

**Validation.** The report gives two benchmarks (`emef_distance_validation.csv`):

| Benchmark (2021) | Report | This method |
|---|---:|---:|
| Mean straight-line distance of a driving trip | 8.9 km | 8.94 km |
| Mean straight-line distance of a trip, all modes | 4.7 km | 4.71 km |
| Daily road km per mobile person, 16–29 | 29.7 | 27.6 |
| Daily road km per mobile person, 30–64 | 29.2 | 30.2 |
| Daily road km per mobile person, 65+ | 14.7 | 15.2 |
| Daily road km per mobile person, all ages | 26.5 | 26.6 |

The walking mean is underestimated (0.74 against 1.0 km), but walking is not used here.

**Where the kilometres come from** (`emef_km_by_band.csv`, 2022–2024). The 10–50 km band holds 49–56%
of the car-driver kilometres of drivers under 65, but only 31% of those of drivers aged 65 and
over. Older drivers make proportionally more short trips, and also more very long ones. In this
group, 12.7% of kilometres come from trips of 100 km or more (29 sample trips), and 22.4% from
trips without a band (79 sample trips, mostly to, from or outside the survey area). About a third
of the kilometres of drivers aged 65 and over thus rest on roughly 110 sample trips. This is the
main reason their interval is the widest, and the main reason the treatment of long and unbanded
trips is tested below.

**Trips without a band.** Every trip before 2021 has no band, and so do 1.2% of car-driver trips
from 2021. Their distance is the same model's mean given duration alone, bounded by the distance
the duration allows at 100 km/h door to door. Three treatments were compared on 2021–2024 trips
that do have a band, where the band-based distance is known (`emef_imputation_check.csv`):

| Treatment | All trips | Trips of 60 min or more | Trips of 120 min or more | Trips leaving the survey area |
|---|---:|---:|---:|---:|
| Mean bounded at 100 km/h (**central**) | 1.03 | 1.09 | 1.10 | 0.92 |
| Distribution truncated at 100 km/h | 0.90 | 0.86 | 0.77 | 0.64 |
| Unbounded mean | 1.03 | 1.10 | 1.13 | 0.93 |

The bounded mean is within 10% of the band-based total in every year and age group. Truncating
the distribution, which an earlier version used, removes the long-distance tail from every trip and
underestimates long trips by up to a third. The bound itself matters only for the few trips
with implausible durations (up to 720 minutes), where an unbounded mean exceeds 1,000 km.

**Multimodal trips.** 1.7% of car-driver trips also use public transport or another vehicle, and
the files do not record the length of each stage. These trips count for half their distance in
the central estimate, and for none or all of it in the sensitivity analysis. Trips that combine
driving only with walking count in full.

## Contemporary estimates, 2022–2024

The three most recent years are pooled with equal weight, so each figure describes the mean
working day of 2022–2024. The survey area is the province of Barcelona
(`emef_exposure_contemporary.csv`).

| Age | Drove on the day | Car-driver km per resident (95% CI) | Car-driver km per driver | Relative to 45–64, per resident |
|---|---:|---:|---:|---:|
| 16–29 | 19.8% | 9.16 (8.26–10.08) | 46.4 | 0.47 |
| 30–44 | 37.2% | 17.57 (16.44–18.59) | 47.3 | 0.91 |
| 45–64 | 40.4% | 19.29 (18.32–20.16) | 47.8 | 1 |
| 65+ | 18.9% | 7.87 (6.72–9.09) | 41.7 | 0.41 |
| All 16+ | 30.9% | 14.40 (13.87–14.83) | 46.6 | |

By sex, women aged 65 and over drove 2.95 km per resident (2.31–3.67), and 9.7% of them drove on
the reference day. Men of the same age drove 14.58 km (12.18–16.85), and 31.4% drove. Among those
who drove, older drivers covered about 13% less distance than drivers aged 45–64 (41.7 against
47.8 km), and made a similar number of trips (2.9 against 3.2). Most of the difference per
resident comes from how many older people drive at all, not from how far they drive when they do.

Residents aged 65 and over account for 12.5% of the car-driver kilometres of a working day.

## Area of residence

The level of driving depends strongly on where people live (`emef_exposure_area.csv`). In 2022–2024,
residents of Barcelona city drove 7.4 km per working day, and those of the rest of the province
23.6 km. The **ratio of older to middle-aged driving is nearly the same everywhere**: 65+ against
45–64 is 0.47 in Barcelona city, 0.41 in the rest of the metropolitan area, 0.42 in the rest of the
metropolitan region and 0.40 in the rest of the province. The ratio for young drivers is not
stable. Against 45–64 it is 0.34 in Barcelona city and 0.73 in the rest of the province, because
young residents of the city rarely drive. Any transfer of these ratios beyond the province is
therefore safer for the older group than for the youngest.

## Historical series, 2014–2024

The series uses the three age groups that every year supports and the metropolitan region that
every edition covers (RMB) (`emef_exposure_series.csv`, `emef_exposure_periods.csv`). Kilometres
before 2021 are modelled from durations, as above. 2020, surveyed under pandemic restrictions, is
reported but left out of every pooled period.

| Period (RMB) | 16–29 | 30–64 | 65+ | 65+ against 30–64 | 65+ who drove on the day |
|---|---:|---:|---:|---:|---:|
| 2014–2016 | 8.84 | 16.83 | 5.02 (4.18–5.98) | 0.30 | 12.7% |
| 2017–2019 | 9.11 | 19.66 | 7.46 (6.52–8.45) | 0.38 | 17.1% |
| 2021–2024 | 7.99 | 17.23 | 7.07 (6.04–8.10) | 0.41 | 17.0% |
| 2014–2024 without 2020 | 8.56 | 17.83 | 6.61 (5.95–7.17) | 0.37 | 15.8% |

Values are car-driver km per resident per working day, with 95% confidence intervals for the 65+
group.

Older residents' driving has risen relative to middle-aged residents' driving, from 0.30 of it
in 2014–2016 to 0.41 in 2021–2024 (0.46 in 2024 alone). The share of residents aged 65 and over who
drove on a working day rose from 12.3% in 2014 to 17.6% in 2024. Young residents moved the other
way: 20.7% drove in 2014 and 17.8% in 2024. These are the trends to expect as cohorts in which
nearly everyone holds a licence, women included, reach retirement age. Year-to-year levels for
all ages move together with the fieldwork. For example, every group's kilometres rose in 2018,
when respondents recorded more trips each. So the ratios between age groups are more reliable
than any single year's level. A rate for a given year should use exposure from the same or
adjacent years.

## Sensitivity

`emef_sensitivity.csv` recomputes the kilometres per resident and each group's share of car-driver
kilometres under every alternative choice. The rates in that table are means of yearly rates, so
its central row differs slightly from the pooled-total figures above. The share of kilometres
driven by residents aged 65 and over is the quantity that later carries the 65+ rate per kilometre:

| Choice | 65+ share of car-driver km | 65+ km per resident |
|---|---:|---:|
| Central (2022–2024; unbanded bounded; multimodal half) | 12.5% | 7.87 |
| Years: 2021–2024 / 2023–2024 / 2024 / 2019 and 2021–2024 | 12.0% / 12.7% / 13.1% / 12.0% | 7.46–8.14 |
| Area: metropolitan region only | 12.7% | 7.52 |
| Multimodal trips counted as none / all of the trip | 12.7% / 12.3% | 7.63 / 8.11 |
| Unbanded trips excluded / truncated / unbounded | 10.9% / 12.1% / 13.0% | 6.11 / 7.38 / 8.56 |
| Fixed points within bands: geometric / arithmetic midpoint | 12.2% / 11.7% | 8.01 / 9.24 |
| Road distance bounded at 80 / 100 km/h, ratio recalibrated | 12.2% / 12.3% | 7.67 / 7.70 |
| Logical bounds: 10–50 km band all at 10 km / all at 50 km | 14.1% / 10.7% | 6.71 / 11.69 |
| Logical bound: band over 100 km all at 100 km | 12.1% | 7.42 |

Excluding the logical bounds, which place every trip of a band at one edge and are not plausible
values, the share ranges from 10.9% to 13.1%. The lower end comes from ignoring trips without a
band, as the 2021 distance report did. The speed-bounded variant tests a known weakness of a
single road ratio. With the ratio applied to trips over 100 km in a straight line, the implied
median door-to-door speed is above 130 km/h, which suggests that a ratio of means overstates the
road distance of long motorway trips. Bounding the speed and recalibrating the ratio to the report's
mean lowers the older group's share by 0.2–0.3 points. The young group's share ranges from 11.0% to
12.5% under the same choices. The ratio of older to middle-aged kilometres per resident
(0.41 centrally) stays between 0.36 and 0.42 under every choice except the logical bounds.

## Usual driving

The reference day measures driving on one working day. The opinion module asks how often
respondents usually drive a car (`emef_driving_frequency.csv`, 2022–2024; the published 2024
share of habitual drivers is reproduced to its rounding). Over half of residents aged 65 and over (51.1%)
never drive, against 28.7% of those aged 45–64. Only 13.4% drive every day or almost, against
38.0%. Among those who drive every day, between 79% and 86% drove on their reference day in every
age group, which confirms that the reference day captures regular driving as intended.

## A working-day design matched in place: Barcelona city

The national comparison below transfers a regional age profile to Spain and spreads it over every
day of the year. Barcelona allows one comparison that needs neither step, because the Guàrdia
Urbana's 2025 person table records the exact age of every driver involved, uninjured drivers
included, and the date of the crash (`src/dgt_stats/exposure_risk/barcelona.py`;
`risk_barcelona_*.csv`).

**Numerator.** The numerator is car drivers involved in crashes in the city with at least one
casualty on the 248 working days of 2025. The calendar has the thirteen Catalan holidays of Ordre
EMT/85/2024 and Barcelona's local holidays of 9 June and 24 September; taxis are excluded. Of
3,486 such drivers, 205 (5.9%) have no recorded age. The police do not record where drivers live,
so the numerator also includes drivers from outside the province and people who drive ordinary
cars for work.

**Denominator.** The denominator is EMEF 2022–2024 car-driver kilometres inside the city on a
working day, multiplied by 248. A trip with both ends in Barcelona lies inside the city in full. A
trip with one end in the city lies inside it only in part. The public files have neither
coordinates nor the municipality at the other end, so that part cannot be measured, and trips
passing through cannot be identified at all. Three denominators therefore bracket the truth:
internal trips only (the smallest possible total); crossing trips counted at the mean length of an
internal trip (4.7 km by road) or their own length if shorter; and crossing trips in full (far more
than the city holds). The absolute rates differ about twentyfold between the first and the last, so only
the ratios between ages are informative:

| Age | Drivers involved, working days | Ratio to 45–64: internal trips only | crossing at an internal trip's length | crossing in full |
|---|---:|---:|---:|---:|
| 16–29 | 652 | 2.56 (1.78–4.20) | 2.19 (1.85–2.68) | 2.11 (1.74–2.67) |
| 30–44 | 981 | 1.15 (0.86–1.45) | 1.20 (1.04–1.36) | 1.05 (0.90–1.24) |
| 45–64 | 1,294 | 1 | 1 | 1 |
| 65+ | 354 | 0.78 (0.58–1.03) | 1.07 (0.87–1.31) | 0.91 (0.69–1.14) |

Each ratio is shown with its 95% interval, which combines the EMEF sampling error and Poisson error
in the count.

On working days in Barcelona, drivers aged 65 and over were involved in injury crashes at about the
same rate per kilometre as drivers aged 45–64, and drivers under 30 at about twice that rate,
whichever denominator is used. The internal-trip estimate rests on few young respondents (49
respondents aged 16–29 made a car trip inside the city), hence its wide interval.

## Weekends and public holidays

The EMEF describes working days only. Any annual rate assumes something about the other 117 days of
the year. Three pieces of evidence bear on it.

* **The EMEF 2023 weekend question.** In 2023 the survey asked whether respondents had spent any of
  the last four weekends away from home, and by what means (`emef_weekend_2023.csv`). Residents aged
  65 and over were about 1.26 times as likely to have driven away for a weekend as their working-day
  driving would suggest. The factor was 0.95 for those aged 45–64, 0.90 for those aged 30–44 and
  1.15 for those aged 16–29, each relative to all residents (`national.weekend_weights`). Older
  residents' driving is therefore somewhat less concentrated on working days.
* **Barcelona crashes by type of day** (`risk_barcelona_day_type.csv`). For drivers aged 65 and over,
  involvements per Saturday were 0.59 times those per working day, against 0.63 for drivers aged
  45–64. Per Sunday or holiday the figures were 0.55 against 0.51. Drivers aged 16–29 were involved
  as often on a Saturday as on a working day (1.04). Crash counts mix exposure and risk, so these
  figures show only that the older group's weekend pattern resembles the middle-aged group's.
* **No source measures weekend kilometres by age.** The share of annual kilometres driven on
  non-working days is itself unknown. It is 32% if a non-working day carries as much driving as a
  working day, and 22% if it carries 60% as much.

The central estimate spreads DGT's annual kilometres with the working-day age mix. The sensitivity
analysis gives non-working days the EMEF 2023 weekend mix, with 22% or 32% of annual kilometres
(`risk_weekend_sensitivity.csv`). The ratio of the 65-and-over rate to the 45–64 rate falls from
1.16 to 1.09 or 1.06, and the 16–29 ratio from 2.57 to 2.46 or 2.41. Weekends are a modest source
of uncertainty and move the older group's ratio downward.

## Spain: four ways to put kilometres on ages

No national source measures kilometres by the driver's age. Four methods are compared
(`src/dgt_stats/exposure_risk/national.py`; `risk_national_shares.csv`).

* **A, demographic calibration.** The EMEF's working-day kilometres per resident by age group and
  sex are applied to the population of Spain on 1 July 2024 (INE, single years of age, so the
  groups start exactly at 16, 30, 45 and 65). This assumes that, within each age group and sex,
  residents of Spain drive in the same proportion to one another as residents of the province of
  Barcelona.
* **B, kilometre scale.** Method A's shares are applied to DGT's 2024 car kilometres from
  inspection odometer readings: 289.8 billion km once the 3.2 billion km of taxis and ride-hailing
  cars are removed (their drivers drive for a living and are excluded from both the survey and the
  numerator). Two variants keep all 293.0 billion km, or also remove car hire without driver and
  driving schools (278.1 billion). B sets the level of the rates but not their ratios. As a scale
  check, Method A's working-day kilometres times 248 days come to 150 billion km, 52% of the DGT
  total. The rest is non-working days, professional and company driving, and the higher mileage
  of cars outside the Barcelona area (11,861 km per car registered in Catalonia, against 14,670 in
  Madrid).
* **C, regional calibration.** Method A is repeated with the age profile of each part of the
  province and with the Madrid household travel survey of 2018 (EDM2018), which has exact ages.
  The spread across these profiles shows how much the answer depends on which region's profile is
  transferred.
* **D, registered owners.** DGT's kilometres by the age of the car's registered owner were the
  denominator of the former driver-age figure. Cars are driven by people other than their owners,
  and company cars carry no age, so D is kept as a comparison only.

| Share of car-driver km | 16–29 | 30–44 | 45–64 | 65+ |
|---|---:|---:|---:|---:|
| A: EMEF profile, province of Barcelona (95% CI) | 11.3% (10.3–12.4) | 27.7% (26.1–29.3) | 47.7% (46.0–49.5) | 13.4% (11.6–15.3) |
| C: Barcelona city profile | 8.3% | 25.2% | 50.1% | 16.4% |
| C: rest of the metropolitan area | 10.4% | 25.9% | 49.9% | 13.9% |
| C: rest of the metropolitan region | 11.5% | 30.1% | 45.7% | 12.8% |
| C: rest of the province | 15.7% | 30.4% | 42.5% | 11.5% |
| C: Madrid survey 2018 | 11.2% | 34.0% | 46.0% | 8.8% |
| D: registered owners (DGT bands 18–24, 25–34, 35–54, 55–64, 65+) | 2.1% / 11.6% | 47.7% | 22.4% | 16.3% |

Spain's older population makes the 65-and-over share larger nationally (13.4%) than in the province
(12.5%). The profiles disagree most about the oldest and youngest groups. In the Madrid survey of
2018, residents aged 65 and over drove 0.26 times as far per resident as those aged 30–64, against
0.39 in the EMEF of the same year. This is the largest single source of uncertainty in the national
rates for older drivers, and the main reason those rates are given as ranges.

## Ages 75 and over

The EMEF cannot separate 65–74 from 75 and over ([`EMEF_INVENTORY.md`](EMEF_INVENTORY.md)), and a
request for that split has been prepared but not sent ([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md)).
The Madrid survey has exact ages (`edm_profile.csv`, `edm_older_split.csv`):

| Age (Madrid, 2018) | 45–64 | 65–69 | 70–74 | 75–79 | 80–84 | 85+ |
|---|---:|---:|---:|---:|---:|---:|
| Car-driver km per resident, weekday | 11.84 | 5.58 | 3.67 | 2.31 | 1.41 | 0.33 |
| Hold a car licence | 81% | 70% | 60% | 50% | 35% | 20% |
| Km per licence holder | 14.7 | 8.0 | 6.1 | 4.6 | 4.1 | 1.7 |

In Madrid, residents aged 75 and over drove 0.30 times (0.24–0.39) the distance per resident of
those aged 65–74. Men's ratio was 0.34 and women's 0.28. Residents aged 75 and over were 43% of the
65-and-over population but drove 19% (15–23%) of that group's kilometres.

Dividing the EMEF's 65-and-over kilometres between 65–74 and 75 and over requires one of those
ratios. It is therefore a *model-dependent* estimate, not a measurement. `national.older_split`
applies each assumption by sex, using the population of each age in the province of Barcelona (to
take the EMEF's 65+ average apart) and in Spain (to put it back together). It never changes the
measured 65-and-over total (`risk_older_split.csv`):

| Assumption | 75+ share of 65+ km | 65–74: involved per bn km (ratio to 45–64) | 75+: involved per bn km (ratio to 45–64) |
|---|---:|---:|---:|
| Madrid km per resident, by sex (central) | 23% | 233 (0.92) | 509 (2.01) |
| Madrid km per licence holder, applied to Spain's licence holders | 21% | 227 (0.90) | 554 (2.19) |
| Registered owners' split of the 65+ km | 31% | 260 (1.02) | 375 (1.48) |
| Equal km per licence holder at 65–74 and 75+ (an upper bound for 75+ km) | 34% | 274 (1.08) | 336 (1.32) |

On every assumption, drivers aged 65–74 are involved at about the middle-aged rate per kilometre
(0.9–1.1). Drivers aged 75 and over are involved at 1.3 to 2.2 times that rate. The range is wide
because the oldest drivers' kilometres are small and poorly measured. The evidence supports a
statement of direction: the per-kilometre involvement of drivers aged 75 and over is higher than
that of middle-aged drivers, and that of drivers aged 65–74 is not. It does not support a single
precise rate, so none is published.

## The crash numerator

The numerator is car drivers involved in injury crashes in Spain in 2024, and car drivers killed
within 30 days (DGT, tables 4.2 I/U and 4.1.1 I/U), drivers of private cars with or without a
trailer (`risk_national_numerator.csv`). The 1,852 drivers of public-service cars (taxi and
ride-hailing) are excluded to match the denominator. The EMEF group 16–29 is matched to drivers
aged 18–29: residents aged 16 and 17 count in the EMEF population but cannot hold a car licence,
and the 41 drivers aged 15–17 in the tables are excluded. The tables give age by sex and by urban or
interurban road, but not age by day of the week or by province. A national working-day design would
therefore need DGT's own cross-tabulation, which no public table provides, and none is inferred
here from the margins. 2,234 drivers (2.2%) have no recorded age. They are allocated in proportion
for absolute rates, which raises every rate by 2.3%; ratios between ages are unaffected.

| Age | Drivers involved | Drivers killed | Killed per 1,000 involved (95% CI) | Involved per 1,000 car-licence holders |
|---|---:|---:|---:|---:|
| 18–29 | 21,234 | 88 | 4.1 (3.4–5.1) | 6.2 |
| 30–44 | 28,775 | 113 | 3.9 (3.3–4.7) | 4.0 |
| 45–64 | 35,092 | 163 | 4.6 (4.0–5.4) | 3.0 |
| 65+ | 11,425 | 130 | 11.4 (9.5–13.4) | 2.4 |
| 65–74 | 6,970 | 59 | 8.5 (6.5–10.8) | 2.1 |
| 75+ | 4,455 | 71 | 15.9 (12.6–19.8) | 2.8 |

(`risk_severity_and_licences.csv`)

## Involvement per kilometre by age

Under Methods A and B, the central estimate for 2024 is shown below (`risk_national_rates.csv`). The
95% intervals combine sampling error in the exposure shares with Poisson error in the counts.

| Age | Billion km | Involved per bn km (95% CI) | Ratio to 45–64 (95% CI) | Driver deaths per bn km | Ratio to 45–64 (95% CI) |
|---|---:|---:|---:|---:|---:|
| 18–29 | 32.6 | 651 (593–716) | 2.57 (2.28–2.86) | 2.70 | 2.29 (1.73–2.95) |
| 30–44 | 80.1 | 359 (338–380) | 1.42 (1.30–1.55) | 1.41 | 1.20 (0.92–1.53) |
| 45–64 | 138.3 | 254 (244–264) | 1 | 1.18 | 1 |
| 65+ | 38.7 | 295 (260–338) | 1.16 (1.00–1.35) | 3.36 | 2.85 (2.12–3.74) |

**Sensitivity ranges** (not confidence intervals) for the ratio to 45–64:

| Source of variation | 18–29 | 30–44 | 65+ |
|---|---|---|---|
| Regional profile (Method C, five profiles) | 1.64–3.65 | 1.11–1.63 | 1.00–1.70 |
| Non-working days (age mix and share) | 2.41–2.57 | 1.42–1.44 | 1.06–1.16 |
| Kilometre total (Method B variants) | none: a common factor | none | none |
| Barcelona city, working days, matched in place | 2.11–2.56 | 1.05–1.20 | 0.78–1.07 |

The absolute rates move with the kilometre total, from 292 (all cars) to 308 (no hire cars or
driving schools) per billion km for the 65-and-over group, but the ratios do not.

**Against the former figure.** The former figure divided the same drivers by the kilometres of cars
registered to owners of each age (`risk_owner_age_comparison.csv`). It put drivers aged 18–24 at
6.75 times the rate of those aged 35–54, and those aged 65–74 at 0.71 times. Young drivers largely
drive cars registered to their parents, and older owners' cars are partly driven by others. Owner
kilometres therefore understate young drivers' driving, which inflates their rate, and overstate
older drivers' driving, which deflates theirs. Measured by the driver's age, the young drivers'
excess is about two and a half times rather than nearly seven times. The older drivers' rate is
about the middle-aged rate or slightly above it, rather than well below it.

## Quasi-induced exposure

Quasi-induced exposure estimates each group's share of driving from its share of the not-at-fault
drivers in two-vehicle crashes. It needs one record per driver in each crash, with the driver's age
and an indicator of fault, such as the presumed infraction the police record. None of the available
public sources has that:

* DGT's public microdata (`data/raw/dgt/microdata/`) have one row per crash, with no driver records
  and no ages.
* DGT's published tables give infractions by vehicle type (table 6.1), not by driver age.
* The Guàrdia Urbana's driver-cause table for Barcelona has no key to the person or vehicle
  concerned.
* The Catalan crash file has one row per crash.

The method is therefore not applied. It would become feasible with DGT's driver-level records,
which DGT's road-safety observatory holds, for two-vehicle crashes with one driver at fault. It
would answer a different question from the per-kilometre rates: how often drivers of each age are
judged responsible, relative to how often they are on the road.

## Uncertainty

The intervals above are 95% confidence intervals for sampling and count error. They pair 300 EMEF
bootstrap replicates (respondents resampled within year and comarca), or household replicates for
the Madrid survey, with gamma draws for each count. They are narrower than the honest uncertainty in
two respects:

* The public EMEF files carry no fieldwork clusters.
* The intervals take the analytic choices as given.

Those choices are covered by the sensitivity ranges, which are reported separately and never merged
into the intervals: the regional profile, non-working days, distance imputation and band treatment
(above, in the EMEF sections) and, for 75 and over, the split assumption. For drivers aged 65 and
over, the regional profile dominates. For drivers aged 75 and over, the split assumption dominates,
and no interval is attached to a figure that is itself an assumption.

## Conclusions

1. **Involvement per kilometre.** Per kilometre driven, drivers aged 18–29 were involved in injury
   crashes about two and a half times as often as drivers aged 45–64 (2.57; 95% CI 2.28–2.86;
   range across methods 1.6–3.7). Drivers aged 30–44 were involved 1.4 times as often. Drivers aged
   65 and over were involved about as often as the middle-aged, or modestly more (1.16; CI
   1.00–1.35; range 1.0–1.7). The matched working-day comparison in Barcelona, which needs no
   national transfer, gives 0.78–1.07 for the older group.
2. **Ages 75 and over.** The available evidence places drivers aged 65–74 at the middle-aged rate
   (0.9–1.1) and drivers aged 75 and over above it (1.3–2.2, model-dependent). A precise 75+ rate
   would need the EMEF's confidential ages or a national survey with exact ages.
3. **Severity once involved.** Older drivers are far more likely than others to die once in a
   crash. Car drivers aged 65 and over were killed in 11.4 of every 1,000 involvements, against
   4.6 at 45–64; drivers aged 75 and over in 15.9. Driver deaths per kilometre are therefore 2.9
   times the middle-aged rate at 65 and over, although involvement is only 1.2 times. The excess
   in deaths comes from the outcome once a crash has happened, not from being in more crashes;
   these data cannot say why older drivers fare worse.
4. **Responsibility** cannot be assessed with public data (see above). Involvement counts every
   driver in an injury crash, whoever caused it.
5. **Per licence holder.** Older licence holders are involved less often than middle-aged ones (2.4
   against 3.0 per 1,000 a year) because many drive little. Rates per licence holder or per
   resident describe the burden on a population, not the risk of a kilometre driven.
6. **The former owner-age figure** exaggerated young drivers' excess risk and understated older
   drivers' risk, because a car's owner is often not its driver.
