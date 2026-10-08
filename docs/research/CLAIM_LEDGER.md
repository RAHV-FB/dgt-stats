# Claim ledger

[`CLAIM_LEDGER.csv`](CLAIM_LEDGER.csv) lists 402 claims published on the site at the start of the
final audit (commit `4ce9e4b` and the builds before it), one row per claim, and 21 rows added
later (ledger-B|94–98 and ledger-E|1–16). Each row records:

- the page, source year, population, numerator, denominator and calculation;
- the code that computes the claim;
- an independent check, made by a reviewer who recomputed the claim from the raw or committed
  data without reusing the site's code;
- the audit result: `agree`, `wording` (the number is right but the sentence says more or less
  than it shows), `disagree`, or `not checked`;
- the claim's status after the corrections, with a note.

The claims were split among four reviewers by area:

| Ledger | Area | Claims |
|---|---|---|
| A | national trends, the home page and the summary findings | 82 |
| B | drivers, vehicles, speed and recorded factors | 93 |
| C | Catalonia, Barcelona, the crash-circumstances page and the 2006 points licence | 107 |
| D | models, validation, sources, methodology and the withdrawn notices | 120 |

## Result

| Audit result | Claims | Status after correction |
|---|---|---|
| agree | 329 | confirmed |
| wording | 47 | 44 corrected, 2 removed, 1 confirmed on recheck |
| disagree | 22 | 22 corrected |
| not checked | 4 | 2 confirmed, 1 corrected, 1 removed |

Each status was set by reading the rebuilt page, not by trusting the fix.

- **Corrected** means the page now says something different, given in the row's resolution.
- **Removed** means the claim is no longer published. The three removed claims are:
  - the former owner-age multiple ("nearly seven times");
  - an unsourced sentence about speed cameras;
  - the calculator's headline box, whose score now appears only in the method section.

Five of the 22 disagreements changed a result, not just its wording:

- **A double rounding:** one result table printed vans at 4.5 fatal crashes per billion km instead
  of 4.4.
- **A wrong ranking:** the Julys of the points-licence placebo test were ranked by z-score where
  the text described the percentage shortfall. July 2006 is third of 15, not fourth.
- **Model claims carried by a recording artefact (two claims):** the calculator's model ranked
  interurban crashes well and urban ones barely, and most of its skill was said to be on
  interurban roads. Both rested on recording categories that occur only in the training years. The
  model was refitted without the affected crashes and evaluated on the roads a reader can choose.
- **An estimate that was not one:** for roads through towns the calculator showed the province's
  observed average, which the page had called the model's estimate. It now says so.

The other seventeen were sentences that said more than the numbers show, or described them
wrongly:

- **Causal wording:** "mostly because crashes became less deadly".
- **Mismatched age bands:** the former "nearly seven times".
- **Stale cross-references:** the text quoted a score or a page that had since changed.
- **Wrong population:** a statistic computed on 2010–2022 was described as 2010–2023.
- **Coding artefact:** a dual-carriageway gap that comes from how the Catalan records are coded.
- **Inverted reading:** a calibration slope was read the wrong way round.
- **Factual errors in notices:** for example, the simulator's speeds were measured in Spain, not
  abroad.

The pages' build checks now guard each corrected claim; the build stops if a table no longer
supports the sentence.

The ledger describes the site as audited. Claims added later by the editorial pass are numbers
formatted from the same tables and are covered by the same build checks; they are not rows of
this ledger, except the principal ones listed in section E (below).

**Later revisions (October 2026).** The 75+ investigation revised rows ledger-B|4, 9 and 10 and
added rows 94–98 for the conditional estimate, the counts per licence holder, the men's marking
rule, the tiered sentence and the Barcelona check. The final audit then revised rows 26 and 27,
which still gave the first-published 75+ range as a finding, and rows 94, 97 and 98 (the Monte
Carlo error of the joint interval, the wording of the tiered sentence, the reason the Barcelona
check is inconclusive), and checked row 25 against the archived methodology report. The table
above counts the audit's own results and does not include these.

## Final status (October 2026)

The status column now gives each claim's fate on the final site, not only the audit's first
correction. Two reviewers re-read every row of sections A–D against the pages and tables built at
`0370825`; 164 rows changed status or resolution, and each changed resolution ends with the text
or table value that was checked ("Final check (0370825)"). The table above records the audit as
it was first run and is not updated.

| Status on the final site | Rows | Meaning |
|---|---|---|
| confirmed | 205 | the page still says it, with the same numbers |
| corrected | 148 | the page now says something different; the resolution gives the current text and, where it was found, the commit |
| revised | 38 | the page makes the same claim in substance, reworded, with values moved by later work (the distance corrections, the coverage scenarios, the method fixes of October 2026, the nested validation) or printed to a different precision |
| removed | 15 | no page makes the claim any more |
| added | 17 | rows added after the audit: one in section B and the sixteen of section E |

Most changes come from later work, not from errors the audit missed. The home page's model
finding was replaced (ledger-A|18–23). The trends intervals moved from a normal to a Student's t
distribution, so hospital admissions as a count are no longer beyond ordinary variation
(ledger-A|30–39 and 51–62). The driver-age rows (ledger-B|1–30) now give the final values: 18–29
2.53 (2.2–2.8; sensitivity range 1.49–3.63), 65 and over 1.19 (1.0–1.4; 0.85–1.82), 75 and over
0.97–3.20. The severity rows give the nested result, 0.739 against 0.709 on 11,611 crashes
(ledger-D). Resolutions that themselves quoted superseded figures were rewritten.

Section E adds the principal claims of the final site that had no row: the 75+ range and the
bounds left out of it, the split values, the coverage of DGT's kilometres and the age mixes that
set the ends of the ranges, the Monte Carlo precision rule, the nested severity result and its
calibration misses, the junction correction, three trend statements, the lowest 75+ combination
not at odds with men's driving, two points-licence results and the zone × road contrast. They
were checked against the committed tables at `0370825`, not recomputed from the raw files.
The ledger's `audit_note` column keeps what each reviewer found at the time, including figures
since superseded. Rows whose pages changed again after `0370825` (ledger-B|21, ledger-D|51 and
ledger-E|1, E|2 and E|6) were rechecked against the final pages after the final check of
`4735d9d` (`reviews/FINAL_CHECK_4735d9d.md`).
