# Second independent audit (Task 22), dispositions

Four reviewers audited the branch after the editorial, design and statistical passes. This
record keeps what each examined and what became of its findings. The third review
([`THIRD_REVIEW_3af96b3.md`](THIRD_REVIEW_3af96b3.md)) later re-examined the integrated result.

## The commits examined

Reviewers worked in checkouts that start at `main` (d111da8), and the first brief named no
commit:

- The national reviewer audited d111da8, the live site. Its findings were checked against the
  build of the day; most were already fixed. It was rerun on f6968ca.
- The drivers reviewer noticed and reviewed 2339f2e, identical to f6968ca for its paths.
- The severity and documents reviewers were told to reset to f6968ca during their run.

Since then every brief names the commit and every reviewer records it.

## Drivers, vehicles, speed and recorded factors (2339f2e): no P0, 2 P1, 12 P2

- P1, "more likely too low": the evidence on both sides is now stated (df78867).
- P1, the survey covers at most about half of DGT's kilometres: the coverage and the
  assumption are stated, and coverage scenarios enter the range.
- P2: "supports" for 75 and over, "what sets older drivers apart", the killed-per-km range,
  the bootstrap width, long trips, the bounds for unknown ages, the per-km comparison of
  men and women, Madrid's measurement of 75 and over, a rounding (0.61 to 0.60), vehicles per
  crash: all fixed.
- P2, the Figure dr1 legend: fixed with the chart pass.
- P2, illegal manoeuvres +49% across 2016: not changed; the page says the level was reached by
  2017.

## National pages (f6968ca): no P0, 2 P1, 11 P2; every number recomputed from the raw files

- P1, counter-evidence missing on the home and trends pages: added (84ee283).
- P1, hospital admissions rise beyond ordinary variation only per tonne of fuel: stated, with
  the drift that would remove it.
- P2: the p-value floor, visitors and foreign drivers in the numerators, the opposite
  direction of DGT's kilometre series, 2023 partly estimated, a rounding (1.2 to 1.3), the
  road-ratio interval, the statistic confounded by the trend (DGT cited), a 0.52 wording, the
  speed table label, Figure 3's caption, Table 3's normal-quantile label, the twelve-month
  comparison not detrended: all fixed.

## Severity (2339f2e): no P0, 2 P1, 9 P2

- Nesting of the model's choices (F1 to F5, F8 to F10): the evaluation was rebuilt with every
  choice nested; the province intercepts, chosen outside the nest, were nested after the third
  review.
- The 2024 Catalan coding of streets inflating the "other road" odds ratio, the pedestrian
  profile with two vehicles, duplicated "urban street" rows: fixed.
- A posted limit recorded more often when fatal: not established; reported on the page.

## Documents (f6968ca)

- The DGT microdata audit (cells that do not apply, check 7) and the licence and source
  records were corrected by their own passes; the final report, the statistical audit and the
  claim ledger were brought up to the final results in the reconciliation after the third
  review.
