"""The validation step: test the fitted source models outside their own held-out rows.

Runs after ``scripts/microdata.py models`` (which fits the models and writes their own tables) and
``analyse`` (which writes the Catalan-DGT reconciliation). In order:

1. transfer tests with in-domain references (:mod:`transport`);
2. the Barcelona transfer diagnosis and domain-specific against pooled models (:mod:`diagnosis`);
3. the DGT microdata audit (:mod:`dgt_audit`);
4. representativeness and the outward path toward Spain (:mod:`generalisability`);
5. the model decision table (:mod:`decisions`);
6. the model cards, which carry the validation evidence, and ``reports/model_metrics.json``.

No step creates an observation: every score is on real held-out records.
"""

from __future__ import annotations

import logging

import pandas as pd

from dgt_stats.microdata.ml import features, reporting
from dgt_stats.microdata.validation import (
    decisions,
    dgt_audit,
    diagnosis,
    generalisability,
    transport,
)

log = logging.getLogger(__name__)


def run() -> dict[str, pd.DataFrame]:
    results = reporting.load()
    tables = reporting.read_tables()
    for name, step in (
        ("transfer tests", lambda: transport.run(results)),
        ("Barcelona transfer diagnosis", lambda: diagnosis.run(results)),
        ("DGT microdata audit", lambda: dgt_audit.run(tables)),
    ):
        log.info("validation: %s", name)
        out = step()
        reporting.write_csvs(out)
        tables.update(out)
    log.info("validation: representativeness and the outward path")
    tables.update(generalisability.run(tables))
    log.info("validation: model decisions")
    tables.update(decisions.run(tables))
    reporting.write_docs([results[t.name] for t in features.TABLES], tables)
    generalisability.write_metrics_json(tables)
    return tables


def documents() -> dict[str, pd.DataFrame]:
    """Re-render the validation documents from the saved tables, without refitting anything.

    Representativeness, the outward path and the decisions are recomputed (they are cheap); the
    transfer tests, the diagnosis and the DGT audit are read as the validation step wrote them.
    """
    from dgt_stats.microdata.validation import harmonise

    results = reporting.load()
    tables = reporting.read_tables(("ml_", "cat_", "bcn_", "mq_", "dgt_audit_"))
    tables["ml_common_feature_validation"] = harmonise.validate_dgt()
    tables.update(generalisability.run(tables))
    tables.update(decisions.run(tables))
    reporting.write_docs([results[t.name] for t in features.TABLES], tables)
    generalisability.write_metrics_json(tables)
    return tables
