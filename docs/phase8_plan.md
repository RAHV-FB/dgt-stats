# Phase 8: publish

Plan date: 19 September 2026. Phase 8 is the last of the nine phases (0 to 8) of
[`analytics_plan.md`](analytics_plan.md): review the site as a whole, rewrite the README to match
what was actually built, and bring the documents that predate the results into line with them. No
new analysis. Same working rules: Python only, one commit per step on branch `phase-8`, `ruff` and
`pytest` before each commit, squash-merge at the end.

## 1. What needs publishing

The site has eleven pages answering the nine questions of the analytics plan, 434 reconciliation
checks, 137 tests and a Pages workflow that has deployed every merge since Phase 2. Around it, three
things are out of date:

- **The README** still opens with "early-stage portfolio project ... does not yet publish analytical
  results", describes the objective in the future tense, promises research tracks the data cannot
  support (alcohol × speed, road design, a campaign register) and lists "planned outputs" that are
  either done or dropped. The results paragraphs added phase by phase sit under those promises.
- **`docs/methodology.md`** was written before the data were audited: it plans vehicle and person
  tables, an alcohol × speed model and a road-segment analysis. The analytics plan said these should
  be marked "requires person-level data", not deleted.
- **`docs/data_sources.md`** lists the seed files of Phase 0; the INE population, the census tables
  2014–2025, the yearly and chapter workbooks 2014–2023, the MOVILIA, ECEPOV and EHMA extracts and
  the driving-activity file were added later and are only in `data_inventory.md` and `data/README.md`.

Two decisions are left open and flagged, not taken:

- **Licence.** The README says none has been chosen. The code could take a permissive licence (MIT or
  Apache-2.0); the DGT and INE data keep their own reuse terms, which the README will state either
  way. Nothing is added until one is chosen.
- **Notebooks.** The plan's notebook sequence (`00_source_audit` to `09_speed_context`) was never
  started because the scripts, the tests and the site took their place. The default is to say so in
  `notebooks/README.md` and the README rather than write ten notebooks that repeat the site.

## 2. Build steps

### Step 1 — Site review
- Read every page's prose against its tables and flag any sentence that is typed rather than
  computed and could go stale (the occupant-death series paragraph on the vehicles page and the
  timeline table on the policy page are the known ones); either compute the numbers or word them so
  a data update cannot contradict them.
- Overview page: add a "What the data say" digest, one computed line per page in the order of the
  navigation, so a reader who stops at the front page leaves with the findings; keep the tiles.
- Every page gets a `<meta name="description">` and a `<title>` of the form "Page · Road safety in
  Spain"; every image already has alt text (41 of 41), which the test will now enforce; the footer
  names the data vintage (microdata 2016–2024, yearbook 2024) rather than a build date, so rebuilds
  stay byte-identical.
- Data page: the "Reproduce" section lists the full command sequence including `model.py` and
  `ingest.py reports`, with the run times; the sources list matches the source register.
- Tests: every internal link and anchor resolves to a page or an id that exists, every `<img>` has
  a non-empty `alt`, every page has one `<h1>`, a description and no `<script>`.
- Headless screenshots of all eleven pages at 1280 px and 390 px, checked for overflow and for
  captions that wrap badly.

### Step 2 — README rewrite
- Structure: what this is (two sentences and the site link); what the site answers (a table of the
  nine questions with the page, the method and the one-line finding); what could not be done and why
  (the person-level fields, road design, the campaign register; one paragraph each, with the
  analytics plan's scope decisions as the reference); data (the source groups and the audit); how to
  reproduce (the command sequence with timings, the checks, the tests); project structure; what
  remains (the two user decisions and the person-level data request); data reuse terms.
- The "Analytical standards" list stays, reworded from "will" to what the site does, with a pointer
  to where each standard is visible (denominators on the rates pages, unknowns on the data page,
  intervals everywhere, the policy page's wording rule).
- The context citations (ERSO reports) stay in the "what could not be done" section as the reason
  the interaction question mattered, marked as European context, not Spanish results.

### Step 3 — Documents
- `docs/methodology.md`: an "As built" note at the top; each section keeps its text and gains a
  status line: done (with the page), reframed (with what replaced it), or requires person-level data.
  (Later superseded: the file was rewritten as built in the final review, replacing the planning
  text and its status lines; see [`final_review.md`](final_review.md).)
- `docs/data_sources.md`: the register completed with every file under `data/raw/` grouped as in
  `data_inventory.md`, each with coverage, role and the page that uses it.
- `docs/analytics_plan.md`: phase 8 row done; the notebook sequence section marked as replaced by the
  scripts and the site; section 6 (external data to add) updated for what was added.
- `notebooks/README.md`: the decision recorded. `data/README.md` and `docs/data_inventory.md`
  checked for stale counts.

### Step 4 — Repository metadata
- `pyproject.toml` version 1.0.0 and a description that matches; `.github/workflows/pages.yml` left
  as is (it builds from the committed tables and has deployed seven times) but documented in the
  README's reproduce section; the `site/` folder's role stated (committed output, rebuilt on push).
- Final full run from a clean interim layer (`ingest.py all --force`, `build_tables.py`, `model.py`,
  `analyse.py all`, `build_site.py`) to prove the sequence in the README works end to end and leaves
  no diff.

### Step 5 — PR, merge, verify
- PR; squash merge; the Pages deploy checked; the live site fetched once to confirm the front page,
  the digest and one figure are served; the stale branches listed; the two open decisions
  restated.

## 3. Outcome (19 September 2026)

All five steps are merged.

- Site: the front page carries a computed one-line digest per page; the road-users and vehicles
  pages compute their long-run sentences from the series; the data page lists the full reproduce
  sequence with timings and the data reuse terms; the front page has its own title. Three new tests
  check every internal link and anchor, every image's alt text, every page's description and title,
  and that the digest links every content page. All eleven pages render at 1280 px and 390 px with no
  horizontal overflow.
- README rewritten: what the site answers (nine questions, page, method, finding), what could not be
  done and why, the standards as applied, the data groups, the reproduce sequence, the structure,
  what remains. `docs/methodology.md` gained a status line per section (later rewritten as built in
  the final review, [`final_review.md`](final_review.md), which replaced the planning text and its
  status lines), `docs/data_sources.md` lists every raw file with its role and page,
  `docs/analytics_plan.md` is closed, `notebooks/README.md` records that no notebook was written
  and why.
- `pyproject.toml` at 1.0.0 with the unused notebook and geo dependencies dropped.
- The full sequence in the README was run from an empty interim layer: `ingest.py all` (314 s, 434
  checks passed), `build_tables.py`, `model.py`, `analyse.py all`, `build_site.py`. It reproduced
  every committed table, figure and page byte for byte in the environment that produced them
  (Python 3.11.15, pandas 3.0.6, numpy 2.4.6, scipy 1.17.1, statsmodels 0.15.0, matplotlib 3.11.2,
  scikit-learn 1.9.1, pyarrow 25.0.1, since recorded in `requirements.lock`); at the dependency
  floors the numbers agree to the printed precision but every figure differs in its matplotlib
  version string and tight-bbox geometry, as `docs/methodology.md`, section 10, records.
- One decision was left open at merge time and taken afterwards: the code was released under the
  MIT licence, as the README and `pyproject.toml` now record. The notebook question
  was settled in this phase itself: `notebooks/README.md` records that none were written and none
  are planned. Both are restated in [`final_review.md`](final_review.md).

## 4. Verification

- `pytest` 140, `ruff` clean, no diff after the clean rebuild.
- The live site at https://rahv-fb.github.io/dgt-stats/ answers with the front page and its digest.
