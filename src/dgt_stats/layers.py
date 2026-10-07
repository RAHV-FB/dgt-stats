"""The project's source hierarchy: which dataset answers which kind of question.

Four layers, each with its own unit of observation. No layer is merged into another and no record
is linked across sources: the layers meet only where a shared aggregate (province and year) or a
held-out test (a model trained in one layer, scored on another's real records) says they may.

* **National context** (DGT and INE): trends, exposure and denominators, province and year
  comparisons, historical context, aggregate rates, benchmarks for the regional files.
* **Crash microdata: Catalonia** (Servei Català de Trànsit): the crash-severity model and its
  temporal and geographic validation; the training domain of the transfer tests.
* **Rich microdata: Barcelona** (Guàrdia Urbana): person and crash severity, road users, recorded
  causes; diagnostics and external checks of the Catalan model.
* **Validation and transportability**: not a source but a use. Cross-source data test models
  here; they never manufacture observations.

The site groups its pages by these layers and every page names its layer; the data contract
(``docs/DATA_CONTRACT.md``) and the source comparison (``docs/SOURCE_COMPARISON.md``) state the
same roles in prose.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Layer:
    key: str
    title: str
    sources: tuple[str, ...]
    unit: str
    answers: tuple[str, ...]
    not_for: tuple[str, ...]


NATIONAL = Layer(
    key="national",
    title="National context",
    sources=(
        "DGT crash microdata",
        "DGT yearbook series and statistical tables",
        "DGT driver census and kilometre estimates",
        "INE resident population",
        "Ministry of Transport traffic and CORES fuel series",
    ),
    unit="Spain by province and year; one DGT crash with victims",
    answers=(
        "trends over time",
        "exposure and denominators",
        "province and year comparisons",
        "historical context",
        "aggregate rates",
        "benchmarks for the regional files",
    ),
    not_for=(
        "training a severity model, unless the DGT microdata audit allows it",
        "denominators attached to individual crashes",
    ),
)
CATALONIA = Layer(
    key="catalonia",
    title="Crash microdata: Catalonia",
    sources=("Servei Català de Trànsit, crashes with a death or serious injury",),
    unit="one crash with a death or serious injury",
    answers=(
        "which recorded circumstances are associated with a fatal rather than a serious outcome",
        "temporal and geographic validation of that model",
        "the training domain of the transfer tests",
    ),
    not_for=(
        "crash frequency or injury-crash totals (slight-injury crashes are not in the file)",
        "record linkage to Barcelona or DGT records",
        "driving speed (the speed field is the road's limit)",
    ),
)
BARCELONA = Layer(
    key="barcelona",
    title="Rich microdata: Barcelona",
    sources=("Ajuntament de Barcelona, Guàrdia Urbana crash tables",),
    unit="one crash; one person record",
    answers=(
        "person severity by road user",
        "crash severity and recorded causes",
        "diagnostics and external checks of the Catalan model",
    ),
    not_for=(
        "trends (one year)",
        "unique-vehicle analysis (no vehicle key)",
        "a statistically useful fatal-against-serious benchmark (too few fatal crashes)",
    ),
)
VALIDATION = Layer(
    key="validation",
    title="Validation and transportability",
    sources=(),
    unit="held-out records of another year, place or source",
    answers=(
        "does a model hold in later years, another place, another recording source",
        "how the populations differ (representativeness), measured separately",
    ),
    not_for=("creating observations", "joining records across sources"),
)
LAYERS: tuple[Layer, ...] = (NATIONAL, CATALONIA, BARCELONA, VALIDATION)
BY_KEY = {layer.key: layer for layer in LAYERS}
