# Methodology

## 1. Units of analysis

DGT sources may describe different entities: crashes, vehicles, drivers, passengers and casualties. These units must remain separate until explicit keys and relationship cardinalities are documented.

Planned core tables:

- `crashes`: one row per recorded crash;
- `vehicles`: one row per vehicle involved in a crash;
- `people`: one row per involved person or casualty, depending on source coverage;
- `exposure`: denominator observations by time, geography, road or vehicle group;
- `roads`: road-segment and junction characteristics; and
- `interventions`: campaigns, enforcement periods and policy changes.

## 2. Outcomes and denominators

The project will distinguish at least three questions:

1. **Crash incidence:** how often crashes occur relative to exposure.
2. **Crash involvement:** how often a road-user or vehicle group is involved relative to its exposure.
3. **Crash severity:** the probability or ordered level of injury conditional on a recorded crash.

Candidate metrics include crashes, serious injuries or fatalities per 100 million vehicle-kilometres; involvement per 10,000 registered vehicles; and casualties per 100,000 population. Each published rate must state its numerator, denominator, geography, period and inclusion rules.

## 3. Factor attribution

Police-recorded contributory factors are observations, not complete causal explanations. Detection may depend on crash severity, enforcement practice, testing, survivorship and investigator judgement.

For alcohol and speed, the first model will estimate an interpretable specification such as:

```text
severity ~ alcohol + speed + alcohol:speed + road + weather + time + driver + vehicle controls
```

The interaction term tests whether the association of one factor changes in the presence of the other. It does not by itself establish that one factor caused the other or that either is the sole cause of the crash.

If alcohol plausibly changes speed choice, speed may act as a mediator. Estimating direct and indirect effects would require temporal ordering, confounder assumptions and stronger measurement than a basic crash record may provide. The project will state when that analysis is not identifiable.

## 4. Selection and missingness

A database containing only crashes conditions on crash occurrence. Comparing alcohol-positive and alcohol-negative drivers within that database can answer questions about recorded crash characteristics or severity, but not the population risk of crashing without non-crash exposure data.

Missingness will be profiled by year, geography, severity and enforcement context. The following states must not be collapsed:

- negative or absent;
- not tested or not measured;
- unknown;
- not applicable; and
- structurally unavailable in a given year.

Complete-case analysis will not be the default if missingness is substantial or systematic. Sensitivity analyses and, where justified, multiple imputation will be considered.

## 5. Modelling sequence

1. Validate source totals and schemas.
2. Produce descriptive distributions and missingness profiles.
3. Calculate exposure-adjusted rates with confidence intervals.
4. Fit transparent baseline models.
5. Add pre-specified interactions and nonlinear terms.
6. Check calibration, residual patterns, influential observations and temporal/geographic stability.
7. Compare predictive models only after a defensible baseline exists.

Likely methods include Poisson or negative-binomial models for counts, logistic or ordinal models for severity, multilevel models for geographic clustering and survival-style exposure models where appropriate.

## 6. Road design analysis

Road-design analysis requires a segment or junction denominator. Mapping crash points alone identifies concentrations of recorded crashes but may simply identify the busiest roads.

Planned approach:

- geocode or use supplied coordinates with documented accuracy;
- map crashes to road segments and junction influence areas;
- join traffic volume, speed limit and road attributes;
- account for spatial clustering and regression to the mean;
- compare observed counts with exposure-based expectations; and
- treat before/after infrastructure evaluations separately from cross-sectional associations.

## 7. Campaign and policy evaluation

A simple comparison immediately before and after a campaign is vulnerable to seasonality, traffic changes and concurrent policies.

Preferred designs:

- interrupted time series with sufficient pre- and post-intervention observations;
- difference-in-differences with a defensible comparison group;
- synthetic control for a major geographically specific intervention; or
- event-study estimates that make pre-trends visible.

Each evaluation will define the intervention date, target population, expected mechanism, outcome window and possible spillovers before modelling.

## 8. Reproducibility and reporting

- Raw inputs are immutable.
- Cleaning logic belongs in `src/` or `scripts/`, not only in notebooks.
- Tests will enforce schemas, key uniqueness, value ranges and reconciliation totals.
- Random procedures use fixed seeds.
- Tables and charts are generated from code.
- Estimates include uncertainty and sample sizes.
- Limitations appear beside the relevant result, not only in a final disclaimer.
- Findings will be separated into descriptive evidence, model-based associations and causal estimates.
