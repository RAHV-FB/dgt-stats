# Refocus audit

An audit of the published site and repository against one question: **does a reader learn something
here that DGT's own tables do not already tell them?** Everything user-facing is placed in one of
four classes — original analytical value, necessary support, reference material, redundant — and
then given a disposition: KEEP, MERGE, DEMOTE (to the repository), or DELETE.

The project had ten pages, forty figures and about sixty tables, built to answer nine questions.
Most of it was competent and none of it was wrong. That is the problem: competence and coverage are
not the same as insight, and a reader who has to cross ten pages to find the three ideas worth
remembering will not find them. This audit cuts the site to the analyses that survive the question
above.

## 1. Findings of the audit, in short

Four analyses answer a question DGT does not answer, and survive being pushed on:

- **Crash severity given an injury crash.** The interesting result is not that head-on collisions
  kill — it is that rain, snow and wet road surfaces are associated with *lower* conditional
  severity, and that junctions are too. That was buried in row 30 of a 50-row coefficient table.
- **Age against driving exposure.** The answer changes sign with the denominator. That is the
  point, and it needed a denominator that is actually kilometres.
- **Vehicle risk per kilometre.** A heavy truck looks ten times a car per vehicle and 2.5 times per
  kilometre, and only 0.18 of its own occupants die per fatal crash it is in, against 0.93 for a
  motorcycle. Nothing in DGT's tables says this, because DGT does not divide the two publications
  by each other.
- **The July 2006 break in monthly deaths.** Worth keeping only if it survives a falsification test
  aimed at the actual alternative explanation, which the old generic placebo was not.

One further thing is worth a reader's time and is not an analysis but a measurement problem:
**the share of drivers with no recorded speed status jumps from 17 % to 52 % in 2016**, which
changes how DGT's own published speed series must be read.

Everything else — long-run trends, hour-by-weekday grids, road-user distributions, province league
tables, the transcribed speed report, the 2019 speed-limit study — is either context for the above
or a republication of DGT's annual report in a different typeface.

## 2. Page-by-page classification

| Section | Class | Disposition | Why |
|---|---|---|---|
| **Home** — four headline tiles | support | KEEP, shortened | Orients the reader in one screen. |
| **Home** — "Where to start", three featured analyses | support | MERGE into one findings list | Two competing summaries of the same analyses (the features and "the other six") on one page. |
| **Home** — "The other six analyses" | redundant | DELETE | A second navigation bar written as prose. |
| **Home** — "How to read the numbers" | support | KEEP, one sentence | "Counts are not risks" is said here, on trends, on geography, on older drivers and in the README. Once is enough. |
| **Trends** — 1993–2024 deaths and indexed series | support | MERGE into Context | Two figures of genuine context for everything else; the rest of the page is not. |
| **Trends** — "Injury crashes and victims per year" table | redundant | DEMOTE to CSV | Twelve rows of the figure above it. |
| **Trends** — rates per vehicle and per resident | reference | DELETE | DGT publishes both. The rate that changes an answer is on the vehicles page, per kilometre. |
| **Trends** — deaths by zone table | reference | DEMOTE to CSV | |
| **Trends** — seasonality heatmap | reference | MERGE into Policy | Its only real use is as the backdrop to the July 2006 question; that is where it now sits, rebuilt as a falsification test rather than a picture. |
| **Timing** — hour × weekday crash counts | reference | DELETE | DGT's annual report has this. |
| **Timing** — hour × weekday fatal share | original, weak | DELETE | The page itself admits the top cells are not resolvable and that the cause is unobservable. A finding that cannot be interpreted is not a finding. |
| **Timing** — road type × hour band | reference | DELETE | Subsumed by the severity model, which estimates the same thing with everything else held constant. |
| **Timing** — darkness by zone | support | MERGE into Context, one sentence | Real, small, and already a term in the severity model. |
| **Road users** — deaths by road-user type, shares by zone | support | MERGE into Context, one figure | Needed to know who the deaths are; does not need a page. |
| **Road users** — driver deaths by vehicle since 1993 | reference | MERGE into Context as one line | The motorcycle series is the only surprise and it is one sentence. |
| **Road users** — pedestrian series | reference | DELETE | |
| **Geography** — province ranking, 52 rows, two denominators | reference | DELETE | A map of deaths per resident is the canonical example of a table that looks analytical and is not: the page's own text says the ranking is driven by through-traffic on rural motorways and that the intervals overlap. It reaches no conclusion, and the CSV stays in the repository. |
| **Geography** — national rates over time | reference | DELETE | Same series as Trends, different denominator. |
| **Older drivers** — four-denominator ladder | original | REBUILD | The idea is right and the denominator was not kilometres. See §3. |
| **Older drivers** — licence-holding by sex and age | support | MERGE into two sentences | It explains why the per-resident rate is misleading; the seven-row table said it no better than a sentence with the two numbers that matter, and its bands did not match the rest of the page. |
| **Older drivers** — "What the travel-weighted estimate is, and is not" | support | DELETE with the estimate | A 400-word disclaimer is a sign the measure should not have been published. |
| **Older drivers** — rates by band over time, per licence holder | reference | DEMOTE to CSV | |
| **Older drivers** — all road users by age since 2002 | reference | DELETE | DGT's own thematic report on older road users publishes this. |
| **Severity** — the two models, odds-ratio forests | original | KEEP, lead with the counterintuitive result | |
| **Severity** — full coefficient tables, 50 rows × 2 | reference | DEMOTE to CSV + appendix | Shown as two complete tables *and* two forest plots *and* narrated. |
| **Severity** — predicted-probability profiles | support | KEEP, trimmed to four rows | The only place the model becomes concrete. |
| **Severity** — year effects table | support | MERGE into one sentence | Its message is "the serious model's year terms track how injuries were coded", which is a sentence. |
| **Severity** — holdout and calibration | support | KEEP as three numbers, figure DEMOTED | A reader needs to know it validates; the decile plot belongs in the appendix. |
| **Severity** — year-by-year stability figure and paragraph | support | KEEP, compressed | The 2024 road-type coding break is a real caveat. |
| **Severity** — "How the codes were grouped", 120 rows | reference | DEMOTE to repository | Reproducibility material on a public page. |
| **Vehicles** — per-vehicle vs per-kilometre | original | KEEP, lead with it | |
| **Vehicles** — three-rate table by type | support | KEEP, one table | |
| **Vehicles** — who dies in the crash | original | KEEP | The 0.18-vs-0.93 contrast is the second half of the finding. |
| **Vehicles** — fleet and kilometres by type | reference | DEMOTE to CSV | |
| **Vehicles** — units involved 2020–2024 | reference | DEMOTE to CSV | |
| **Vehicles** — occupant deaths since 1993 | reference | DELETE | Yearbook series, republished. |
| **Vehicles** — van/light-truck split table | support | MERGE into the limits paragraph | |
| **Vehicles** — 22-type mapping table | reference | DEMOTE to repository | |
| **Policy** — 2006 points licence | original | REBUILD | See §4. |
| **Policy** — 2019 speed limit | redundant | DEMOTE to a paragraph | See §5. |
| **Policy** — "What an interrupted series can and cannot show" | support | KEEP, two sentences | |
| **Policy** — confounder table | support | KEEP | Short, and it is the honest part of the page. |
| **Speed** — recording discontinuity | original | KEEP, make it the page | |
| **Speed** — driver tables 6.1 by year | support | KEEP, one table | |
| **Speed** — speed status by vehicle | reference | DEMOTE to CSV | |
| **Speed** — infraction ranking | reference | DELETE | |
| **Speed** — report tables by road type, limit, transport, age, licence, day × hour | reference | DELETE from the site | Six tables and two figures transcribing DGT's thematic report. The transcription stays in the repository, where it is a reproducibility asset; on the site it is someone else's report. |
| **Data** — sources | support | KEEP, compressed | |
| **Data** — reuse and licensing, ~300 words | reference | DEMOTE to repository | Data-governance detail on a public page. One paragraph and a link is enough. |
| **Data** — definitions | support | KEEP | |
| **Data** — reconciliation check table | support | KEEP as a total plus a link | 434 checks is the number that matters; the twelve-row breakdown is repository material. |
| **Data** — missingness figure and coding breaks | original, small | KEEP | The 2024 Barcelona recoding is a real trap for anyone using these files. |
| **Data** — reproduce steps | support | MERGE into README | Duplicated verbatim from the README. |
| **README** — nine-question table | redundant | DELETE | The site's navigation, restated. |
| **README** — "Standards, as applied", 6 bullets × 5 lines | reference | DEMOTE to methodology | |
| **README** — data group table, project structure, module roles | reference | DEMOTE to docs | |
| **README** — "How it was built" AI-tooling sentence | — | REWRITE | See §6. |

Net effect, as built: **ten pages become seven** (four analyses, context, data, overview),
**forty figures become eleven**, and the tables printed on the site fall from about sixty to
**eleven** — with every full result table one click away as a CSV download from the page that uses
it. The site's HTML drops from 190 KB to 74 KB. The repository loses eight planning documents that
described the structure being replaced; `refocus_audit.md`, `methodology.md`, `data_sources.md` and
`data_inventory.md` are what remain.

## 3. Older drivers: what was wrong and what replaces it

The published denominator, "travel-weighted drivers", was an ESRA national driving share spread
across ages by MOVILIA 2006 car-trip counts and capped at the licence share. It combined a survey
whose Spanish sample stops at 74 with a travel profile that counts passengers as drivers and whose
top band is 65+, then applied a 2006 profile to 2014–2024. The page carried a 400-word explanation
of why the number it had just printed should not be trusted, and gave 65–74 and 75+ the same
assumed travel intensity, which makes the comparison between them meaningless.

DGT publishes what was needed and the project had not found it. The 2024 release of *Kilómetros
anualizados recorridos por el parque móvil* includes `KM_Edad_Propietario.xlsx`: registered
vehicles, total annual kilometres and mean annual kilometres **by vehicle category and by the
owner's age band** (18–20, 21–24, then five-year bands to 70–74, then 75+, plus vehicles registered
to companies). For cars in 2024 that is 23.8 million vehicles and 293 billion kilometres, and it
reconciles with DGT's published fleet total to within 0.1 %.

That gives a denominator with the properties the old one lacked: it is kilometres, it is national,
it is the same year as the crash counts, it has a 75+ band, and — the point the previous version
missed — **the same construction applies to the middle-aged baseline as to the older group**.
Pairing it with the car rows of DGT's driver tables 4.1.1 and 4.2 separates the two questions that
the denominator ladder conflated:

1. how often a car driver of each age is *involved* in an injury crash per kilometre driven;
2. how often an involved driver of each age is *killed*.

Their product is deaths per kilometre. The residents and licence-holder rungs stay, in one table,
as the contrast that shows why the answer moves.

The measure's own limit is stated once and is real: it is the *owner's* age, not the driver's, and
vehicles registered to companies (2.2 million cars, 40 billion kilometres) have no age at all and
leave the denominator. Both push the same way, and the page says so.

## 4. Policy, 2006: what the old test did not test

The old placebo distribution moved the break to 38 arbitrary months between January 2002 and
February 2005 and reported that July 2006 ranked first. That answers "is a 12 % drop large for this
series?" It does not answer the question a sceptic actually asks: **Spanish road deaths peak in
July and August every year; is the June→July→August→September movement of 2006 unusual compared
with the same calendar transition in other years?** Placing a break in, say, March 2003 cannot
speak to that, and the page's own admission that all twelve 2004 placebos came out negative shows
the distribution was contaminated by trend rather than by season.

The rebuild replaces it with four tests aimed at the seasonal alternative, plus two real monthly
exposure series (`docs/methodology.md` §7). **The headline did not survive them**, and the page now
says so:

- The pre-2006 months, asked on their own, reject a single straight trend in favour of one with a
  kink in 2003 by about 16 points of AIC. Under the trend they prefer, the July 2006 level change
  is **−7.1 % (−13.2 to −0.5)**, not −12.0 %.
- Placed at 1 July of every year with a clean window, the same model ranks 2006 **first of
  fifteen** — but the runner-up (July 2004) is close, so the one-sided empirical p-value is about
  0.07.
- The twelve months from July 2006 divided by the twelve before — a statistic in which seasonality
  cancels exactly — fall 11.4 %, the **fourth largest** of the 27 measurable years.
- A forecast fitted before each July and run forward 17 months puts 2006 **fourth of fifteen**:
  three other Julys undershot their own forecast by more. This is the test that most damages the
  original claim.
- Adding CORES road-fuel consumption or toll-motorway vehicle-kilometres as a covariate moves the
  estimate by less than a percentage point, so a fall in traffic is not the explanation.

Four of the thirteen specifications now give an interval that includes zero. The page reports
about seven per cent with a wide interval, says which tests it failed, and keeps the two claims —
that the series changed, and that the licence changed it — apart.

## 5. Policy, 2019: Option B

The brief offered a choice: improve the design or demote it. Improving it needs road-section
identifiers, section speed limits, measured speeds and traffic volumes, and a set of untreated
sections. The DGT microdata carry a road-type code and a kilometre post on a non-inventoried road
name; there is no section identifier, no limit, no volume and no speed. The Ministerio de
Transportes publishes traffic volumes on the state network by counting station, but the crash file
cannot be joined to a station, and the roads the decree changed are mostly not on the state
network. Nothing available closes that gap, and the current aggregate design already fails its own
placebo: a false break in January 2017 produces a divergence of +12 % with an interval that
excludes zero.

So: demoted to a paragraph under "what we could not establish". An elaborate section reporting that
the answer is inconclusive is not analytical value; it is analytical throat-clearing.

## 6. Public site versus repository

The rule applied throughout: the site answers *what was asked, what was found, why it matters, how
confident to be, and what the main limitation is*. Everything else — the full methodology, the
source register with URLs and checksums, the reuse terms, the 434 reconciliation checks one by one,
the coding-break inventory, every coefficient, every sensitivity fit, the code-grouping tables —
lives in `docs/` and `reports/` and is linked, not printed.

The AI-assistance note is rewritten. The old wording ("the code and the prose were written with the
help of AI coding assistants") both overstates the tools' role in the decisions and understates the
author's responsibility for them. The replacement describes the development method once, in the
README and on the data page, and does not make the tooling a feature of the landing page.

## 7. Writing standards applied

Every page now opens with its answer. Limitations are stated once, where the result is. The
generic reminders that were repeated on four pages — counts are not risks, unknown is not no,
association is not causation — appear once each, in the place where they change how a number should
be read. Prose that narrated the cells of a table has gone with the table.
