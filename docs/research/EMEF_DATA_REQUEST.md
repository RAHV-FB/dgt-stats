# Request for EMEF car-driving tables by finer age group

**Status: prepared, not sent.** No data have been requested or received. One piece of EMEF
information on ages within 65 and over is used, from the public files, and only as aggregates
under the survey's 20-observation rule: the routing of question P1b, which identifies retirees
aged 75 and over, sets one sensitivity bound (the share of people aged 75 and over in the 65+
sample, `emef.older_routing`, `emef_routing_older.csv`) and an exploratory validation of the
Madrid split documented in [`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md). The request asks
the data holders to confirm that reading. Nothing else will use finer ages until the holders reply
and the reply is filed under `data/raw/` with its terms of use.

## Why the request is needed

The public EMEF files publish age only as 16–29, 30–64 and 65 and over (2014–2018) or 16–29,
30–44, 45–64 and 65 and over (2019–2024) ([`EMEF_INVENTORY.md`](EMEF_INVENTORY.md)). Drivers aged
75 and over are the group whose crash risk per kilometre is most disputed, and the 65 and over
group mixes them with drivers aged 65–74, who drive more and probably differently. Without a
split, the figure per kilometre at 75 and over is a conditional estimate: it assumes that people
aged 75 and over drive as much less than those aged 65–74 as in Madrid in 2018 (EDM2018), and its
sampling error comes mostly from that survey. Three other splits widen the sensitivity range to
0.97–3.28 times the 45–64 rate.

The split exists in the data holders' records. From 2008 to 2016, 65–74 and 75 and over were
separate sampling strata (methodology report 2003–2018, Table 5). The strata were merged from
2017, and the questionnaire filters on exact age (retired respondents under 75 are asked about
paid work: filter "P1a=3 i edat<75"), so the confidential files hold exact age for every year.

The public files show the routing. In 2014 the weighted share of 65+ respondents it identifies
as retirees aged 75 and over matches the population share (men 0.46 against 0.45, women 0.55
against 0.54), and in 2016 it roughly does; in those years an exploratory calculation gives a
75+/65–74 ratio of car-driver km per resident of about 0.25, close to Madrid's 0.30. From 2017
the share falls well below the population's (2022–2024: men 0.38 against 0.47, women 0.35
against 0.53), either because the routing or coding changed or because the 65+ sample holds too
few people aged 75 and over. The second reading is now a bound inside the sensitivity range (up to
+11% at 75 and over). Both findings make the request more useful: the holders can say which
reading is right and give the measured split.

A second question concerns the weights of the 65 and over group. The weighted share of residents
aged 65 and over who are employed was 4.3–4.4% in 2019–2021, the same as the census share for
Catalonia on 1 January 2024 (4.3%), but 6.0–8.3% in 2022–2024 (`emef_employment_benchmark.csv`).
Employed older residents drive more on working days, so an excess of them raises the 65 and over
kilometres; reweighting the group to the census share raises the national 65 and over ratio of
involvement per kilometre from 1.19 to 1.23
([`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md)). The 2024 technical sheet says that the
weights are calibrated to the census of 1 January 2025, by place of birth since 2023, but not which
margins are used, nor whether 65–74 and 75 and over are calibrated separately. If they are not,
the weighted 65 and over group could hold too many of the younger and more active old.

## Two routes

1. **A tabulation produced by the data holders (preferred).** The Institut Metròpoli's data
   access page (<https://www.institutmetropoli.cat/ca/acces-solicitud-dades-fitxers/>, read on
   8 October 2026) asks anyone who cannot find what they need in the public files to write to
   `cessio.dades@institutmetropoli.cat` with a short presentation and the purpose of the request;
   fees up to the cost of preparing the tables may apply. A table of weighted totals and sample
   counts identifies no one, and the data holders can apply their own publication rule: a cell is
   published only if it rests on at least 20 sample observations and at least 60% of the table's
   cells are valid. The ATM, which owns the survey, gives `atm@atm.cat` as its contact and should be
   copied.
2. **Confidential microdata for scientific purposes.** Administered by the ATM, not Idescat, for
   research entities recognised by Eurostat or by the ATM. It requires the application forms, a
   description of the project, signed confidentiality undertakings by every researcher,
   acceptance of the cost of preparing the data, delivery by VSFTP, and a declaration that the data
   were destroyed at the end of the agreed period; any further use needs a new application. This
   route is heavier, and the project does not need record-level data: route 1 asks for everything
   the exposure estimate uses.

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

**Weights and calibration.** For each survey year, ideally 2019–2024 and at minimum 2022–2024:

| Item | Definition |
|---|---|
| `calibration_margins` | the variables and population totals to which `PESAIX` is calibrated (for example age group by sex by area, place of birth), and the census or register date of those totals |
| `weights_65_74`, `weights_75_plus` | the sum of `PESAIX` over respondents aged 65–74 and over those aged 75 and over, by sex, with the census or register population of the same groups |
| `employed_65_plus` | the sum of `PESAIX` over employed respondents aged 65–74 and aged 75 and over, if the margins do not include employment |
| `design_variables` | the strata and primary sampling units, or replicate weights, from which design-based standard errors can be computed |

These items identify no one; they describe the weights, not the respondents.

**Ages within 65 and over, for the split at 75.** These are the items that would replace the
Madrid transfer, in order of priority:

| Item | Definition |
|---|---|
| `older_km_pooled` | for 65–74, 75–84 and 85 and over (fallback: 65–74 and 75 and over), by sex, pooled over 2014–2016 and over 2022–2024: car-driver km per resident, car-driver trips, respondents and drivers (sample and weighted), licence holders (where asked), and design-based standard errors |
| `routing_by_true_age` | for every year 2014–2024, respondents aged 65 and over by true age group (65–74, 75 and over) and P1b routing status (asked, not asked), sample and weighted, by sex |
| `calibration_75` | for every year, whether 75 and over was a separate calibration cell, with the weighted and census totals by sex |
| `status_coding_65` | whether the 2020–2024 situation variables (V01D1, V01A) fold "home duties" and "other" at 65 and over into code 3 (retired or pensioner) |
| `distances_2014_2020` | geocoded straight-line distances of car-driver trips for 2014–2020, or the same km tables computed from them |

## How a reply would be used

The reply would be filed as `data/raw/emef/requested/emef_age_tables_<years>.csv` (one row per
year, area, age group and sex, with the fields above), registered in `data/raw/manifest.csv` with
its date and terms of use, and read by a new function in `src/dgt_stats/emef/`. It would replace
the Madrid transfer, the central condition of the conditional estimate for 75 and over described
in [`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md), and the largest part of its sampling error,
with the profile region's own measurement; the routing table would settle the composition bound;
and the published 65 and over totals of the public files would serve as a check: the age groups
of a reply must add up to them. The
calibration margins and the weighted totals at 65–74 and 75 and over would show whether the 65 and
over group's weights reproduce the population of each part of it; if they do not, the group would
be reweighted to the census before any kilometre estimate. The design variables would replace the
bootstrap within year and comarca, which ignores clustering and calibration.

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
> També us agrairia, per a cada any (com a mínim 2022–2024), els marges de calibratge de les
> ponderacions (les variables i els totals de població utilitzats, i si el grup de 75 anys i més és
> una cel·la de calibratge pròpia) i la suma de les ponderacions (PESAIX) de les persones de 65 a 74
> anys i de 75 anys i més, per sexe, juntament amb la població de referència corresponent. Si és
> possible, també els estrats i les unitats primàries de mostreig, o pesos rèplica, per calcular
> els errors estàndard segons el disseny.
>
> Per als grups de 65 a 74, de 75 a 84 i de 85 anys i més (o, si cal, de 65 a 74 i de 75 anys i
> més), per sexe i agregant 2014–2016 i 2022–2024, us demanaria els quilòmetres com a conductor de
> turisme per resident amb el seu error estàndard. També, per a cada any 2014–2024, la taula de les
> persones de 65 anys i més per grup d'edat real i per si se'ls va fer la pregunta P1b (filtre
> «P1a=3 i edat<75»), que fem servir de manera agregada per estimar quina part de la mostra de 65
> anys i més té 75 anys o més; us agrairia que ens confirméssiu si aquesta lectura és correcta i si
> des de 2020 les situacions «tasques de la llar» i «altres» a 65 anys i més es codifiquen com a
> jubilació (codi 3). Si fos possible, també les distàncies en línia recta geocodificades dels
> desplaçaments de 2014–2020.
>
> Acceptem qualsevol supressió de cel·les que apliqueu i citarem la font tal com indiqueu. Si
> l'elaboració de les taules té un cost, us agrairia que me l'indiquéssiu. Si aquesta petició
> requereix seguir el procediment d'accés a dades confidencials que administra l'ATM, us agrairia
> que m'indiquéssiu els passos.
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
> I would also be grateful, for each year (at least 2022–2024), for the calibration margins of the
> weights (the variables and population totals used, and whether people aged 75 and over form a
> calibration cell of their own) and the sum of the weights (PESAIX) of people aged 65–74 and of
> those aged 75 and over, by sex, with the corresponding reference population. If possible, the
> strata and primary sampling units, or replicate weights, would allow design-based standard
> errors.
>
> For 65–74, 75–84 and 85 and over (or, if needed, 65–74 and 75 and over), by sex and pooled over
> 2014–2016 and 2022–2024, I would ask for car-driver kilometres per resident with their standard
> errors. And, for each year 2014–2024, the table of respondents aged 65 and over by true age group
> and by whether they were asked question P1b (filter "P1a=3 i edat<75"), which we use in aggregate
> to estimate how much of the 65 and over sample is aged 75 and over; could you confirm that
> reading, and whether from 2020 "home duties" and "other" at 65 and over are coded as retired
> (code 3)? If possible, also the geocoded straight-line distances of the 2014–2020 trips.
>
> Any cell suppression you apply is acceptable, and the source will be cited as you indicate. If
> preparing the tables has a cost, I would be grateful to know it. If the request must go through
> the confidential-data procedure administered by the ATM, I would be grateful to know the steps.
>
> With thanks,
>
> [Name]

## Other sources examined for ages above 65

| Source | Finer than 65+? | Use here |
|---|---|---|
| EMEF publications and annual reports (2014–2016 STI reports, 2024 results and publication, the 2013–2023 trend report) | No; every table stops at 65 and over | none |
| EMEF confidential files | Yes (exact age) | the request above |
| Madrid household travel survey, EDM 2018 (Consorcio Regional de Transportes de Madrid; public microdata with exact age, licence, weekday and straight-line trip distance) | Yes | the split of the conditional estimate at 75 and over, and the like-for-like check of men's driving per licence holder ([`DRIVER_AGE_EXPOSURE.md`](DRIVER_AGE_EXPOSURE.md)) |
| CRTM Encuesta Sintética de Movilidad 2024 (8,200 respondents, Comunidad de Madrid) | No: ages 14–80 only, one 65–80 band, driver and passenger merged, no km tables and no microdata on datos.crtm.es (checked 8 October 2026) | context only: older private-vehicle trips relative to 46–64 about as in 2018 |
| Fundació RACC, *Mayores al volante* (2013; 3,003 licence holders aged 65+, Spain) | Yes, 65–69, 70–74, 75+, but days, not km, and frequency not by sex | the men's limit of the RACC split (quoted, not archived) |
| EMQ 2006 (Catalonia) via Fundació RACC/CED 2011 | Five-year bands, driving frequency only | validation; microdata on request through the Generalitat |
| MOVILIA 2006–2007 (Ministry of Transport; national, `data/raw/transportes/`) | Published tables only; no driver status by age and sex | too old and too coarse for the split; MOVILIA 2006 table 64 (car or motorcycle trips on weekend and working days, by age) gives one weekend age mix in a sensitivity analysis |
| DGT kilometres by owner age, 2024 | Yes, but by registered owner, not by driver | the former owner-age figure, kept as a comparison; no longer used to split the 65 and over kilometres, because owner kilometres credit too much driving to older owners |
