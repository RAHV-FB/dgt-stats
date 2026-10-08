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
of mobility professionals are outside the survey. Carried to Spain, the survey's working days
account for about half of DGT's car kilometres; [The kilometres the survey does not
cover](#the-kilometres-the-survey-does-not-cover) sizes each missing part and tests other age
mixes for it. The reference days fall in the fieldwork months. In 2024 these were
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

**Publication rule.** Every EMEF dictionary (sheet `Sumari`, note 3) adopts the precision
requirements of Eurostat and Idescat: an estimate may be published only if its cell rests on at
least 20 sample observations, and a table only if at least 60% of its cells can be; other cells are
marked "..". The `emef_*.csv` tables and `risk_barcelona_km.csv` apply it
(`src/dgt_stats/emef/publication.py`): a cell below the threshold keeps its sample count, its
estimates are left empty, and, in the three tables where a cell falls below it, a `suppressed`
column marks the row. Three cells do: trips of 100 km or more at 16–29 in `emef_km_by_band.csv`
(11 sample trips), "less than monthly" at 16–29 in `emef_driving_frequency.csv` (17 respondents)
and trips of three hours or more in `emef_imputation_check.csv` (8 sample trips). The rule is
about precision, not confidentiality, so no further cell is hidden to stop a suppressed share
being recovered from the others. The drivers page reads only cells above the threshold: it
combines trips of 100 km or more with trips without a band, at least 52 sample trips in every age
group.

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

A few long trips weigh heavily. In 2022–2024, trips without a band carry 19.6% of the kilometres of
drivers aged 65 and over (79 sample trips), against 4.8% at 16–29, 6.8% at 30–44 and 10.2% at
45–64.

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
| 180 min or more | 8 | .. | .. | .. | .. | .. |
| All | 46,567 | 8.8 | 39% | 1.05 | 0.87 | 1.06 |

Up to two hours, the central treatment is within 14% of the band-based total in every class,
although it often places an individual trip in the wrong band (21–44% of trips). Truncating the
distribution at the speed bound, which an earlier version used, removes the long-distance tail
from every trip and gives 0.84–0.89 of the band-based total in the same classes. Beyond two hours
the central treatment gives 1.82 times the band-based kilometres at 120–180 minutes; the eight
banded trips of three hours or more are too few to publish.

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

The EMEF describes working days only. Any annual rate assumes something about the other 118 days of
2024 (366 days less 248 working days: the 262 weekdays less the fourteen paid public holidays a
year that Spanish law allows, two of them local; `national.working_days`). Three pieces of
evidence bear on it. None measures weekend kilometres by age.

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
non-working day carries as much driving as a working day, and 22% if it carries 60% as much
(`national.NON_WORKING_RATIOS`, an assumption). MOVILIA 2006 (tables 61 and 72, Spain) counted
0.83 times as many car or motorcycle trips, drivers and passengers together, on an average
weekend day as on a working day, and weekend trips of all modes lasted 1.24 times as long; both
measure trips, not kilometres, and neither separates drivers.

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
1.05–1.11. Neither measures kilometres, so the size of this effect rests on assumptions. The 2024
fieldwork left out July and August. Fuel sales and toll-motorway traffic put the mean day of 2024
within 1.3% below and 2.0% above the mean fieldwork day, so the months outside the fieldwork
change DGT's total little; the age mix of their driving is unknown. The next section takes the
weekend mixes further, applying them to every part of DGT's total that the survey does not cover.

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
  driving schools (278.1 billion). B sets the level of the rates but not their ratios. Method A's
  working-day kilometres (591 million a day) times the 248 working days of 2024 come to 146.5
  billion km, 51% of the DGT total. Method A uses only the age shares, so the other half matters
  for the ratios only if it has a different age mix; [the next
  section](#the-kilometres-the-survey-does-not-cover) sizes it and tests that.
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

## The kilometres the survey does not cover

`src/dgt_stats/exposure_risk/coverage.py`; `risk_coverage.csv` (the parts),
`risk_coverage_evidence.csv` (every measured value behind them), `risk_coverage_mixes.csv` (the
age mixes tested) and `risk_coverage_scenarios.csv` (the ratios under each scenario).

Method A carries the survey's working-day kilometres per resident to Spain's population. Over the
248 working days of 2024 that is 146.5 billion km, 51% of DGT's 289.8 billion car kilometres less
taxis and ride-hailing cars; over all 262 weekdays it would be 53%. The central estimate spreads
DGT's whole total with the working-day age mix, so it assumes that the other half has the same
age mix as the working days. This section measures what the other half is made of, with the data
in the repository, and tests how the ratios move if it has another age mix. Every allocation below
is an explicit assumption; none is a measurement of kilometres by age.

### What the other half is made of

The parts are added in the order of the table, each at the setting that explains least and at the
one that explains most. The regional level scales the working days and professionals' driving;
the non-working days are a ratio of the regional-level working day; the months outside the
fieldwork scale everything before them.

| Part | Billion km | Share of DGT's total | Evidence | Age mix | Uncertainty |
|---|---:|---:|---|---|---|
| Working days (Method A) | 146.5 | 50.6% | EMEF 2022–2024 km per resident by age and sex, times Spain's population, times 248 working days | EMEF working day: 11.4% at 18–29, 13.0% at 65+ | sampling, and the distance and transfer choices above |
| Professionals' work driving | 9.4–18.9 | 3.3%–6.5% | EMEF counts of the work trips of people making eight or more a day (`V02C_3`, `V02D1`), 25% or 50% taken as car trips of the group's mean length | EMEF professionals: 16.6% at 18–29, 2.4% at 65+ | their car share and length are not recorded; all of them by car would add 37.7 billion (13%) |
| Regional level | 7.6–40.8 | 2.6%–14.1% | Spain over the province: 1.05 times the car or motorcycle trips per resident (MOVILIA 2006, five working days and two weekend days); Spain over Catalonia: 1.18 (without Madrid) to 1.25 times the car km per resident aged 15+ (DGT 2024, by the owner's community) | working-day mix | trips against km, 2006 against 2024, province against Catalonia; Madrid's figure carries fleets registered there; the difference is in cars per resident (1.20 times), not km per car (1.00) |
| Non-working days | 43.9–86.9 | 15.1%–30.0% | 118 days, each carrying 60% to 100% of a working day's resident driving | working-day mix (central); two weekend mixes tested | the ratio is an assumption; MOVILIA 2006: 0.83 times the car trips on a weekend day, and longer trips (1.24 times the duration) |
| Months outside the fieldwork | −2.6 to 5.9 | −0.9% to 2.0% | the mean day of 2024 over the mean fieldwork day: petrol sales 1.00, petrol and diesel 0.99, toll-motorway vehicle-km 1.02 | working-day mix | fuel includes foreign vehicles and lorries; toll motorways over-represent holiday traffic; long-distance car journeys bunch in July and August (20.7% of the year's in MOVILIA 2007) |
| Not explained | −9.3 to 85.0 | −3.2% to 29.3% | DGT's total less the parts above | unknown: the scenarios below | the sum of all the uncertainties above |
| Cars registered to companies (not added) | 40.4 | 14.0% | DGT's 2024 owner-age file, company row | no age recorded | overlaps every part: residents drive company and leased cars on working days |
| Car hire without driver (not added) | 11.1 | 3.8% | DGT's 2024 km by class of service (A01) | no age recorded | the upper bound of visitors' driving in Spanish cars; residents hire cars too |

What can be explained:

* **Weekends and public holidays** are the largest part, 15% to 30% of the total, and its size
  depends on an assumed ratio. The data say only that weekend days have fewer car trips and
  longer ones.
* **The regional level** adds 3% to 14%. The two sources disagree: car trips per resident in
  MOVILIA 2006 put Spain only 5% above the province (7% on working days, level at weekends), while
  DGT's 2024 kilometres per resident put Spain 18% to 25% above Catalonia. DGT's figure is by the
  owner's community, so company and leasing fleets count where they are registered; the province's
  own kilometres are not published, and the province is more urban than Catalonia.
* **Professionals' unrecorded work driving** adds 3% to 7%, almost all under 65.
* **The months outside the fieldwork** change the total by −1% to 2%: fuel sales and toll traffic
  on an average day of 2024 are close to their average over the fieldwork days.
* **Long-distance driving** is not a separate part. Residents' long trips on working days are in
  the survey (trips of 100 km or more carry 12.6% of the 65+ kilometres); those on other days
  fall in the non-working days and the months outside the fieldwork. MOVILIA 2007 gives their age
  mix: residents aged 65 and over made 0.26 times as many car journeys over 50 km as those aged
  45–64.
* **Non-residents** drive Spanish-registered cars mainly as hire cars, 3.8% of the total at most.
  Foreign-registered cars are outside DGT's total, but their drivers are in the crash count.
* **Company vehicles** (2.2 million cars, 40.4 billion km, 18,573 km a car) carry no age and
  overlap every part, so they bound nothing.

What cannot be explained: at their lowest, the measured parts leave 29% of DGT's total
unexplained; at their highest they exceed it by 3%. The size of the remainder therefore ranges
from nothing to over a quarter of the total, and its content (survey under-reporting of trips,
company driving beyond professionals', the province's own level against Catalonia's) cannot be
told apart with these data. Its age mix is unknown.

### Age mixes for the uncovered kilometres

Each mix is a set of shares of national kilometres by age (`risk_coverage_mixes.csv`). The weekend
mixes are weights on the covered part's own mix; the others are national shares in their own
right.

| Mix | 18–29 share | 65+ share | 65+ km per resident, against 45–64 | 65+ km per B-licence holder, against 45–64 | Status |
|---|---:|---:|---:|---:|---|
| EMEF working day (central) | 11.4% | 13.0% | 0.41 | 0.67 | measured |
| DGT km of cars by the private owner's age, 2024 | 6.5% | 16.3% | 0.48 | 0.79 | measured |
| Car journeys over 50 km per resident, MOVILIA 2007 | 19.8% | 7.6% | 0.26 | 0.43 | measured |
| EMEF 2023 overnight weekend stays, driving (weights) | 13.1% | 16.4% | 0.54 | 0.88 | measured proxy |
| MOVILIA 2006 weekend car trips (weights) | 12.3% | 18.1% | 0.59 | 0.96 | measured proxy |
| EMEF professionals' work trips (that part only) | 16.6% | 2.4% | 0.07 | 0.11 | measured |
| Equal km per B-licence holder at every age | 12.7% | 17.8% | 0.61 | 1.00 | bound |
| Under 65 only (working-day mix without 65+) | 13.1% | 0% | 0 | 0 | bound |

A mix is treated as **credible** when it comes from a measured age pattern of driving or car
travel, and as a **bound** when it is constructed. Every measured mix tested for the remainder
gives licence holders aged 65 and over less driving than those aged 45–64 (0.43 to 0.96 of their
kilometres per licence holder) and gives residents aged 65 and over some (0.26 to 0.59 of the
45–64 kilometres per resident). Equal kilometres per licence holder lies beyond the first range
and no driving at 65 and over beyond the second, so both are reported as bounds and left out of
the published ranges. "Under 65 only" would need the whole remainder, up to 85 billion km, to be
driving like professionals' work driving, which at most (every work trip by car) is 37.7 billion.
The owners' mix and the licence mix measure 75 and over themselves (30.7% and 32.4% of their 65+
kilometres); the others take the split assumptions of the next section.

### Scenarios

The scenarios take the setting that explains least: the covered working days hold 52.4% of the
total, professionals' work driving 3.4%, the non-working days 14.9% and the remainder 29.3%. That
gives the remainder its largest share, and the non-working days and the remainder together, the
two parts that take other age mixes, 44% of the total, more than any other setting. Each scenario
gives the non-working days one of three mixes (working day, EMEF 2023 proxy, MOVILIA 2006) and the
remainder one of seven. With Method A's profile for the covered part
(ratios to 45–64; each cell spans the three non-working-day mixes and, for 65–74 and 75 and over,
the three split assumptions):

| Remainder's age mix | 18–29 | 30–44 | 65+ | 65–74 | 75+ |
|---|---:|---:|---:|---:|---:|
| Working-day mix | 2.43–2.50 | 1.41–1.43 | 1.15–1.23 | 0.89–1.14 | 1.31–2.31 |
| DGT km by owner's age | 2.80–2.90 | 1.44–1.46 | 1.09–1.16 | 0.88–1.06 | 1.29–1.87 |
| MOVILIA 2007 journeys over 50 km | 1.95–2.00 | 1.34–1.36 | 1.27–1.36 | 0.98–1.26 | 1.45–2.56 |
| EMEF 2023 weekend proxy | 2.29–2.36 | 1.43–1.45 | 1.06–1.12 | 0.81–1.04 | 1.21–2.11 |
| MOVILIA 2006 weekend car trips | 2.35–2.42 | 1.45–1.47 | 1.03–1.09 | 0.79–1.01 | 1.17–2.04 |
| **All credible** | **1.95–2.90** | **1.34–1.47** | **1.03–1.36** | **0.79–1.26** | **1.17–2.56** |
| Bound: equal km per licence holder | 2.29–2.36 | 1.39–1.41 | 1.02–1.08 | 0.83–0.99 | 1.18–1.68 |
| Bound: under 65 only | 2.43–2.51 | 1.41–1.43 | 1.68–1.84 | 1.30–1.70 | 1.92–3.45 |

The same scenarios are computed with every other profile for the covered part (the licence-
calibrated transfer, the four parts of the province and the Madrid survey), because the regional
profile and the uncovered half are separate uncertainties. The credible combinations give 1.49–3.75
at 18–29, 1.13–1.72 at 30–44, 0.85–1.75 at 65 and over, 0.66–1.63 at 65–74 and 0.97–3.28 at 75 and
over. The lowest values at 65 and over and at 75 and over combine Barcelona city's profile with
a weekend mix for both the non-working days and the remainder; the highest combine the Madrid
profile with the MOVILIA 2007 long-distance mix.

### Do the published ranges widen?

With Method A's profile, the credible scenarios lie inside the ranges published before this
section was added (1.64–3.63 at 18–29, 0.99–1.65 at 65 and over, 0.76–1.54 at 65–74, 1.13–3.09 at
75 and over), because the regional profiles set both ends of those ranges. On their own they
would widen nothing. Taken together with another region's profile they do, and nothing in the
data ties the age profile of the covered half to the age mix of the uncovered half. The published
sensitivity ranges therefore include the combinations of each profile with each credible scenario
(source "regional profile with the uncovered kilometres" in `risk_national_sensitivity.csv` and
`risk_older_sensitivity.csv`), and they widen:

| Group | Before | Now |
|---|---:|---:|
| 18–29 | 1.64–3.63 | 1.49–3.75 |
| 30–44 | 1.12–1.64 | 1.12–1.72 |
| 65+ | 0.99–1.65 | 0.85–1.75 |
| 65–74 (four splits) | 0.76–1.54 | 0.66–1.63 (unmarked 0.66–1.47) |
| 75+ (four splits) | 1.13–3.09 | 0.97–3.28 (unmarked 1.21–3.28) |

The 65–74 and 75+ rows have 544 combinations, 136 structures under each of four splits; the 136
equal-split rows are marked as at odds with surveys of men's driving and stay in the range
([ages 75 and over](#ages-75-and-over)).

The two bounds stay out. Other choices taken together, such as a distance treatment with a
regional profile, would widen the ranges further, so the ranges are not bounds either. The
direction at 18–29 holds under every combination. At 65 and over the range includes the 45–64 rate,
so no direction is claimed for it nationally; at 75 and over the range includes it too, and only
combinations at odds with surveys of men's driving reach it (see the next section).

## Ages 75 and over

Three kinds of result are kept apart here, and the drivers page labels them the same way.
**Counted**: the counts, involvement per licence holder and deaths once involved, which need no
kilometres. **Conditional estimate**: involvement per kilometre at 75 and over on one stated
assumption about how the 65-and-over kilometres divide between 65–74 and 75 and over, with a
sampling interval that holds that assumption fixed. **Sensitivity range**: the span of the same
ratio across every split and every other choice tested. None of them shows who caused a crash:
involvement counts every driver in an injury crash.

### Counted

In 2024, 4,455 car drivers aged 75 and over and 6,970 aged 65–74 were involved in injury crashes in
Spain, and 71 and 59 of them died within 30 days: 15.9 and 8.5 per 1,000 involved, against 4.6 at
45–64 ([the crash numerator](#the-crash-numerator)). Per 1,000 B-licence holders (DGT census
2024), 2.84 drivers aged 75 and over were involved, 2.13 at 65–74 and 2.98 at 45–64
(`risk_older_reference_checks.csv`). The 75+/45–64 ratio per licence holder is 0.95 (0.92–0.98
from the Poisson error of the two counts alone). Many holders aged 75 and over drive little or
not at all, so these are not rates per driver.

The two measures are tied by an identity: the per-km ratio equals the per-holder ratio divided by
the ratio of km per holder. Every per-km ratio in the sensitivity range (lowest 0.97) is above the
per-holder ratio (0.95), so every assumption tested gives holders aged 75 and over fewer
kilometres than holders aged 45–64. The page states that and guards it.

### The conditional estimate (internal name `REFERENCE_SPLIT`)

The EMEF's public files group everyone aged 65 and over; the survey sampled 65–74 and 75 and over
as separate strata only until 2016 and never published either group
([`EMEF_INVENTORY.md`](EMEF_INVENTORY.md)). The Madrid household survey of 2018 has exact ages
(`edm_profile.csv`, `edm_older_split.csv`):

| Age (Madrid, 2018) | 45–64 | 65–69 | 70–74 | 75–79 | 80–84 | 85+ |
|---|---:|---:|---:|---:|---:|---:|
| Car-driver km per resident, weekday | 11.48 | 5.58 | 3.67 | 2.31 | 1.41 | 0.33 |
| Hold a car licence | 81% | 70% | 60% | 50% | 35% | 20% |
| Km per licence holder | 14.2 | 8.0 | 6.1 | 4.6 | 4.0 | 1.7 |

Residents aged 75 and over drove 0.30 times (0.24–0.39) the distance per resident of those aged
65–74: men 0.34 (0.26–0.45), women 0.28 (0.16–0.45). The EDM2018 reading was reproduced
independently, and every published figure matches (one driver differs under a km > 0 count).
`DISTANCIA_VIAJE` is a straight-line distance ("a vuelo de pájaro", CRTM, EDM2018 Documento
síntesis, chapter 10, note 6; 97.8% of respondents with two trips have identical out-and-back
distances), so only ratios between ages are read from it.

**The estimate.** `national.older_split` takes the men's and women's ratios, removes the
province of Barcelona's 65-and-over age mix from the EMEF's 65+ km per resident and applies
Spain's, everything else as in the central estimate (Method A, DGT's 289.8 bn car km less taxis
and ride-hailing, the central distance treatment). It never changes the 65-and-over total. Drivers
aged 75 and over were involved **2.06 times** as often per km as drivers aged 45–64 (95% sampling
interval **1.63–2.64** in the table, 1.6–2.6 to the precision its Monte Carlo error supports), and
drivers aged 65–74 0.94 times (0.80–1.10, printed 0.8–1.1) (`risk_older_split.csv`).
On the site it is "the Madrid-pattern estimate", always printed with its condition; "reference"
there means the 45–64 group.

**The interval.** The EMEF and the EDM are independent samples, so the interval crosses all 300
EMEF Rao–Wu replicates with all 300 EDM household replicates (90,000 cells), each cell with its
own gamma draws of the three counts. The Monte Carlo standard error of each endpoint is 0.019
(lower) and 0.033 (upper) (`mc_se_low`, `mc_se_high`). It comes from a pigeonhole bootstrap
(Owen 2007, *Annals of Applied Statistics* 1:386–411), which resamples the EMEF replicates and
the EDM replicates independently and so respects the crossed design. The batch estimate first
published (0.006 and 0.010, from 5 × 5 blocks that share rows and columns) was several times too
small: eight independent sets of 300 × 300 replicates gave endpoints of 1.62–1.65 and 2.57–2.70,
standard deviations 0.012 and 0.039 (an independent check found 0.018 and 0.045). The second
decimal of the ends is therefore not stable, and the pages print them to one decimal, 1.6–2.6;
the same holds for every joint interval in `risk_older_split.csv` and `risk_older_extremes.csv`,
whose ends the pages print to the decimals their standard errors support (`site.numbers.
joint_interval`). The page wordings never rest on an end within three standard errors of 1. An exploratory
decomposition, not reproduced by the pipeline, put the log half-widths at about 0.18 from the
EDM, 0.14 from the EMEF and 0.03 from the counts. The earlier published interval, 1.78–2.35
(kept as `ratio_low_split_fixed`, `ratio_high_split_fixed`), held the Madrid ratio at its point
value and so left out the EDM's own sampling error: it was too narrow. The new one may still be
too narrow or too wide: the EMEF bootstrap ignores clustering, the EDM household bootstrap ignores
stratification, and neither recalibrates the weights. It covers sampling error and chance in the
counts only, never the choice of assumption.

**Robustness of the Madrid reading** (exploratory calculations, not reproduced by the pipeline):
caps on trip distance, dropping trips over 50 or 100 km, private cars only, unweighted, trimmed
weights, equal weekday shares and a network-circuity factor give 1.98–2.09. CAPI/CATI and
reduced-mobility splits were looked at as diagnostics only. Applying the pooled (both-sexes)
ratio to each sex is mis-specified (it gives 2.19) and is not used.

**What supports it, with its limits** (`risk_older_reference_checks.csv`):

* Car-licence holding falls almost equally from 65–74 to 75 and over in the province of Madrid,
  the province of Barcelona and Spain (holders per resident, 75+ over 65–74, DGT 2024: men 0.715,
  0.716, 0.710; women 0.285, 0.276, 0.262). That is consistent with the split but does not test
  whether the km gradient transfers: with similar licence structures, Madrid's residents aged 65
  and over drive much less relative to 45–64 than the EMEF profile implies after transfer (0.29
  against 0.41 on working days).
* Its implied km per DGT holder, 75+ over 65–74, is men 0.48 and women 1.08. These lie inside
  the like-for-like EDM intervals (the EDM ratio per resident over DGT's Madrid prevalence ratio:
  men 0.48 (0.36–0.63), women 0.99 (0.56–1.58)). The agreement is nearly automatic, because
  Spain's and Madrid's prevalence gradients are nearly equal: a consistency check, not support.
* In the EMEF itself, retirees aged 75 and over can be identified through the routing of
  question P1b (see [`EMEF_INVENTORY.md`](EMEF_INVENTORY.md)). In 2014 and 2016, the years whose
  routing share matches INE's, an exploratory calculation gives about 0.25 for the 75+/65–74
  ratio of km per resident (single years 0.29 and 0.20; 2014–2016 pooled 0.27, 0.20–0.34),
  against Madrid's 0.30. Validation only; not built into the pipeline (P2).

**Why it stays conditional: the direction of possible bias.**

| Source of bias | Direction for the 75+ figure | Size | Status |
|---|---|---|---|
| Time and cohort: licence holding at 75+ has risen since 2018. Holders of any class per resident, Spain, 2024 over 2018 (DGT census tables 2018 and text file 2024, INE; `risk_older_reference_checks.csv`): at 75 and over, men 1.08, women 1.68; against 65–74, men 1.07, women 1.30. The 2018 tables give licences by age only for all classes together, so no B-licence trend is used | down | 1.88 if km per licence holder at each age stayed as in Madrid in 2018 (the Madrid ratios times the change against 65–74; computed, an extrapolation) | documented |
| International gradients (Netherlands ODiN 0.50–0.58 per resident; England NTS 70+/60–69 0.56–0.58; Germany MiD 70–79/60–69 about 0.55) are gentler than Madrid's | down | context only | quoted, docs only |
| EDM2004 to EDM2018: Madrid's own 75+/65–74 ratio rose from 0.20 (0.11–0.30) to 0.30 | down | direction only | exploratory (P3) |
| EMEF 65+ sample composition: calibration is on sex × 65+ only, and the methodology report notes lower response at 75+ | up | at most about +11% (2.28) | a bound in the range |
| Women's implied km per DGT licence holder, 75+ over 65–74, is 1.08 under the Madrid split, while RACC's non-driving shares for women (about 0.5 in days) and the EMEF 2016 licence question (0.32, 0.10–0.71) point lower per holder; the EDM like-for-like 0.99 (0.56–1.58) does not rule out 1 | up | 2.08, 2.30 or 2.40 with the women's ratio at 0.99, 0.5 or 0.32 and the men's as in Madrid: about +1%, +12% and +17% (exploratory) | documented |
| Monday–Thursday window: in INE's EET 2009–10 the weekend 75+/65–74 car-time ratio (0.36) is below the weekday one (0.42) | if anything the working-day split overstates weekend driving at 75+, so up | small | exploratory (P3) |
| Proxy or under-reported trips of the oldest respondents | unknown | unknown | documented |

The net direction is not known. The figure is therefore never called the rate for 75 and over,
a best estimate or most likely.

**Driver over owner km.** At the estimate, drivers aged 75 and over drive 0.68 times the km DGT
records for cars registered to owners of that age, against 1.03 at 65–74 and about 1.10 at
45–64. A ratio at or above 1 is normal at younger ages (other people's cars, company cars); these
are descriptive only and never mark a row.

### The other three splits

* **Madrid km per licence holder, Spain's licence holders** (2.24, 1.77–2.89). It multiplies the
  EDM's km per *self-reported* licence holder by DGT's census prevalence. At 75 and over the
  self-reported prevalence in 2018 (men 0.670, women 0.167) is above DGT's Madrid figure for 2024
  (0.606, 0.127) despite cohort growth, so attrition is counted twice; like for like it would be
  about 2.09 (exploratory). It stays in the range, labelled as mixing two definitions of a licence.
* **RACC driving-days limit for men, equal km per licence holder for women** (1.69, 1.45–1.95).
  `national.racc_men_limit` derives the men's limit in code from the constants quoted from
  Fundació RACC, *Mayores al volante* (slide dossier published 29 May 2013; 3,003 licence holders
  aged 65 and over; fieldwork dates not stated): interviews by sex and age (slide 5), the share
  of holders who do not drive (slide 11: men 14.1%, 20.2% and 38.7% at 65–69, 70–74 and 75+) and
  the days a week active drivers drive (slide 19, by age only, both sexes), at the midpoints 1,
  2.5, 4.5 and 7 days. Men aged 75 and over with a licence drive on 0.677 times as many days as
  men aged 65–74 (0.66–0.69 under other midpoints). It counts days, not km, and older drivers
  make shorter and slower trips, so it is an upper limit for km, not an estimate. Women are set
  equal (1.0), because the survey gives frequency by age only; RACC's non-driving shares for women
  (29.5%, 37.5%, 63.0%) suggest about 0.5 in days, which would give about 1.83 centrally
  (exploratory). That variant is not added: 0.5 is an approximation and it would move neither end
  of the range nor its lowest unmarked value. The split is not "the most driving Spanish surveys
  allow": for women it lies below the Madrid split's own implied 1.08. Its purpose is to stop the
  Madrid split, lowest at about 1.47 across structures, reading as a floor among the unmarked
  rows. The
  figures are quoted, not archived: the RACC site grants no licence and forbids redistribution.
* **Equal km per licence holder at 65–74 and 75 and over** (1.36, 1.16–1.57). Spanish surveys of
  men's driving contradict it (below). It stays in the range, while the two coverage bounds ("the
  same km per licence holder at every age" and "under 65 only") stay out, because the coverage
  bounds were declared bounds before any result and no source supports them; the equal split was
  in the range as first published, women's evidence does not rule it out, and the evidence against
  it for men is regional or dated. Narrowing the range on a rule adopted after seeing the results
  would understate the uncertainty.

### The sensitivity range and what moves it

Repeating the four splits under every alternative for the 65-and-over km (136 structures: the
regional profiles, the licence-calibrated transfer, 13 distance treatments, 4 survey-year sets,
professionals' work driving, the employment reweight, the composition bound, the weekend mixes,
and the 15 credible coverage scenarios with each of the 7 profiles) gives 544 rows
(`risk_older_sensitivity.csv`). The range is **0.97–3.28** at 75 and over (0.9747–3.2812) and
0.66–1.63 at 65–74. No row is dropped.

**Composition bound.** `emef.older_routing` flags retirees aged 75 and over in 2022–2024 (P1b
blank among respondents aged 65+ not in work). Weighted, they are 37.7% of men and 35.2% of
women in the 65+ sample, against an INE province share of 46.6% and 53.1%
(`emef_routing_older.csv`). The flag finds retirees only, so this is a lower limit on the
sample's 75+ share, and the adjustment km65 × [s_p r + (1 − s_p)] / [s_r r + (1 − s_r)] (s_p the
INE share, s_r the routing share, r the split's ratio per resident) an upper bound on the bias:
2.28 at 75 and over (+11%), 1.43 under the equal split (+5%) and 1.32 at 65 and over. It overlaps
the employment reweight, so the two are never combined.

**One at a time** (`risk_older_decomposition.csv`; each factor's span includes the estimate's own
choice, everything else as in the Madrid-pattern estimate):

| Choice varied | 75+ ratio | Log width |
|---|---:|---:|
| All combinations tested (the sensitivity range) | 0.97–3.28 | 1.21 |
| Region whose age profile stands in for Spain | 1.71–2.85 | 0.51 |
| Split of the 65+ km (hatched below 1.69: equal split only) | 1.36–2.24 | 0.50 |
| Age mix of the unexplained km (non-working days and professionals at the working-day mix) | 1.73–2.27 | 0.27 |
| Trip-distance conversion | 1.95–2.43 | 0.22 |
| Weekends (standalone) | 1.80–2.06 | 0.13 |
| Professionals' work driving | 2.06–2.29 | 0.11 |
| Composition bound | 2.06–2.28 | 0.10 |
| Carried to Spain per licence holder (A2) | 2.06–2.13 | 0.035 |
| Employment reweight | 2.06–2.12 | 0.03 |
| Survey years | 2.04–2.09 | 0.026 |

The remainder bar is recomputed so that it varies one choice: with the remainder at the
working-day mix it equals the estimate exactly (tested). The low end of the region bar is
Barcelona city, whose replicate spread of the 65+/45–64 km ratio (0.75–1.43 relative) is much
wider than the province's (0.87–1.14), so it lies within sampling error; part of the profile's
share below is sampling noise. Bar lengths depend on which alternatives were tried, not on how
likely they are.

**Shapley shares** of the variance of the log 75+ ratio over the one full factorial in the table,
profile (7) × non-working mix (3) × remainder mix (5) × split (`risk_older_attribution.csv`; SD
of the log 0.236 with four splits, 0.191 without the equal split):

| Factor | Four splits | Without the equal split |
|---|---:|---:|
| Split | 58% | 32% |
| Profile | 27% | 40% |
| Remainder | 15% | 26% |
| Non-working days | 1% | 2% |

These are descriptive and depend on the alternatives chosen: adding one post-hoc split moved the
split's share without the equal split from 6% (the earlier 315-cell table) to 32%. They are not
used to rank data priorities and are not on the site.

**The ends** (`risk_older_extremes.csv`, joint 95% sampling intervals with the mixes' external
weights, the coverage weights and the RACC constant held fixed, so too narrow if anything; their
pigeonhole Monte Carlo errors are 0.006–0.055, so at most one decimal of each end is firm):

* Minimum, 0.975: Barcelona city's profile, MOVILIA 2006's weekend mix for both the non-working
  days and the unexplained km, equal split; marked. Interval 0.74–1.42. The second row at or below
  1 (0.989) is the same structure with the EMEF overnight-stay proxy for the non-working days.
* Lowest unmarked, 1.214: the same structure with the RACC split. Interval 0.91–1.76, which
  reaches 1. Its implied 65–74/45–64 km per holder is 0.995. The edge is set by how the RACC split
  is built and is not stable under fuller crossing (exploratory 1.15–1.19), so the site prints
  "about 1.2" and says what sets it.
* Maximum, 3.281: Madrid's profile, the working-day mix for non-working days, MOVILIA 2007's
  over-50-km journeys for the unexplained km, the Madrid licence-holder split; not marked.
  Interval 2.67–4.10 (profile and split from the same EDM resample, paired one to one).

**The range is not a bound.** Distance, survey years, professionals, A2, employment and
composition are varied one at a time; crossing them would move both ends and the unmarked
minimum. Exploratory crossings, not reproduced by the pipeline and not on the site, gave
0.92–3.53 with survey years pooled, 0.78–3.59 with single-year area cells, and an unmarked
minimum of about 1.15–1.19 with four splits.

**Two top-end biases of opposite sign**, neither corrected: the licence split's definitional
mismatch, about +7–9% (3.28 against about 3.07 like for like), and the Madrid-profile cells
understating Madrid's own pattern, about −5% (a direct transfer gives 3.01 against 2.85). At the
top, drivers aged 75 and over would drive 41% of the km DGT records for cars of owners aged 75 and
over, against 69% at 65–74 and 105% at 45–64: a national tension, reported, not used to mark rows.
The top's agreement with the EDM is circular (a Madrid profile checked against Madrid's survey).

### Joint-scenario checks: the marking rule

A row is marked `at_odds_with_mens_driving` when the km it allocates to men aged 75 and over per
DGT B-licence holder are at least those of men aged 65–74 (≥ 1 − 1e-9). It is computed from the
km allocation by sex and age over DGT holders by sex and age, and is a property of the split: men's
implied ratio is 0.48 (Madrid per resident), 0.45 (Madrid per licence holder), 0.68 (RACC limit)
and 1.00 (equal split) in every structure. The rule marks exactly the 136 equal-split rows, and
the same set for any threshold in (0.68, 1]. Evidence that men aged 75 and over drive less per
holder than men aged 65–74 (men drive 78–86% of 75+ km under any split):

* EDM2018 like for like: 0.48 (0.36–0.63), computed;
* RACC driving days per holder: at most 0.68, computed from quoted constants;
* EMEF 2016 per self-reported holder: 0.31 (0.18–0.53), exploratory; self-report understates the
  per-DGT-holder ratio, if anything;
* INE EET 2009–10 car time per DGT holder: 0.59, driver and passenger together, exploratory.

Women are not used: the EDM's like-for-like 0.99 (0.56–1.58) does not rule out 1, and a by-sex
rule would mark the Madrid split itself (women 1.08). Pooled per-holder ratios are reported
(`pooled_km_per_holder_75_vs_65_74`) but not used, because they depend on the sex mix: in an
exploratory crossing equal-split rows escaped a pooled rule at 0.990. The counts of marked rows
are counts, not weight of evidence.

The earlier rule that also marked rows with 65–74 at or above 45–64 per holder is dropped as a
marking rule and kept as the diagnostic `km_per_holder_65_74_vs_45_64`. It is algebraically
ratio_65_74 ≤ 0.715 (the involved-per-holder ratio), so it set the 65–74 edge by construction;
its evidence (EDM Monday–Thursday 0.51, EMEF province 0.55–0.62) is working-day and regional and
does not test the weekend mixes it marked; the only all-days national figure is owner-based
(0.81). At threshold 1 it does not change the lowest unmarked 75+ value (1.214 with or without
it). The ten Barcelona-city rows with weekend mixes under the Madrid splits (75+ 1.47–1.70, implied
65–74/45–64 per holder 1.00–1.09) and the RACC minimum row (0.995) are tensions, described here.

The minimum row gives drivers aged 75 and over 1.47 times the km of cars registered to owners
of that age (`driver_over_owner_km_75_plus`); by an exploratory calculation, that is 18.5 bn km,
about 11,800 km per B holder (1.08 times holders aged 65–74 and 0.98 times those aged 45–64),
with 44% of all km on weekend-type mixes. Earlier versions of this document said that,
each choice being credible, the combination was credible too; it relies on a split at odds with
men's driving. The coherence checks apply only to the older rows: no measured ordering exists for
18–44.

**Low mileage.** Drivers who drive few km, at any age, tend to have more crashes per km, partly
because more of their driving is on streets with junctions (Janke 1991, *Accidents, mileage, and
the exaggeration of risk*, Accident Analysis and Prevention 23:183–188; Langford, Methorst and
Hakamies-Blomqvist 2006, Accident Analysis and Prevention 38:574–578), so a higher rate per km at
75 and over would not by itself show that age makes driving less safe. No number from these goes
on the site.

### Barcelona's working-day check

In the city, 120 of the 344 car drivers aged 65 and over with a recorded age were 75 or over.
Splitting the city's 65+ km with the four splits gives 0.80–1.82 at 75 and over across the three
denominators (`risk_barcelona_older.csv`), below the 45–64 rate in some combinations and above
it in others. The 95% sampling intervals (EMEF city replicates, crossed with the EDM's for the
Madrid splits, and gamma draws; Monte Carlo errors 0.01–0.03, so the page prints one decimal)
are wide, but not every one includes 1: for the Madrid split they are 0.83–1.79, 1.22–2.29 and
1.00–1.99, and with crossing trips counted at an internal trip's
length the licence and RACC splits' intervals (1.33–2.51, 1.07–1.78) exclude 1 too. The check
neither confirms nor rules out a rate above 45–64 because the splits and the ways of counting
crossing trips disagree, not because every interval is wide. For the Madrid split, one interval
includes 1 (internal trips only), one lies above it (crossing trips at an internal trip's
length) and one has its lower end at 0.999 with a Monte Carlo error of 0.012 (crossing trips in
full): nine independent sets of replicates put that end between 0.998 and 1.020, so the page
says another set of resamples could put it on either side of 1 rather than counting it.

### Validation and context sources

Every source in this table is validation or context only. None replaces the conditional split or
narrows the range. Values not computed in the pipeline are marked *quoted* or *exploratory*.

| Source | Coverage | Measure | Value | Use |
|---|---|---|---|---|
| CRTM Encuesta Sintética de Movilidad 2024 | Comunidad de Madrid, ages 14–80 (over 80 excluded by design); 8,200 (web), 8,215 achieved, 7,143 validated | private-vehicle trips (driver and passenger together) per resident, 65–80 against 46–64 | 0.470, against EDM2018 0.461 (0.438–0.480) on the same bands (exploratory) | currency of the Madrid pattern only; one 65–80 band, no km, no microdata (portal checked 2026-10-08) |
| EDM2004 | Comunidad de Madrid | 75+/65–74 car-driver km per resident | 0.196 (0.114–0.295) (exploratory, P3) | direction of change |
| EMEF routing, 2014 and 2016 | province of Barcelona | 75+/65–74 km per resident of identified retirees | about 0.25 (exploratory, P2) | validation |
| EMEF 2016 licence question | province of Barcelona | km per self-reported holder, 75+/65–74 | men 0.31 (0.18–0.53), women 0.32 (0.10–0.71) (exploratory) | men's marking evidence; questions Madrid's women's figure |
| RACC, *Mayores al volante* (2013) | Spain, 3,003 holders aged 65+ | driving days per holder, 75+/65–74 | men 0.677 (computed from quoted constants); about 0.67 for both sexes | RACC split's men's constant |
| EMQ 2006 via Fundació RACC/CED 2011, table A-4 | Catalonia | share who drive "very often", per resident | men 0.45–0.55, women 0.19–0.24 (quoted) | consistent with Madrid once km per habitual driver fall with age |
| INE EET 2009–10 | Spain, all days | car-travel time, 75+/65–74 | 0.39 (0.30–0.49), driver and passenger; men per DGT holder 0.59; weekdays 0.42, weekends 0.36 (exploratory, P3) | context and marking evidence |
| INE EET 2002–03 | Spain | — | not usable: 49% of travel slots have no mode | — |
| ODiN (NL), NTS (England), MiD (Germany) | national | km or trips per resident at the oldest ages over the next band | 0.50–0.58; 0.56–0.58; about 0.55 (quoted) | context: Madrid's gradient is steep |
| DGT owner km 2024 | Spain | owner km 75+/65–74 | 0.45 per resident, 0.76 per car, 0.92 per holder; cars per holder 1.14 against 0.94 (computed) | comparison and diagnostics; owner is not driver |

### Sources examined and not usable

* MITMA big-data mobility (mobile phones): no age of the driver, no driver/passenger split.
* CRTM phone-data contract: aggregate flows, no age.
* ESRA3: attitudes, no km by exact age.
* Línea Directa 2016 older-driver report: no microdata, unstated sample.
* MAPFRE older-driver reports: no km by age.
* RACE–Liberty 2013 senior-driver survey (fieldwork November 2012 to January 2013): no km by age
  band beyond 65+.
* CRTM ESM2014: same design limits as ESM2024.
* MOVILIA microdata: availability not verified.
* INE ECEPOV: no km.
* EHMA 2008 (disability survey): no driving km.
* Idescat EUT 2023–24: confidential microdata; a tabulation is requested.
* Basque Encuesta de Movilidad 2016 and Estudio de Movilidad 2021: candidate, not yet obtained.

### Missing data that would help

In order of what they would resolve, with the holder and the route (details in
[`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md)):

1. **EMEF aggregates for 65–74, 75–84 and 85+** (fallback 75+), by sex, 2014–2016 and 2022–2024
   pooled: car-driver km per resident, trips, respondents, drivers, licence holders, design-based
   SEs; the true age × P1b routing table for every year 2014–2024; the calibration cells and
   margins; the coding of 65+ "home duties" from 2020; geocoded straight-line distances for
   2014–2020 (Institut Metròpoli for tabulations; ATM for confidential microdata). It would
   replace the Madrid transfer with the profile region's own measurement and settle the
   composition bound.
2. **A national, all-days measure of driving by exact age that separates driver from passenger**
   (INE EET 2024–25 on release; Idescat EUT 2023–24 tabulation).
3. **The age mix of the unexplained km, weekends and long trips** (a MOVILIA successor with
   driver role and age; DGT owner km by owner sex and licence status, or by declared main driver;
   insurers).
4. **A second exact-age regional survey with no upper age limit** (Basque EM 2016 and 2021).
5. **RACC km by sex and age band** (Fundació RACC), to replace the days-based men's limit and the
   women's equal assumption.
6. **DGT B-licence holders by age and sex for the province of Madrid in 2018**, to make the
   like-for-like comparison consistent in time.
7. **CRTM ESM2024 records** (exact age to 80, licence, driver/passenger, zones): low priority, as
   its universe stops at 80 and only about 30–37 respondents aged 75–80 drove on the day.
8. **EMQ 2006 microdata**: historical validation only.

### Change log

* 2026-10-08: the section gives a conditional estimate beside the sensitivity range instead of
  saying that no figure can be given. The Madrid split's interval now includes the EDM's sampling
  error (1.63–2.64 instead of 1.78–2.35). A fourth split (RACC limit), the men's marking rule, the
  composition bound, the one-at-a-time decomposition, the Shapley shares, the intervals at the
  ends of the range and the Barcelona intervals were added. The envelope (0.97–3.28) is unchanged
  and no row was dropped. The statements "403 of 405 combinations" and "each of these choices is
  credible, so the combination is credible too" were removed.
* 2026-10-08, after the final audit: the Monte Carlo standard errors of the joint intervals are
  re-estimated by a pigeonhole bootstrap (0.019 and 0.033 for the Madrid split at 75 and over,
  against 0.006 and 0.010 by batches, which ignored the shared replicates); the interval values
  are unchanged, and the pages print their ends to one decimal. The licence trend is the archived
  any-class series (the "+7% and +29% in B licences" were the change against 65–74 of all classes,
  mislabelled), and the cohort update, 1.88, is now computed in `reference_checks`. A row on
  women's implied km per holder joins the table of possible biases. Figure 3's bars are labelled
  by the assumption they change ("Age mix of the unexplained km" replaces "Km outside working
  days", which read as including weekends). The Barcelona check's reason is corrected. The EMEF
  questionnaires of 2014–2016 and 2022–2023 and the methodology report 2003–2018 are archived in
  `data/raw/emef/`.

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
kilometre sensitivity, weekend and coverage tables above, and in `risk_coverage_scenarios.csv`):

| Source of variation | 18–29 | 30–44 | 65+ |
|---|---|---|---|
| Regional profile (Method C: four parts of the province, Madrid 2018) | 1.64–3.63 | 1.12–1.64 | 0.99–1.65 |
| Licence-calibrated transfer (Method A2) | 2.24 | 1.27 | 1.23 |
| Distance treatment (thirteen alternatives) | 2.36–2.66 | 1.35–1.45 | 1.13–1.41 |
| Survey years (2024; 2023–2024; 2021–2024; 2019 and 2021–2024) | 2.46–2.85 | 1.28–1.54 | 1.18–1.21 |
| Professionals' unrecorded work driving (25% or 50% of work trips by car) | 2.44–2.48 | 1.41–1.42 | 1.26–1.33 |
| Older sample's employed share set to the census | 2.53 | 1.40 | 1.23 |
| Non-working days (two age mixes, 22% or 32% of annual km) | 2.38–2.47 | 1.42–1.45 | 1.05–1.11 |
| Age mixes of the kilometres the survey does not cover (five credible mixes, Method A's profile) | 1.95–2.90 | 1.34–1.47 | 1.03–1.36 |
| Those mixes with each other regional profile | 1.49–3.75 | 1.13–1.72 | 0.85–1.75 |
| **All of the above** (the sensitivity range on the site) | **1.49–3.75** | **1.12–1.72** | **0.85–1.75** |
| Kilometre total (Method B variants) | none: a common factor | none | none |

The regional profile, combined with the age mixes of the uncovered kilometres, sets both ends of
the ranges at 18–29 and 65 and over. Without the regional profiles and the uncovered kilometres,
the alternatives span 2.24–2.85 at 18–29, 1.27–1.54 at 30–44 and 1.05–1.41 at 65 and over. For 65
and over, most of those alternatives raise the ratio: the distance treatments (up to 1.41),
professionals' driving (1.26–1.33), the census employment share (1.23) and the licence-calibrated
transfer (1.23). The weekend mixes lower it (1.05–1.11), and so does the Barcelona city profile
(0.99). Under all the alternatives the ratio of driver deaths per kilometre to 45–64 ranges from
1.33 to 3.35 at 18–29 and from 2.09 to 4.29 at 65 and over. The absolute rates move with the
kilometre total, from 299 (all cars) to 315 (no hire cars or driving schools) per billion km for
the 65-and-over group, but the ratios do not.

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
never merged into the intervals. For drivers aged 18–29 and 65 and over the regional profile
(1.64–3.63 and 0.99–1.65 alone) and the age mix of the half of DGT's kilometres that the survey
does not cover dominate; together they give 1.49–3.75 and 0.85–1.75. The distance treatment
(1.13–1.41 at 65 and over) comes next. For drivers aged 75 and over the region and the split
move the figure most one at a time (1.71–2.85 and 1.36–2.24); the sampling interval of the
conditional estimate holds the split fixed but includes the Madrid survey's sampling error. The sensitivity ranges are not
bounds: they combine only the regional profile with the uncovered kilometres, and other choices
taken together would widen them.

## Conclusions

1. **Coverage.** Carried to Spain, the survey's working days account for 51% of DGT's 2024 car
   kilometres less taxis and ride-hailing cars. Weekends and holidays (15–30%), Spain's higher
   driving per resident (3–14%), professionals' unrecorded work driving (3–7%) and the months
   outside the fieldwork (−1% to 2%) can account for the rest, or leave up to 29% unexplained. No
   source gives the age mix of that half; the ratios below assume the working-day mix and test
   others.
2. **Involvement per kilometre** (modelled). Per kilometre driven in Spain in 2024, car drivers
   aged 18–29 were involved in injury crashes 2.53 times as often as drivers aged 45–64 (95% CI
   2.25–2.82; sensitivity range 1.49–3.75; 2.24 with the licence-calibrated transfer). The
   direction holds under every alternative; the size does not. Drivers aged 30–44 were involved
   1.40 times as often (1.30–1.53; range 1.12–1.72). Drivers aged 65 and over were involved 1.19
   times as often on the central estimate (1.03–1.36), but the alternatives give 0.85–1.75, so
   whether they are involved more or less often per kilometre than drivers aged 45–64 is not
   established. Most alternatives taken one at a time raise their ratio, among them the distance
   treatments (1.13–1.41) and professionals' unrecorded driving (1.26–1.33); the weekend mixes
   and the more urban profiles lower it.
3. **Barcelona, a different population.** In Barcelona city on the working days of 2025, drivers
   aged 65 and over were involved at about the 45–64 rate per kilometre driven inside the city by
   residents (0.80–1.11 across three denominators; every interval includes 1), with a downward
   bias from drivers counted only in the numerator. Drivers aged 18–29 were involved at 2.14–2.61
   times that rate.
4. **Ages 75 and over** (conditional, beside the sensitivity range). If people aged 75 and over
   drive as much less than those aged 65–74 as in Madrid in 2018, with everything else central,
   drivers aged 75 and over were involved 2.06 times as often per km as drivers aged 45–64 (95%
   sampling interval 1.6–2.6, which includes both surveys' sampling error; its second decimal is
   within Monte Carlo error) and drivers aged 65–74 0.94 times (0.8–1.1). Across four splits and
   every other choice the sensitivity range is 0.97–3.28 (65–74: 0.66–1.63); below about 1.2 it is
   reached only with equal km per licence holder, at odds with Spanish surveys of men's driving.
   The lowest other combination, 1.21, has a sampling interval of 0.9–1.8, so these data cannot
   show that drivers aged 75 and over are involved more often per km whatever the assumption, nor
   by how much. Involvement per licence holder at 75 and over is 0.95 times the 45–64 rate. In
   Barcelona the four splits give 0.80–1.82 and disagree with each other. The EMEF's own aggregates
   for 65–74 and 75 and over would replace the Madrid transfer
   ([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md)).
5. **Severity once involved** (counted). Car drivers aged 65 and over were killed in 11.4 of every
   1,000 involvements in 2024 (9.5–13.4), against 4.6 (4.0–5.4) at 45–64; drivers aged 75 and over
   in 15.9 (12.6–19.8). This needs no kilometres. Driver deaths per kilometre at 65 and over are
   2.92 times the middle-aged rate on the central estimate (2.21–3.82; sensitivity range
   2.09–4.29), against 1.19 for involvement (range 0.85–1.75). Under every alternative the death
   ratio exceeds the involvement ratio, so the excess in deaths per kilometre comes mainly from the
   outcome once a crash has happened; these data cannot say why older drivers fare worse.
6. **Responsibility** cannot be assessed with public data (see above). Involvement counts every
   driver in an injury crash, whoever caused it, so no rate here says that drivers of any age
   cause more crashes.
7. **Per licence holder.** Older licence holders are involved less often than middle-aged ones
   (2.4 against 3.0 per 1,000 in 2024) because many drive little. Rates per licence holder or per
   resident describe the burden on a population, not the risk of a kilometre driven.
8. **Men and women.** On the same transfer, men drove about two thirds of car-driver kilometres in
   2024. Per kilometre, male private-car drivers were involved 0.91 times as often as female
   drivers (0.85–0.98; 0.60–1.23 under the other profiles), so neither sex is shown to be involved more often per km, and killed 2.65 times
   as often (2.10–3.38; 1.75–3.55).
9. **The former owner-age figure.** Compared like for like (drivers aged 18–29, 30–44 and 65 and
   over against 45–64), owner kilometres gave 4.62, 1.51 and 1.00, against 2.53, 1.40 and 1.19 by
   the driver's age. The former figure's 6.75 compared owners aged 18–24 with 35–54. A car's owner
   is often not its driver, so owner kilometres overstated young drivers' excess and understated
   older drivers' rate.
