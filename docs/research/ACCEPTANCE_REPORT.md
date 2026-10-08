# Final acceptance report

Task 25 of the final audit. It records the state of the branch `cl/inspiring-wozniak-uqpemm`
(pull request [RAHV-FB/dgt-stats#25](https://github.com/RAHV-FB/dgt-stats/pull/25)) at commit
`53776a6`, the last commit that changed code, results or pages, against `main` at
`d111da8`, where the rebuild began. This report was added in the commit after it. Every figure
below comes from a committed table or from the document named beside it.

## 1. Overall status

**Ready for publication once the pull request is merged**, with the limitations in section 6.
Independent reviews were run in four rounds. In the last three, each reviewer worked on a
recorded commit and each P0 or P1 finding went to a separate verifier who tried to refute it:
- the second audit, of the branch after the editorial, design and statistical passes (f6968ca);
- the third review, of the integrated branch at 3af96b3, which found no P0 and twelve verified
  P1 findings;
- a focused recheck of the fixes at `417cf04`, which found no P0, one P1 and 26 P2 findings.
  The P1, a regression, was confirmed by its verifier: on phones the estimate line pinned to the
  foot of the screen could cover the control a keyboard user had just reached;
- a final check of every change since the recheck, at `4735d9d`, which found no P0 and one P1,
  reported by three reviewers and confirmed by each verifier: this report, which the records
  cited, was not yet committed. It found 27 P2 findings.

Every finding is fixed or set out, with its reason, in the review records (section 7). The full
test suite passes (587 tests, none skipped; section 5), and CI passes on the final commit (run
[37843708799](https://github.com/RAHV-FB/dgt-stats/actions/runs/37843708799), both jobs).

The site is published from `main` by `.github/workflows/pages.yml`, so the rebuilt pages are not
yet live. Deployment is verified after the merge (section 5).

## 2. Research and statistical audit

**Data issues corrected.**
- The Catalan provinces' junction flag (`NUDO`) in DGT's 2023–2024 records is inverted. It is
  now read the right way round wherever it enters a model, which moves the junction odds ratio
  from 0.75 to 0.69 (0.65–0.73) (`features.junction_codes`, `q3_junction_coding.csv`).
- Fields that do not apply to a crash are no longer counted as unrecorded. On its own, which
  fields are left unrecorded ranks fatal crashes with ROC-AUC 0.68, not 0.72, and the audit's
  check 7 fails narrowly (54%) (`dgt_audit_artefacts.csv`).
- Catalan crashes with an artefactual road owner (1,840) are left out of fitting and
  evaluation.
- Rates per resident use the 1 July population.

**EMEF issues corrected.**
- The distances of unbanded trips truncated the fitted distribution at the speed bound, which
  made them too short: by 10% overall and up to a third on long trips when the audit found it
  (`STATISTICAL_AUDIT.md`, corrections). Each now takes the mean of the distribution, bounded at
  80 km/h door to door.
- The 20-observation publication rule is enforced (`emef/publication.py`).
- The questionnaires and the methodology report behind the 75+ routing filter are archived
  with hashes.
- 154 structural checks pass, and fifteen published 2024 figures are reproduced to their
  rounding.
- The distance fit runs on one BLAS thread, which reproduces the committed tables on any
  machine.

**National exposure assumptions reviewed.**
- The EMEF's working-day driving, carried to Spain's population, accounts for 51% of DGT's
  289.8 bn car km (`risk_coverage.csv`).
- The central estimate gives the remaining km (weekends, professional driving and an
  unexplained part) the same age mix. The sensitivity range tests other measured mixes.
- Three allocations are reported as bounds outside the range, because their bias has a known
  direction: equal km per licence holder at every age, no driving at 65+ in the unexplained km,
  and km by the car owner's age.
- The Madrid profile is age-standardised to Spain's population before transfer.

**Older-driver conclusions verified or revised.**
- Per km driven, Spain 2024, against drivers aged 45–64:
  - 18–29: 2.53 (95% sampling interval 2.2–2.8; sensitivity range 1.49–3.63);
  - 65 and over: 1.19 (1.0–1.4; 0.85–1.82), so the direction is not established;
  - 75 and over: sensitivity range 0.97–3.20, conditional estimate 2.06 (1.6–2.6).
- The conditional estimate holds only on the assumption that people aged 75 and over drive as
  much less than those aged 65–74 as in Madrid in 2018. It is never printed without that
  condition. The data do not establish that drivers aged 75 and over are involved more often
  per km.
- Involvement, responsibility (not measured), deaths once involved (75+: 15.9 against 4.6
  per 1,000) and deaths per km are kept apart.
- The former owner-age figure is explained and replaced.

**Other claims corrected.** Every published claim at the start of the audit has a row in
[`CLAIM_LEDGER.csv`](CLAIM_LEDGER.csv) with its final status. The rebuild's verdicts in
[`STATISTICAL_AUDIT.md`](STATISTICAL_AUDIT.md) now carry a final-audit column. Examples:
- the speed ratio is now given by road type;
- the points-licence intervals are flagged as too narrow;
- the monthly forecast is withdrawn;
- the frequency and severity split is qualified.

**Results that remain uncertain.**
- The direction of per-km involvement at 65 and over and at 75 and over.
- The age mix of the half of DGT's km that the survey's working days do not cover.
- The calibration of the severity model in three province-by-zone cells, in 2016 and in two
  provinces as a whole.

## 3. Machine learning

| Item | Result |
|---|---|
| Active model and target | Penalised logistic regression with an intercept per zone and province (model `924e1606d1d6`); the target is whether a Catalan crash with a death or serious injury was fatal within 24 hours |
| Real validation performance | Nested rolling origin, 2016–2023: each year is predicted by a model whose penalty, specification, through-town rule and province intercepts were chosen, and whose coefficients were fitted, on earlier years only. ROC-AUC 0.739 (0.725–0.753) on 11,611 crashes |
| Baseline comparison | Road × crash-type table 0.709; gain 0.030 (paired interval 0.021–0.040); boosted trees 0.748 |
| Calibration | Slope 1.03; mean predicted 12.4% against 12.3% observed; all ten groups of predicted risk inside the observed 95% interval. Misses: 2016, urban streets (outside Barcelona city in particular), the provinces of Barcelona and Girona, and three province-by-zone cells, all named on the pages |
| Geographic limitations | Tested only within Catalonia. A province left out scores 0.68–0.77, with the fatal share missed in three of four. National use is not established |
| Prediction engine verification | The browser engine reproduces the Python predictions and their intervals to 10⁻¹⁰ (`tests/test_severity_engine.py`, over 300 scenarios under Node) |
| Interactive calculator tests | `tests/test_site_browser.py` (125 cases in Chromium, among them the calculator's): engine against Python; comparison; refusals; warnings; keyboard; phone layout; the pinned estimate line never covering the focused control; a link to the calculator landing on it; no-script fallback. In the third review, 69 combinations entered through the page's controls and 2,000 random scenarios through its engine matched an independent Python refit (largest difference 9.0e-9, the export's rounding), and five keep-and-compare pairs matched `compare_exported` |

Earlier figures are superseded:
- 0.772 against 0.745, on 12,961 crashes including the artefact;
- 0.743 (not nested);
- 0.741 (nested but without the province choice).

The research-only models and the removed ones are listed in [`ML_MODEL_REVIEW.md`](ML_MODEL_REVIEW.md).

## 4. Writing and design

**Pages consolidated or removed.**
- Navigation is by question: Over time; Drivers, vehicles and factors; Crash severity; Data
  and methods.
- Five analyses that drew results from published coefficients are withdrawn notices: the
  speed simulator, distraction, alcohol and drugs, enforcement, and the monthly forecast.
- Three moved pages redirect.
- Only tables a page links are published.

**Major editorial changes.**
- Each page opens with its answer.
- Every number is formatted from a table and guarded at build time.
- One wording per evidence tier is shared by every page that states the 75+ conclusion.
- Sampling intervals, sensitivity ranges and conditional estimates are defined on the
  methodology page and linked at first use.

**Confusing explanations corrected.**
- "The survey accounts for half of DGT's km" now says what is carried and how.
- "Whatever the assumption" read as "under no assumption".
- The penalty C was described backwards.
- A calibration miss printed as a hit.
- The validation table's "passed" now reads "ranking held".
- A change note described unpublished versions instead of the live page.
- Intervals wholly on one side of 1 printed as reaching it (men against women per km now
  0.86–0.98).
- Two calibration misses (urban streets outside Barcelona city; Barcelona's urban streets on the
  validation page) were not named as misses.

**Unnecessary design elements removed.**
- Key-figure tiles, compare blocks and decorative typography.
- A second typeface.
- Uppercase labels.

**User-experience improvements.**
- Phone versions of every chart.
- An estimate line pinned to the foot of the screen in the calculator on phones.
- No dark-theme chart frame below 64rem, so a chart is as wide in dark as in light.
- The pinned estimate line never covers the control in use, and shows the comparison when a
  crash is kept.
- Outlined sensitivity bands.
- Charts that draw a zero share whole.
- A favicon, which removes the only console error.
- The calculator's warnings and notes read correctly for every input, for single counts and for
  more than one warning.
- A link to the calculator lands on it, although it is shown only once its model loads.

## 5. Technical verification

| Check | Result |
|---|---|
| Tests run | `REQUIRE_BROWSER=1 pytest`: 587 passed, none skipped, one slow test deselected. The local run found one failure, a footer over its length limit; it was fixed before the commit and the site, engine and browser tests were rerun (198 passed), and CI ran the full suite on the commit. `pytest -m slow` (raw-file hashes): passed. `ruff check`, `ruff format --check`: clean |
| Failures fixed | Tests updated for deliberate wording changes; a browser-test skip that hid a missing build now fails; tables reject format keys for missing columns; the design test's disclosure patterns missed disclosures with an id; new browser tests for the pinned line, the dark chart frame and the calculator link, each shown to fail without its fix |
| Clean build | The national, EMEF and driver-age tables reproduce byte for byte from the raw files (the EMEF and exposure scripts run on one BLAS thread). In the third review's rebuild, a severity refit moved two tables (`sev_geography`, `sev_penalty`) in the sixth decimal (solver noise). The committed pages equal a fresh build and the build writes no uncommitted page, which CI and the Pages workflow check; CI also checks that every table and document it regenerates under `reports/` and `docs/` equals the committed copy |
| Browser testing | 125 Chromium cases, run in CI and in the Pages workflow before deploying. The third review swept 24 pages at 12 widths (320–1280 px) with no horizontal overflow and no console errors; the final check crawled the 24 pages at 360 and 1366 px in both themes and tabbed through the calculator at nine sizes with no focused control covered |
| Deployment status | Not deployed. `.github/workflows/pages.yml` publishes from `main`, so the rebuilt pages go live when the pull request is merged; the live pages are then checked against the committed `site/` at `53776a6` |
| Final commit | `53776a6` |

## 6. Remaining limitations

**Inaccessible external data:**
- The EMEF's own 65–74 and 75+ tabulations. A request to the Institut Metròpoli and the ATM is
  prepared but not sent ([`EMEF_DATA_REQUEST.md`](EMEF_DATA_REQUEST.md)).
- A national all-days driving survey by exact age, which does not exist.
- The RACC 2013 figures, which are quoted but cannot be archived (no reuse licence).
- The EMEF 2021 distance report, whose values are transcribed.

**Methods left as they are, and disclosed:**
- The Barcelona-area survey's km at 65 and over are not standardised to Spain's ages, as
  Madrid's are; the drivers page says so, and standardising would lower the 65+, 65–74 and 75+
  figures by under 1% (0.85% under the Madrid split).
- The four sub-area profiles of the Barcelona-area survey are split between 65–74 and 75 and
  over with the province's population, an approximation: no population by single age is
  archived for Barcelona city or the other sub-areas. Barcelona city's profile sets the lowest
  75+ combination not at odds with men's driving.
- The test of Barcelona city from the rest of Catalonia keeps the published model's design, a
  starting level for each province and kind of road, refitted without the city's crashes; the
  choice to have them was made on years that include the city's crashes. The page says so.

**Incomplete or accepted work:**
- Chart text falls below 11 px for every chart at 320 px (down to about 9.6 px), for one chart
  at 360 px (10.9 px) and for most of the wide charts from 641 to about 960 px (down to about
  10.2 px), where nine of them also scroll sideways at 768 px. It follows from the figure scales
  and the breakpoint shared by every chart; the fix is site-wide.
- Merging retires 32 table and figure URLs of the live site. 25 of the files stay in the
  repository's `reports/` folder; the other seven (six figures of withdrawn analyses and
  `q7_breakeven_km.csv`) were deleted and remain in the repository's history. There is no 404
  page, because GitHub Pages serves it at any depth, where the site's relative links would
  break.
- The Pages workflow runs its own checks of the pages (the page diff, the site, engine and
  browser tests) rather than waiting for the Checks workflow. Its actions are pinned to tags,
  not commit SHAs, and Playwright and its dependencies are installed by version, without the
  hashes that `requirements.lock` gives everything else. Four engine tests need the regional
  feature layer and run only in the Checks workflow.
- Scripts and styles carry no version in their URLs; GitHub Pages lets browsers cache them for
  ten minutes.
- The published column `calibration_intercept` is the calibration-in-the-large offset in the
  `ml_*` tables and `gen_calculator_transfer` (`microdata/ml/modelling.calibration_fit`), and
  the intercept of the joint recalibration fit in the `review_*` and `sev_*` tables
  (`model_review.calibration_fit`).
- The check that the cross-source models use only validated DGT fields needs the harmonised
  tables, which only the source models' step writes, so CI skips it.
- The drivers page opens with one long paragraph, which keeps the 75+ figures beside their
  range and condition and involvement apart from deaths and responsibility.

## 7. Audit evidence

The review records are [`reviews/SECOND_AUDIT.md`](reviews/SECOND_AUDIT.md),
[`reviews/THIRD_REVIEW_3af96b3.md`](reviews/THIRD_REVIEW_3af96b3.md),
[`reviews/RECHECK_417cf04.md`](reviews/RECHECK_417cf04.md) and
[`reviews/FINAL_CHECK_4735d9d.md`](reviews/FINAL_CHECK_4735d9d.md). The last three list every
finding, with the commit reviewed, its disposition, and what each reviewer checked and found
correct.
The claim ledger ([`CLAIM_LEDGER.md`](CLAIM_LEDGER.md)) gives the final status of every
published claim, and [`STATISTICAL_AUDIT.md`](STATISTICAL_AUDIT.md) the final status of each
verdict.

### Task matrix

The third review's audit-process reviewer graded every task at 3af96b3. The last column gives
the status at `53776a6` and what changed it. "Done" means there is evidence in the
repository that a reader can check. "Partial" means part of the task has no record or is left
undone, as stated.

| Item | At 3af96b3 | Final status and evidence | What remains |
|---|---|---|---|
| T1 Completion of previous development | Partial | Partial. `AUDIT_BASELINE.md` records `main` at `d111da8`, the 299-test baseline and the build commands; `FINAL_REPORT.md` holds the rebuild's 20 points; `data/raw/manifest.csv` hashes every raw file (`pytest -m slow`) | No record pins the commit at which the final audit began; the claim ledger was read at `4ce9e4b` |
| T2 Dependency map and claim ledger | Partial | Done. `CLAIM_LEDGER.csv` and `.md` give every row a final status, with rows for the claims added after `4ce9e4b` (coverage, nested validation, junction, 75+) (32d33c3) | `DEPENDENCY_MAP.md` is a snapshot at `d111da8` |
| T3 Source interpretation | Done | Done. Not-applicable fields (067aaeb), the inverted Catalan junction flag (e179eb2), 482 of 482 reconciliation checks in a clean rebuild | The 24-hour (Catalonia) and 30-day (DGT) death definitions differ; disclosed |
| T4 EMEF processing | Done | Done. 154 checks, fifteen published figures reproduced, the 20-observation rule; byte-identical rebuild | Public files carry no sampling units, so the bootstrap ignores clustering; disclosed |
| T5 Driving distance | Done | Done. Interval-censored distances; truncation fixed; one BLAS thread (93edb1f) | The 1.45 road ratio is transcribed from an unarchived 2021 report |
| T6 National extrapolation and day types | Done | Done. Coverage 146.5 of 289.8 bn km; the Madrid profile age-standardised; owner-age km and two other allocations as bounds (eb7b70f, 316a52f) | Half of DGT's km has no measured age mix |
| T7 Driver-age findings | Done | Done. 18–29 2.53 (2.2–2.8; 1.49–3.63); 65+ 1.19 (1.0–1.4; 0.85–1.82); 75+ 0.97–3.20, conditional 2.06 (1.6–2.6) | Direction at 65+ and 75+ not established |
| T8 Responsibility | Done | Done. Quasi-induced exposure is not feasible with public data; stated on the page | No driver-level fault data |
| T9 Re-evaluate every model | Done | Done. Nested rolling origin, now including the province choice (fe7a76e): 0.739 (0.725–0.753) against 0.709 | Regional source models not refitted by the third review |
| T10 Interactive tool | Done | Done. Engine parity to 10⁻¹⁰; 125 browser tests in Chromium; an estimate line pinned on phones (6632d95), which shows the comparison when a crash is kept and never covers the focused control (the recheck's P1, fixed, tested, and confirmed over 5,264 focus records in the final check); a link to the calculator lands on it | No automated test of Reset; the interval covers coefficient uncertainty only (disclosed) |
| T11 ML page | Done | Done. The 2016, urban-street, provincial and cell misses are named on the page (fe7a76e) | — |
| T12 Rest of the site | Done | Done. `STATISTICAL_AUDIT.md` carries a final-audit column (32d33c3) | — |
| T13 Signs of AI writing | Partial | Partial. The outcome is in the per-page editorial commits and the template-furniture tests | No record of the review itself |
| T14 Sentence-by-sentence pass | Partial | Partial. The 75+ additions were edited after the third review (4f8ac06, e74cd57) | The drivers page opens with one long summary paragraph |
| T15 Information architecture | Done | Done. Navigation by question; README page table matches (4a26a40) | — |
| T16 Design audit | Partial | Partial. The third review, the recheck and the final check examined the pages at 320–1366 px in both themes; the dark chart frame no longer narrows charts below 64rem | Wide charts show text under 11 px, and some scroll sideways, between 641 and about 960 px; no design-review report from the rebuild |
| T17 Figures and tables | Partial | Partial. Unknown format keys fail the build; zero shares drawn whole; a figure is as wide in dark as in light (browser test) | Chart text below 11 px at 320 px, on one chart at 360 px and on most wide charts from 641 to about 960 px, where some scroll |
| T18 Reader experience | Not evidenced | Evidenced by the third review only: each of the nine reader tasks is answered within two clicks of the home page | No usability record from the rebuild |
| T19 Technical audit | Partial | Done. CI and the Pages workflow check that the committed pages equal a fresh build and that the build writes no uncommitted page (93edb1f, recheck); CI checks that every regenerated table and document under reports/ and docs/ equals the committed copy; `source_comparison` regenerated (c1ef923); both scripts that refit the distance model run on one BLAS thread | A severity refit can move two tables in the sixth decimal |
| T20 Browser testing | Done | Done. `REQUIRE_BROWSER=1` fails when the site is not built (4a26a40); new tests of the pinned line at four sizes, of the dark frame at 360 and 768 px and of the calculator link, each shown to fail without its fix | The phone figure test checks text size at 390 px only |
| T21 Performance and deployment | Partial | Partial until the merge. Deployment runs the site tests, the engine tests and the browser tests first, with a 20-minute limit (93edb1f, recheck, final check) | Not deployed until the merge; the Pages workflow does not wait for the Checks workflow; actions pinned to tags; Playwright installed without hashes; scripts and styles carry no version in their URLs (Pages caches them for ten minutes) |
| T22 Second independent audit | Partial | Done. `SECOND_AUDIT.md` records the second audit; `THIRD_REVIEW_3af96b3.md` seven reviewers on 3af96b3; `RECHECK_417cf04.md` three reviewers and a verifier on 417cf04 (one P1, fixed); `FINAL_CHECK_4735d9d.md` five reviewers and three verifiers on 4735d9d (one P1, this report, now committed) | The second audit's reviewer SHAs, except f6968ca, were not kept |
| T23 Verify the audit process | Partial | Done. The audit-process reviewer's matrix, updated here; the final check verified the recheck's dispositions and found three that it corrected | — |
| T24 Cleanup | Partial | Partial until the merge. All 164 commits since `d111da8` are under the owner's identity with no co-author lines; stale documents reconciled (32d33c3) | Not deployed until the merge |
| T25 Acceptance report | Not evidenced | Done. This document, committed after the final check that found it missing | — |
| Priority 1: numerical consistency | Partial | Done. Ledger and documents reconciled (32d33c3); the final check's scan found a few passages still stale, which the last fixes corrected (53776a6) | — |
| Priority 2: coverage of DGT km | Done | Done. Ranges rebuilt with the standardised profile and the bounds outside them | The unexplained km cannot be given an age mix |
| Priority 3: 75+ interpretation | Done | Done. One wording per evidence tier on every page (`OLDER_CONCLUSION`) | — |
| Priority 4: ML independence and calibration | Done | Done. Every choice nested, including the province intercepts; misses on the page | — |
| Priority 5: reviews and integration | Partial | Done. Exposure fixes merged (0370825) and rebuilt; every reviewer recorded its SHA; the recheck at 417cf04 and the final check at 4735d9d each found one P1, both fixed | The fixes made after the final check were checked by the test suite and CI, not by another review round |
| 75+ step 1: conditional estimate | Done | Done. 2.06 (1.6–2.6), the Madrid survey's sampling error included; the page says the survey's 65+ km are not standardised to Spain's ages (under 1%) | Ignores EMEF clustering; disclosed |
| 75+ step 2: assumptions behind the ends | Done | Done. `risk_older_decomposition.csv`; bounds kept outside the range | — |
| 75+ step 3: CRTM ESM2024 | Done | Done. Validation only (ages capped at 80, aggregate tables) | No archived copy of its documents |
| 75+ step 4: EMEF strata and other sources | Partial | Partial. RACC on the sources page and in the figure sources (4f8ac06); MOVILIA 2006/2007 recorded | The EMEF request is prepared, not sent |
| 75+ step 5: no artificial narrowing | Done | Done. The home page no longer argues from scenario counts | — |
| 75+ step 6: visualisation | Done | Done. Figure 1 shows counts, conditional estimate, intervals and bands | Text under 11 px at tablet widths (section 6) |
| 75+ step 7: range, estimate and missing data | Partial | Done. The drivers page names the data that would narrow the range (10e83cb) | — |
