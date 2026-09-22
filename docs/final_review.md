# Final review

Review date: 20 September 2026, after the nine phases of [`analytics_plan.md`](analytics_plan.md)
had been merged. One pass over the whole repository, not a diff: every page against its tables,
every method against its code, every document against the others, the sources against their
notices, and the writing itself. Each finding was checked again against the code and the data
before anything changed, and the checks below were run on the result. Nothing in this pass added
an analysis; it corrected, qualified or computed what was already there.

## 1. What was reviewed

Twelve passes, one each over: the statistical methods (`rates`, `models`, `policy`, `vehicles`,
`speed`, `summaries`) against `methodology.md`; the assumptions the analyses rest on, tested
against the microdata and DGT's own documentation; the page text against the result tables, in
three groups of pages; the readers and every code-to-label map against the DGT dictionary; the
documents against each other and against the code; the manifest, the reuse notices and the
licence; the writing, for anything that did not read as written by a person; the site's HTML and
CSS at phone and desktop widths and in print; the tests; and the build from a clean tree. A
second round covered what the first had reached only in passing: the coding breaks in the
microdata year by year, the figures one by one, the plan documents, and the numbers typed into
the page code rather than computed. Of 169 findings raised, 141 stood after re-checking; the rest
were withdrawn as inaccurate, immaterial or already stated on the page.

## 2. What changed

### Analyses

- **The 2019 case study** (policy page, `policy.py`). The two groups are now built from the raw
  road-type code: conventional roads (codes 5 and 6) against motorways and dual carriageways
  (codes 1 to 3). Code 5, "carretera convencional de doble calzada", had sat in the control group
  although it is a conventional road under the 2018 decree, and from 2021 most of its crashes are
  coded as 6, which had moved about 150 deaths a year from the control to the treated group inside
  the extended window and produced a spurious reversal of the estimate. Regrouped, the clean-window
  estimate is −13.1 % (−19.1 to −6.8), the extended fit −15.4 % (−20.8 to −9.7), and a placebo
  break in January 2017 gives +12.3 % (+1.3 to +24.6): the two groups did not move together before
  the limit, so the page still makes no claim, for that reason rather than the 2018 placebo it
  named before. The text of that section is now gated on the placebo intervals rather than on one
  date.
- **The severity models** (`features.py`, `models.py`). A field's explicit unknown code (weather 7,
  surface 9, alignment 4) is a level of its own, apart from "not specified" (999), as the standard
  says and as every descriptive table already did. The two profile labels that set a time band
  without saying so now name it. The fit halves a Newton step when the likelihood would fall and
  stops when the likelihood stops rising, which the 2019 per-year refit needed once two
  nearly coincident missing-state levels appeared in the same year; the published odds ratios are
  unchanged at the precision shown. The urban-motorway zone level and the junction field's 2023
  break are named on the page.
- **Vehicles per kilometre.** The denominator is DGT's circulating fleet (its "parque circulante",
  vehicles with an inspection, insurance, ownership or fine record in ten years), not the register;
  every column, tile and sentence says so. The comparison words ("less often", "about as often")
  follow the interval of the rate ratio, not the point estimate, which changes the heavy-truck
  occupant sentence. Quadricycles and agricultural tractors are placed where the kilometre table
  puts them, and a fourth limit states that the numerator counts foreign-registered vehicles while
  the denominator does not.
- **Older drivers.** The travel-weighted denominator's assumptions are on the page: ESRA samples
  adults 18–74, so the 75+ weight is an extrapolation; MOVILIA's oldest band is 65 and over, so the
  75+ band inherits the 65–74 intensity and the two ratios cannot be ordered against each other; the
  licence cap is not redistributed, so the estimate sums to 60 % of residents 15–74 in 2024 against
  the ESRA 76 %; the share is interpolated between the waves and held flat outside them. The
  sentence that attributed older drivers' fatality to the crash types they are in was removed,
  since no table gives crash type by driver age; the claim that the 65+ rate has been the highest
  since 2011 is computed and now reads 12 of 14 years.
- **Trends, timing, geography.** The deaths-per-crash claim was wrong (the ratio has been flat
  since 2015) and is computed with its range; the seasonality sentence counts the years; the timing
  paragraph computes the peak hours and compares weekend and weekday nights with their intervals in
  view and no longer offers a cause the data cannot show; the front page says "crashes in darkness"
  rather than "night hours"; the 2024 mixture in the "other road" row is stated beside the table;
  the rank-shift sentence on the geography page is computed for the two smallest provinces.
- **Speed.** The status table carries the "driving too slowly" column that the totals include, the
  duplicate column headers are named, and the report's rounded shares print as whole percentages.

### Figures and site

Tick labels are formatted from the tick values, so no two ticks share a label and zero is not
"+0%"; multi-series lines differ in dash or marker as well as hue; the two panels of the 2019
series share a scale; interurban and urban keep the same colours on every figure; the stability
figure says it excludes missing-state levels; every "n =" names its unit. The link colour meets
the contrast ratio for body text; captions wrap instead of clipping at phone width; prose columns
wrap while numeric columns stay on one line; wide tables print in full; figures scroll sideways on
a phone instead of shrinking their labels; images carry their dimensions; column headers are
unique; the footer names every source.

### Data and sourcing

The four ESRA reports were removed from `data/raw/`: Vias institute offers no reuse licence, and
the project needs two numbers from them, which are cited by report and URL. The manifest cites
direct file URLs where DGT serves them, describes every file in words, and records the publisher's
last-update date where the datos.gob.es record gives one. The DGT row of the reuse table says what
DGT's notice does and does not grant; the INE extract and the hand-typed survey file are named as
the two files that are not downloads; MOVILIA figures name the ministry. The ESRA 2018 share is
attributed to the online dashboard, where it comes from.

### Documents

`methodology.md` was rewritten as built earlier in this pass and then corrected against the code:
road groups quoted from the dictionary, night as lighting codes 4 to 6, the two-group design of
section 7, the vehicles numerator, the sensitivity list, the thresholds the page wording uses, and
the byte-for-byte claim qualified with the versions in `requirements.lock`. `data/README.md`,
`reports/README.md` and `scripts/README.md` describe what exists rather than what was planned. The
data inventory records the coding breaks found this time: the 2021 collapse of road-type code 5
into 6, the 2022 swap of codes 1 and 2, the 2023 junction break in Barcelona, the 2019 fall of the
urban-motorway zone code, and the alternating unknown codes in the Catalan provinces. The plan
documents lost the sentences that addressed a reader instead of describing the work.

### Code and tests

The descriptive result tables are written with ten significant digits (`analyse.py`) and the model
tables with six (`model.py`), so that library versions do not change them; the dependency floors
exclude a `pymupdf` without the import name used and a `statsmodels`
that does not import against `numpy` 2; two workbooks are closed after reading. Tests were added
for the profile table and predicted grid, for the assembly of every policy table, for the two
summaries that had none, and for the figure build; the synthetic model data are seeded per test;
the policy-page test pins the placebo wording to the table rather than copying the page's own
condition; the census-age check no longer exempts the unknown band.

### Licence and authorship

The code is under the MIT licence; the data files keep their providers' terms, listed in
[`data_sources.md`](data_sources.md). No notebooks are planned. The README and the data page
now say how the code was written: with Claude Code, Anthropic's coding assistant, from written
instructions and under the author's review, the sources, methods and published figures being the
author's responsibility.

## 3. Not changed

- The branches of the earlier phases still exist on GitHub. They were squash-merged and their
  history is of no further use; they should be deleted there.
- The heavy-truck rate remains a lower bound to the extent that agricultural tractors sit in its
  denominator, and the 75+ travel-weighted ratio a lower bound for the reasons above; both are
  stated, not corrected, because no source separates them.

## 4. Verification

- `ruff check` and `ruff format --check` clean; the test suite passes, the slow manifest check
  deselected as usual.
- `build_tables.py`, `model.py`, `analyse.py all` and `build_site.py` rerun from the interim
  layer; the committed tables, figures and pages are their output.
- Every page measured at 390 px and 1,280 px: no horizontal overflow, no caption wider than the
  viewport.
- The tool the code was written with is named in three places by design: the README's "How it was
  built", the last paragraph of the data page's Reproduce section (and the string in
  `src/dgt_stats/site.py` that renders it) and the "Licence and authorship" paragraph above. No
  other tracked file names it, the history of `main` names none, and no commit carries a
  generated-by or co-author trailer.

## 5. Second review, 22 September 2026

A second pass over the same ground and in the same shape as the first: the statistical methods and
the assumptions under them, the pages against their tables, the figures one by one, the readers and
every code-to-label map, the documents against each other and against the code, the manifest and
the reuse notices, the writing, the site's markup and stylesheet, the tests, the dependency floors
and the deploy workflow. Of 273 findings raised, 220 stood after re-checking each one against the
code, the tables or the raw files; the rest were withdrawn as inaccurate, immaterial or already
stated where they belonged. All 220 were fixed.

What that changed, in outline. The 2019 difference-in-differences columns and labels now say that
the estimate is the treated group's change relative to the control, which is what the interaction
is; no number moved. The severity page and section 5 of the methodology name all three exceptions
to keeping every level as its own: a level under 500 crashes merged into its reference, the
alignment "not applicable" code folded into "straight" because it is exactly the urban-street zone
and would otherwise duplicate the zone predictor, and a level with no event in a fit left out
instead of estimated — the last of which had been printing an empty estimate as text and a missing
marginal effect as zero. The year-stability selection now leaves out every missing-state level and
its per-year refits are clustered by province like the full model, so the figure's bands and the
counts in `q3_year_stability.csv` moved. The missingness profile counts the placeholders of the
fields that carry no code list — `KM` 9999 and, in 2019, 1000; `CARRETERA` "No inventariada"; the
`COD_MUNICIPIO` placeholder — as not observed, which removes an apparent improvement in km-post
recording in 2019, 2020 and 2022. The speed shares are no longer rounded before they are written,
so the pages format full precision. The 75+ travel-weighted ratio is no longer called a lower
bound, which supersedes the second item of section 3: counting passengers pushes it down, but the
2006 travel profile is frozen across the whole period and could move it either way, so the
direction of the net bias is not established and the page says that instead. The kilometre-table
coverage is stated against the register, where it was computed. The dependency floors are now a set
that can be installed together, and the
Pages workflow installs the locked versions on the interpreter the pages were built with. The
package version matches `pyproject.toml`. Three manifest rows cite the file URLs that serve the
bytes they describe, each downloaded and matched by SHA-256 before the row was touched, and the
reuse table gained the row for Fundación MAPFRE it was missing.

What stays unchanged. No analysis was added and nothing was recomputed for its own sake: the
full-model odds ratios are the same to the precision shown, and the 2006 and 2019 estimates are
the same numbers under better labels. The phase plans keep their dated records and were corrected
only where they state something the repository never did. The raw files are untouched, and so are
the `bytes` and `sha256` columns of the manifest: one candidate source URL was left as it was,
because the file behind it could not be fetched and checked. The checks in section 4 were run again
on the result.
