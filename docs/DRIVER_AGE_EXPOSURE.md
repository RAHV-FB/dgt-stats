# Driver age and crashes per kilometre

This document explains how the repository estimates how often car drivers of each age are involved
in injury crashes per kilometre driven, and how far that answer can be trusted. It quotes no result
that is not in a committed table; the tables named below hold the numbers, and the drivers page of
the site prints them with their intervals.

## The question

DGT counts the car drivers involved in injury crashes and killed within 30 days, by age band and
sex. It publishes no kilometres by the age of the driver. Its only kilometre table by age is by the
age of the *registered owner* of the car, which is not the age of the driver (young people drive
cars registered to their parents, older owners' cars are partly driven by others, company cars
carry no age), so it is not used for driver age. Without kilometres the crash counts say nothing
about risk per distance, so the kilometres by age are estimated from travel surveys.

Two results do not depend on that estimate and are the firmest: how often a crash kills the driver
once the driver is involved, by age (`risk_severity_and_licences`), and men against women per
licence holder and once involved (`drivers_sex_ratios`). The per-kilometre results depend on it.

## The data

**EMEF, 2014-2024.** The Enquesta de mobilitat en dia feiner is the annual survey of the mobility of
residents aged 16 and over on a working day in the planning area of the Autoritat del Transport
Metropolità of the Barcelona area, run with Idescat and the Institut Metròpoli. The public files
(`data/raw/emef/<year>/`) hold, for each year, a respondent file (including respondents who made no
trip), a trip file and a dictionary. The code is `src/dgt_stats/emef/`: `variables.py` records, year
by year, which column holds each harmonised variable and what its codes mean, `ingest.py` reads and
checks the files, `distance.py` turns distance bands into road kilometres and `exposure.py`
estimates driving.

The eleven years are made comparable variable by variable, each checked against that year's own
dictionary and the codes present in the file; where the two disagree the file wins.

* *Weight.* `PESAIX`, the respondent expansion factor, constant over a respondent's trips; a
  weighted count of respondents is a number of residents.
* *Car driver.* A trip with at least one stage coded as car driver; a passenger stage never makes a
  trip a driving trip. Trips that combine driving with another vehicle count for half their distance
  in the central estimate, because the files do not record each stage's distance.
* *People without trips* stay in every denominator: a rate per resident divides by all residents of
  the group.
* *Age.* The published group: 16-29, 30-64 and 65 and over in every year, with 30-44 and 45-64 apart
  from 2019. No year publishes exact age or a split of 65 and over.
* *Survey area.* It changed over the years and became the province of Barcelona in 2019. The
  estimates for Spain use the 2022-2024 editions, which share one area.
* *Distance.* A trip's straight-line distance in seven bands exists only from 2021; before 2021 there
  is only duration.
* *Mobility professionals,* who make many work trips a day, have only their journey to and
  from work described. Their driving at work is outside the survey's kilometres.

`ingest.validate()` runs a set of checks per year (respondent and trip counts, weights summing to
the survey universe, unique keys, code meanings, the 2024 renamed columns) and every estimate
depends on all of them passing. `tests/test_emef.py` asserts that they pass, that the published 2024
figures of the survey are reproduced from the microdata, and that the distance model reproduces the
benchmarks of the survey's own reports. None of this writes a table.

**EDM2018.** The Encuesta Domiciliaria de Movilidad of the Consorcio Regional de Transportes de
Madrid gives respondents with *exact* age and their trips as car drivers with distance
(`src/dgt_stats/edm2018.py`; `scripts/fetch_edm.py` extracts the public workbooks). It is used for
the split of driving between 65-74 and 75 and over, which the EMEF cannot give, and as a second
regional age profile. Madrid survey data are (c) Consorcio Regional de Transportes de Madrid, reused
under its open-data licence; Powered by CRTM (<https://www.crtm.es>).

## From distance bands to kilometres

The model of `emef/distance.py` places each trip within its band. Straight-line distance is modelled
as log-normal given the trip's duration, whether the trip stays inside one municipality, whether it
leaves the survey area, whether it touches Barcelona city, the respondent's age group and the year,
fitted by maximum likelihood with interval censoring: each trip contributes the probability of its
observed band, so the model never contradicts a band. A trip's distance is the mean of the fitted
distribution truncated to its band. Before 2021 the same model gives a duration-only mean, so the
kilometres of 2014-2020 are modelled, not measured, and are not used for the estimates for Spain.

Straight-line distance becomes road distance with one typed input: the road-to-straight-line ratio
of **1.45**, which the EMEF 2021 distance report (Institut Metròpoli for the ATM, October 2022,
Table 1) measured for driving trips from the straight-line and road distances of every trip with
coordinates. The report is not archived in the repository; the ratio and the report's benchmarks
used to check the model are transcribed in `emef/distance.py`. A common ratio multiplies every age
group's kilometres alike, so it changes the level of the rates and hardly the ratios between ages.

Trips without a band, and trips whose band cannot be reached in their duration, take the model's
mean given duration, but no more than the duration allows at a long-distance door-to-door speed
(`exposure.UNBANDED_MAX_SPEED`). A few such long
trips weigh heavily for drivers aged 65 and over, which is why the treatments of long and unbanded
trips are tested (`emef_sensitivity`) and why the older groups' intervals are the widest.

## From the survey to Spain

The central object is the car-driver kilometres per resident, by sex and age group, on a working
day (`emef_exposure_contemporary`, 2022-2024). Each survey's kilometres per resident are applied to
the population of Spain by sex and single year of age (INE, 1 July 2024), which gives each age
group's share of the car kilometres (`risk_national_shares`). This assumes that residents of Spain
of a given age and sex drive in the same proportion to one another as the survey's residents.
Neither the province of Barcelona nor the Madrid region stands for Spain, and the two disagree most
at 65 and over, so the central estimate takes the average of the two shares. The shares are applied
to DGT's 2024 car kilometres from inspection odometer readings, less taxis and ride-hailing cars,
whose drivers drive for a living and are in neither the survey nor the numerator. The scale sets the
level of the rates and not their ratios.

The numerator is DGT's count of private-car drivers involved in injury crashes in 2024 and of those
killed within 30 days, by age band (`risk_national_numerator`). Drivers of unrecorded age are left
out of every rate.

The EMEF's youngest group is 16-29 while drivers must be 18, so the group is matched to drivers aged
18-29 and the tables name it by its drivers.

## What DGT's kilometres are made of

The survey describes working days of residents in the fieldwork months. Carried to Spain, its
working days account for about half of DGT's car kilometres (`risk_coverage`). The rest is weekends
and public holidays, more driving per resident in Spain than in the province, the work trips of
people who drive for a living, the months outside the fieldwork, and a remainder that no measured
part explains. `exposure_risk/coverage.py` sizes each part from MOVILIA 2006, DGT's kilometres by the
owner's autonomous community, fuel sales and toll-motorway traffic, at the setting that explains
least and the one that explains most. The central estimate gives all of it the working-day age mix;
the ranges give the weekends and the remainder other measured age mixes.

## The ranges

`risk_national_ranges` holds, for each age group, the central ratio to drivers aged 45-64, its 95%
sampling interval and the lowest and highest ratio under the alternative assumptions, each computed
around the published estimate: another regional profile (each survey alone, the Barcelona area
carrying driving per licence holder instead of per resident, or one part of the province alone);
another age mix for weekends and holidays and for the remainder (the EMEF's overnight weekend stays
away, MOVILIA 2006's weekend trips and MOVILIA 2007's long car journeys); another split of the
65-and-over kilometres at 75; and all the drivers of unrecorded age placed in one age group. The
first three are crossed; the last is tried alone. The table also names what produces each end. A
range is the spread of the alternatives tried; it is not a confidence interval and not a bound, and
other choices would widen it. The sampling interval holds every such choice fixed; it comes from
resampling respondents within strata (and households for Madrid) crossed with Poisson error in the
crash counts, and is probably too narrow because the public files carry neither the sampling units
nor the calibration of the weights.

What the tables show: the direction at 18-29 holds under every alternative, 30-44 is modestly above
the reference under every alternative, 65-74 cannot be told apart from it, and for 75 and over no
direction is established.

## Drivers aged 75 and over

The EMEF groups everyone aged 65 and over. The split of its 65-and-over kilometres between 65-74 and
75 and over is taken from the Madrid survey's ratio of kilometres per resident,
which makes the estimate for 75 and over a *conditional* estimate: it holds if drivers aged 75 and
over drive as much less than those aged 65-74 in Spain as in Madrid. Two other splits are tried
(`risk_older_split`): Madrid's kilometres per licence holder applied to Spain's licence holders, and
equal kilometres per licence holder at both ages. Licence holding falls from 65-74 to 75 and over
about as much in the province of Madrid as in Spain, which makes the first split close to the
central one; the second gives the lowest ratios. The range for 75 and over includes 1, so the data do
not establish that these drivers are involved more often per kilometre, or by how much. What they do
show, with no kilometres, is that a crash is far more often fatal for them.

The EMEF's respondents aged 65 and over are in work more often in 2022-2024 than the census counts
for Catalonia (`emef_employment_benchmark`); setting the share to the census lowers the 65-and-over
kilometres per resident slightly (`emef_sensitivity`).

## The check in Barcelona

Inside Barcelona on working days, involvement per kilometre can be compared without carrying the
survey to Spain: the Guardia Urbana's 2025 records give the age of most of the car drivers involved in
injury crashes in the city, uninjured drivers included, and the EMEF gives the kilometres the
survey area's residents drove inside the city on a working day, over the working days of 2025
(`exposure_risk/barcelona.py`, `risk_barcelona_rates`). The part of a trip into or out of the city
that lies inside it cannot be measured, so three versions of the kilometres are given. The crashes
include drivers whose kilometres the survey does not count, mostly of working age, so older drivers'
ratio is more likely biased down than up.

## Men and women

The survey's kilometres are split by sex and carried to Spain in the same way
(`risk_sex_per_km`). Per kilometre, neither sex is shown to be involved more often (the range spans
1), while men are killed far more often; per licence holder, men are involved more often, which on
the estimated kilometres comes from their driving further (`drivers_sex_ratios`).

## Limitations

* The kilometres by age are estimated by transfer from two regional surveys; no national source
  measures them.
* Involvement counts every driver in a crash, whoever caused it; deaths once involved count only the
  driver's own death.
* The survey measures residents on working days; non-residents, weekends and driving at work are
  outside it and are covered only through the alternatives of the ranges.
* The sampling intervals are probably too narrow, and the ranges are not bounds.
* The 75-and-over estimate rests on a split taken from another region and another year.
* DGT describes its kilometre totals as valid only in aggregate.
