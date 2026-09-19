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

Two decisions belong to the user and are flagged, not taken:

- **Licence.** The README says none has been chosen. The code could take a permissive licence (MIT or
  Apache-2.0); the DGT and INE data keep their own reuse terms, which the README will state either
  way. Nothing is added until the user chooses.
- **Notebooks.** The plan's notebook sequence (`00_source_audit` to `10_speed_context`) was never
  started because the scripts, the tests and the site took their place. The default is to say so in
  `notebooks/README.md` and the README rather than write eleven notebooks that repeat the site.

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
  the digest and one figure are served; the stale branches listed for the user; the two open
  decisions restated.

## 3. Verification

- `pytest` (with the new site tests), `ruff`, `analyse.py all` and `build_site.py` idempotent after
  the clean rebuild.
- Every README command runs as written from the repository root.
- The live site serves every page listed in the navigation.
