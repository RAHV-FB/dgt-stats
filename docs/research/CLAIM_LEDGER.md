# Claim ledger

[`CLAIM_LEDGER.csv`](CLAIM_LEDGER.csv) lists 402 claims published on the site at the start of the
final audit (commit `4ce9e4b` and the builds before it), one row per claim. Each row records:

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
formatted from the same tables and are covered by the same build checks. They are not rows of
this ledger.
