# Adversarial review, at e593b6b

Independent agents attacked the study at commit `e593b6b`. Twenty each tried to disprove one major
published finding. Seven each examined one dimension across the whole study: data leakage, biases,
uncertainty, model assumptions, statistical significance and multiplicity, reproducibility, and
data integrity. They recomputed the numbers with their own code, from the raw files or, where parsing them was impractical, the built data layers, and took no study document's
statement as evidence.

Every issue they raised went to a separate verifier (seven that only repeated an issue already sent were matched to it), who tried to refute it and confirmed only what
it reproduced. Each issue confirmed as critical or major went to a second checker, who redid it from
scratch. A completeness critic then compared the attack with every published page, and
two further attackers took the two gaps it ranked highest. The whole pipeline was rebuilt from `data/raw` in
a clean checkout. The review was done on 5 November 2026.

The issue register, one row per issue raised with the verifier's reproduction and verdict, is
[`ADVERSARIAL_REVIEW_e593b6b.csv`](ADVERSARIAL_REVIEW_e593b6b.csv).

## Summary

**No published number was found to be miscomputed.** Every attacker reproduced its finding's
numbers, nearly all of them, mostly from the raw files and most of them exactly. The clean rebuild reproduced every page of the
site byte for byte. What the attack established is about what the numbers are said to show.

- **One critical issue (C1).** Catalonia's road-type figures describe a change in how the source
  file codes road type, not the roads. 'Most fatal crashes were on conventional roads: 1,981 of the
  3,093' is not supported. About half were, and motorways, put at 224 crashes, had three to five and a half
  times as many.
- **Five major issues, each confirmed twice** (seven rows of the register, which lists M5 under
  each of the three statements it affects).
  - (M1) The home page's 2.68 for young drivers per km carries only a ±7% sampling interval. The
    last substantive commit (`268caf2`) removed the study's own 1.49–3.63 sensitivity range from the home page, the
    drivers page, its figure and the tool.
  - (M2) The driver risk comparison opens on the 75+ per-km figure and states it as established,
    though the drivers page says the data do not establish it.
  - (M3) The national location odds ratios (6.63; 8.75 'largest') are inflated by an
    outcome-dependent recording level in DGT's Catalan records.
  - (M4) 'An immediate fall of about 7% that did not last' after the 2006 points licence rests on
    one of several pre-trends the data cannot tell apart. Under an equally simple one that fits
    better, the fall lasts.
  - (M5) The data page treats DGT's 2022–2024 kilometre estimates as one series. DGT itself says
    it changed method for 2024, so the site's 'the other source of kilometres points the other way'
    has no valid support. An earlier version of the site said the figures could not be joined; an
    internal audit removed that caveat, and a test now forbids it.
- **33 moderate and 93 minor issues.** They are mostly missing qualifications:
  - confounded crude comparisons;
  - borderline significance read as firm;
  - low-power nulls read as near-equivalence;
  - denominators that do not measure what a rate implies;
  - a few figures from a single peak year;
  - stale documentation and loose numerical tolerances.
- **12 issues an attacker raised were refuted by verification**, two could not be settled with
  the data available, and 27 were duplicates of others.

Of the twenty findings, none survives every attack. Eight survive with caveats, seven are
weakened, four are overstated, and one, Catalonia's road types, is refuted in part. The
direction of every home-page finding survives:

- deaths fell about three quarters and have not fallen since;
- young drivers are involved more per km under every assumption tested;
- drivers aged 75 and over die about three times as often once involved;
- crashes with recorded speed are deadlier on every road type, clearly on three;
- in Catalonia, a heavy vehicle doubles the fatal share of a severe crash.

What weakens is the precision and generality the pages attach to them.

## How the review was done

**Attack.** Twenty-seven agents worked independently, each in its own folder, with read-only
access to the repository at `e593b6b`. None saw another's work. Twenty each took one published
finding and were told to disprove it. Seven each took one methodological dimension across the
whole study: data leakage, selection and measurement biases, uncertainty, model assumptions,
statistical significance and multiplicity, reproducibility, and data integrity. Every attacker
was told to:

- recompute the numbers with its own code from `data/raw`, or from the built layers where parsing
  the raw files was impractical;
- treat the earlier internal audits as claims to test;
- report the attacks that failed as well as those that succeeded;
- say whether each weakness is disclosed, and where.

Between them they raised 162 issues; the two gap attackers (below) raised 13 more. A container
restart interrupted eight attackers. They were run again from the start and were told where their
predecessors' unverified partial work lay.

**Verification.** No issue is reported here on an attacker's word. Duplicates raised by several
attackers were grouped, and each group of related issues went to a verifier who had not seen the
attacker's overall verdict. The verifier was told that attackers over-claim, and was asked to:

- refute each issue where the defence is sound;
- confirm only what it reproduced itself;
- check whether the site discloses the problem where a reader of the claim would see it;
- assign its own severity.

Every issue a verifier confirmed as critical or major then went to a second, independent checker
who saw only the attacker's claim. That checker recomputed the key quantities from scratch. Where
both confirm, the lower of the two severities is used.

**Gaps.** A completeness critic compared the attack with every published page and listed the
claims it had not examined. The highest-priority gaps went to new attackers, and their issues to
verifiers, in the same way.

**Rebuild.** The README's Reproduce sequence was run in full in a clean checkout of `e593b6b`, with
Python 3.11 and the locked, hashed dependencies, on one BLAS thread. Then `pytest` ran, then the
withdrawn step, and the result was compared with the committed files. The CI-equivalent build of
the data layers was also run in the main checkout.

**Scales.** An issue's severity:

| Severity | Meaning |
|---|---|
| critical | the published statement is false: a number wrong beyond rounding, or a conclusion reversed or not supported by the data |
| major | materially overstated, uncertainty materially understated, or a failed assumption that could change the conclusion, and not adequately disclosed |
| moderate | a real weakness that qualifies but does not overturn the finding, or one disclosed only in part or away from the claim |
| minor | a small numerical, wording or documentation problem |

The scale corresponds roughly to the P0, P1 and P2 of the earlier reviews (critical to P0, major
to P1, moderate and minor to P2).

A finding's verdict:

| Verdict | Meaning |
|---|---|
| refuted | the statement is false as published |
| overstated | the direction holds, but the statement says materially more than the evidence |
| weakened | the finding holds, but an important qualification or uncertainty is missing |
| survives with caveats | the finding holds; its qualifications are minor, or moderate ones that leave its main statement standing |
| survives | every attack failed |

## Verdicts on the published findings

One attacker took each finding. The verdict below is the review's, set after verification: it
rests only on issues a verifier reproduced, and the column on what withstood attack lists checks
the finding passed. Issue severities are in brackets. Duplicates found by other attackers are
folded in.

| # | Finding (page) | Verdict | What the attack established | What withstood attack |
|---|---|---|---|---|
| F1a | Deaths fell about three quarters 1993–2013 and have shown 'no clear rise or fall since' (home, long-run) | survives with caveats | 'No clear rise or fall' is symmetric where the evidence is not. Only a fall faster than about 0.2% a year is excluded, and a rise of 1.2% a year to 2019 is not statistically clear (p = 0.07, about 40% power) (minor). The 30-day count stepped up about 6% in 2016, as the 30-day/24-hour ratio left its 2011–2015 dip (minor). | Every number reproduces from the raw yearbook. On 24-hour deaths the 1993–2013 fall is 73.0%, with the same turning points, so it does not rest on DGT's pre-2011 correction factors. The 10.9% a year is robust: endpoint −11.0%, bootstrap −11.0%. |
| F1b | Deaths per tonne of fuel fell 76%; 2023 and 2024 were 16% and 14% above trend, 'outside its range' (long-run) | weakened | 'Outside its range' assumes the 2011–2019 slope carried on. By the page's own method, ranges set before 2020 missed 14 of 24 outcomes four to five years ahead, and a smooth-trend model puts 2023 and 2024 inside, though a random walk with drift and an OLS fit keep them outside (moderate). The interurban fuel check is outside by 4.9 deaths (minor). | The 76% reproduces. The Ministry's measured interurban kilometres since 1996, in a yearbook table (1.2.13) the analysis does not use, give a fall of 78–81% per km, so 76% is if anything conservative. Every specification tried leaves a point excess, from 1.08 to about 1.4. |
| F16 | Conventional roads 3.45 times the deaths per vehicle-km of motorways (long-run) | survives with caveats | In DGT's Catalan records the road-owner code depends on whether a crash was fatal. Keeping owners 1–3 drops deaths on regional roads whose kilometres stay in the denominator: the rates are 2–3% low, the ratio becomes 3.40, and the '8.7% to 11.2%' of interurban deaths on unmeasured roads is about 6.6–9.1% (moderate). The interval treats the kilometres as exact; 2023 was partly extrapolated (minor). 'Deaths per kilometre of motorways' in the heading reverses if read per km of road (minor). | Every number reproduces. Annual ratios run from 2.91 to 4.23 under every mapping tried, and all round to '3 to 4'. Within each network conventional roads still have 2.6–5.1 times the motorway rate. |
| F2 | 2024 against 2019: deaths within ordinary variation; admissions +13.0% per tonne of fuel, 'beyond it' (trends) | weakened | The page's only 'beyond' is borderline: t = 2.96 on 5 df, not significant after Holm over its 13 rows, and sensitive to the scatter window (moderate). About 80% of the extra admissions are riders of personal mobility vehicles (VMP), whose travel burns no road fuel, and motorcyclists. Without VMP riders and the yearbook's 'Otros' column, which held them before 2020, the change is +8.8% (−2.6% to +21.5%), within ordinary variation; the page never says so. For motor-vehicle occupants, motorcyclists included, the rise per tonne is still beyond it (+10.8%, +0.9% to +21.6%) in three of four constructions (moderate). | All 13 changes and intervals reproduce. 'Deaths within ordinary variation' survives every construction: 24 scatter windows, leave-one-year-out fits, the rate's own dispersion. No change of definition in the admissions series was found (HG30DF/HG24H is 0.972–0.976 every year). |
| F3 | Summer peak; per tonne July and August above the average month; April 2020 deaths −68%, per tonne −24% (seasons) | weakened | The April 2020 '−24% per tonne' has no interval. On 40 deaths it is −48% to +11%, so 'deaths fell more than road fuel sold' is not established (moderate). The per-tonne pattern for February and August depends on the freight in road fuel: per tonne of petrol, February is 0.99 (moderate). February fails a 12-month family-wise correction, and February 2020 has 29 days (minor). | Every number reproduces, and the monthly deaths equal the microdata in all 108 months. The raw summer peak holds in every window, per calendar day and under Bonferroni. Per tonne, July and September above and April–May below hold under every denominator. |
| F4 | 2006 points licence: 'An immediate fall of about 7% that did not last'; it cannot be attributed to the licence (policy) | overstated | 'Did not last' and the −2.5% estimate hold only for pre-trends limited to one continuous bend. Under the page's own QAIC rule a January 2004 level drop fits the pre-period better (473.4 against 476.2) and gives a lasting fall (−11.5%, −14.9% to −8.0%), the top of the range: pre-trends that keep the 2004–2006 slope give a lasting −6% to −7%. Two bends at least a year apart tie and give −9.5%, and window starts in 1995–1997 give about −9%; the pre-trend is not identified (major). The Newey–West(12) intervals undercover; with valid errors neither the step nor the slope change excludes zero (moderate). | Every number reproduces from the raw monthly series. 'Cannot be attributed to the licence' holds and is strengthened: every placebo-calibrated interval for the 17-month change includes zero. Every specification gives some fall at July 2006 (−3.6% to −12.6%), and no fall appears before it. |
| F5a | Car drivers 18–29 involved 2.68 times as often per km as 45–64 (95% sampling interval 2.5–2.9) (home, drivers) | overstated | The 1.49–3.63 sensitivity range was removed from the home page, the drivers page, Figure 1 and the tool by commit `268caf2`; it is 5.7 times as wide as the sampling interval, and 65% of the study's own variants fall outside the printed 2.5–2.9 (major). Both source regions have Spain's lowest young licence holding; the study's own licence calibration, applied to both surveys, gives 2.37 (moderate). The averaged interval is narrower than either survey's (moderate). | 2.68 reproduces from the raw tables and surveys. The direction holds under every alternative, the lowest being 1.49. The road-to-straight-line factor cancels. The survey bootstrap respects the one-person-per-household design. |
| F5b | Drivers 75+ per km 2.43 (2.0–3.0), range 0.97–3.20, 'the data do not establish' a higher rate; 65–74 1.11 (drivers) | overstated (tool and figure) | The driver-risk tool opens on 75+ against 45–64 and states 2.43 'times as often' with only its sampling interval: no condition, no range, no 'do not establish' (major). Figure 1 shows 75+ at 2.0–3.0 without the range, and the heading 'highest among drivers aged 18–29' ranks 18–29 above 75+, an order that reverses on the Madrid profile (moderate). The range probably understates the upside, about 3.4–3.6 (moderate). The 65–74 figure, 1.11 (1.0–1.2), is shown without its 0.67–1.70 range (moderate, part of M1). | The text on the drivers page says the figure rests on Madrid's survey and gives the range, and its conclusion stands. 2.43 and 0.97–3.20 reproduce. |
| F6 | Once in a crash, drivers 75+ died 3.4 times as often as 45–64 (home, drivers) | survives with caveats | 3.4 is printed without its 95% interval, 2.6–4.5 (minor). The crude ratio is partly sex mix: for drivers of the same sex it is about 3.0 (2.3–4.0) (minor). | 15.9, 8.5, 4.6 and 3.43 reproduce from one table universe. The rounding of 3.4 is correct (3.46 is the quotient of two rounded rates). Lowering the ratio to 2.0 would need 42% of 75+ involvements to be missing, and no proxy suggests that. |
| F7 | Men 0.91 times women per km, killed 2.63 times; 1.39 per licence holder; 2.62 once involved 'in every age band' (drivers) | weakened | Every ratio is crude and age distorts it. Once involved it is 2.35 at equal age; per licence holder 1.45, outside the printed 1.38–1.40 (moderate). Per km the 0.91 hides a reversal: men aged 18–29 are involved about 1.3 times as often as women (1.19–1.63 across every profile), so 'which ... comes from their driving further' is false for young drivers (moderate). The per-licence denominator counts any licence class: per car-licence holder the ratio is 1.42, and 1.60 rather than 1.43 at 75+ (minor). The lede's 'men 2.6 times' pools 2022–2024; 2024 alone gives 2.9 (minor). | All four figures reproduce exactly; the intervals are correctly computed; 'in every age band' holds at nominal 95%. |
| F8 | 2022: heavy truck 10.3 times a car in fatal crashes per vehicle, 2.5 times per km; motorcycles 10.1 per km (vehicles) | weakened | 2022 is the peak year. 2023 and 2024 give 1.7–2.0 times per km and 7.9–8.3 per vehicle; pooled 2016–2024, 2.2 (moderate). 'About the same rate per kilometre' for truck occupants hides a pooled gap of about a fifth (minor). | Every number reproduces from the raw tables and kilometre file. The qualitative pattern (frequency for motorcycles, severity for trucks, the ranking depending on the denominator) holds in every year 2020–2024. The 82% logic is right. |
| F9 | Speed-recorded crashes 2.0 times the deaths per crash within road type, 1.2 to 5.9 (home, speed) | survives with caveats | With the study's own t convention the dual-carriageway ratio is 1.22 (0.98–1.52), so 'every interval lies above one' fails for one road type (moderate). Outcome-dependent recording of 1.2–1.7 times would produce every interurban ratio (minor). | Every number reproduces from the raw report and the microdata. Catalonia and the Basque Country are excluded alike on both sides. 'Most of all on urban streets' holds on the ratio and on the absolute excess. The summary interval is conservative for the weighted summary it describes. |
| F10 | Recorded alcohol 5.5% to 8.2% of interurban crashes; recorded speed fell about a quarter (factors) | weakened | Interurban illegal manoeuvres count as 'comparable 2014–2023, +49%' only because the 25% break threshold sits 2% above the series' own 2017 jump (×1.223). At 20% the run splits into 2014–2016 +26% and 2017–2023 −3% (moderate). The 2014 urban baseline sits inside a step in recorded urban crashes, so the size of the urban speed fall is uncertain (moderate). 'As crashes shifted to urban streets' describes mostly a recording step; Table 1's changes are endpoint ratios with no interval (minor). | Every share reproduces from the raw report. The lead's alcohol rise and fall in recorded speed hold in direction: their overdispersed trend intervals exclude zero. Every other comparable run is the same for any threshold from 1.22 to 1.57. |
| F11 | DGT regression: head-on OR 5.48, conventional interurban road 6.63 against urban street, junction 0.69, wet 0.56 (severity) | overstated | In DGT's Catalan records road alignment is filled in almost only when someone died or was admitted within 24 hours, and its 'unknown' level stands in for the outcome. Fitted without that leak, the conventional-road contrast is 4.9–6.2, not 6.63; urban crossing/conventional is 3.8–6.9, not 8.75, and the 'largest location contrast' only when the zone terms come from outside Catalonia (major). Crash-type odds ratios differ by zone: head-on 2.8 on urban streets against 5.6 interurban, so the ranking sentence holds only on interurban roads (moderate). Catalan surface coding depends on severity, so wet is about 0.60, not 0.56 (moderate). The Catalan 2024 'other road' coding moves two rows of Table 1 (moderate). | Every odds ratio reproduces. The Catalan junction inversion is real, and the re-reading is justified. The junction OR (0.685–0.707) and wet below 1 hold in every specification. Crash-type and junction ORs barely move without alignment. |
| F12 | Catalonia 2010–2023: 12.6% of serious crashes fatal; by road type, 'most fatal crashes were on conventional roads' (catalonia) | refuted in part | The road-type field codes motorways and dual carriageways as such almost only in 2013–2015; in the other eleven years their crashes are coded as conventional roads. 'Most fatal crashes were on conventional roads: 1,981 of the 3,093' becomes about 1,460–1,620 (47–52%), at most 1,801. Motorways had about 700–1,250 crashes, not 224, with a fatal share of 22–25%, clearly above conventional roads (about 18%), so 'overlaps that of conventional roads' reverses (critical). | 24,478, 3,093, 12.6%, 19.2% against 6.9% and 27.8% reproduce. The 32 province-year equality with DGT holds, and extends to 2014. The headline contrasts keep their direction within zone. |
| F13 | Barcelona 2025: who is seriously hurt; the crash model 'no better than the shares' (barcelona) | survives with caveats | 'Ranked crashes no better than the shares by crash type' rests on one test with 58 serious crashes: gain +0.003 (−0.04 to +0.05), with 17–47% power for gains of 0.02–0.04. It shows 'not shown to be better', not 'no better' (moderate). Speed 'most often' is the largest of 17 causes; the pedestrian-struck ranking is within chance of two others (minor). | Every descriptive number reproduces exactly from the six raw files, and the contrasts hold against the exclusions, clustering, the night definition and merging the rear-end code. The decision to publish the table instead of the model stands. |
| F14a | Catalan model: a heavy vehicle 2.0 times the fatal share (1.7–2.2) (home, severity-models) | survives with caveats | On urban streets the heavy-vehicle excess sits only in crashes with a pedestrian or two-wheeler. The model's additive flags spread it to car-versus-lorry crashes, so the calculator's urban car-versus-lorry ×2.55 is about ×1.7 (moderate). The home page gives a ratio from one reference crash (minor). | The refit matches the exported coefficients to 5e-9. 'About twice' survives an unpenalised fit (2.02), a bootstrap that re-chooses the penalty (1.71–2.18), interactions (1.88–2.32) and either period. Standardised over all crashes it is 1.97 (1.79–2.16). |
| F14b | Catalan model: ROC-AUC 0.74 against 0.71, 12.4% against 12.3%, nested rolling-origin test (severity-models, validation) | survives with caveats | The road-owner exclusion depends on the outcome. Two of the three misses the page names in the later-years test (interurban Girona and Tarragona) disappear when the excluded crashes are kept (moderate). The benchmark is the two-variable table declared in advance: adding the heavy-vehicle flag halves the lead to about 0.015, with the model ahead in six of eight years (minor). 'All ten groups inside' clears its bound by 0.08 points (minor). The options menu was designed after test-year scores were seen (minor). | An independent re-implementation reproduced the nested test exactly (AUC 0.7395 against 0.7090, mean 12.37% against 12.31%, slope 1.033). It found no code-level leakage. The lead over the declared table holds in every year, and overall calibration is good (Hosmer–Lemeshow p = 0.28). The leakage attacker found that the province-left-out calibration misses persist with the excluded crashes restored (not rechecked by a verifier). |
| F15 | Validation: ranking held across provinces and Spain; national records unfit for a predictive model (validation, sources) | survives with caveats | The Barcelona 'no better' wording (as F13). The Barcelona outcome-recording crash code inflates the person model's district-transfer score, 0.86 to 0.82 (moderate). 'Train no published model' lacks 'predictive' (minor). | Leave-one-province-out reproduces closely (0.69–0.78 against the published 0.68–0.77), with every gain over the table excluding zero. The national transfer (0.709) and its reference reproduce. The DGT audit's failures are far beyond noise. |
| G1 | DGT's inspection-based kilometres 2022–2024 'as one series', against road fuel: 'points the other way' (data.html, sources.html; found by the completeness critic) | refuted | DGT's own 2024 report says the 2024 estimates use a different method from the 2022 and 2023 exercises (a new contractor, 2024 inspections only, a new filter). The whole 2022–2024 fall in kilometres per tonne (−3.0%) lies in the step that crosses that change. On DGT's like-for-like step, 2022–2023, kilometres per tonne rose 1.9%, as the Ministry's interurban (+3.4%) and toll-motorway (+5.1%) series did. So 'points the other way' has no valid support, and the sign of 'deaths per kilometre rose 3.9%' is not identified (major). An earlier version of the site said these figures 'cannot be joined'; an internal audit removed that, and a test now forbids it. | Every number reproduces. The repository's 2024 workbooks are byte-identical to DGT's release. The categories and fleet definitions match. The Spain-against-Catalonia kilometre ratio (1.18–1.25) is robust to the change. |
| G2 | Barcelona working-day check: 65+ involved 0.80–1.11 times the 45–64 rate per km across three versions, 18–29 2.14–2.61 (data.html; found by the completeness critic) | survives with caveats | The three versions do not bound the 65+ ratio. Capping the in-city part of crossing trips at a plausible 3–10 km gives 1.06–1.16, at or above the top of the published range (moderate). The on-duty variant removes only part of the on-duty drivers, because trip motive is unknown for about half of them (minor). The 18–29 kilometres rest on 49 respondents; single EMEF years give 2.05–3.99 (minor). | Every number reproduces from the raw Guàrdia Urbana and EMEF files. The design checks hold: every driver listed, no-victim crashes excluded, the 248-day calendar, the inside-city definition. Under every single change the 65+ interval includes 1 and the 18–29 interval lies above 1. |
| F19 | Interactive tools | weakened | The driver-risk tool's 75+ default (as F5b) (major). The calculator's interval assumes one specification and penalty: coverage about 92–94%, and 85–90% for unusual combinations (moderate). The crash explorer shows unflagged Basque and Murcian road-type recodings, while data.html says all road-type and junction breaks are Catalan (moderate). | The tools' arithmetic is exact. The JS engine matches the model, every crash-explorer cell matches, and the tool JSON regenerates byte for byte. |

## Critical and major issues

Each issue below was confirmed by its verifier and again, from scratch, by a second checker.

### C1 (critical). Catalonia: the road-type figures describe the file's coding, not the roads

**Published** (catalonia.html): "Most fatal crashes were on conventional roads: 1,981 of the 3,093,
with 18.8% of the 10,540 serious crashes on those roads fatal. ... Motorways had the highest share
of any road type (20.5%), but from only 224 crashes, and its 95% interval (15.8–26.3%) overlaps that
of conventional roads." The same figures appear in Figure 1 and in data.html Table 18.

**What is wrong.** The Servei Català de Trànsit file's road-type field (`D_TIPUS_VIA`) codes
motorways (`Autopista`) and dual carriageways (`Autovia`) as such almost only in 2013–2015:

- 204 of the 224 motorway crashes and 414 of the 496 dual-carriageway crashes are from those three
  years.
- In the other eleven years, crashes on the same roads are coded `Carretera convencional`. The AP-7,
  a motorway along its whole length, is coded as a motorway in 108 of 108 crashes in 2013–2015 and as
  a conventional road in 413 of 422 crashes in the other years. The A-2, C-32, C-17, B-23 and T-11
  switch the same way.
- DGT's microdata hold the same Catalan crashes for 2016–2023: 12,957 against the file's 12,961,
  with the same 1,627 fatal ones. DGT codes 1,572 of them as motorways or autovías; the file codes
  73. A record-level link (91.6% linked, fatal flags agreeing in every case) confirms it.

With roads classified consistently (several ways were tried: DGT's coding of the same crashes, the
file's own 2013–2015 coding as a template, and the named motorways):

| | Published | Consistently classified |
|---|---|---|
| Fatal crashes on conventional roads | 1,981 of 3,093 (64%) | about 1,460–1,620 (47–52%); at most 1,801 (58%) under the strictest rule |
| Share of serious crashes fatal, conventional roads | 18.8% of 10,540 | about 17.6–18.0% of about 8,300–8,600; 18.9% under the strictest rule |
| Motorway crashes | 224 | about 700–1,250 |
| Share fatal, motorways | 20.5% (15.8–26.3%), overlapping conventional roads | 22.4–25.0%, lower 95% bound 20.2–22.3%, above every conventional upper bound |

'Most' is not established, the motorway count is 3 to 5.6 times too small, and the overlap the page
reports reverses. The rest of the page stands: the totals, the zone, heavy-vehicle and lighting
contrasts, and the equality with DGT's fatal crashes. The verifier noted a knock-on effect it did
not quantify. The calculator's 'Conventional road, State network' and regional levels contain about
a quarter to two fifths motorway and dual-carriageway crashes, and its test years include only 7 motorway and 65
dual-carriageway crashes. So the published out-of-sample test says almost nothing about the
calculator's motorway and dual-carriageway options.

**Disclosure.** None on catalonia.html, Figure 1 or Table 18. The related remarks on data.html and
validation.html concern the cross-source model and put road-type coding breaks down to DGT's records.

**Reproduce** (from the repository root):

```python
import pandas as pd
df = pd.read_csv('data/raw/catalonia/accidents_morts_ferits_greus_catalunya_2010_2023.csv', dtype=str)
print(pd.crosstab(df.Any, df.D_TIPUS_VIA)[['Autopista', 'Autovia']].T)
ap7 = df[df.via == 'AP-7']
print(pd.crosstab(ap7.Any, ap7.D_TIPUS_VIA).T)  # Autopista almost only in 2013-2015
```

**Fix.** Either restrict the road-type shares to 2013–2015, or classify roads by name and kilometre
point (or by DGT's coding for 2016–2023), and rewrite the paragraph. Add the break to the coding
breaks on data.html. Check the calculator's road levels.

### M1 (major). The 18–29 per-km ratio is published without the uncertainty that dominates it

**Published** (index.html, drivers.html, Figure 1, driver-risk tool): "an estimated 2.68 times as
often as drivers aged 45–64 in 2024 (95% sampling interval 2.5–2.9)"; on drivers.html also "drivers aged
30–44 1.24 times (1.18–1.31) and drivers aged 65–74 1.11 times (1.0–1.2)".

**What is wrong.** The sampling interval covers survey and count chance for a fixed 50/50 average of
two metropolitan age profiles. It leaves out the transfer of those profiles to Spain. The study's
own sensitivity range for 18–29 is 1.49–3.63, 5.7 times as wide. 65% of its tested variants fall
outside the printed 2.5–2.9.

That range was printed beside the estimate until commit `268caf2`, which removed it from the home
page, the drivers page, Figure 1 and the tool; tests now forbid it there (`tests/test_site.py:501`,
`:1006`). The methodology page still says the ratios 'are published with these ranges' and that 'only
the direction at 18–29 is firm' (`src/dgt_stats/site/data.py:1337`). The same applies to 30–44
(range 1.12–1.72) and 65–74 (0.67–1.70). At 30–44 and 65+ the two surveys disagree beyond chance,
and the printed interval contains neither survey's own estimate.

Two related issues were confirmed as moderate:

- Both source regions have the lowest ratio of young to middle-aged car-licence holding of Spain's
  52 provinces (Barcelona 0.488, Madrid 0.493, Spain 0.551). The study's own licence calibration,
  applied to both surveys rather than to Barcelona alone, gives 2.37 (2.20–2.53), below the printed
  interval.
- Averaging the two surveys makes the interval narrower than either survey's own (log width 0.14
  against 0.23 and 0.16) without adding information about Spain.

**Reproduce:** `git show 268caf2^:site/index.html | grep -o 'sensitivity range</a> 1.49–3.63'`;
`reports/tables/risk_national_sensitivity.csv` (18–29: 1.491 to 3.634).

**Fix.** Restore the range beside each per-km ratio (for example "2.68 times (95% sampling interval
2.5–2.9; 1.5 to 3.6 times under the other assumptions tested)"), or lead with the robust statement
("more often under every assumption tested"). Add the symmetric licence calibration to the
sensitivity analysis.

### M2 (major). The driver risk comparison states the 75+ per-km figure as established

**Published** (driver-risk.html, default view): "Per kilometre driven, drivers aged 75 and over were
involved in injury crashes 2.43 times as often as drivers aged 45–64." The detail reads "75 and
over: 95% sampling interval 2.0–3.0".

**What is wrong.** The drivers page says this estimate "rests on Madrid's survey alone" (the methodology page
gives its condition: that people aged 75 and over "drive as much less than those aged 65–74 as in
Madrid in 2018"). It says that under other plausible
assumptions it runs from 0.97 to 3.20, "so the data do not establish that they are involved more
often per kilometre than drivers aged 45–64". The tool opens on exactly this comparison and gives
neither the condition nor the range nor the conclusion. A 2.0–3.0 interval reads as an established
excess. Commit `268caf2` removed the condition, the conclusion and the range from
`site/tools/driver-risk.json`. The editorial guard checks only the drivers, home and data pages
(`tests/test_site_editorial.py:352`). STATISTICAL_AUDIT.md's writing rule 4 requires a conditional
estimate to appear only with its condition and its full range.

Three moderate issues compound it:

- Figure 1 on the drivers page draws 75+ at 2.0–3.0 with no range.
- The heading 'Crashes per kilometre: highest among drivers aged 18–29' ranks 18–29 above 75+. The
  ordering holds with about 80% probability under sampling error and reverses on the Madrid profile.
- The documented upward alternatives, crossed like the four splits, would take the top of the range to about
  3.4–3.6.

**Fix.** Show the condition, the range and the conclusion whenever the tool shows 75+ (or 65–74) per
km, or open the tool on another comparison. Extend the guard to the tool. Add the ranges to
Figure 1, and make the heading say 'highest among the groups with an established figure', or drop
the ranking.

### M3 (major). The DGT location odds ratios are inflated by an outcome-dependent recording level

**Published** (severity.html): "a crash on a conventional interurban road 6.63 times the odds
(against an urban street)". Table 1 gives 5.66–7.23 for the four interurban road types, and "a
conventional road where it runs through a town ... 8.75 times". A build check asserts that this
is the largest location contrast.

**What is wrong.** In DGT's records for the four Catalan provinces, road alignment
(`TRAZADO_PLANTA`) on non-street crashes is filled in almost only when someone died or was admitted
to hospital within 24 hours. Otherwise it is 'unknown': for 99.8% of non-street crashes without such
an outcome, against 28.4% with one. In the rest of Spain the figures are 1.5% and 0.8%. The model
keeps 'unknown' as a nuisance level (OR 0.12), and inside Catalonia it stands in for the outcome.
68% of urban-crossing crashes are Catalan, so the location terms are estimated partly from crashes
selected for severity.

Refitted without the leak in ten ways (alignment dropped; unknown read as straight; Catalonia left
out; province fixed effects):

| Contrast | Published | Without the leak |
|---|---|---|
| Conventional interurban road vs urban street | 6.63 (4.95–8.89) | 4.9–6.2 |
| Four interurban road types | 5.66–7.23 | about 4.4–5.8 (at most 6.2) |
| Urban crossing, conventional | 8.75 (6.52–11.75), 'largest' | 3.76–6.87; 3.76–5.63 in every same-population fit, below the published lower bound |

The directions hold, and the crash-type and junction odds ratios barely move. The data
page does warn that a recording practice could distort other coefficients through such a level. Its
check, refitting without Catalonia, was applied only to the 32 single-term odds ratios, never to the
joint location contrasts.

**Reproduce:**

```python
import pandas as pd
df = pd.read_parquet('data/processed/dgt_accidentes.parquet', columns=[
    'COD_PROVINCIA', 'ZONA', 'TRAZADO_PLANTA', 'TOTAL_MU24H', 'TOTAL_HG24H'])
cat = df.COD_PROVINCIA.astype(int).isin([8, 17, 25, 43])
nonstreet = df.ZONA.astype(int) != 3
serious = (df.TOTAL_MU24H + df.TOTAL_HG24H) > 0
unknown = df.TRAZADO_PLANTA.astype(int) == 4
for name, region in [('Catalonia', cat), ('rest of Spain', ~cat)]:
    s = region & nonstreet
    print(name, unknown[s & ~serious].mean(), unknown[s & serious].mean())
# Catalonia 0.998 0.284; rest of Spain 0.015 0.008
```

**Fix.** Fit the location contrasts without the alignment term, or with Catalan alignment treated
as missing. Drop the 'largest location contrast' wording and its build check, and give the
leakage-free values (for example conventional interurban 5.7, 4.7–6.9).

### M4 (major). The 2006 points licence: 'did not last' depends on an unidentified pre-trend

**Published** (policy.html): the heading "An immediate fall of about 7% that did not last". The text
reads "fitted deaths rejoin the projected path in about July 2007 and end the window 2.3% above it;
averaged over the 17 months, the change is −2.5%". It also says a straight line "fits the months
before the change less well than a trend that bends once, in August 2003 ... That difference
favours the bend without being decisive."

**What is wrong.** The pre-trend is chosen by QAIC on the months before July 2006, but only among a
straight line and a single continuous bend (`src/dgt_stats/policy.py:772–830`). Apply the same rule (same months,
same c = 1.6076, same two parameters per change) to an equally simple trend with a one-off level
drop, and the January 2004 drop fits better than the August 2003 bend: QAIC 473.4 against 476.2. It
does so at every c from 1.0 to 1.86. In the raw counts, 2003 deaths (5,399) exceeded 2002's
(5,347), and the drop starts in January 2004. Under that pre-trend:

| | Bend, August 2003 (published) | Level drop, January 2004 | Two bends at least 12 months apart (ties the one bend) |
|---|---|---|---|
| Step at July 2006 | −7.1% (−13.2% to −0.5%) | −12.6% (−16.6% to −8.5%) | −10.9% |
| Mean change over 17 months | −2.5% (−7.8% to +3.2%) | −11.5% (−14.9% to −8.0%) | −9.5% (−14.2% to −4.4%) |
| End of window | +2.3% | −10.4% | |

The single-bend answer also flips with the window's start, which is not justified anywhere: starts
in 1995–1997 give about −9%. On those longer windows one bend is misspecified; allowing two
returns them to about −3%, but then starts in 1998, 1999, 2001 and 2002 give −7.5% to −10.5%.

The −11.5% is the top of the range. The level drop forces a slope (−2.6% a year) flatter than the
local decline of 2004–2006 (−5.1% a year); pre-trends that keep the local slope give a lasting
−6% to −7%. Averaging over pre-trends by QAIC gives a 17-month change of about −7% to −8%, with an
interval reaching zero.

The data cannot tell which pre-trend is right. In simulation:

- when the true fall lasted, the published procedure still reports 'did not last' in about 30–40%
  of series;
- when the truth is the published bend, a rule that also allows level drops picks a drop about half
  the time.

So the page's lead, 'the series cannot show ... that it lasted', is correct. But the
heading's 'did not last', 'rejoin the projected path in about July 2007' and the single −2.5%
report one unidentified choice as the finding. The page's disclosure tells readers the pre-period
favours the transient pattern. Under an equally simple extension it slightly favours a lasting fall.
'Cannot be attributed to the licence' is unaffected.

**Fix.** Make the heading say that whether the fall lasted depends on the earlier trend (for
example 'A fall of 7% to 13% at the change; whether it lasted depends on the earlier trend'). Give
the level-shift and two-bend results beside the bend, or a QAIC-weighted average with its interval.
Compute the intervals with model-based quasi-Poisson or negative-binomial errors (see the moderate
issues).

### M5 (major). DGT's 2022–2024 kilometre estimates are not one series

Found by the completeness critic's gap attacker. The register lists it as three entries, one for
each statement affected (`GAP-dgt-inspection-km-series-comparability.I1`–`I3`).

**Published.** data.html (Since 2019 notes): "DGT's kilometre release of 2024 gives the mean
distance driven per vehicle for 2022, 2023 and 2024 as one series ... all vehicles together drove
1.6% fewer kilometres in 2024 than in 2022, while road fuel sold rose 1.5%"; "Over those years
deaths per kilometre by DGT's estimate rose 3.9% and deaths per tonne of fuel 0.8%". data.html
(long-run notes): "The other source of kilometres points the other way: DGT's inspection-based
kilometres ... put kilometres per tonne of fuel 3.0% lower in 2024 than in 2022". The same claim
appears as 'as one series' on sources.html, 'on the same basis' in the vehicle notes, and 'estimates
on one basis' in `docs/methodology.md:224–225`.

**What is wrong.** DGT's own report on the 2024 estimates says the opposite. Its report
(`KM_Estimados_Publicacion_Parque2024.pdf`, made by Applus IDIADA; the 2022 and 2023 exercises were
the Observatorio Nacional de Seguridad Vial's) states on p. 4:

- it applies "una metodología distinta a la utilizada en la publicación del parque circulante de
  2023";
- it uses 2024 inspections only, a new filter on extreme values and new model variables;
- "Estos cambios han generado diferencias en algunos valores respecto al informe anterior".

Its Table 6, the source of the site's series, is "los tres ejercicios de estimación". Its 2022 and
2023 rows are copied from the earlier releases. Split at the declared change:

| | 2022 → 2023 (same approach) | 2023 → 2024 (across the change) | 2022 → 2024 (published) |
|---|---|---|---|
| Vehicle-km | +0.8% | −2.3% | −1.6% |
| Road fuel sold | −1.0% | +2.5% | +1.5% |
| Kilometres per tonne of fuel | +1.9% | −4.8% | −3.0% |
| Car mean distance | −0.9% | −5.1% | −6.0% |

On the like-for-like step, kilometres per tonne rose, as the Ministry's measured interurban series
(+3.4%) and the toll motorways (+5.1%) did. Deaths per kilometre then rose less than deaths per
tonne (+2.6% against +4.5%), the reverse of the ordering the site reports. About 2.7 points
of the 6.0% fall in cars' mean distance over 2022–2024 is genuine fleet ageing; the rest sits in
the youngest band, mostly model-imputed because those cars have had no inspection (−22% in 2024
alone), while every older band rose.

'Points the other way' therefore has no valid support. The sign of the 2022–2024 changes is not
identified; deaths per kilometre run from about −1.8% to +3.9% under the alternatives tested.

An earlier version of the site said these figures were "built by different methods and cannot be
joined into a series" (commit `c2fa89b`). The claim ledger records that caveat as 'not checked'
against DGT's documents (ledger-B|66), and it was then replaced on the strength of Table 6 alone. A
test now forbids the correct wording (`tests/test_site.py:877–878`).

**Provenance.** The repository does not archive DGT's 2023 and 2024 reports. The verifier and the
second checker each fetched them from dgt.es. The release's tables are byte-identical to the
repository's `data/raw/dgt/km_itv_2024/` files.

**Prominence.** The statements sit in supporting notes, not in a headline: the trend pages use road
fuel, the vehicles page uses 2022 alone, and the drivers page uses 2024 alone. But this is the
site's only all-roads kilometre evidence against road fuel, and it is used to present the
km-per-tonne evidence as pointing both ways.

**Fix.** Restore the caveat: three estimation exercises, with DGT's stated change of method in
2024. Report 2022–2023 as the only like-for-like step. Drop 'points the other way' and the 2022–2024
per-kilometre changes, or give them as a range. Replace the test that forbids the caveat, reopen
ledger-B|66, and archive DGT's 2023 and 2024 reports with the raw files if their terms allow.

## Moderate issues and their fixes

Every row was confirmed, at least in part, by a verifier who reproduced it. The issue register
([`ADVERSARIAL_REVIEW_e593b6b.csv`](ADVERSARIAL_REVIEW_e593b6b.csv)) gives each one's factual core as the
verifier confirmed it, its materiality, its disclosure and a suggested fix.

| Finding | Issue | Fix |
|---|---|---|
| F1b | 'Outside its range' (2023–2024 per tonne of fuel) assumes the 2011–2019 decline went on; the method's ranges missed most pre-2020 outcomes four to five years ahead, and a smooth-trend model puts both years inside, though random-walk and OLS forms keep them outside. | Say the range assumes the trend continued, or call the years 'above the continued 2011–2019 trend' and give the smooth-trend interval beside it. |
| F2 | About 80% of the 2019–2024 rise in admissions is VMP riders (the yearbook's new column, in 'Otros' before 2020) and motorcyclists. Without VMP and 'Otros', admissions per tonne are +8.8% (−2.6% to +21.5%), within ordinary variation; motor-vehicle occupants alone are still beyond it, +10.8% (+0.9% to +21.6%). | Give the change without VMP and 'Otros' beside the per-tonne figure, and add the road-user mix to the explanations of more admissions per crash. |
| F2 | The single 'beyond' (lower bound +1.6%) is borderline: t = 2.96 on 5 df, not significant after Holm over 13 rows, sensitive to the scatter window and to dropping a year. | Call it borderline and stop singling it out in the summary without that qualifier. |
| F2 | 'Beyond' rests on 0.3% a year of km-per-tonne drift being hypothetical, while the only measured series (interurban) drifted about 1.9% a year in 2019–2023. | Put the measured drift next to the 0.3% threshold. |
| F3 | The April 2020 '−24% per tonne' has no interval (about −48% to +11% on 40 deaths), and the heading's 'deaths fell more than road fuel sold' is not established. | Add the interval and the baseline sensitivity (−15% to −28%), and soften the heading. |
| F3 | Road fuel weights freight heavily, so February below and August above depend on the denominator (per tonne of petrol February is 0.99). | Say the measures disagree about February too; April–May below and July and September above hold under both. |
| F4 | The Newey–West(12) intervals undercover even under a correct model; with quasi-Poisson or NB errors neither the step (−14% to +1%) nor the slope change excludes zero. | Use model-based quasi-Poisson or NB2 errors throughout, and report the residual diagnostics (Ljung–Box p at least 0.33). |
| F4 | 'Did not last' rests on intervals that placebos matched to the main fit show to be about 2.5 to 2.8 times too narrow (the page's own straight-line placebos give about 4, which overstates it); the data cannot rule out a lasting fall of 10–15%. | Reword the heading so that the size and persistence of the fall are not pinned down. |
| F5a | Both survey regions have Spain's lowest young licence holding. The study's own calibration, applied to both, gives 2.37, below the printed interval. | Add the symmetric calibration to the sensitivity analysis, and say the transfer probably overstates the 18–29 ratio. |
| F5a | The averaged profile's interval is narrower than either survey's; at 30–44 and 65+ the surveys differ beyond chance and the interval contains neither. | Show both surveys' estimates, or the range, beside the average. |
| F5b | Figure 1 shows 75+ at 2.0–3.0 with no range. | Draw the 65–74 and 75+ ranges, or add them to the caption and alt text. |
| F5b | The heading 'highest among drivers aged 18–29' ranks 18–29 above 75+, which reverses on the Madrid profile. | Drop the ranking against 75+, or qualify it as the central estimate. |
| F5b | 0.97–3.20 understates the upside: crossing the documented upward alternatives gives about 3.4–3.6. | Write 'from 0.97 to at least 3.20', or add the upward variants. |
| F5b | The 65–74 figure, 1.11 (1.0–1.2), appears without its 0.67–1.70 range. | Print the range beside it, as for 75+ (part of M1). |
| F7 | The sex ratios are crude, and age distorts them. Once involved: 2.35 at equal age, against 2.62. Per licence holder: 1.45, outside the printed 1.38–1.40. | Give age-standardised ratios beside the crude ones, and say the excess once involved falls with age. |
| F7 | Per km, men aged 18–29 are involved about 1.3 times as often as women (1.19–1.63 across every profile), so 'which ... comes from their driving further' holds only from age 30. | Limit the sentence to drivers aged 30 and over, or add the 18–29 figure. |
| F8 | The heavy-truck multiples come from 2022, the highest year: 2023 and 2024 give 1.7–2.0 times per km with each year's DGT kilometres, and 2.03 and 1.95 on the 2022 kilometres; about half the 2022–2024 gap comes from DGT's revised kilometres. | Say 2022 was the highest year, and give the 2022–2024 figure (2.0, 1.9–2.2). |
| F9 | Under the study's own t convention the dual-carriageway ratio's interval is 0.98–1.52. | Use t(7), and say 'clearly on three road types'. |
| F10 | The +49% for interurban illegal manoeuvres counts as comparable only because the 2017 jump (×1.223) sits just under the 25% rule; at 20% the run splits and is flat after 2017. | Show the run as 2014–2016 and 2017–2023, or say the 2017 rise was just under the rule. |
| F10 | The 2014 urban baseline sits inside a step in recorded urban crashes. | Say so beside the urban speed fall. |
| F11 | Crash-type odds ratios differ sharply between urban streets and interurban roads (head-on 2.8 against 5.6); the ranking sentence holds only on interurban roads. | Say the odds ratios are averages weighted towards interurban roads, and give the urban values. |
| F11 | Catalan surface recording depends on severity: without it, wet is about 0.60, not 0.56. | Add the caveat and the figure without the Catalan records. |
| F11 | Catalonia's 2024 urban streets coded 'Otro' are 14,349 of the 29,209 crashes in Table 1's 'Street / Other road' row (1.74, but 2.67 when corrected). | Read that code as urban street, as the junction flag is already re-read. |
| F13, F15 | 'Ranked crashes no better than the shares by crash type' rests on 58 serious crashes (+0.003, −0.04 to +0.05). | Say 'was not shown to rank crashes better', with the interval. |
| F14a | On urban streets the heavy-vehicle excess sits in crashes with pedestrians and two-wheelers. The calculator's urban car-versus-lorry ×2.55 is about ×1.7. | Add a heavy × vulnerable-user term, or state the limitation beside the urban figure. |
| F14b | The outcome-dependent owner exclusion produces two of the three named later-year misses (interurban Girona and Tarragona). | Give the excluded share by province and period, and the misses with the excluded crashes scored. |
| F14b, calculator | The owner exclusion moves the reference estimate (13.4% against 11.6–17.5% under other handlings). | State the alternative estimate beside Table 1. |
| F15 | The Barcelona outcome-recording crash code lifts the person model's district score (0.86, but 0.82 without it). | Refit without the code, or report both. |
| F16 | The road-owner codes in DGT's Catalan records depend on the outcome, so the numerator drops deaths whose kilometres are counted. | Set coverage from the road name in the Catalan provinces, and recompute (3.40; the '8.7% to 11.2%' becomes about 6.6–9.1%). |
| F19 | The calculator's interval leaves out the shrinkage bias of the penalised fit: even when the model is right it covers about 92–94% for recorded crash profiles and 85–90% for unusual combinations. It is also conditional on one specification and penalty, which the linked report states and the page only implies. | Say so, or widen it with a bootstrap that repeats the selection. |
| F19 | The crash explorer shows Basque (2017, 2021) and Murcian (2017) road-type recodings without a caveat, and data.html says all road-type and junction breaks are Catalan. | Add them to the coding breaks, and make the explorer's caveat fire for them. |
| G1 | DGT's 2022 kilometres are pure model output, while its 2024 figures use observed inspection readings where valid. About 0.8 points of the −3.0% in kilometres per tonne comes from that difference of basis alone. | State it in the caveat that M5 restores. |
| G2 | The three versions of Barcelona's working-day kilometres do not bound the 65+ ratio. Capping the in-city part of crossing trips at a plausible 3–10 km gives 1.06–1.16, at or above the top of the published 0.80–1.11. | Say the versions are not bounds, and give the capped values. |

## Minor issues

93 issues were confirmed as minor. They are in the register with the verifier's reading of
each, which often narrows the attacker's claim, and a fix. By kind:

| Kind | Issues |
|---|---|
| Wording that says slightly more or less than the numbers | 21 |
| Missing or understated uncertainty | 13 |
| Recording and measurement | 12 |
| Reproducibility and documentation | 10 |
| Significance and multiplicity | 9 |
| Model assumptions | 6 |
| Confounding | 6 |
| Denominators | 5 |
| Data integrity | 4 |
| Other (leakage process, selection, computation) | 7 |

The minor issues with a visible effect on a page are in the verdicts table above. Two
documentation items recur and are worth one pass each:

- The research documents and the data page still describe Method A (the Barcelona-area profile, 2.53)
  as the central driver-age estimate, and the sensitivity alternatives are centred on it, while the
  pages publish the two-survey average (2.68).
- Several documents carry intervals that later commits changed: `docs/methodology.md`,
  `STATISTICAL_AUDIT.md` and `DRIVER_AGE_EXPOSURE.md`.

## The six questions asked

**Data leakage.** No leakage was found in the code of any out-of-sample evaluation.

- An independent re-implementation of the calculator's nested rolling-origin test made the same
  choice in every test year and reproduced its scores exactly. It used only earlier years for the
  penalty, the specification, the through-town rule and the province intercepts.
- The calibration figure and every rolling score are computed from the nested predictions alone.
- The Barcelona person model's splits keep the people of one crash together.
- The DGT association model's later-year scores re-decide their merges on the earlier years only.
- The averaged driver-age profile (2.68) was a late change, but no sign was found that it was tuned
  on outcomes.

The leakage that exists comes in through recording that depends on the outcome:

- DGT's Catalan road alignment, which inflates the national location contrasts (M3, major).
- The Barcelona file's Catalan-language rear-end code, used on 26 of its 43 crashes for a serious
  injury against 2 of 1,672 for the force's own code. Both Barcelona models read it. The person
  model's published score on districts left out, 0.86, is 0.82 without it (moderate).
- The Catalan road-owner exclusion, decided on all years. A blank owner is 53% fatal and 'other'
  3%. The exclusion moves the calculator's reference estimate (13.4% against 11.6–17.5% under other
  handlings) and creates two of the three province misses named on the model page (two issues,
  moderate).

Two process points are minor. The leakage audit can flag only placeholder levels, so an outcome-coded
ordinary level passes it as safe. The claim that the decision rules were set before any result was
read cannot be verified, because rules and results arrive in the same commit; no sign of tuning was
found.

**Biases.** The selection and measurement biases that matter here are the ones that move a published
magnitude:

- The metropolitan transfer of driving by age (M1).
- The age mix in the sex ratios (F7, moderate).
- The freight in road fuel, as a denominator of the seasonal pattern (F3, moderate).
- The new road users in the admissions series (F2, moderate).
- Catalan surface recording that depends on severity (F11, moderate).
- The definition break in the Catalan road-type field (C1, critical).

Some checks the site's design passed:

- The collider check: conditioning on a death or serious injury can flip signs. Pedestrians go
  from 1.62 among all Catalan injury crashes to 0.85 within severe ones, and rain from 0.70 to
  1.10. The site already warns that a lower fatal share among severe crashes (in rain, at a
  junction) does not make them safer, and keeps the model's contrasts scoped to severe crashes; no
  published statement is falsified by the reversal.
- Conditioning on severity attenuates the heavy-vehicle association rather than creating it, and the
  association stays above 2 under every stratification.
- The older-driver death ratio barely moves with road mix (3.43 to 3.33).
- The speed ratio's numerator and denominator exclude the same regions.

The 24-hour definition of a Catalan death narrows the urban–interurban gap that 30-day deaths would
show (2.8 to about 2.3), but the page states its definition (minor).

**Uncertainty.** Most intervals are computed correctly and say what they cover. Three were found
anti-conservative or missing where a reader needs them:

- The per-km age ratios carry a sampling interval that omits the dominant uncertainty (M1).
- The points-licence model uses Newey–West errors with 12 lags. They undercover even when the model
  is right, and with valid errors neither the step nor the slope change excludes zero (moderate).
- The April 2020 per-tonne change and the 3.4 death ratio have no interval (moderate and minor).

The calculator's interval is conditional on one specification and penalty, and covers about 92–94%
for ordinary crashes (moderate). The 'outside its range' of the fuel trend assumes the slope carried
on (moderate).

Several intervals held: the seasonal intervals (a year-block bootstrap agrees), the road-class
Poisson interval (no excess scatter across years), and the DGT model's province clustering. In the
DGT model only one minor Table 1 row includes 1 under a delete-one jackknife.

**Model assumptions.** Most held when tested:

- Weak residual autocorrelation in the long-run trends, and calibrated projection ranges when the
  trend continues.
- No autocorrelation in the points-licence series.
- Additivity of zone and road type behind 6.63.
- Invariance of the per-fuel month effects to days per month.
- A constant road-to-straight-line factor, which moves the age ratios by under 1%.
- The speed pooling, which agrees with the SMR and Mantel–Haenszel within 4%.

Four assumptions failed in ways that change what a reader is told:

- Transportability of two metropolitan age profiles to Spain (M1).
- Main effects only in the DGT regression: crash-type odds ratios differ sharply between urban
  streets and interurban roads (F11, moderate).
- Additive road-user flags in the Catalan model: on urban streets the heavy-vehicle excess is
  confined to crashes with vulnerable road users (F14a, moderate).
- A pre-trend limited to one bend in the points-licence model (F4).

**Statistical significance.** The highlighted results mostly survive multiplicity:

- the raw summer peak, and July, September and April–May per tonne;
- every highlighted odds ratio (p at most 1e-10);
- the speed heterogeneity;
- the model's lead in every year;
- 'in every age band' for the sex ratio, under Holm.

Four do not:

- The single 'beyond' among the 13 rows on trends.html is borderline and fails a 13-row correction.
- February per tonne fails a 12-month correction.
- The Barcelona cause ranked first (speed, on 38 crashes) is the largest of 17 and not established
  over the runner-up.
- The dual-carriageway speed ratio's interval crosses 1 under the study's own t convention.

Several nulls are read as near-equivalence with low power. 'No clear rise' since 2013 had about 40%
power for the observed rise. 'Within ordinary variation' for 2024 deaths could not detect changes
under about 15%. The Barcelona 'no better than the table' had 17–47% power for the gains that matter.
One threshold sits on a knife edge: the illegal-manoeuvres run, at 1.223 against 1.25.

**Reproducibility.** See the section on reproducibility and data integrity: every published number
reproduces from the raw files. The exceptions are minor drift in seven secondary model tables, the
undocumented step that renders two generated documents, and stale numbers in the methods documents.

## Reproducibility and data integrity

Every number printed on the site reproduces from the raw files.

- **Raw files.** All 168 raw files match the SHA-256 values in `data/raw/manifest.csv`.
- **CI-equivalent build** (main checkout). `ingest.py all` passed its 482 reconciliation checks.
  After it, `build_tables.py`, the five regional steps that CI runs and `emef.py build`
  regenerated their committed files byte for byte (`git status` empty).
- **Full clean rebuild** (separate checkout of `e593b6b`). It ran the README's Reproduce sequence
  in order: `ingest.py all`, `build_tables.py`, `model.py`, `analyse.py tables`,
  `microdata.py all`, `severity_calculator.py all`, `emef.py all`, `exposure_risk.py all`,
  `analyse.py figures` and `cards`, `build_site.py`, `pytest`, `analyse.py withdrawn`.
  - Every step exited with code 0. A container restart stopped the run during `microdata.py all`.
    The four steps before it had finished, and the run resumed from that step.
  - `pytest`: 483 passed. The 2 skipped are the browser tests, which need Python Playwright. The
    1 deselected is the SHA-256 test, run separately above.
  - Reproduced byte for byte: every page of `site/`, every national table, every EMEF and
    driver-age table (the 2.68 headline included), the calculator's exported model and `sev_*`
    tables, the forecast tables and the model cards.
- **Independent recomputation.** Every attacker recomputed its target's numbers with its own code.
  The data-integrity attacker used its own raw-XML reader for the DGT workbooks and recomputed more
  than 60 published values. It found no parsing or coding error that changes a published number.
  Two disputed claims were confirmed independently:
  - DGT's records for the four Catalan provinces code the junction flag the wrong way round in
    2023 and 2024;
  - the Catalan file's fatal crashes equal DGT's 24-hour fatal crashes in all 32 province-years
    of 2016–2023.

Eleven committed files are not reproduced byte for byte. No number on any page changes.

| Issue | Severity | Finding |
|---|---|---|
| Thread-dependent fits | minor | The logistic fits in `microdata/ml/modelling.py:137`, `model_review.py:109` and `microdata/validation/dgt_audit.py:530` use lbfgs at its default tolerance of 1e-4, and no script pins the BLAS thread count. The same model-review fit gives three different results on 1, 2 and 4 threads; the committed `review_catalonia_2023.csv` matches 4 threads. Seven tables differ: `dgt_audit_artefacts`, `gen_calculator_transfer`, `ml_domain_strategies`, `ml_geography`, `ml_variants`, `review_catalonia_2023` and `review_catalonia_rolling`. So does the transfer figure `tr0_calculator_transfer.svg`, by about 0.001 px. Of the 159 cells that move, 95 exceed a relative 1e-4: up to 4.7e-4 on an ROC-AUC and 0.008 on a calibration intercept. The calculator model (newton-cholesky at 1e-10) is unaffected. Methodology §17 says the rebuild 'reproduces the committed result tables (checked for this release to a relative tolerance of 1e-4)'; that is not true for this release. Fix: tighten the tolerance or use newton-cholesky, pin threads in `scripts/microdata.py` and `scripts/severity_calculator.py`, and regenerate. |
| Generated documents from an unlisted step | minor | The committed `docs/GENERALISABILITY.md` and `reports/model_metrics.json` were rendered by `microdata.py documents`, which re-reads the CSVs at six significant digits. The README's `microdata.py all` renders from memory. The two differ: an interval end is 0.709 committed (a double rounding) and 0.708 from `all`, and two empty cells print as `NA`. |
| What CI checks | minor | CI regenerates and compares only `ingest`, `build_tables`, `model.py` and five regional steps. It never runs `analyse.py tables`, `figures` or `cards`, `emef.py`, `exposure_risk.py`, `severity_calculator.py`, or the regional model and validation steps. Its data-layer cache key omits `requirements.lock` and `src/dgt_stats/paths.py`. The drift above went unnoticed for this reason. |
| Reconciliation wording | minor | The README and the data contract say the 482 checks 'tie' the data to DGT's published totals. Sixty-four of them are internal or dictionary checks. Every gap the integrity attacker filled reconciled, so this is wording. |
| Typed-in values and README | minor | Code comments cite unarchived documents for figures that are in archived files. The `distance.py` docstring gives walking and transit road ratios of 1.32 and 1.50, but the constant computes 1.40 and 1.49; this touches 2021 validation rows only, by up to 0.9 points. `manifest.csv` cites `docs/phase3_plan.md`, which does not exist. The README gives `model.py` about two minutes (it took 13 here), and omits `playwright install chromium` for the browser tests. |
| Madrid junction coding | minor | Madrid city's 2016–2018 junction coding is partly inconsistent (2018: 2,052 junction crashes with no junction type). It falls below the inversion rule's threshold. The pooled junction odds ratio moves by 0.002; the data page's yearly range would read 0.61–0.79, not 0.63–0.79. |

## Where attackers disagreed

The attackers worked blind to each other, and on several points they reached opposite conclusions.
The verifiers settled each one.

- **'No clear rise' since 2013.** One attacker said correctly sized tests find a significant
  2013–2019 rise; two others said the null was adequately powered. The verifier found the printed
  test correctly sized: the estimated dispersion (1.45) is above the floor, so the interval is that
  of an unfloored quasi-Poisson t(5) test. A rise is significant only if the dispersion is treated
  as known and below about 2. Result: wording (minor). Say 'no fall, and a rise that is not
  statistically clear'.
- **The points-licence heading.** Attackers attacked it from opposite sides: a lasting fall under
  other pre-trends, and no established fall or persistence under valid intervals. Both lead to the
  same correction. The size and persistence of the fall cannot be pinned down, while 'cannot be
  attributed to the licence' stands and is strengthened.
- **Recording bias in the speed ratios.** One attacker found fatal crashes' fields recorded only
  about 1.1 times as often as slight crashes', 'far too small' to make a 5.9 ratio. Another found
  modest differentials enough to make the interurban ratios. Both hold. The urban ratio would need
  about five-fold differential recording; the interurban ratios only 1.2–1.7 times (minor).
- **Intervals of the Catalan model.** For the heavy-vehicle contrast, a bootstrap that re-chooses
  the specification and penalty gives 1.71–2.18: the published contrast interval is adequate. For
  individual calculator estimates, coverage falls to about 92–94% (moderate).
- **The speed summary interval.** The verifier sided with the attacker who judged the pooling
  sound. For the weighted summary the page defines, the interval errs on the wide side. Only a
  'typical road type' reading, which the page disclaims, needs random-effects intervals.
- **Province clustering in the DGT model.** An exact delete-one-province jackknife removes the
  significance of one thin Table 1 row, not two (minor).
- **The late switch to the averaged driving profile** (commit `268caf2`). No evidence was found that
  it was chosen on outcomes. The documents were not updated around it (minor).
- **The owner exclusion and the province misses.** The misses in the later-years test (interurban
  Girona and Tarragona) come from the exclusion. The leakage attacker found that the misses when
  each province is left out of fitting persist without it; no verifier rechecked that. The model
  page's single 'missed in some provinces' covers both.

## Claims the verifiers refuted

Twelve issues raised by attackers did not survive verification. They are listed so that they are not
raised again.

| Attacker's claim | Why it was refuted |
|---|---|
| The '3.4 times' for drivers 75+ should be 3.5, the quotient of the printed 15.9 and 4.6 (F6) | 3.4 is the correctly rounded ratio of the counts (3.43); 3.46 is the quotient of two rounded rates. |
| 'A lorry or bus' is unverified because the source does not define the heavy-vehicle class (F14a) | The class includes coaches and buses; only an internal harmonisation note is out of date. |
| 'At least one death per crash' mixes lethality with occupancy (F11) | The odds ratios are correct for the stated outcome, the model adjusts for vehicles, and the ranking holds per victim. |
| Barcelona road-user shares compare groups with different selection into the file (D2) | The page states no ratio, and 'far more often' holds under the attacker's own alternative (7.2% against 0.36%). |
| The Barcelona shares shown are not the table compared with the model (F13) | The comparison is stated as made; with both merged the model is still no better on the test. |
| December 2025's low serious share suggests incomplete follow-up (F13) | No artefact is established, and the page makes no claim by month. |
| 'Nearly as well as a model fitted there' holds only against a restricted reference (F15) | A richer reference widens the gap to −0.03, still inside the study's 0.05 tolerance. |
| 'No model has passed every kind of test' is true by construction (F15) | The heading is literally true and matches the page's conclusion; the failing column is a declared stage. |
| The national road-class ratio reflects the mix of networks (F16) | Within each network conventional roads still have 2.6–4.4 times the motorway rate. |
| One dispersion for all months misfits December, March and April (F3) | No evidence against a common dispersion (p about 0.7). |
| Calendar length inflates the lead's July and August figures (F3) | Per day they are 1.20 and 1.12, inside the published intervals; the raw panel's caption discloses it. |
| 'Most of all on urban streets' holds only on the ratio scale (F9) | The sentence says it is a ratio, and urban streets also lead on the absolute excess. |

Two issues could not be settled with the data available:

- Age-differential recording of slight-injury crashes behind the 75+ death ratio (F6). A ratio of
  2.0 would need about 42% of 75+ involvements to be missing, and no proxy suggests it.
- Moped kilometres imputed to a dormant fleet (F8). Only an extreme scenario would make the
  motorcycle interval touch the mopeds'.

## Coverage

The completeness critic read every page and matched each number in it against the attackers'
outputs. The home page, the page leads and the analysis pages turned out densely covered: almost
every number on them appears in some attacker's reproduction or reasoning. The untouched numbers sat
in supporting text on data.html, validation.html and sources.html. Two of those claims have their
own pipelines and had stood untested. Both went to new attackers (G1 and G2 in the verdicts).

The critic's other gaps were not attacked:

- **The scope of the fleet denominator** (medium). The registered fleet may include vehicle types
  whose occupants the per-vehicle numerator leaves out.
- **The data page's description of the central driver-age method** (low). It still describes the
  Barcelona-area profile alone; this is partly covered by F5a's documentation issue.
- **The EMEF age profile itself** (low). It is benchmarked against published totals and shares,
  never against a published figure by age.
- **The validation page's secondary tests** (low). The Barcelona-city test of the published model is
  the only reader-facing one among them, and the critic's spot checks of the cross-source numbers
  found them right.
- **The DGT regression's stability statements and its 2019 negative result** (low).

The critic also listed eleven points where attackers disagreed. The verifiers settled each one. The
section above describes those that bear on a published statement.

## Recommendations, in order

1. **Correct the Catalonia road-type paragraph** (C1). Restrict it to 2013–2015, or classify roads
   by name and kilometre point. Add the break to the coding breaks, and check the calculator's road
   levels.
2. **Restore the uncertainty that commit `268caf2` removed** (M1, M2). Put the sensitivity ranges
   beside the per-km ratios on the home page, the drivers page, Figure 1 and the driver-risk tool.
   Put the Madrid condition and 'the data do not establish' wherever the tool shows 75+ per km.
   Extend the editorial guard to the tool, and relax the tests that forbid the ranges.
3. **Refit the DGT location contrasts without the alignment term** (M3), and drop the 'largest
   location contrast' wording and check. While refitting, read Catalonia's 2024 'Otro' streets as
   streets, and give the wet-road figure without the Catalan surface coding.
4. **Restore the caveat on DGT's kilometre estimates** (M5): three estimation exercises, with a
   change of method in 2024. Report 2022–2023 as the only like-for-like step, drop 'points the other
   way', and replace the test that forbids the correct wording. Change the points-licence heading
   (M4) so that it no longer asserts that the fall did not last.
5. **Qualify the borderline and selective claims.** In particular:
   - the single 'beyond' on trends.html, with the VMP and motorcycle composition;
   - 'outside its range' for the 2023–2024 fuel trend;
   - the April 2020 per-tonne fall;
   - the Barcelona 'no better';
   - the dual-carriageway speed interval;
   - the illegal-manoeuvres run.
6. **Report the confounded crude comparisons with their adjusted values**: the sex ratios at equal
   age, the 18–29 per-km sex reversal, and the urban heavy-vehicle interaction in the calculator.
7. **Fix the numerical hygiene** that stops the committed model tables reproducing:
   - fit the lbfgs models to a tight tolerance and pin threads;
   - render the generated documents from the step the README lists;
   - correct methodology §17;
   - add a scheduled full-rebuild check to CI.

## Limits of this review

- **Scope.** The review examined the site and documents at `e593b6b`, working from the repository's
  raw files. It used publishers' documents from outside the repository in one place: DGT's 2023 and
  2024 kilometre reports behind M5. The verifier and the second checker fetched these from dgt.es
  themselves and checked them against the archived tables.
- **Time and judgement.** Each attacker had about thirty to fifty minutes. Absence of an issue for
  a finding means the attacks tried failed, not that none exists. Severity is a judgement on a
  stated scale, set by the verifiers and, for critical and major issues, by a second checker; the
  author may weigh some issues differently.
- **Evidence.** The verifiers' reproductions were run in the review's own working folders, which
  are not committed. The register records what each verifier ran and found, and the critical and
  major issues carry short reproduction snippets above.
- **Restart.** A container restart interrupted eight attackers and the rebuild. The attackers were
  run again from the start. The rebuild resumed from the interrupted step, after the four steps
  before it had finished.
