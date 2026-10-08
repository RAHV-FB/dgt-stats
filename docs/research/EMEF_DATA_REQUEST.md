# Request for EMEF car-driving tables by finer age group

**Status: prepared, not sent.** No data have been requested or received. Nothing in this
repository uses EMEF information on ages finer than 65 and over, and nothing will until the data
holders reply and the reply is filed under `data/raw/` with its terms of use.

## Why the request is needed

The public EMEF files publish age only as 16–29, 30–64 and 65 and over (2014–2018) or 16–29,
30–44, 45–64 and 65 and over (2019–2024) ([`EMEF_INVENTORY.md`](EMEF_INVENTORY.md)). Drivers aged
75 and over are the group whose crash risk per kilometre is most disputed, and the 65 and over
group mixes them with drivers aged 65–74, who drive more and probably differently. Without a
split, a 75 and over rate per kilometre can be obtained only by borrowing the age profile of
another survey, which is a modelling assumption rather than a measurement.

The split exists in the data holders' records. From 2008 to 2016, 65–74 and 75 and over were
separate sampling strata (methodology report 2003–2018, Table 5). The strata were merged from
2017, and the questionnaire filters on exact age (retired respondents under 75 are asked about
paid work), so the confidential files hold exact age for every year.

## Two routes

1. **A tabulation produced by the data holders (preferred).** The Institut Metròpoli's data
   access page (<https://www.institutmetropoli.cat/ca/acces-solicitud-dades-fitxers/>, read on
   8 October 2026) asks anyone who cannot find what they need in the public files to write to
   `cessio.dades@institutmetropoli.cat` with a short presentation and the reason for the request.
   A table of weighted totals and sample counts identifies no one, and the data holders can apply
   their own publication rule: a cell is published only if it rests on at least 20 sample
   observations and at least 60% of the table's cells are valid. The ATM, which owns the survey,
   gives `atm@atm.cat` as its contact.
2. **Confidential microdata for scientific purposes.** Open only to researchers at centres
   recognised by Idescat or Eurostat (or after applying for recognition). It requires the
   application form, a description of the project, physical and procedural safeguards, signed
   confidentiality undertakings by every researcher, acceptance of the cost of preparing the data,
   and destruction of the data at the end of the agreed period; any further use needs a new
   application. This route is heavier, and the project does not need record-level data: route 1
   asks for everything the exposure estimate uses.

## What to ask for

One table per survey year, ideally 2014–2024 (2017–2024 at minimum, 2022–2024 as the priority),
with these dimensions:

* **Age group:** 16–29, 30–44, 45–64, 65–69, 70–74, 75–79, 80–84, 85 and over. If the five-year
  groups above 65 fail the 20-observation rule, 65–74, 75–84 and 85 and over; if that fails,
  65–74 and 75 and over.
* **Sex:** men, women and both.
* **Area of residence:** the whole survey area, and the RMB (residence zones 1–4), the area
  common to every year.

For every cell:

| Field | Definition |
|---|---|
| `respondents_sample` | respondents in the cell, unweighted |
| `population_weighted` | sum of `PESAIX` over those respondents |
| `drivers_sample` | respondents who made at least one trip with a stage as car driver (code 12) on the reference day, unweighted |
| `drivers_weighted` | the same, weighted by `PESAIX` |
| `car_driver_trips_weighted` | car-driver trips, weighted |
| `car_driver_km_weighted` | the distance of those trips, weighted, in km; road distance if available (as in the 2021 distance report), otherwise straight-line distance from coordinates, stating which |
| `car_driver_km_se` | the standard error of `car_driver_km_weighted` under the survey design, or the replicate weights or design strata and units from which it can be computed |
| `habitual_drivers_weighted` | residents who drive a car at least once a month, weighted (from the frequency question; 2016 also the licence question) |

Each answer should state the population base (residents aged 16 and over), that the reference day
is a working day, how multimodal trips were treated, and any cell the data holders suppressed.

## How a reply would be used

The reply would be filed as `data/raw/emef/requested/emef_age_tables_<years>.csv` (one row per
year, area, age group and sex, with the fields above), registered in `data/raw/manifest.csv` with
its date and terms of use, and read by a new function in `src/dgt_stats/emef/`. It would replace
the model-dependent split of the 65 and over group described in
[`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md), and the published 65 and over totals of the
public files would serve as a check: the age groups of a reply must add up to them.

## Draft message

The repository owner would send the message from their own address, filling in the bracketed
fields. A Catalan version is given first, as the institute's working language, followed by an
English one.

> **Assumpte:** Sol·licitud de taules agregades de l'EMEF per grups d'edat (conducció de turismes)
>
> Benvolgudes, benvolguts,
>
> Em dirigeixo a vosaltres en relació amb l'Enquesta de mobilitat en dia feiner (EMEF). Faig
> servir els fitxers de microdades d'ús públic de 2014 a 2024 en un projecte obert d'anàlisi de
> la sinistralitat viària per edat del conductor, en què es calcula la implicació en accidents per
> quilòmetre conduït [nom, afiliació i enllaç al projecte].
>
> Els fitxers públics agrupen l'edat en 65 anys i més, i per a la nostra anàlisi és essencial
> separar les persones de 65 a 74 anys de les de 75 anys i més. Us voldria demanar, si és
> possible, una taula agregada (no microdades) per a cada any 2014–2024, o com a mínim 2022–2024,
> amb els grups d'edat 16–29, 30–44, 45–64, 65–69, 70–74, 75–79, 80–84 i 85 i més (o els que
> permeti el vostre criteri de publicació de 20 observacions mostrals), per sexe i per àmbit de
> residència (conjunt de l'àmbit i RMB), amb: el nombre de persones de la mostra, la població
> ponderada, les persones que han conduït un turisme el dia de referència (mostra i ponderades),
> els desplaçaments com a conductor de turisme i els quilòmetres corresponents (ponderats, i
> indicant si la distància és per carretera o en línia recta), l'error estàndard d'aquests
> quilòmetres i la població que condueix habitualment.
>
> Acceptem qualsevol supressió de cel·les que apliqueu i citarem la font tal com indiqueu. Si
> aquesta petició requereix seguir el procediment d'accés a dades confidencials, us agrairia que
> m'indiquéssiu els passos i el cost aproximat.
>
> Moltes gràcies per la vostra atenció.
>
> [Nom]

> **Subject:** Request for aggregate EMEF tables by age group (car driving)
>
> Dear colleagues,
>
> I am writing about the working-day mobility survey (EMEF). I use the public-use microdata for
> 2014–2024 in an open project on road crash involvement per kilometre driven by driver age
> [name, affiliation and link to the project].
>
> The public files group age as 65 and over, and the analysis needs to separate people aged 65–74
> from those aged 75 and over. Could you provide, if possible, an aggregate table (not microdata)
> for each year 2014–2024, or at least 2022–2024, by age group (16–29, 30–44, 45–64, 65–69, 70–74,
> 75–79, 80–84 and 85 and over, or whatever your 20-observation publication rule allows), sex and
> area of residence (the whole survey area and the RMB), giving: respondents in the sample, the
> weighted population, people who drove a car on the reference day (sample and weighted), trips
> as a car driver and their kilometres (weighted, stating whether distance is by road or straight
> line), the standard error of those kilometres, and the population who drive habitually?
>
> Any cell suppression you apply is acceptable, and the source will be cited as you indicate. If
> the request must go through the confidential-data procedure, I would be grateful to know the
> steps and the approximate cost.
>
> With thanks,
>
> [Name]

## Other sources examined for ages above 65

| Source | Finer than 65+? | Use here |
|---|---|---|
| EMEF publications and annual reports (2014–2016 STI reports, 2024 results and publication, the 2013–2023 trend report) | No; every table stops at 65 and over | none |
| EMEF confidential files | Yes (exact age) | the request above |
| Madrid household travel survey, EDM 2018 (Consorcio Regional de Transportes de Madrid; public microdata with exact age, licence, weekday and trip distance) | Yes | the age profile of driving within the 65 and over group, as a labelled model-dependent split ([`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md)) |
| MOVILIA 2006–2007 (Ministry of Transport; national, `data/raw/transportes/`) | Published tables only; no driver status by age and sex | too old and too coarse for the split |
| DGT kilometres by owner age, 2024 | Yes, but by registered owner, not by driver | sensitivity only |
