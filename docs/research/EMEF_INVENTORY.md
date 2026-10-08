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
revised dictionary that omc.cat now links, which differs from the first release only in the
trip-file value-label sheet. The files were published under different names over the years
(`..._Indivi_...`, `..._Individus`, `..._Opinió`, `..._Desplaçaments`); the manifest keeps each
original name. The full inventory, with counts, the source column of each harmonised variable,
missing-value shares and the method notes below, is `reports/tables/emef_inventory.csv`.

| Year | Survey area | Respondents | Of whom made a trip | Trips | Car-driver trips | Respondents who drove | Population 16+ | Age groups |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2014 | STI | 9,461 | 8,663 | 35,147 | 10,497 | 3,230 | 4,644,923 | 16–29 / 30–64 / 65+ |
| 2015 | STI | 9,490 | 8,657 | 38,340 | 10,989 | 3,344 | 4,692,584 | 16–29 / 30–64 / 65+ |
| 2016 | STI | 9,601 | 8,708 | 32,990 | 11,272 | 3,539 | 4,713,222 | 16–29 / 30–64 / 65+ |
| 2017 | STI and Berguedà | 10,010 | 8,926 | 32,334 | 11,504 | 3,769 | 4,780,181 | 16–29 / 30–64 / 65+ |
| 2018 | STI and Berguedà | 10,117 | 9,355 | 40,013 | 13,041 | 3,947 | 4,815,772 | 16–29 / 30–64 / 65+ |
| 2019 | SIMMB | 10,106 | 9,365 | 41,041 | 12,734 | 3,982 | 4,749,821 | 16–29 / 30–44 / 45–64 / 65+ |
| 2020 | SIMMB | 10,145 | 8,671 | 35,276 | 10,585 | 3,514 | 4,833,042 | 16–29 / 30–44 / 45–64 / 65+ |
| 2021 | SIMMB | 10,164 | 9,165 | 35,687 | 11,331 | 3,719 | 4,826,057 | 16–29 / 30–44 / 45–64 / 65+ |
| 2022 | SIMMB | 10,151 | 9,281 | 40,215 | 11,621 | 3,740 | 4,853,758 | 16–29 / 30–44 / 45–64 / 65+ |
| 2023 | SIMMB | 10,154 | 9,379 | 42,121 | 11,905 | 3,669 | 4,927,771 | 16–29 / 30–44 / 45–64 / 65+ |
| 2024 | SIMMB | 11,420 | 10,710 | 45,552 | 12,431 | 3,892 | 5,019,771 | 16–29 / 30–44 / 45–64 / 65+ |

STI is the Integrated Fare System area; SIMMB, the ATM's planning area, is the province of
Barcelona. The seven-comarca Barcelona Metropolitan Region (RMB; residence zones 1–4) is the only
area every edition covers in full, so it is the basis of every comparison across the eleven years.

## What the survey covers and what it does not

* **Residents, working days.** Non-residents' trips (visitors, tourists, through traffic),
  weekends and public holidays are outside the survey. The 2023 edition added one weekend question
  (overnight trips away in the previous weekend), used for weekend exposure.
* **Mobility professionals.** Respondents who make eight or more work trips a day (`TIPOL` 2:
  2,132 of 100,880 respondents with trips, by the code on their first trip; taxi drivers, couriers, hauliers, sales staff) have only
  their journey to and from work recorded. Driving in the course of such work is therefore not in
  the survey, which matters when the survey's kilometres are compared with national vehicle
  kilometres.
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
| Multimodal trips | `car_driver_only` marks trips whose every recorded stage is car driving; other car-driver trips (4.2% of them) combine driving with walking, and 1.7% with public transport or another vehicle. | The files do not record each stage's distance; the exposure estimate counts half the trip distance when driving was combined with another vehicle, and tests 0% and 100%. |
| Van, lorry, motorcycle, moped | Kept apart from car driving. | Van and lorry were one code (16) to 2019, then 16 and 22; neither says whether the respondent drove. Moped driver has its own code (20) only from 2020. |
| People without trips | Kept in every denominator: a rate per resident divides by all respondents of the group. | 6.3–10.5% of residents in ordinary years, 14.4% in 2020. |
| Age | The published group of the respondent. `age3` (16–29, 30–64, 65+) exists in every year; `age4` (16–29, 30–44, 45–64, 65+) from 2019. The 2019–2024 groups collapse exactly onto `age3` (tested). | Column `V15_R1` (2014–2015), `V23_R1` (2016), `V19_R1` (2017–2018), `S02_R3` (2019–2024; `S02` in the 2024 respondent file). No year publishes exact age or any split of 65 and over. |
| Sex | 1 man, 2 woman, as in the population register. | `V00` to 2018, `S01` from 2019. |
| Residence | `CAMB` zones 1–5 (identical codes in every year) and comarca. | Comarca codes were renumbered in 2017 after the Moianès was created; each year is read with its own list. |
| Distance | `DISTANCIA_ORTO_REC_R1`, the straight-line distance between origin and destination in seven bands (0–0.5, 0.5–2, 2–5, 5–10, 10–50, 50–100 and 100 km or more). | Published from 2021. Before 2021 there is no distance variable, only duration (`V03F`). |
| Usual car driving | The opinion module's frequency of driving a car. | A five-point scale to 2019 (`V09C`, `V08C`, `V08A_3`), an eight-point scale from 2021 (`V09A_4`, `V08_4`). 2020 asked only about use before the pandemic and is left out. |
| Car licence | `V21A` | Asked only in 2016. |
| Missing codes | 9, 99 and 999 are no answer; 998 minutes means "998 minutes or more"; a blank or 0 in the second and third mode means no further stage. | |

Two dictionary errors were found and the file followed: the 2015 trip dictionary names the age
variable `V23_R1` (the 2016 name) where the file has `V15_R1` with the same codes; and the 2024
respondent dictionary lists `S02_R3`, `S03A`, `COMARCA2` and `V01D1` where the file has `S02`,
`S03`, `COMARCA` and `V01A`. Each renamed 2024 column equals its trip-file counterpart for every
respondent (`tests/test_emef.py`).

## Checks

`ingest.validate()` runs 142 checks, about thirteen per year, and every estimate depends on all of
them passing (`reports/tables/emef_checks.csv`; `build` refuses to write the tables otherwise):

* the number of respondents equals the final sample, and the weighted total equals the population
  aged 16 and over, in Table 1 of the survey's technical document (exactly, every year);
* respondent `ID` and the pair (`ID`, `ORDRE`) are unique, and every trip has a respondent;
* the weight, sex, age group and zone carried on the trip file equal those of the respondent file;
* trip numbering starts at 1 for every respondent, and the number of trip rows equals the number of
  trips the respondent reported (`V02C_2`; not in the 2017 file). Three 2020 respondents skip a
  number (1 and 3 for two trips); their reported counts match the rows present, so the gap is in
  the numbering, not a lost trip;
* weights are positive and every trip has a first mode.

**Reproduction of published figures.** Fifteen figures from the official 2024 results were
recomputed from the microdata (`reports/tables/emef_reproduction.csv`): trips per working day
(19,819.6 thousand), trips by men and by women, walking trips, the shares of active, public and
private main modes, the car's share of private-vehicle trips, and the shares of residents who drive
a car habitually or never, overall and by area (53.7% habitual drivers in the SIMMB, 37.4% in
Barcelona). Every one agrees to within 0.06 of the published value, i.e. to the published rounding.
This confirms the weights, the mode codes and the frequency scale.

## Changes of method that affect comparisons

| Year | Change | Consequence here |
|---|---|---|
| 2017 | Area extended to the Berguedà; comarca codes renumbered; the 65–74 and 75+ sampling strata dropped | Series restricted to the RMB; comarca read per year |
| 2019 | Area becomes the province of Barcelona (SIMMB); age published in four groups | `age4` only from 2019; contemporary estimates use the SIMMB |
| 2020 | Fieldwork under COVID-19 restrictions; 14.4% of residents made no trip | Reported, but excluded from every pooled or "historical" estimate unless stated |
| 2021 | Straight-line distance band published | Kilometres are band-based from 2021, duration-based (modelled) before |
| 2024 | Barcelona city sample enlarged by 1,300 respondents; respondent columns renamed | Weights absorb the oversample; renamed columns verified |

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
aged 65 or over drove on their reference day each year (146–163 women), against roughly 2,750–2,950
aged 30–64. The data holders publish an estimate only when it rests on at least 20 sample
observations; a 75 and over cell by sex would meet that only when years are pooled.
