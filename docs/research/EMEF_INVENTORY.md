# The EMEF working-day mobility survey, 2014–2024: inventory and harmonisation

The EMEF (Enquesta de mobilitat en dia feiner) is the annual survey of the mobility of residents
aged 16 and over on a working day (Monday to Friday, not a public holiday) in the planning area of
the Autoritat del Transport Metropolità (ATM) of the Barcelona area. It is run by the ATM with
Idescat and the Institut Metròpoli. This document records which public-use files exist, how
they were read, how the eleven years were made comparable, which checks they pass, and which
questions they cannot answer. The code is `src/dgt_stats/emef/` (`variables.py` for the year-by-year
layout, `ingest.py` for reading and checking); `python scripts/emef.py build` writes the
harmonised tables and the inventory, and `python scripts/emef.py validate` the reproduction of
published figures. Provenance and reuse terms of each file are in
[`docs/data_sources.md`](../data_sources.md) and `data/raw/manifest.csv`.

## Files

Every year from 2014 to 2024 has three files under `data/raw/emef/<year>/`: a respondent file
(one row per respondent, including those who made no trip on the reference day), a trip file (one
row per trip, keyed by respondent `ID` and trip order `ORDRE`) and a dictionary. 2022 also has the
"revised" dictionary that omc.cat now links. The two 2022 versions differ only in the trip-file
value labels, and the first release is the one that matches the file: the 2022 file uses code 25
(another private vehicle) in 11 first stages and codes every trip made only as a car driver as 14
in `V03G_R1`, as the first release says. The later "revised" one carries the 2021 labels for mode
codes 23–25 and for `V03G_R1` (car driver 13). Codes 12 and 13, the only ones the estimates read
directly, mean the same in both. The files were published under different names over the years
(`..._Indivi_...`, `..._Individus`, `..._Desplaçaments`, and `..._Opinió` for the respondent files
of 2018, 2019, 2020 and 2023); the manifest keeps each original name. The full inventory, with
counts, the source column of each harmonised variable, missing-value shares and the method notes
below, is `reports/tables/emef_inventory.csv`.

| Year | Survey area | Respondents | Of whom made a trip | Trips | Car-driver trips | Respondents who drove | Population 16+ | Age groups |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2014 | STI | 9,461 | 8,663 | 35,147 | 10,497 | 3,230 | 4,644,923 | 16–29 / 30–64 / 65+ |
| 2015 | STI with the whole of Osona | 9,490 | 8,657 | 38,340 | 10,989 | 3,344 | 4,692,584 | 16–29 / 30–64 / 65+ |
| 2016 | STI with the whole of Osona | 9,601 | 8,708 | 32,990 | 11,272 | 3,539 | 4,713,222 | 16–29 / 30–64 / 65+ |
| 2017 | STI with Osona, the Berguedà and the Moianès | 10,010 | 8,926 | 32,334 | 11,504 | 3,769 | 4,780,181 | 16–29 / 30–64 / 65+ |
| 2018 | STI with Osona, the Berguedà and the Moianès | 10,117 | 9,355 | 40,013 | 13,041 | 3,947 | 4,815,772 | 16–29 / 30–64 / 65+ |
| 2019 | SIMMB | 10,106 | 9,365 | 41,041 | 12,734 | 3,982 | 4,749,821 | 16–29 / 30–44 / 45–64 / 65+ |
| 2020 | SIMMB | 10,145 | 8,671 | 35,276 | 10,585 | 3,514 | 4,833,042 | 16–29 / 30–44 / 45–64 / 65+ |
| 2021 | SIMMB | 10,164 | 9,165 | 35,687 | 11,331 | 3,719 | 4,826,057 | 16–29 / 30–44 / 45–64 / 65+ |
| 2022 | SIMMB | 10,151 | 9,281 | 40,215 | 11,621 | 3,740 | 4,853,758 | 16–29 / 30–44 / 45–64 / 65+ |
| 2023 | SIMMB | 10,154 | 9,379 | 42,121 | 11,905 | 3,669 | 4,927,771 | 16–29 / 30–44 / 45–64 / 65+ |
| 2024 | SIMMB | 11,420 | 10,710 | 45,552 | 12,431 | 3,892 | 5,019,771 | 16–29 / 30–44 / 45–64 / 65+ |

STI is the Integrated Fare System area; SIMMB, the ATM's planning area, is the province of
Barcelona. The survey area changed three times: the whole of Osona was included from 2015, the
Berguedà and the Moianès from 2017, and from 2019 the area became the province of Barcelona, which
took out the Baix Penedès and the Selva (in other provinces). A series for the whole survey area is
therefore not on a constant area before 2019. The seven-comarca Barcelona Metropolitan Region
(RMB; residence zones 1–4) is the only area every edition covers in full, so it is the basis of
every comparison across the eleven years.

## What the survey covers and what it does not

* **Residents, working days, fieldwork months.** Non-residents' trips (visitors, tourists, through
  traffic), weekends and public holidays are outside the survey. The reference days fall in the
  fieldwork months; in 2024 these were 1 April to 21 June and 26 September to 27 November (EMEF
  2024 executive summary, archived as `data/raw/emef/2024/emef_2024_executive_summary.pdf`), so
  July and August are not covered.
* **Sample design.** The same technical sheet describes a stratified multi-stage sample drawn from
  the population register of Catalonia, with weights calibrated to the census of 1 January 2025,
  by place of birth since 2023. The public files carry neither the sampling units nor the
  calibration margins, so variance estimates from them cannot reflect the design in full.
* **The 2023 weekend module.** Asked in both waves, `V11` counts how many of the last four weekends
  the respondent spent Saturday night away from their municipality of residence, long stays
  excluded. The follow-up questions (destination, purpose, means of transport out and back, car
  occupancy) refer only to the most recent such weekend. The module measures overnight stays away,
  not weekend driving; it supplies only a proxy age mix in a sensitivity analysis.
* **The 2023 accident module.** Asked in the first wave only (5,051 respondents), `V35_W1` asks
  whether the respondent suffered any accident or fall in a public space in the last 12 months,
  however minor, falls on pavements included. 379 said yes, and 34 mentioned driving a car. The
  module mixes falls with crashes, rests on 12-month recall, covers one wave, and has too few car
  drivers for any age comparison. It is not used.
* **Mobility professionals.** Respondents who make eight or more work trips a day (code 2 of
  `V02A_2R` in the respondent file, `TIPOL` in the 2024 respondent file: 1,609 respondents in
  2014–2024; taxi drivers, couriers, hauliers, sales staff) have only their journey to and from
  work recorded. Their trips in the course of work are counted but not described (`V02C_3` in
  2020–2023, `V02D1` in 2024). Driving in the course of such work is therefore not in the survey's
  kilometres, which matters when they are compared with national vehicle kilometres; a sensitivity
  analysis counts a share of those trips as car trips. The 2016 trip file's `TIPOL` disagrees with
  the respondent file for 504 respondents, so status is read from the respondent file.
* **The reference day.** Each respondent reports the trips of one working day. Having driven that
  day and being a driver are different things; the opinion module's usual-frequency question
  answers the second.

## Harmonisation

Nothing was harmonised by column name alone. Each variable was checked against every year's
dictionary and against the codes present in the file; where the two disagree the file wins and the
disagreement is recorded.

| Concept | Rule | Years and caveats |
|---|---|---|
| Weight | `PESAIX`, the respondent expansion factor: constant over a respondent's trips, summing to the population aged 16 and over. A weighted count of respondents is a number of residents, and a weighted count of trips is a number of trips per working day. | All years. `PESMOS` (the same weight rescaled to the sample) is not used. Weights are written with a decimal comma and sometimes no leading zero. |
| Car driver | A trip with at least one stage (`V03G`, `V03H`, `V03I`) coded 12, "car as driver". | Code 12 means car driver in every year's dictionary (tested). Code 13 is car passenger, 14 motorcycle driver. |
| Passenger | Code 13 in any stage. A passenger stage never makes a trip a driving trip. | 129 trips have both a driver and a passenger stage (a driver who also rode as a passenger) and count as driving trips. |
| Multimodal trips | `car_driver_only` marks trips whose every recorded stage is car driving. The other 4.2% of car-driver trips (2014–2024) combine driving with another mode: 2.5% with walking only, and 1.7% with public transport or another vehicle (1.6% in 2022–2024). | The files do not record each stage's distance; the exposure estimate counts half the trip distance when driving was combined with another vehicle, and tests 0% and 100%. |
| Van, lorry, motorcycle, moped | Kept apart from car driving. | Van and lorry were one code (16) to 2019, then 16 and 22; neither says whether the respondent drove. Moped driver has its own code (20) only from 2020. |
| People without trips | Kept in every denominator: a rate per resident divides by all respondents of the group. | 6.3–10.5% of residents in ordinary years, 14.4% in 2020. |
| Age | The published group of the respondent. `age3` (16–29, 30–64, 65+) exists in every year; `age4` (16–29, 30–44, 45–64, 65+) from 2019. The 2019–2024 groups collapse exactly onto `age3` (tested). | Column `V15_R1` (2014–2015), `V23_R1` (2016), `V19_R1` (2017–2018), `S02_R3` (2019–2024; `S02` in the 2024 respondent file). No year publishes exact age or any split of 65 and over. |
| Sex | 1 man, 2 woman, as in the population register. | `V00` to 2018, `S01` from 2019. |
| Residence | `CAMB` zones 1–5 (identical codes in every year) and comarca. | Comarca codes were renumbered in 2017 after the Moianès was created; each year is read with its own list. |
| Distance | `DISTANCIA_ORTO_REC_R1`, the straight-line distance between origin and destination in seven bands (0–0.5, 0.5–2, 2–5, 5–10, 10–50, 50–100 and 100 km or more). | Published from 2021. Before 2021 there is no distance variable, only duration (`V03F`). |
| Mode groups (distance model only) | Walking, cycling, public transport and driving, from the codes of the three stages, public transport taking priority. | Codes 20–25 change meaning between years. From 2022, 23 is other bus, 24 other public transport and 25 another private vehicle; in 2020 and 2021, 23 is other public transport and 24 another private vehicle, with no code 25. The groups are read year by year. |
| Usual car driving | The opinion module's frequency of driving a car. | A five-point scale to 2019 (`V09C`, `V08C`, `V08A_3`), an eight-point scale from 2021 (`V09A_4`, `V08_4`). 2020 asked only about use before the pandemic and is left out. |
| Mobility professional | Code 2 of `V02A_2R` (2014–2023) or `TIPOL` (2024) in the respondent file. | The trip file's `TIPOL` disagrees with the respondent file for 504 respondents in 2016 and for 0–5 in other years; the respondent file is used. Work trips counted in `V02C_3` (2020–2023) and `V02D1` (2024). |
| Car licence | `V21A` | Asked only in 2016, in an opinion module put to about 77% of respondents (the rest are blank). Not used: holding a licence does not identify active drivers, which the frequency question and reference-day driving do better. |
| Missing codes | 9, 99 and 999 are no answer; 998 minutes means "998 minutes or more"; a blank in the second and third mode means no further stage (no year codes it 0). | |

Two dictionary errors were found and the file followed: the 2015 trip dictionary names the age
variable `V23_R1` (the 2016 name) where the file has `V15_R1` with the same codes; and the 2024
respondent dictionary lists `S02_R3`, `S03A`, `COMARCA2` and `V01D1` where the file has `S02`,
`S03`, `COMARCA` and `V01A`. Each renamed 2024 column equals its trip-file counterpart for every
respondent (`tests/test_emef.py`).

## Checks

`ingest.validate()` runs 154 checks, fourteen per year, and every estimate depends on all of them
passing (`reports/tables/emef_checks.csv`; `build` refuses to write the tables otherwise):

* the number of respondents equals the final sample, and the weighted total equals the population
  aged 16 and over, in Table 1 of the survey's technical document (exactly, every year);
* respondent `ID` and the pair (`ID`, `ORDRE`) are unique, and every trip has a respondent;
* the weight, sex, age group and zone carried on the trip file equal those of the respondent file;
* trip numbering starts at 1 for every respondent, and the number of trip rows equals the number of
  trips the respondent reported (`V02C_2`; `V02C` in the 2017 file), in every year. Three 2020
  respondents skip a number (1 and 3 for two trips); their reported counts match the rows present,
  so the gap is in the numbering, not a lost trip;
* the mobility-professional status in the respondent file agrees with the `TIPOL` of the
  respondent's first trip for all but 0–5 respondents a year; 2016, with 504 disagreements, is the
  known exception, and the respondent file is used;
* weights are positive and every trip has a first mode.

**Reproduction of published figures.** Fifteen figures from the official 2024 results were
recomputed from the microdata (`reports/tables/emef_reproduction.csv`): trips per working day
(19,819.6 thousand), trips by men and by women, walking trips, the shares of active, public and
private main modes, the car's share of private-vehicle trips, and the shares of residents who drive
a car habitually or never, overall and by area (53.7% habitual drivers in the SIMMB). Every one
agrees to within 0.06 of the published value. Fourteen agree to the published rounding; the share
of habitual drivers in Barcelona city computes to 37.34% against 37.4% published, one rounding unit
off. This confirms the weights, the mode codes and the frequency scale.

**Distance benchmarks.** The distance model behind the kilometre estimates reproduces the mean
straight-line trip and the daily straight-line kilometres per person who travelled, by age, in the
EMEF 2024 executive summary, to within 3% (`emef_distance_validation.csv`;
[`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md)). The EMEF 2021 distance report, the source of
the road-to-straight-line ratio of 1.45 and of the 2021 benchmarks, is not archived and could not
be found online again.

## Changes of method that affect comparisons

| Year | Change | Consequence here |
|---|---|---|
| 2015 | Area extended to the whole of Osona | Series restricted to the RMB |
| 2016 | Car-licence question (`V21A`) asked of about 77% of respondents; trip-file `TIPOL` disagrees with the respondent file for 504 people | Licence question not used; professional status read from the respondent file |
| 2017 | Area extended to the Berguedà and the Moianès; comarca codes renumbered; the 65–74 and 75+ sampling strata merged; reported trip count named `V02C` | Series restricted to the RMB; comarca read per year |
| 2019 | Area becomes the province of Barcelona (SIMMB): the Baix Penedès and the Selva leave it; age published in four groups | `age4` only from 2019; contemporary estimates use the SIMMB. Before 2019, a trip of the group 30–64 takes the 30–44 and 45–64 effects of the distance model in proportion to the two groups' 2019 shares |
| 2020 | Fieldwork under COVID-19 restrictions; 14.4% of residents made no trip; mode code 24 is another private vehicle (also in 2021) | Reported, but excluded from every pooled or "historical" estimate unless stated; mode groups read per year |
| 2021 | Straight-line distance band published | Kilometres are band-based from 2021, duration-based (modelled) before |
| 2022 | The first-release dictionary matches the file; the later "revised" one carries 2021 labels | The first release is followed |
| 2023 | Weights calibrated to the census by place of birth; weekend module (both waves) and accident module (first wave) | Weekend module used only as a proxy in a sensitivity analysis; accident module not used |
| 2024 | Barcelona city sample enlarged by 1,300 respondents (3,500 in all); respondent columns renamed | Weights absorb the oversample; renamed columns verified |

**Employment at 65 and over.** The weighted share of residents aged 65 and over who are employed
was 4.3–4.4% in 2019–2021, the same as the census share for Catalonia on 1 January 2024 (4.3%), and
6.0%, 8.3% and 7.1% in 2022, 2023 and 2024 (`emef_employment_benchmark.csv`). The rise began a year
before the change of calibration in 2023. Employed older residents drive more on working days, so
an excess of them raises the 65-and-over kilometres; the exposure study reweights the group to the
census share as a sensitivity analysis.

## The age limit, and why no public file can resolve it

The public files publish age only in the groups above; none has exact age, and none separates
65–74 from 75 and over. This is a disclosure-control choice, not a gap in collection. The
methodology report for 2003–2018 (*Organització, disseny operatiu i metodologia*, Table 5) shows
that 65–74 and 75 and over were separate **sampling strata** from 2008 to 2016, and were merged
from 2017 "because of the difficulty of obtaining responses from this last age group and because
results are not given disaggregated". The questionnaire also filters on exact age (for example,
retired respondents under 75 are asked whether they did any paid work), so the confidential
records hold it. The way to a 75 and over estimate from this survey is therefore a request to the
data holders; [`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md) sets one out. Until a reply arrives,
every EMEF estimate in this repository stops at 65 and over, and any split of that group is
labelled as model-dependent and drawn from other evidence
([`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md)).

Sample sizes bound what any finer table could show. In 2022–2024 between 501 and 523 respondents
aged 65 or over drove on their reference day each year (466 women over the three years), against
2,754–2,940 aged 30–64. The data holders publish an estimate only when it rests on at least 20
sample observations; a 75 and over cell by sex would meet that only when years are pooled.
