"""The pipeline: every stage of every section, in the order a full build runs them.

``python scripts/run.py --list`` prints this table; ``python scripts/run.py <section>`` runs one
section's stages in order, ``python scripts/run.py <section>.<stage>`` one stage, and
``python scripts/run.py all`` everything. Each stage runs in a process of its own, so that a stage
pinned to one BLAS thread (``single_thread``) cannot change the arithmetic of another.

A stage reads only what the stages before it wrote, and the raw files are never modified. The
national data come first because the regional comparison, the driver rates and the models all
read them; the national model cards come after the models because one of them quotes the DGT
microdata audit; the figures and the site come last and read only the committed result tables
(and, for the figures, the data layers).
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Stage:
    section: str
    name: str
    # ``module:function``, imported only when the stage runs
    target: str
    does: str
    writes: str
    # wall-clock minutes of a full build on a four-core machine
    minutes: float
    single_thread: bool = False
    # run by ``all`` and by its section; the others are run by name
    in_all: bool = True
    takes_force: bool = False
    takes_years: bool = False

    @property
    def key(self) -> str:
        return f"{self.section}.{self.name}"

    def function(self):
        module, function = self.target.split(":")
        return getattr(importlib.import_module(module), function)


STAGES: tuple[Stage, ...] = (
    Stage(
        "national",
        "ingest",
        "dgt_stats.national.stages:ingest",
        "parse the raw DGT, INE, Ministry and CORES files",
        "data/staging/dgt/",
        5,
        takes_force=True,
        takes_years=True,
    ),
    Stage(
        "national",
        "reconcile",
        "dgt_stats.national.stages:reconcile_checks",
        "tie the staging layer to DGT's published totals (482 checks); stop if one fails",
        "reconciliation.csv, missingness_by_year.csv",
        0.7,
    ),
    Stage(
        "national",
        "process",
        "dgt_stats.national.stages:process",
        "add derived fields and English labels to the DGT crash records",
        "data/processed/dgt_accidentes.parquet",
        0.5,
        takes_force=True,
    ),
    Stage(
        "national",
        "associations",
        "dgt_stats.national.stages:run_associations",
        "fit the supporting association analysis of DGT crash records; the crash explorer's counts",
        "assoc_*.csv, explore_dgt_crashes.csv",
        10,
    ),
    Stage(
        "national",
        "results",
        "dgt_stats.national.stages:results",
        "every other national result table",
        "trends_*, longrun_*, season_*, road_class_*, vehicles_*, speed_*, factor_*, policy_*.csv",
        1.5,
    ),
    Stage(
        "regional",
        "build",
        "dgt_stats.regional.stages:build",
        "stage the Catalan and Barcelona files and write their canonical tables",
        "data/staging/{catalonia,barcelona}/, data/processed/{catalonia,barcelona}_*.parquet",
        0.2,
        takes_force=True,
    ),
    Stage(
        "regional",
        "quality",
        "dgt_stats.regional.stages:run_quality",
        "the data-quality report and the Barcelona vehicle audit",
        "cat_quality_*, bcn_quality_*, bcn_vehicle_audit_counts.csv, two documents",
        0.2,
    ),
    Stage(
        "regional",
        "analyse",
        "dgt_stats.regional.stages:analyse",
        "descriptive tables; the comparison with DGT and INE by province and year",
        "cat_*.csv, bcn_*.csv",
        0.2,
    ),
    Stage(
        "drivers",
        "tables",
        "dgt_stats.drivers.stages:tables",
        "driver rates by sex and by the car owner's age, from DGT's tables, census and km estimates",
        "drivers_*.csv",
        0.2,
    ),
    Stage(
        "drivers",
        "emef",
        "dgt_stats.drivers.stages:emef",
        "read and check the EMEF survey; car-driving exposure by age, sex, area and year",
        "data/processed/emef_*.parquet, emef_*.csv",
        2.5,
        single_thread=True,
    ),
    Stage(
        "drivers",
        "exposure",
        "dgt_stats.drivers.stages:exposure_all",
        "kilometres by driver age (EMEF, EDM2018, MOVILIA) and car drivers involved per km",
        "risk_*.csv (driver age), edm_*.csv, emef_routing_older.csv",
        4.5,
        single_thread=True,
    ),
    Stage(
        "models",
        "features",
        "dgt_stats.models.stages:features",
        "the model matrices of the regional records",
        "data/features/",
        0.2,
    ),
    Stage(
        "models",
        "fit",
        "dgt_stats.models.stages:fit",
        "fit the source models and their rule baselines; the leakage audit",
        "ml_*.csv, harmonised cross-source tables, ML leakage audit",
        12,
    ),
    Stage(
        "models",
        "validate",
        "dgt_stats.models.stages:validate",
        "transfer tests, Barcelona diagnosis, DGT microdata audit, generalisability, decisions, cards",
        "ml_*, gen_*, dgt_audit_*.csv, model_metrics.json, model cards, decisions and other documents",
        27,
    ),
    Stage(
        "models",
        "calculator",
        "dgt_stats.models.stages:calculator",
        "the crash-severity calculator's model, by nested rolling origin, and its export",
        "sev_*.csv, reports/models/severity_model.json",
        22,
    ),
    Stage(
        "models",
        "review",
        "dgt_stats.models.stages:review",
        "the independent re-evaluation of every model",
        "review_*.csv",
        7.5,
    ),
    Stage(
        "national",
        "cards",
        "dgt_stats.national.stages:cards",
        "the cards of the national models (after models.validate, which they quote)",
        "docs/models/cards/dgt_*.md",
        0.2,
    ),
    Stage(
        "sources",
        "inventory",
        "dgt_stats.sources.stages:inventory",
        "profile every raw file: size, checksum, encoding, rows, columns, unit",
        "data_inventory.csv, raw-file inventory document",
        0.5,
    ),
    Stage(
        "sources",
        "profile",
        "dgt_stats.sources.stages:profile",
        "how each source came to exist, against the same questions",
        "source_comparison.csv, source comparison document",
        0.2,
    ),
    Stage(
        "charts",
        "figures",
        "dgt_stats.pipeline:draw_figures",
        "every figure, wide and narrow, with its caption and title",
        "reports/figures/",
        0.6,
    ),
    Stage(
        "site",
        "build",
        "dgt_stats.pipeline:build_site",
        "the static site, from the committed result tables and figures only",
        "site/",
        0.5,
    ),
    Stage(
        "sources",
        "catalogue",
        "dgt_stats.sources.stages:catalogue",
        "the map of sections, sources and tables, and an index in each table folder",
        "docs/catalogue.md, reports/tables/*/README.md",
        0.1,
    ),
    # Run by name only.
    Stage(
        "national",
        "withdrawn",
        "dgt_stats.national.stages:withdrawn",
        "the withdrawn monthly forecast's tables, the record behind its card (slow)",
        "forecast_*.csv",
        30,
        in_all=False,
    ),
    Stage(
        "regional",
        "organise",
        "dgt_stats.regional.stages:organise",
        "file loose regional downloads under data/raw/<source>/ and register them",
        "data/raw/, data/raw/manifest.csv",
        0.1,
        in_all=False,
    ),
    Stage(
        "models",
        "documents",
        "dgt_stats.models.stages:documents",
        "re-render the validation documents and model cards from the saved tables",
        "model cards, decisions and other documents",
        0.1,
        in_all=False,
    ),
)
BY_KEY = {stage.key: stage for stage in STAGES}
SECTIONS = tuple(dict.fromkeys(stage.section for stage in STAGES))


def select(targets: list[str]) -> list[Stage]:
    """The stages named by ``targets`` (``all``, a section or ``section.stage``), in pipeline
    order for ``all`` and a section, and in the order given otherwise."""
    chosen: list[Stage] = []
    for target in targets:
        if target == "all":
            found = [stage for stage in STAGES if stage.in_all]
        elif target in SECTIONS:
            found = [stage for stage in STAGES if stage.section == target and stage.in_all]
        elif target in BY_KEY:
            found = [BY_KEY[target]]
        else:
            raise SystemExit(f"unknown stage or section: {target} (see --list)")
        chosen.extend(stage for stage in found if stage not in chosen)
    return chosen


def draw_figures() -> None:
    """Every figure, from the data layers and the committed tables."""
    from dgt_stats.charts import figures

    captions = figures.build_all()
    log.info("wrote %d figures and captions.json", len(captions))


def build_site() -> None:
    """The site, from the committed tables and figures."""
    from dgt_stats import site

    written = site.build()
    pages = [path.name for path in written if path.suffix == ".html"]
    log.info("wrote %d files to %s (pages: %s)", len(written), site.SITE_DIR, ", ".join(pages))
