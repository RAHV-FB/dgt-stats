# Car-driving exposure by driver age

This document estimates how far people of each age drive a car, and then how often car drivers of
each age are involved in injury crashes per kilometre driven (Tasks 10–20). The main source of
exposure is the EMEF working-day mobility survey, 2014–2024
([`EMEF_INVENTORY.md`](EMEF_INVENTORY.md)). The Madrid household travel survey of 2018 (EDM2018)
gives the age profile above 65 and a second regional profile. The code is `src/dgt_stats/emef/`
(kilometres from distance bands, exposure estimates, intervals and sensitivity analyses),
`src/dgt_stats/edm2018.py` (the Madrid survey) and `src/dgt_stats/exposure_risk/` (the Barcelona
working-day check, the national methods and the rates). `python scripts/emef.py validate exposure`
writes the `reports/tables/emef_*.csv` tables cited here, and `python scripts/exposure_risk.py all`
writes the `risk_*.csv` and `edm_*.csv` tables. The method and every figure below were revised in
October 2026 after an independent audit.

The Madrid survey data are © Consorcio Regional de Transportes de Madrid, reused under its
open-data licence. Powered by CRTM (<https://www.crtm.es>).

## What is measured

The unit is the **car-driver kilometre on a working day** by a resident aged 16 or over of the
survey area. A car-driver trip is a trip with at least one stage driven as a car driver. A
respondent "drove" if they made at least one such trip on their reference day, which is the
working day before the interview. Every rate per resident divides by all residents of the group,
including those who made no trip. Weekends, public holidays, non-residents and the in-work driving
of mobility professionals are outside the survey; later sections address weekends, professionals
and the national scale. The reference days fall in the fieldwork months. In 2024 these were
1 April to 21 June and 26 September to 27 November, so July and August are not covered; the
archived sources give the months for 2024 only.

Each estimate is shown with a **95% confidence interval** from a rescaling bootstrap of
respondents within strata of year and comarca (Rao and Wu, 300 replicates). The EMEF 2024
executive summary (`data/raw/emef/2024/emef_2024_executive_summary.pdf`, technical sheet)
describes a stratified multi-stage sample drawn from the population register of Catalonia, with
weights calibrated to the census of 1 January 2025, by place of birth since 2023. The public files
carry neither the sampling units nor the calibration margins. The bootstrap therefore reflects
neither the clustering above the respondent nor the calibration, and the intervals are probably
too narrow. **Sensitivity ranges**, reported separately, describe how much an estimate moves under
other defensible analytic choices.

## From distance bands to road kilometres

The public files give each trip's straight-line distance only from 2021, and only in seven bands:
0–0.5, 0.5–2, 2–5, 5–10, 10–50, 50–100 and 100 km or more. Two steps turn a band into road
kilometres.

**1. Placing each trip within its band.** Straight-line distance is modelled as log-normal given
the trip's duration (its log and the square of its log), whether it stays within one
municipality, whether it leaves the survey area, whether it touches Barcelona city, the
respondent's age group and the year. The spread of the distribution depends on duration. The
model is fitted on the driving trips of 2021–2024 by maximum likelihood with interval censoring:
each trip contributes the probability of its observed band, so the model never contradicts a band.
A trip's distance is then the mean of the fitted distribution truncated to its band. A 15-minute
trip in the 10–50 km band is therefore placed near 10 km and a 50-minute one much further. No trip
records a distance beyond 100 km, so the mean of the open band (100 km or more) is a parametric
extrapolation from the duration terms, not an observed distance. Before 2019 the files give only
the age group 30–64; such a trip takes the 30–44 and 45–64 effects in proportion to the two
groups' shares of the 2019 respondents aged 30–64.

**2. Converting straight-line distance to road distance.** The EMEF 2021 distance report
(Institut Metròpoli for the ATM, October 2022, Table 1) computed both the straight-line and the
road distance (Google Distance Matrix) of every trip with coordinates. Driving trips averaged
8.9 km in a straight line and 12.9 km by road, a ratio of 1.45. That ratio is applied to every
trip. The report is not archived in this repository and could not be found online again, so the
ratio and the 2021 benchmarks below rest on the transcription in `emef/distance.py`. A common ratio
multiplies every age group's kilometres alike, so it changes absolute rates per kilometre and
changes the ratios between age groups only slightly (trips without a band are bounded by a
door-to-door speed whatever the ratio).

**Validation** (`emef_distance_validation.csv`). The model is checked against the 2021 report and
against the EMEF 2024 executive summary, which is archived:

| Benchmark | Published | This method |
|---|---:|---:|
| 2021 report: mean straight-line distance of a driving trip | 8.9 km | 8.95 km |
| 2021 report: mean straight-line distance of a trip, all modes | 4.7 km | 4.71 km |
| 2021 report: daily road km per person who travelled, 16–29 | 29.7 | 27.6 |
| 2021 report: daily road km per person who travelled, 30–64 | 29.2 | 30.2 |
| 2021 report: daily road km per person who travelled, 65+ | 14.7 | 15.2 |
| 2021 report: daily road km per person who travelled, all ages | 26.5 | 26.6 |
| 2024 summary: mean straight-line distance of a trip, all modes | 4.7 km | 4.74 km |
| 2024 summary: daily straight-line km per person who travelled, 16–29 | 22.5 | 22.0 |
| 2024 summary: daily straight-line km per person who travelled, 30–64 | 22.0 | 22.3 |
| 2024 summary: daily straight-line km per person who travelled, 65+ | 12.3 | 11.9 |

The model reproduces the 2024 benchmarks to within 0.8% to 3.0% (the largest gap, −3.0%, is at
65 and over).
The walking mean is underestimated (0.74 against 1.0 km), but walking is not used here. Every
benchmark covers trips that have a band, so none of them tests the treatment of trips without one.

**Where the kilometres come from** (`emef_km_by_band.csv`, 2022–2024). The 10–50 km band holds
50–56% of the car-driver kilometres of drivers under 65, but 32% of those of drivers aged 65 and
over. Older drivers make proportionally more short trips, and also more very long ones. In this
group, 12.6% of kilometres come from trips of 100 km or more (29 sample trips), and 19.6% from
trips without a band (79 sample trips, mostly to, from or outside the survey area). About a third
of the kilometres of drivers aged 65 and over thus rest on 108 sample trips. This is the main
reason their interval is the widest, and the main reason the treatment of long and unbanded trips
is carried into every national ratio. On trips of 100 km or more, the central method implies
median door-to-door road speeds of 126–142 km/h by age group, which suggests that a single road
ratio overstates the road length of long motorway trips. Two sensitivity variants bound the road
speed and recalibrate the ratio to the report's mean.

**Trips without a usable band.** Every trip before 2021 has no band, and so do 1.2% of the
car-driver trips of 2021–2024 (558 trips). Many of these are long: 144 of the 558 lasted three
hours or more, against 17 of the 46,730 banded trips. A further 25 banded trips of 2021–2024 are
treated as unbanded, because their band cannot be reached in their duration: the band's lower edge
times 1.45, divided by the duration, exceeds 150 km/h door to door. The distance of all these trips
is the model's mean given duration and the other covariates, but no more than the distance the
duration allows at 80 km/h door to door (100 km/h before the revision). 80 km/h is a long-distance
average that allows for stops and slower roads at either end. It is a choice, not an estimate.

A handful of long trips weighs heavily. In 2022–2024, six unbanded trips of 6.5 to 12 hours by
respondents aged 65 and over carry about a tenth of that group's working-day car-driver
kilometres. Trips without a band carry 19.6% of the kilometres of drivers aged 65 and over,
against 4.8% at 16–29, 6.8% at 30–44 and 10.2% at 45–64.

**Checking the duration-only treatment** (`emef_imputation_check.csv`). The duration-only
treatments are applied to banded car-driver trips of 2021–2024 whose band is closed (under
100 km), and compared with the band-based distance, by duration class. The open band is left out
because its distances are the model's own extrapolation; an earlier version of the check compared
with it, which made the check circular.

| Duration | Banded trips | Mean band-based km | Outside the trip's band, central treatment | Relative km: bounded at 80 km/h (central) | truncated | unbounded mean |
|---|---:|---:|---:|---:|---:|---:|
| Under 30 min | 35,358 | 4.5 | 44% | 1.03 | 0.89 | 1.03 |
| 30–60 min | 8,775 | 17.5 | 21% | 1.00 | 0.84 | 1.00 |
| 60–120 min | 2,281 | 37.3 | 29% | 1.14 | 0.87 | 1.15 |
| 120–180 min | 145 | 50.3 | 78% | 1.82 | 1.29 | 1.90 |
| 180 min or more | 8 | 54.7 | 100% | 3.26 | 2.20 | 3.72 |
| All | 46,567 | 8.8 | 39% | 1.05 | 0.87 | 1.06 |

Up to two hours, the central treatment is within 14% of the band-based total in every class,
although it often places an individual trip in the wrong band (21–44% of trips). Truncating the
distribution at the speed bound, which an earlier version used, removes the long-distance tail
from every trip and gives 0.84–0.89 of the band-based total in the same classes. Beyond two hours
the central treatment gives 1.82 times the band-based kilometres at 120–180 minutes and 3.26 times
at three hours or more.

That last comparison is biased the other way for long trips. The check keeps only trips known to
be under 100 km in a straight line, and among long durations that selects slow trips with stops.
Of the 17 banded trips of three hours or more, 8 were under 100 km. A long trip without a band,
often to or from somewhere outside the survey area, may be genuinely long. The data therefore
cannot settle the distance of long unbanded trips, and their treatment is carried into every
national ratio as a sensitivity range: bounds at 60 and 100 km/h, durations capped at four hours,
the unbounded mean, and the trips left out.

**Multimodal trips.** 1.6% of the car-driver trips of 2022–2024 also use public transport or
another vehicle, and the files do not record the length of each stage. These trips count for half
their distance in the central estimate, and for none or all of it in the sensitivity analysis.
Trips that combine driving only with walking count in full.

## Contemporary estimates, 2022–2024

The three most recent years are pooled by dividing each respondent's weight by the number of
years, so each figure describes the mean working day of 2022–2024, each year counting in
proportion to its population. The survey area is the province of Barcelona
(`emef_exposure_contemporary.csv`).

| Age | Drove on the day | Car-driver km per resident (95% CI) | Car-driver km per driver | Relative to 45–64, per resident |
|---|---:|---:|---:|---:|
| 16–29 | 19.8% | 9.07 (8.19–9.97) | 45.9 | 0.48 |
| 30–44 | 37.2% | 17.33 (16.26–18.33) | 46.6 | 0.92 |
| 45–64 | 40.4% | 18.86 (17.98–19.66) | 46.7 | 1 |
| 65+ | 18.9% | 7.52 (6.50–8.59) | 39.9 | 0.40 |
| All 16+ | 30.9% | 14.10 (13.59–14.47) | 45.6 | |

By sex, women aged 65 and over drove 2.90 km per resident (2.28–3.59), and 9.7% of them drove on
the reference day. Men of the same age drove 13.81 km (11.76–15.96), and 31.4% drove. Among those
who drove, drivers aged 65 and over covered about 15% less distance than drivers aged 45–64 (39.9
against 46.7 km) and made a similar number of trips (2.9 against 3.2). Most of the difference per
resident comes from how many older people drive at all, not from how far they drive when they do.

Residents aged 65 and over account for 12.2% of the car-driver kilometres of a working day in the
province.

## Area of residence

The level of driving depends strongly on where people live (`emef_exposure_area.csv`). In
2022–2024, residents of Barcelona city drove 7.2 km per working day, and those of the rest of the
province 23.4 km. The ratio of older to middle-aged driving per resident is similar across the
province: 65+ against 45–64 is 0.47 in Barcelona city, 0.39 in the rest of the metropolitan area,
0.40 in the rest of the metropolitan region and 0.40 in the rest of the province. The ratio for
young residents is not stable. Against 45–64 it is 0.34 in Barcelona city and 0.74 in the rest of
the province, because young residents of the city rarely drive. Any transfer of these ratios
beyond the province is therefore safer for the older group than for the youngest.

## Historical series, 2014–2024

The series uses the three age groups that every year supports and the metropolitan region that
every edition covers (RMB) (`emef_exposure_series.csv`, `emef_exposure_periods.csv`). The rest of
the survey area changed in 2015 (the whole of Osona included), 2017 (the Berguedà and the Moianès
added) and 2019 (the Baix Penedès and the Selva, outside the province, left), so the "survey area"
rows of the series are not on a constant area before 2019. Kilometres before 2021 are modelled from
duration alone; from 2021 the band is used as well. 2020, surveyed under pandemic restrictions, is
reported but left out of every pooled period.

| Period (RMB) | 16–29 | 30–64 | 65+ | 65+ against 30–64 | 65+ who drove on the day |
|---|---:|---:|---:|---:|---:|
| 2014–2016 | 8.81 | 16.19 | 4.77 (4.05–5.57) | 0.29 | 12.7% |
| 2017–2019 | 9.03 | 18.94 | 7.15 (6.28–8.05) | 0.38 | 17.1% |
| 2021–2024 | 7.93 | 16.90 | 6.72 (5.83–7.55) | 0.40 | 17.0% |
| 2014–2024 without 2020 | 8.50 | 17.30 | 6.30 (5.72–6.78) | 0.36 | 15.8% |

Values are car-driver km per resident per working day, with 95% confidence intervals for the 65+
group.

Older residents' driving per resident rose relative to middle-aged residents' driving, from 0.29
of it in 2014–2016 to 0.40 in 2021–2024 (0.44 in 2024 alone). Part of that rise may come from the
change of kilometre method in 2021. The share of residents aged 65 and over who drove on a working
day needs no distance, and it rose from 12.3% in 2014 to 17.6% in 2024. Young residents moved the
other way: 20.7% drove in 2014 and 17.8% in 2024. Year-to-year levels for all ages move together
with the fieldwork. For example, every group's kilometres rose in 2018, when respondents recorded
more trips each. So the ratios between age groups are more reliable than any single year's level.
A rate for a given year should use exposure from the same or adjacent years.

## Sensitivity of the kilometres

`emef_sensitivity.csv` recomputes the kilometres per resident and each group's share of car-driver
kilometres in the province under every alternative choice. `risk_national_sensitivity.csv` carries
the same alternatives into the national ratios of involvement per kilometre (see
[Involvement per kilometre by age](#involvement-per-kilometre-by-age)). The province figures here
are means of yearly rates, so the central row differs slightly from the pooled figures above.

| Choice | 65+ share of car-driver km | 65+ km per resident | 65+ against 45–64, km per resident | Spain: ratio to 45–64, 18–29 | Spain: ratio to 45–64, 65+ |
|---|---:|---:|---:|---:|---:|
| Central (2022–2024; unbanded trips bounded at 80 km/h; multimodal trips half) | 12.2% | 7.52 | 0.40 | 2.53 | 1.19 |
| Years: 2021–2024 | 11.7% | 7.14 | 0.39 | 2.47 | 1.21 |
| Years: 2023–2024 | 12.3% | 7.60 | 0.39 | 2.64 | 1.20 |
| Years: 2024 | 12.6% | 7.63 | 0.39 | 2.85 | 1.21 |
| Years: 2019 and 2021–2024 | 11.7% | 7.37 | 0.40 | 2.46 | 1.18 |
| Area: metropolitan region (RMB) only | 12.3% | 7.14 | 0.40 | – | – |
| Unbanded trips bounded at 100 km/h | 12.4% | 7.80 | 0.41 | 2.57 | 1.17 |
| Unbanded trips bounded at 60 km/h | 11.9% | 7.20 | 0.39 | 2.50 | 1.22 |
| Unbanded trips' durations capped at 4 hours | 11.7% | 7.07 | 0.38 | 2.49 | 1.24 |
| Unbanded trips at the model's mean, unbounded | 12.9% | 8.49 | 0.42 | 2.66 | 1.13 |
| Unbanded trips left out | 10.8% | 6.04 | 0.36 | 2.39 | 1.33 |
| Multimodal trips: car leg counted as nothing | 12.3% | 7.29 | 0.41 | 2.51 | 1.17 |
| Multimodal trips: car leg counted in full | 12.1% | 7.75 | 0.39 | 2.55 | 1.21 |
| Geometric midpoints within bands | 11.9% | 7.64 | 0.39 | 2.50 | 1.22 |
| Geometric midpoints, unbanded trips left out | 10.6% | 6.16 | 0.35 | 2.37 | 1.37 |
| Arithmetic midpoints within bands | 11.4% | 8.87 | 0.37 | 2.47 | 1.28 |
| Arithmetic midpoints, unbanded trips left out | 10.3% | 7.39 | 0.34 | 2.36 | 1.41 |
| Road distance bounded at 80 km/h, ratio recalibrated | 11.9% | 7.34 | 0.39 | 2.54 | 1.22 |
| Road distance bounded at 100 km/h, ratio recalibrated | 12.0% | 7.37 | 0.39 | 2.54 | 1.21 |
| Professionals' work trips: 25% by car | 11.6% | 7.61 | 0.38 | 2.48 | 1.26 |
| Professionals' work trips: 50% by car | 11.0% | 7.69 | 0.36 | 2.44 | 1.33 |
| 65+ employed share set to the census | 11.8% | 7.27 | 0.39 | 2.53 | 1.23 |
| Logical bound: 10–50 km band all at 10 km | 13.7% | 6.36 | 0.45 | – | – |
| Logical bound: 10–50 km band all at 50 km | 10.5% | 11.33 | 0.34 | – | – |
| Logical bound: band over 100 km all at 100 km | 11.8% | 7.08 | 0.38 | – | – |

The two "within bands" midpoint rows keep the central treatment of trips without a band; the two
rows with unbanded trips left out are fully independent of the duration model. The logical bounds
place every trip of a band at one edge. They are not plausible values and are not carried into the
national ratios.

Leaving the logical bounds aside, the 65+ share of the province's car-driver kilometres ranges from
10.3% to 12.9%, and the ratio of older to middle-aged kilometres per resident from 0.34 to 0.42
(0.40 centrally). The lowest values come from leaving out trips without a band, as the 2021
distance report did, and the highest from the unbounded mean. The young group's share ranges from
11.1% to 12.7%. Ten of the thirteen distance alternatives raise the national 65+ ratio above the
central 1.19. Only the 100 km/h bound, the unbounded mean and counting nothing for the car leg of
multimodal trips lower it (1.13–1.17).

**Professionals' work driving.** Mobility professionals (eight or more work trips a day) have
only their journeys to and from work recorded. Their work trips are counted but not described
(`V02C_3` in 2020–2023, `V02D1` in 2024). If a quarter or a half of those trips were car-driver
trips of the mean length of the age group's car-driver trips, the 65+ share of the province's
kilometres falls from 12.2% to 11.6% or 11.0%, and the national 65+ ratio rises from 1.19 to 1.26
or 1.33. DGT's kilometre total and the crash numerator both contain this driving; the survey's age
shares do not. Leaving it out understates the driving of working ages and so biases the 65+ ratio
down.

## The survey's older respondents

The survey's weighted share of residents aged 65 and over who are employed
(`emef_employment_benchmark.csv`) matched the census share in 2019–2021 and was well above it in
2022–2024:

| Year | Employed share of residents aged 65+ |
|---|---:|
| EMEF 2019 | 4.3% |
| EMEF 2020 | 4.4% |
| EMEF 2021 | 4.4% |
| EMEF 2022 | 6.0% |
| EMEF 2023 | 8.3% |
| EMEF 2024 | 7.1% |
| Census, Catalonia, 1 January 2024 (Idescat; `data/raw/idescat/`) | 4.3% |

Setting the employed share of each year's 65+ group to the census share, with each year's 65+
total unchanged, lowers the 65+ kilometres per resident from 7.52 to 7.27 and the 65+ share of the
province's kilometres from 12.2% to 11.8%. In the survey, then, employed older residents drive more
on working days than the others, and an excess of them raises the 65+ kilometres. The national 65+
ratio rises from 1.19 to 1.23 under the census share. The benchmark has limits: the census covers
all of Catalonia, not only the province, and defines employment by its own questions. The weights
have been calibrated to the census by place of birth since 2023, but the rise in the employed share
began in 2022, so that change does not explain it alone. Whether the calibration keeps 65–74 and
75 and over apart is not published; the data request asks for the calibration margins
([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md)).

## Usual driving

The reference day measures driving on one working day. The opinion module asks how often
respondents usually drive a car (`emef_driving_frequency.csv`, 2022–2024; the published 2024
share of habitual drivers is reproduced to its rounding). Over half of residents aged 65 and over
(51.1%) never drive, against 28.7% of those aged 45–64. Only 13.4% drive every day or almost,
against 38.0%. Among those who drive every day, between 79% and 86% drove on their reference day in
every age group, which confirms that the reference day captures regular driving as intended.

## A working-day check in Barcelona city: crashes of 2025, driving of 2022–2024

The national estimate transfers a regional age profile to Spain and spreads it over every day of
the year. Barcelona allows a comparison that needs neither step: crashes and driving inside one
city on working days (`src/dgt_stats/exposure_risk/barcelona.py`; `risk_barcelona_*.csv`). It is
not matched in time, because the crashes are of 2025 and the kilometres of 2022–2024, and its
numerator holds drivers its denominator does not count. It is separate evidence about a different
population, not a check that can confirm or bound the national ratio.

**Population.** Crashes recorded by the Guàrdia Urbana in Barcelona city in 2025 with at least one
casualty, slight injuries of people who refused medical care included, on the 248 working days of
2025. The calendar removes the thirteen Catalan holidays of Ordre EMT/85/2024 and Barcelona's local
holidays of 9 June and 24 September. Car drivers (`Turisme` and `Tot terreny`) are counted whether
injured or not. Only the person files of 2024 and 2025 list uninjured drivers; earlier files list
casualties only, so the design cannot be repeated for earlier years. `involved_drivers` checks that
the file holds uninjured drivers and that the drivers of a crash match its vehicles in at least 95%
of crashes, so a file that reverted to casualties only would fail the build. This population
differs from DGT's national one: the streets of one city, the ring roads included, against all
roads, and a casualty definition that includes refused care.

**Numerator.** Taxis are left out, and so are drivers of ordinary cars whose trip motive is
recorded as `Taxi` (ride-hailing cars), as in the national design. That leaves 3,321 car drivers on
working days. The records give the exact age of 94% of them; 204 (6.1%) have no recorded age. These
are almost all records with no age, sex or injury status, probably drivers who were never
identified. The rates leave them out and assume that their ages follow the recorded mix
(`risk_barcelona_unknown_age_bounds.csv`). With internal trips only, if all 204 were aged 65 and
over the 65+ ratio would be 1.28 instead of 0.80, and if all were aged 45–64 it would be 0.69. If
all were aged 18–29, the young ratio would be 3.46 instead of 2.61.

The police do not record where drivers live. The numerator therefore also holds drivers whose
kilometres no denominator counts: people living outside the survey area, traffic passing through
the city, and people driving ordinary cars for work. These lean to working ages, so the 65+ ratio
is biased down by an unknown amount. Two variants of the numerator test part of this (the
`numerator` column of `risk_barcelona_rates.csv`): drivers recorded as on duty (emergency
services, "en missió", driving-school practice, goods transport, scheduled bus) left out, and, in
addition, crashes whose only casualties refused care left out.

**Denominator.** EMEF 2022–2024 car-driver kilometres driven inside the city on a working day by
residents of the survey area, multiplied by 248. A trip with both ends in Barcelona lies inside the
city in full. A trip with one end in the city lies inside it only in part, and the public files
have neither coordinates nor the municipality at the other end, so that part cannot be measured.
Three denominators span the treatments of these crossing trips: internal trips only; crossing
trips counted at the mean length of an internal trip, or their own length if shorter; and crossing
trips in full. They do not bound the kilometres of all drivers in the city, because each omits the
traffic named above. Nor do they bound the ratios: the 65+ ratio is lowest with internal trips only
and highest with crossing trips at an internal trip's length. The absolute rates differ 15 to 21
times between the first and the last denominator, so only the ratios between ages are read.

| Age | Drivers involved, working days | Ratio to 45–64: internal trips only | crossing trips at an internal trip's length | crossing trips in full |
|---|---:|---:|---:|---:|
| 18–29 | 624 | 2.61 (1.81–4.27) | 2.23 (1.89–2.74) | 2.14 (1.76–2.67) |
| 30–44 | 933 | 1.16 (0.87–1.47) | 1.21 (1.05–1.37) | 1.07 (0.92–1.25) |
| 45–64 | 1,216 | 1 | 1 | 1 |
| 65+ | 344 | 0.80 (0.60–1.07) | 1.11 (0.89–1.35) | 0.94 (0.72–1.16) |
| Age not recorded | 204 | | | |

Each ratio is shown with its 95% interval, which combines the EMEF sampling error and Poisson
error in the count. The youngest group's drivers are aged 18–29; its kilometres are those of
residents aged 16–29, of whom those aged 16 and 17 drive no car.

| Numerator | 18–29, across the three denominators | 65+, across the three denominators |
|---|---:|---:|
| Taxis and ride-hailing cars left out (central) | 2.14–2.61 | 0.80–1.11 |
| On-duty drivers also left out | 2.21–2.69 | 0.85–1.17 |
| Crashes whose only casualties refused care also left out | 2.20–2.68 | 0.82–1.14 |

On working days in Barcelona in 2025, drivers aged 65 and over were involved in injury crashes at
about the rate of drivers aged 45–64 per kilometre driven inside the city by residents (0.80–1.11
across the three denominators; every 95% interval includes 1). Drivers aged 18–29 were involved at
2.1 to 2.6 times that rate. The internal-trip estimate rests on few young respondents (49
respondents aged 16–29 made a car trip inside the city), hence its wide interval. Leaving out
on-duty drivers raises the 65+ ratio to 0.85–1.17, in the direction the numerator-only traffic
predicts.

## Weekends and public holidays

The EMEF describes working days only. Any annual rate assumes something about the other 117 days of
the year. Three pieces of evidence bear on it. None measures weekend kilometres by age.

* **The EMEF 2023 module on overnight weekend stays (V11).** Asked in both waves, it counts how many
  of the last four weekends the respondent spent Saturday night away from their municipality (long
  stays excluded), and records the means of transport only for the most recent such weekend
  (`emef_weekend_2023.csv`). 12.2% of residents aged 16 and over spent at least one such weekend
  away and drove a car on the most recent one: 8.7% at 16–29, 13.5% at 30–44, 15.1% at 45–64 and
  9.3% at 65 and over. Divided by each group's share who drove on the reference working day, both
  relative to all residents, this gives weights of 1.15, 0.90, 0.95 and 1.26
  (`national.weekend_weights`). The weight is a ratio of prevalences, not of kilometres,
  and it misses day trips and local weekend driving. It is used only as a proxy age mix.
* **MOVILIA 2006, table 64 (Spain).** Trips whose main mode is a car or motorcycle, by drivers and
  passengers, on an average weekend day against an average working day, by age
  (`national.movilia_weekend_weights`). Relative to all residents aged 15 and over, the weights are
  1.11 (16–29), 0.88 (30–44), 0.99 (45–64) and 1.43 (65 and over); half of MOVILIA's 40–49 band is
  given to each neighbouring group. These are trips, not kilometres, they include passengers, and
  they describe 2006.
* **Barcelona crashes by type of day** (`risk_barcelona_day_type.csv`, 2025). For drivers aged 65
  and over, involvements per Saturday were 0.59 times those per working day, against 0.63 for
  drivers aged 45–64. Per Sunday or holiday the figures were 0.55 against 0.53. Drivers aged 18–29
  were involved as often on a Saturday as on a working day (1.03). Crash counts mix exposure and
  risk, so these figures show only that the older group's weekend pattern resembles the
  middle-aged group's.

The share of annual kilometres driven on non-working days is itself unknown. It is 32% if a
non-working day carries as much driving as a working day, and 22% if it carries 60% as much.

The central estimate spreads DGT's annual kilometres with the working-day age mix. The sensitivity
analysis gives non-working days each of the two mixes above, with 22% or 32% of annual kilometres
(`risk_weekend_sensitivity.csv`):

| Age mix of non-working days | Share of annual km | 18–29 | 30–44 | 65+ |
|---|---:|---:|---:|---:|
| Working-day mix (central) | any | 2.53 | 1.40 | 1.19 |
| EMEF 2023 overnight weekend stays, driving (proxy) | 22% | 2.42 | 1.42 | 1.11 |
| EMEF 2023 overnight weekend stays, driving (proxy) | 32% | 2.38 | 1.42 | 1.08 |
| MOVILIA 2006 car trips, weekend against working day | 22% | 2.47 | 1.44 | 1.09 |
| MOVILIA 2006 car trips, weekend against working day | 32% | 2.44 | 1.45 | 1.05 |

Values are ratios of involvement per kilometre to that of drivers aged 45–64. Both mixes give the
65+ group a larger weight on non-working days than on working days, which lowers its ratio to
1.05–1.11. Neither measures kilometres, so the size of this effect rests on assumptions.
Seasonality adds a further unknown: the 2024 fieldwork left out July and August, and DGT's annual
total is spread with the age mix of spring and autumn working days.

## Spain: methods for putting kilometres on ages

No national source measures kilometres by the driver's age. Five methods are compared
(`src/dgt_stats/exposure_risk/national.py`; `risk_national_shares.csv`).

* **A, demographic calibration (central).** The EMEF's working-day kilometres per resident by age
  group and sex (province of Barcelona, 2022–2024) are applied to the population of Spain on
  1 July 2024 (INE, single years of age, so the groups start exactly at 16, 30, 45 and 65). This
  assumes that, within each age group and sex, residents of Spain drive in the same proportion to
  one another as residents of the province of Barcelona.
* **A2, licence-calibrated transfer.** Method A, but carrying over kilometres per B-licence holder
  rather than per resident: each group's EMEF kilometres per resident, by sex, are multiplied by
  Spain's B-licence prevalence over the province's (DGT driver census 2024, INE population on
  1 July 2024; `risk_licence_prevalence.csv`). Young residents of the province hold car licences
  less often than Spain's: 0.40 B-licence holders per resident among men aged 18–29, against 0.46
  in Spain, and 0.34 against 0.40 among women. The gap is also wide at 30–44 (men 0.69 against
  0.78, women 0.63 against 0.73), small at 45–64 (men 0.85 against 0.87, women 0.67 against 0.71)
  and absent at 65 and over (men 0.73 against 0.74, women 0.29 against 0.28). Prevalence in the
  youngest group is measured as holders aged 18–29 over residents aged 15–29 in both places; only
  the ratio of the two is used.
* **B, kilometre scale.** The shares are applied to DGT's 2024 car kilometres from inspection
  odometer readings: 289.8 billion km once the 3.2 billion km of taxis and ride-hailing cars are
  removed (their drivers drive for a living and are excluded from both the survey and the
  numerator). Two variants keep all 293.0 billion km, or also remove car hire without driver and
  driving schools (278.1 billion). B sets the level of the rates but not their ratios. As a scale
  check, Method A's working-day kilometres (591 million a day) times 248 working days come to
  147 billion km, about half (51%) of the DGT total. The rest is driving on non-working days,
  professional and company driving that the survey does not record, and any excess of driving per
  resident in Spain over the province. Method A uses only the age shares, so the gap matters for
  the ratios only if the missing driving has a different age mix. The weekend, professional and
  regional variants test that.
* **C, regional calibration.** Method A is repeated with the age profile of each part of the
  province and with the Madrid household travel survey of 2018 (EDM2018), which has exact ages. In
  the Madrid survey, eight car-driver trips record 4,199 to 4,517 km, more than a day's drive (the
  next longest is 528 km); their distance counts as nothing, and the trips still count as trips.
  The spread across these profiles shows how much the answer depends on which region's profile is
  transferred.
* **D, registered owners.** DGT's kilometres by the age of the car's registered owner were the
  denominator of the former driver-age figure. Cars are driven by people other than their owners,
  and company cars carry no age, so D is kept as a comparison only.

| Share of car-driver km | 18–29 | 30–44 | 45–64 | 65+ |
|---|---:|---:|---:|---:|
| A: EMEF profile, province of Barcelona (95% CI) | 11.4% (10.4–12.5) | 27.9% (26.4–29.4) | 47.7% (46.0–49.3) | 13.0% (11.5–14.8) |
| A2: per licence holder (95% CI) | 12.4% (11.3–13.6) | 29.6% (28.0–31.2) | 45.9% (44.2–47.5) | 12.1% (10.7–13.8) |
| C: Barcelona city profile | 8.4% | 25.0% | 50.2% | 16.5% |
| C: rest of the metropolitan area | 10.5% | 26.3% | 49.9% | 13.4% |
| C: rest of the metropolitan region | 11.7% | 30.5% | 45.6% | 12.3% |
| C: rest of the province | 15.7% | 30.4% | 42.4% | 11.5% |
| C: Madrid survey 2018 | 9.9% | 34.2% | 46.6% | 9.2% |
| D: registered private owners, same age groups | 6.5% | 27.2% | 50.0% | 16.3% |

Row D sums DGT's owner bands onto the same groups (`risk_owner_age_comparison.csv`; company cars
excluded). Spain's older population makes the 65+ share larger nationally (13.0%) than in the
province (12.2%). The profiles disagree most about the oldest and youngest groups. In the Madrid
survey of 2018, residents aged 65 and over drove about 0.27 times as far per resident as those aged
30–64 (`edm_profile.csv`), against 0.39 in the EMEF of the same year, whose 2018 kilometres are
modelled from duration. This is the largest single source of uncertainty in the national rates for
older drivers.

## Ages 75 and over

The EMEF cannot separate 65–74 from 75 and over ([`EMEF_INVENTORY.md`](EMEF_INVENTORY.md)), and a
request for that split has been prepared but not sent ([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md)).
The Madrid survey has exact ages (`edm_profile.csv`, `edm_older_split.csv`):

| Age (Madrid, 2018) | 45–64 | 65–69 | 70–74 | 75–79 | 80–84 | 85+ |
|---|---:|---:|---:|---:|---:|---:|
| Car-driver km per resident, weekday | 11.48 | 5.58 | 3.67 | 2.31 | 1.41 | 0.33 |
| Hold a car licence | 81% | 70% | 60% | 50% | 35% | 20% |
| Km per licence holder | 14.2 | 8.0 | 6.1 | 4.6 | 4.0 | 1.7 |

In Madrid, residents aged 75 and over drove 0.30 times (0.24–0.39) the distance per resident of
those aged 65–74. Men's ratio was 0.34 (0.26–0.45) and women's 0.28 (0.16–0.45). Residents aged 75
and over were 43% of the 65-and-over population but drove 19% (15–23%) of that group's kilometres.

Dividing the EMEF's 65-and-over kilometres between 65–74 and 75 and over requires one of those
ratios or another assumption, so the result is a *model-dependent* estimate, not a measurement.
`national.older_split` applies each assumption by sex, using the population of each age in the
province of Barcelona (to take the EMEF's 65+ average apart) and in Spain (to put it back
together). It never changes the 65-and-over total (`risk_older_split.csv`). An earlier version
also split the 65+ kilometres in the proportions of the registered owners' kilometres. That
assumption was dropped: owner kilometres credit too much driving to older owners (see
[the former owner-age figure](#involvement-per-kilometre-by-age)), so it was biased towards more
kilometres at 75 and over.

| Assumption | 75+ share of 65+ km | 65–74: ratio to 45–64 (95% CI) | 75+: ratio to 45–64 (95% CI) |
|---|---:|---:|---:|
| Madrid km per resident, by sex (central) | 23% | 0.94 (0.81–1.08) | 2.06 (1.78–2.35) |
| Madrid km per licence holder, applied to Spain's licence holders | 21% | 0.92 (0.79–1.05) | 2.24 (1.94–2.56) |
| Equal km per licence holder at 65–74 and 75+ (an upper bound for 75+ km) | 34% | 1.10 (0.95–1.27) | 1.36 (1.17–1.55) |

The intervals hold the assumption fixed and combine the sampling error of the 65+ kilometres with
Poisson error in the counts. Repeating the split under every 65+ variant (the licence-calibrated transfer, the four parts of
the province, the Madrid profile, the distance treatments, the survey years, professionals' work
driving, the older sample's employment and the weekend mixes; `risk_older_sensitivity.csv`) gives
0.76–1.54 for 65–74 and 1.13–3.09 for 75 and over. The Madrid profile, which gives the highest 65+
ratio (1.65), sets the upper end.

In the Barcelona working-day check, 120 of the 344 car drivers aged 65 and over with a recorded age
were 75 or over. Splitting the city's 65+ kilometres with the same three assumptions gives ratios
to 45–64 of 0.80 to 1.82 at 75 and over and 0.66 to 1.11 at 65–74, across the three denominators
(`risk_barcelona_older.csv`). There the direction is not established.

Nationally, on every assumption and every variant, drivers aged 75 and over are involved above
the middle-aged rate per kilometre (1.13–3.09), and drivers aged 65–74 at about it (0.76–1.54). The range is wide because the oldest drivers' kilometres are small and rest on an
assumption. The national evidence supports a statement of direction for 75 and over but not a
single rate, so none is published.

## The crash numerator

The numerator is car drivers involved in injury crashes in Spain in 2024, and car drivers killed
within 30 days (DGT, tables 4.2 I/U and 4.1.1 I/U), drivers of private cars with or without a
trailer (`risk_national_numerator.csv`). The 1,852 drivers of public-service cars (taxi and
ride-hailing) are excluded to match the denominator. The tables label the youngest group 18-29:
its drivers are aged 18–29, and its kilometres are those of residents aged 16–29, of whom those
aged 16 and 17 cannot hold a car licence. The 41 drivers aged 15–17 in the tables are excluded.
The tables give age by sex and by urban or interurban road, but not age by day of the week or by
province. A national working-day design would therefore need DGT's own cross-tabulation, which no
public table provides, and none is inferred here from the margins.

2,234 drivers (2.3%) have no recorded age. They are left out of every rate. Allocating them to ages
in proportion (`involved_per_bn_km_allocated`) would raise every absolute rate by 2.3% and leave
the ratios between ages unchanged, but only if their ages follow the recorded mix
(`risk_unknown_age_bounds.csv`). If all were aged 18–29, the young drivers' ratio would be 2.80
instead of 2.53. If all were aged 45–64, the ratios would be 2.38 at 18–29 and 1.12 at 65 and
over. If all were aged 65 and over, the 65+ ratio would be 1.42.

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

Under Methods A and B, the central estimate for 2024 is shown below (`risk_national_rates.csv`).
The 95% intervals combine sampling error in the exposure shares with Poisson error in the counts.

| Age | Billion km | Involved per bn km (95% CI) | Ratio to 45–64 (95% CI) | Driver deaths per bn km | Ratio to 45–64 (95% CI) |
|---|---:|---:|---:|---:|---:|
| 18–29 | 33.0 | 643 (587–707) | 2.53 (2.25–2.82) | 2.67 | 2.26 (1.71–2.92) |
| 30–44 | 80.8 | 356 (337–375) | 1.40 (1.30–1.53) | 1.40 | 1.19 (0.91–1.51) |
| 45–64 | 138.2 | 254 (245–264) | 1 | 1.18 | 1 |
| 65+ | 37.8 | 302 (267–341) | 1.19 (1.03–1.36) | 3.44 | 2.92 (2.21–3.82) |

The billion kilometres carry the intervals of the shares in the methods table above.

**Sensitivity ranges** (not confidence intervals) for the ratio of involvement per kilometre to
that of drivers aged 45–64 (`risk_national_sensitivity.csv`; every variant is listed in the
kilometre sensitivity and weekend tables above):

| Source of variation | 18–29 | 30–44 | 65+ |
|---|---|---|---|
| Regional profile (Method C: four parts of the province, Madrid 2018) | 1.64–3.63 | 1.12–1.64 | 0.99–1.65 |
| Licence-calibrated transfer (Method A2) | 2.24 | 1.27 | 1.23 |
| Distance treatment (thirteen alternatives) | 2.36–2.66 | 1.35–1.45 | 1.13–1.41 |
| Survey years (2024; 2023–2024; 2021–2024; 2019 and 2021–2024) | 2.46–2.85 | 1.28–1.54 | 1.18–1.21 |
| Professionals' unrecorded work driving (25% or 50% of work trips by car) | 2.44–2.48 | 1.41–1.42 | 1.26–1.33 |
| Older sample's employed share set to the census | 2.53 | 1.40 | 1.23 |
| Non-working days (two age mixes, 22% or 32% of annual km) | 2.38–2.47 | 1.42–1.45 | 1.05–1.11 |
| **All of the above** (the sensitivity range on the site) | **1.64–3.63** | **1.12–1.64** | **0.99–1.65** |
| Kilometre total (Method B variants) | none: a common factor | none | none |

The regional profile sets both ends of every range. Without it, the alternatives span 2.24–2.85
at 18–29, 1.27–1.54 at 30–44 and 1.05–1.41 at 65 and over. For 65 and over, most alternatives
raise the ratio: the distance treatments (up to 1.41), professionals' driving (1.26–1.33), the
census employment share (1.23) and the licence-calibrated transfer (1.23). The weekend mixes lower
it (1.05–1.11), and so does the Barcelona city profile (0.99). Under the same alternatives the
ratio of driver deaths per kilometre to 45–64 ranges from 1.46 to 3.24 at 18–29 and from 2.43 to
4.04 at 65 and over. The absolute rates move with the kilometre total, from 299 (all cars) to 315
(no hire cars or driving schools) per billion km for the 65-and-over group, but the ratios do not.

**Barcelona, separately.** In Barcelona city on the working days of 2025, the ratios to 45–64 were
2.14–2.61 at 18–29, 1.07–1.21 at 30–44 and 0.80–1.11 at 65 and over, across the three
denominators (see the Barcelona section above). That is a different population and measure: one
city's streets, working days only, the Guàrdia Urbana's casualty definition, and the kilometres of
residents only. It is not a range for the national ratio, and its 65+ figure is biased down by
drivers counted only in the numerator.

**Against the former figure.** The former figure divided car drivers involved in 2024, taxi and
ride-hailing drivers included, by DGT's kilometres of cars registered to owners of each age band,
as ratios to owners aged 35–54 (`risk_owner_age_comparison.csv`). It put the 18–24 band at 6.75,
65–74 at 0.71 and 75 and over at 1.02. Those ratios use other age bands and another reference than
the current figures. Summed onto the same groups and set against 45–64, the owner kilometres give
4.62 at 18–29, 1.51 at 30–44, 1.00 at 65 and over, 0.88 at 65–74 and 1.27 at 75 and over. The
driver-age kilometres give 2.53, 1.40 and 1.19, with 0.92–1.10 at 65–74 and 1.36–2.24 at 75 and
over under the split assumptions. Compared like for like, the change of denominator lowers the
young drivers' ratio from about 4.6 to about 2.5 (2.2 with the licence-calibrated transfer) and
raises the 65+ ratio from about 1.0 to about 1.2. At 65–74 the move from 0.71 to 0.88 is on owner
kilometres throughout: it comes from the change of reference group (and the exclusion of taxi and
ride-hailing drivers), not from the denominator. Owner kilometres credit drivers aged
18–29 with 6.5% of private owners' car kilometres, against 11.4% under Method A: young people
drive cars registered to their parents, and older owners' cars are partly driven by others. The
former figure was arithmetically correct; its denominator did not describe the drivers.

## Men and women

The EMEF profile is by sex as well as age, so the same transfer to Spain gives each sex's share of
car-driver kilometres (`national.sex_per_km`; `risk_sex_per_km.csv`). On that estimate, men drove
66% of car-driver kilometres in Spain in 2024, about two thirds. Per kilometre, male private-car
drivers aged 18 and over were involved in injury crashes 0.91 times as often as female drivers
(95% CI 0.85–0.98; 62,064 men and 34,257 women involved) and were killed 2.65 times as often
(2.10–3.38; 414 men and 79 women killed). Under the licence-calibrated transfer and the other
regional profiles (EMEF areas and Madrid) the involvement ratio runs from 0.60 to 1.23 and the
death ratio from 1.75 to 3.55, so per kilometre men are involved about as often as women and
killed far more often.

Per licence holder (`drivers_sex_ratios.csv`, 2022–2024 pooled), male private-car drivers aged 18
and over were involved 1.39 times as often as female drivers (1.38–1.40), died 2.62 times as often
once involved (2.28–3.00), and were killed 3.63 times as often per licence holder (3.17–4.15). The
comparison now uses private cars only: taxi and ride-hailing drivers are excluded, as in the
driver-age rates. The licence holders are holders of any class, because only the census text files
of 2023–2025 give B-licence holders by sex and age. Counting only B-licence holders raises the
men's excess in deaths per licence holder in 2023–2024 from 3.49 (2.96–4.11) to 3.57 (3.03–4.20)
(`drivers_sex_b_licence.csv`). On these estimates, men's higher involvement per licence holder is
accounted for by the greater distance they drive, while their excess in deaths remains per
kilometre and once a crash has happened.

## Quasi-induced exposure

Quasi-induced exposure (QIE) estimates each group's share of driving from its share of the
not-at-fault drivers in two-vehicle crashes. It needs one record per driver in each crash, with the
driver's age and an indicator of fault, such as the presumed infraction the police record. None of
the available public sources has that:

* DGT's public microdata (`data/raw/dgt/microdata/`) have one row per crash, with no driver records
  and no ages. DGT's published tables give infractions by vehicle type (table 6.1), not by driver
  age.
* The Guàrdia Urbana's driver-cause table for Barcelona (2025) holds the crash number, place, time
  and cause, and no person, vehicle or order key. A cause appears at most once in a crash (7,417
  crashes have one cause row, 317 two and 7 three), so the table records the causes of the crash,
  not of each driver. Without knowing which driver a cause belongs to, the at-fault and
  not-at-fault age profiles cannot be separated: swapping them leaves the distribution of age pairs
  in two-driver crashes unchanged.
* The Guàrdia Urbana's person and vehicle tables have no fault field.
* The Catalan crash file has one row per crash.

The method is therefore not applied. Even with suitable records it has limits. Police-presumed
fault is a recorded judgement, not causal truth. QIE gives relative exposure shares, not
kilometres, so it needs an external total to give a rate per kilometre. It assumes that
not-at-fault drivers represent the drivers on the road, which fails if, for example, older drivers
are less able to avoid a crash that someone else causes.

It would become feasible with the presumed infraction of each driver, with the driver's age, for
two-vehicle crashes. The request would go to DGT for national driver-level records, or to the
Ajuntament de Barcelona (Guàrdia Urbana) for the city's crash reports. It has not been made. It would answer a
different question from the per-kilometre rates: how often drivers of each age are judged
responsible, relative to how often they are on the road.

## Uncertainty

The intervals above are 95% confidence intervals for sampling and count error. They pair 300 EMEF
bootstrap replicates (respondents resampled within year and comarca), or household replicates for
the Madrid survey, with gamma draws for each count. They are narrower than the honest uncertainty
in three respects:

* The EMEF is a stratified multi-stage sample with calibrated weights, and the public files carry
  neither the sampling units nor the calibration margins, so the bootstrap reflects neither.
* The intervals take the analytic choices as given.
* The road ratio of 1.45 and the 2021 benchmarks come from a report that is not archived.

The analytic choices are covered by the sensitivity ranges, which are reported separately and
never merged into the intervals. For drivers aged 18–29 the regional profile dominates
(1.64–3.63). For drivers aged 65 and over the regional profile (0.99–1.65) and the distance
treatment (1.13–1.41) dominate. For drivers aged 75 and over the split assumption dominates, and
the intervals in the split table hold that assumption fixed.

## Conclusions

1. **Involvement per kilometre.** Per kilometre driven in Spain in 2024, car drivers aged 18–29
   were involved in injury crashes 2.53 times as often as drivers aged 45–64 (95% CI 2.25–2.82;
   sensitivity range 1.64–3.63; 2.24 with the licence-calibrated transfer). The direction holds
   under every alternative; the size does not. Drivers aged 30–44 were involved 1.40 times as
   often (1.30–1.53; range 1.12–1.64). Drivers aged 65 and over were involved 1.19 times as often
   (1.03–1.36; range 0.99–1.65). For 65 and over, most of the alternatives, which the interval
   does not cover, raise the ratio, among them the distance treatments (1.13–1.41) and
   professionals' unrecorded driving (1.26–1.33); the weekend mixes lower it (1.05–1.11).
2. **Barcelona, a different population.** In Barcelona city on the working days of 2025, drivers
   aged 65 and over were involved at about the 45–64 rate per kilometre driven inside the city by
   residents (0.80–1.11 across three denominators; every interval includes 1), with a downward
   bias from drivers counted only in the numerator. Drivers aged 18–29 were involved at 2.14–2.61
   times that rate.
3. **Ages 75 and over.** Under three split assumptions, drivers aged 65–74 are involved at
   0.92–1.10 times the 45–64 rate and drivers aged 75 and over at 1.36–2.24 times it; across every
   65+ variant, 0.76–1.54 and 1.13–3.09. In Barcelona the same splits give 0.80–1.82
   at 75 and over, so the direction is not established there. A precise 75+ rate would need the
   EMEF's confidential ages or a national survey with exact ages.
4. **Severity once involved.** Car drivers aged 65 and over were killed in 11.4 of every 1,000
   involvements in 2024 (9.5–13.4), against 4.6 (4.0–5.4) at 45–64; drivers aged 75 and over in
   15.9 (12.6–19.8). Driver deaths per kilometre at 65 and over are therefore 2.92 times the
   middle-aged rate (2.21–3.82; sensitivity range 2.43–4.04), although involvement is 1.19 times. The excess
   in deaths comes from the outcome once a crash has happened, not from being in more crashes;
   these data cannot say why older drivers fare worse.
5. **Responsibility** cannot be assessed with public data (see above). Involvement counts every
   driver in an injury crash, whoever caused it.
6. **Per licence holder.** Older licence holders are involved less often than middle-aged ones
   (2.4 against 3.0 per 1,000 in 2024) because many drive little. Rates per licence holder or per
   resident describe the burden on a population, not the risk of a kilometre driven.
7. **Men and women.** On the same transfer, men drove about two thirds of car-driver kilometres in
   2024. Per kilometre, male private-car drivers were involved 0.91 times as often as female
   drivers (0.85–0.98; 0.60–1.23 under the other profiles), so neither sex is shown to be involved more often per km, and killed 2.65 times
   as often (2.10–3.38; 1.75–3.55).
8. **The former owner-age figure.** Compared like for like (drivers aged 18–29, 30–44 and 65 and
   over against 45–64), owner kilometres gave 4.62, 1.51 and 1.00, against 2.53, 1.40 and 1.19 by
   the driver's age. The former figure's 6.75 compared owners aged 18–24 with 35–54. A car's owner
   is often not its driver, so owner kilometres overstated young drivers' excess and understated
   older drivers' rate.
