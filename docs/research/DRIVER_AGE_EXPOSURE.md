# Car-driving exposure by driver age

This document estimates how far people of each age drive a car, as the denominator of crash
involvement per kilometre driven. The primary source is the EMEF working-day mobility survey,
2014–2024 ([`EMEF_INVENTORY.md`](EMEF_INVENTORY.md)). The code is
`src/dgt_stats/emef/distance.py` (kilometres from distance bands) and
`src/dgt_stats/emef/exposure.py` (estimates, intervals and sensitivity analyses).
`python scripts/emef.py validate exposure` writes every table cited here to
`reports/tables/emef_*.csv`.

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
