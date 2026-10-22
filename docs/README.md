# Documents

The documents follow the project's five sections. Start with the
[catalogue](catalogue.md), which maps every source to the tables that read it and every table to
the page that publishes it; the [methodology](methodology.md) says how every result is made.
Documents marked *generated* are written by the pipeline stage named beside them and must not be
edited by hand; the others are written by hand.

| Document | What it holds | Written |
|---|---|---|
| [`catalogue.md`](catalogue.md) | the map: sections, sources, stages, tables and pages | generated (`sources.catalogue`) |
| [`methodology.md`](methodology.md) | how every result is produced, section by section, with the assumptions tested | by hand |

## Sources and methods (`sources/`)

| Document | What it holds | Written |
|---|---|---|
| [`contract.md`](sources/contract.md) | the rules: what each dataset may be used for, joined to and never joined to | by hand |
| [`register.md`](sources/register.md) | the source register: every file, its publisher, its reuse terms and where it appears | by hand |
| [`raw_file_inventory.md`](sources/raw_file_inventory.md) | every raw file profiled: format, encoding, rows, columns, unit | generated (`sources.inventory`) |
| [`source_comparison.md`](sources/source_comparison.md) | how each crash source came to exist, against the same questions | generated (`sources.profile`) |

## National statistics (`national/`)

| Document | What it holds | Written |
|---|---|---|
| [`file_audit.md`](national/file_audit.md) | the audit of the national files: what each contains and supports, and the checks run | by hand |

## Drivers (`drivers/`)

| Document | What it holds | Written |
|---|---|---|
| [`driver_age_exposure.md`](drivers/driver_age_exposure.md) | car-driving kilometres by age from the travel surveys, and crashes per kilometre by age | by hand |
| [`emef_inventory.md`](drivers/emef_inventory.md) | the EMEF survey files, their harmonisation and checks | by hand |
| [`emef_data_request.md`](drivers/emef_data_request.md) | a prepared, unsent request for finer EMEF age tables | by hand |

## Catalonia and Barcelona (`regional/`)

| Document | What it holds | Written |
|---|---|---|
| [`data_quality.md`](regional/data_quality.md) | keys, cardinality, placeholders and checks of the regional crash files | generated (`regional.quality`) |
| [`barcelona_vehicle_audit.md`](regional/barcelona_vehicle_audit.md) | why Barcelona's vehicle rows are not used as unique vehicles | generated (`regional.quality`) |

## Severity model (`models/`)

| Document | What it holds | Written |
|---|---|---|
| [`severity_calculator.md`](models/severity_calculator.md) | the published crash-severity model behind the calculator | by hand |
| [`review.md`](models/review.md) | the independent re-evaluation of every model | by hand |
| [`decisions.md`](models/decisions.md) | every model's decision by rules declared in advance | generated (`models.validate`) |
| [`generalisability.md`](models/generalisability.md) | representativeness and transfer tests, measured separately | generated (`models.validate`) |
| [`dgt_microdata_audit.md`](models/dgt_microdata_audit.md) | whether the DGT microdata may train a model (they may not) | generated (`models.validate`) |
| [`leakage_audit.md`](models/leakage_audit.md) | which variables each model may use | generated (`models.fit`) |
| [`cards/`](models/cards) | one card per model, the retired and withdrawn ones included | generated (`models.fit`, `national.cards`), except the calculator's |

## History (`history/`)

The audit trail of the 2026 rebuild: the [baseline](history/audit_baseline.md), the
[dependency map](history/dependency_map.md), the [claim ledger](history/claim_ledger.md), the
[statistical audit](history/statistical_audit.md), the reviews, the
[final report](history/final_report.md) and the [acceptance report](history/acceptance_report.md).
They describe earlier commits and may quote figures and file names that have since changed; the
current results are in the result tables and on the site. See [`history/README.md`](history/README.md).
