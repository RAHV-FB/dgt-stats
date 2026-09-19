# Methodology

> **As built (September 2026).** This note was written before the data were audited. Each section
> keeps its original text and gains a status line: done (with where to see it), reframed (with what
> replaced it) or requires data the project does not have. The scope decisions are in
> [`analytics_plan.md`](analytics_plan.md); the results are on the site.

## 1. Units of analysis

**Status: reframed.** The public microdata are one row per injury crash; DGT does not publish the vehicle or person files, so only the `crashes` and `exposure` tables exist (`data/processed/accidentes.parquet`, the interim exposure tables). `roads` requires geometry that is not in the data; `interventions` became the two dated changes on the policy page.

DGT sources may describe different entities: crashes, vehicles, drivers, passengers and casualties. These units must remain separate until explicit keys and relationship cardinalities are documented.

Planned core tables:

- `crashes`: one row per recorded crash;
- `vehicles`: one row per vehicle involved in a crash;
- `people`: one row per involved person or casualty, depending on source coverage;
- `exposure`: denominator observations by time, geography, road or vehicle group;
- `roads`: road-segment and junction characteristics; and
- `interventions`: campaigns, enforcement periods and policy changes.

## 2. Outcomes and denominators

**Status: done.** Incidence and involvement rates per resident, licence holder, travel-weighted driver, registered vehicle and vehicle-kilometre are on the geography, older-drivers and vehicles pages; severity conditional on a crash is the severity page. Every rate states its numerator, denominator, geography and period.

The project will distinguish at least three questions:

1. **Crash incidence:** how often crashes occur relative to exposure.
2. **Crash involvement:** how often a road-user or vehicle group is involved relative to its exposure.
3. **Crash severity:** the probability or ordered level of injury conditional on a recorded crash.

Candidate metrics include crashes, serious injuries or fatalities per 100 million vehicle-kilometres; involvement per 10,000 registered vehicles; and casualties per 100,000 population. Each published rate must state its numerator, denominator, geography, period and inclusion rules.

## 3. Factor attribution

**Status: requires person-level data.** Neither alcohol nor speed is in the crash-level file, so the interaction model was not estimable. The speed page describes the police judgement the two aggregate sources record, with the share of drivers who have no record at all; the severity models use the crash circumstances instead.

Police-recorded contributory factors are observations, not complete causal explanations. Detection may depend on crash severity, enforcement practice, testing, survivorship and investigator judgement.

For alcohol and speed, the first model will estimate an interpretable specification such as:

```text
severity ~ alcohol + speed + alcohol:speed + road + weather + time + driver + vehicle controls
```

The interaction term tests whether the association of one factor changes in the presence of the other. It does not by itself establish that one factor caused the other or that either is the sole cause of the crash.

If alcohol plausibly changes speed choice, speed may act as a mediator. Estimating direct and indirect effects would require temporal ordering, confounder assumptions and stronger measurement than a basic crash record may provide. The project will state when that analysis is not identifiable.

## 4. Selection and missingness

**Status: done.** The five states are kept apart in every table, profiled by year on the data page, and enter the severity models as their own levels rather than being dropped; no complete-case analysis was run.

A database containing only crashes conditions on crash occurrence. Comparing alcohol-positive and alcohol-negative drivers within that database can answer questions about recorded crash characteristics or severity, but not the population risk of crashing without non-crash exposure data.

Missingness will be profiled by year, geography, severity and enforcement context. The following states must not be collapsed:

- negative or absent;
- not tested or not measured;
- unknown;
- not applicable; and
- structurally unavailable in a given year.

Complete-case analysis will not be the default if missingness is substantial or systematic. Sensitivity analyses and, where justified, multiple imputation will be considered.

## 5. Modelling sequence

**Status: done to step 6.** Steps 1 to 4 and 6 are the validation report, the descriptive pages, the rate pages and the severity models with calibration, holdout and per-year stability. Step 5's pre-specified interaction needed the missing person fields; step 7 was not reached, by design.

1. Validate source totals and schemas.
2. Produce descriptive distributions and missingness profiles.
3. Calculate exposure-adjusted rates with confidence intervals.
4. Fit transparent baseline models.
5. Add pre-specified interactions and nonlinear terms.
6. Check calibration, residual patterns, influential observations and temporal/geographic stability.
7. Compare predictive models only after a defensible baseline exists.

Likely methods include Poisson or negative-binomial models for counts, logistic or ordinal models for severity, multilevel models for geographic clustering and survival-style exposure models where appropriate.

## 6. Road design analysis

**Status: requires road data.** No coordinates, segment identifiers, traffic volumes or road attributes beyond type, junction, alignment, surface and lighting are available; those enter the severity models as covariates. Nothing on the list below was possible.

Road-design analysis requires a segment or junction denominator. Mapping crash points alone identifies concentrations of recorded crashes but may simply identify the busiest roads.

Planned approach:

- geocode or use supplied coordinates with documented accuracy;
- map crashes to road segments and junction influence areas;
- join traffic volume, speed limit and road attributes;
- account for spatial clustering and regression to the mean;
- compare observed counts with exposure-based expectations; and
- treat before/after infrastructure evaluations separately from cross-sectional associations.

## 7. Campaign and policy evaluation

**Status: done for two interventions.** The policy page runs an interrupted time series for the July 2006 points licence with placebo breaks and sensitivity fits, and a difference-in-differences series for the January 2019 speed limit against untreated roads, which fails its placebo. No campaign register exists, so no synthetic control or event study was attempted.

A simple comparison immediately before and after a campaign is vulnerable to seasonality, traffic changes and concurrent policies.

Preferred designs:

- interrupted time series with sufficient pre- and post-intervention observations;
- difference-in-differences with a defensible comparison group;
- synthetic control for a major geographically specific intervention; or
- event-study estimates that make pre-trends visible.

Each evaluation will define the intervention date, target population, expected mechanism, outcome window and possible spillovers before modelling.

## 8. Reproducibility and reporting

**Status: done.** Raw inputs are immutable and manifested, all logic is in `src/` and `scripts/` (no notebooks were written), 140 tests and 434 reconciliation checks run, every table and figure is generated, limitations sit beside the results, and the policy page's wording separates coincidence from attribution.

- Raw inputs are immutable.
- Cleaning logic belongs in `src/` or `scripts/`, not only in notebooks.
- Tests will enforce schemas, key uniqueness, value ranges and reconciliation totals.
- Random procedures use fixed seeds.
- Tables and charts are generated from code.
- Estimates include uncertainty and sample sizes.
- Limitations appear beside the relevant result, not only in a final disclaimer.
- Findings will be separated into descriptive evidence, model-based associations and causal estimates.
