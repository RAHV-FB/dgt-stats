# Model card: Catalan crash-severity calculator

Written by hand, unlike the other cards here. It says what the model is and where its evidence
is; every number is in [`SEVERITY_CALCULATOR.md`](../research/SEVERITY_CALCULATOR.md) and is not
repeated here.

**Status:** the published model, behind the calculator on the site's models page. It was built and
decided by the independent model review ([`ML_MODEL_REVIEW.md`](../research/ML_MODEL_REVIEW.md)),
not by the decision rules of [`MODEL_DECISIONS.md`](../MODEL_DECISIONS.md), whose table lists it
with a pointer to its evidence. It replaced the original Catalan model
([`catalonia_fatal_severity.md`](catalonia_fatal_severity.md)), retired because its strongest
predictor recorded how a crash was documented rather than the road.

## Task

Among crashes in Catalonia in which someone was killed or seriously injured, how does the share
that were fatal vary with the recorded road, conditions and crash?

- **Observation (one row):** one crash with at least one death or serious injury in the Servei
  Català de Trànsit file, 2010–2023, on a road a reader can choose. The crashes whose road owner is
  recorded as "Altres" or left blank on interurban conventional roads, a recording artefact, are
  left out of fitting and of evaluation.
- **Target:** fatal (someone died within 24 hours) rather than serious, as the source file defines
  it.
- **Method:** penalised logistic regression (`src/dgt_stats/severity_model.py`,
  `scripts/severity_calculator.py calculator`), exported to `reports/models/severity_model.json`;
  the page's engine (`src/dgt_stats/site/assets/severity-engine.js`) reproduces its predictions and
  their intervals.
- **Inputs:** circumstances a reader can describe: province, zone and road, crash type, road users
  and how many, lighting, weather, surface, junction, posted limit and time of day
  ([`SEVERITY_CALCULATOR.md`](../research/SEVERITY_CALCULATOR.md), "Inputs" and "Specification").

## Evidence

- **Benchmark and ranking:** a table of road by crash type, scored on the same records; each year
  2016–2023 predicted by a model fitted only on the years before it, and a later-year holdout
  ("Choice of model" and "Validation" in `SEVERITY_CALCULATOR.md`; `reports/tables/sev_*.csv`).
- **Calibration:** predicted against observed shares on years the model was not fitted on
  (`sev_calibration.csv`).
- **How far it reaches:** later years and other provinces of Catalonia; no other source records its
  inputs in the same way, and Catalonia's severe crashes differ from Spain's
  ([`GENERALISABILITY.md`](../GENERALISABILITY.md); `ml_outward_path.csv`, model `calculator`).

## Valid interpretation

- The share of similar recorded crashes with a death or serious injury that were fatal, for a
  described combination of circumstances in Catalonia, with its interval.

## Invalid interpretation

- The chance that a crash happens, or any risk per trip or per kilometre: the data hold only
  crashes.
- The effect of changing a road or a condition: a difference between two scenarios is an
  association in these records.
- Severity outside Catalonia, or among crashes with only slight injuries.

## Limitations

See "What the model shows" and "Limitations" in
[`SEVERITY_CALCULATOR.md`](../research/SEVERITY_CALCULATOR.md).
