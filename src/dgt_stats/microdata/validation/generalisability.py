"""How far do the regional results reach? Two questions, measured separately.

* **Representativeness** (no model involved): how Catalonia and Barcelona differ from the rest of
  Spain on variables the DGT crash microdata record identically everywhere (one source, one
  definition), plus residents (INE) by province. This quantifies similarity; it does not make a
  region "representative".
* **Transportability** (held-out records): whether a model keeps its ranking outside its training
  domain, always beside the in-domain reference (:mod:`transport`, :mod:`diagnosis`).

They meet in the **outward path toward Spain**, five stages declared in :data:`STAGES`:

  1. internal: held-out rows of the same source and domain;
  2. later years (or months) of the same source;
  3. another region inside the training source;
  4. another independently recorded Spanish dataset;
  5. national aggregates: does the training population resemble Spain?

A stage counts only if it was tested on real held-out records with enough positives (stages 1-4)
or measured on the national records (stage 5), and passes by the rule declared beside
:data:`MAX_TRANSFER_GAP` and :data:`MAX_RESEMBLANCE_JSD`. "Potentially nationally transferable"
is reserved for a model that passes all five.

Writes ``reports/tables/gen_*.csv``, ``ml_outward_path.csv``, ``reports/model_metrics.json`` and
``docs/GENERALISABILITY.md``.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from dgt_stats import derive, io_population
from dgt_stats.microdata import catalonia
from dgt_stats.microdata.common import wilson
from dgt_stats.microdata.validation import harmonise
from dgt_stats.paths import DGT_PROCESSED_CRASHES, DOCS_DIR, REPORTS_DIR, TABLES_DIR

DOC = DOCS_DIR / "GENERALISABILITY.md"
METRICS_JSON = REPORTS_DIR / "model_metrics.json"
CATALAN = harmonise.CATALAN_PROVINCES
BARCELONA_CITY = "08019"

DGT_COLUMNS = [
    "ANYO",
    "COD_PROVINCIA",
    "COD_MUNICIPIO",
    "ZONA_AGRUPADA",
    "TIPO_VIA",
    "TIPO_ACCIDENTE",
    "CONDICION_ILUMINACION",
    "CONDICION_METEO",
    "CONDICION_FIRME",
    "NUDO",
    "TRAZADO_PLANTA",
    "HORA",
    "DIA_SEMANA",
    "TOTAL_VEHICULOS",
    "TOTAL_MU24H",
    "TOTAL_HG24H",
    "TOTAL_MU30DF",
    "TOTAL_HG30DF",
    "TOTAL_VICTIMAS_30DF",
]


def dgt_frame() -> pd.DataFrame:
    """Every DGT injury crash 2016-2024 with the shared variables, labelled by domain."""
    dgt = pd.read_parquet(DGT_PROCESSED_CRASHES, columns=DGT_COLUMNS)

    def code(column: str) -> pd.Series:
        return pd.to_numeric(dgt[column], errors="coerce")

    province = code("COD_PROVINCIA")
    ns = harmonise.NOT_SPECIFIED
    out = pd.DataFrame(
        {
            "year": code("ANYO"),
            "catalonia": province.isin(CATALAN),
            "barcelona_province": province.eq(8),
            "barcelona_city": dgt.COD_MUNICIPIO.astype(str).eq(BARCELONA_CITY),
            "zone": code("ZONA_AGRUPADA").map({1: "interurban", 2: "urban"}).fillna(ns),
            "road_class": derive.road_group(dgt.TIPO_VIA).fillna(ns).astype(str),
            "crash_type": code("TIPO_ACCIDENTE").map(harmonise.DGT_CRASH).fillna(ns),
            "lighting": code("CONDICION_ILUMINACION").map(harmonise.DGT_LIGHT).fillna(ns),
            "weather": code("CONDICION_METEO").map(harmonise.DGT_WEATHER).fillna(ns),
            "surface": code("CONDICION_FIRME").map(harmonise.DGT_SURFACE).fillna(ns),
            "junction": code("NUDO").map({1: "junction", 2: "section"}).fillna(ns),
            "alignment_recorded": code("TRAZADO_PLANTA")
            .map(
                {
                    1: "recorded",
                    2: "recorded",
                    3: "recorded",
                    4: "unknown",
                    999: ns,
                    998: "not applicable",
                }
            )
            .fillna(ns),
            "hour_band": catalonia.band(code("HORA").astype("Float64"), catalonia.HOUR_BANDS)
            .fillna(ns)
            .astype(str),
            "weekday": code("DIA_SEMANA").map(harmonise.DGT_WEEKDAY).fillna(ns),
            "vehicles": harmonise._vehicles_band(code("TOTAL_VEHICULOS")),
        }
    )
    deaths24 = code("TOTAL_MU24H").fillna(0)
    serious24 = code("TOTAL_HG24H").fillna(0)
    out["severe_24h"] = (deaths24 + serious24) > 0
    out["fatal_24h"] = deaths24 > 0
    out["fatal_30d"] = code("TOTAL_MU30DF").fillna(0) > 0
    out["deaths_30d"] = code("TOTAL_MU30DF").fillna(0)
    out["province_code"] = province
    return out


VARIABLES = (
    "zone",
    "road_class",
    "crash_type",
    "lighting",
    "weather",
    "surface",
    "junction",
    "alignment_recorded",
    "hour_band",
    "weekday",
    "vehicles",
)


def compare(a: pd.DataFrame, b: pd.DataFrame, comparison: str, universe: str) -> pd.DataFrame:
    rows = []
    for variable in VARIABLES:
        pa = a[variable].value_counts(normalize=True)
        pb = b[variable].value_counts(normalize=True)
        jsd = harmonise.jensen_shannon(a[variable], b[variable])
        for level in pa.index.union(pb.index):
            rows.append(
                {
                    "comparison": comparison,
                    "universe": universe,
                    "variable": variable,
                    "level": level,
                    "share_a": float(pa.get(level, 0.0)),
                    "share_b": float(pb.get(level, 0.0)),
                    "variable_jsd": jsd,
                }
            )
    out = pd.DataFrame(rows)
    out["difference"] = out.share_a - out.share_b
    return out


def outcomes(a: pd.DataFrame, b: pd.DataFrame, comparison: str) -> list[dict]:
    rows = []
    for label, frame_filter, column in (
        (
            "crashes with a death or serious injury (24 h), share of injury crashes",
            None,
            "severe_24h",
        ),
        ("fatal (24 h) among crashes with a death or serious injury", "severe_24h", "fatal_24h"),
        ("fatal (30 days) among injury crashes", None, "fatal_30d"),
    ):
        values = []
        for frame in (a, b):
            part = frame[frame[frame_filter]] if frame_filter else frame
            k, n = int(part[column].sum()), len(part)
            low, high = wilson(np.array([k]), np.array([n]))
            values.append((k, n, k / n, float(low[0]), float(high[0])))
        rows.append(
            {
                "comparison": comparison,
                "outcome": label,
                "events_a": values[0][0],
                "n_a": values[0][1],
                "share_a": values[0][2],
                "low_a": values[0][3],
                "high_a": values[0][4],
                "events_b": values[1][0],
                "n_b": values[1][1],
                "share_b": values[1][2],
                "low_b": values[1][3],
                "high_b": values[1][4],
            }
        )
    return rows


def representativeness() -> tuple[pd.DataFrame, pd.DataFrame]:
    dgt = dgt_frame()
    rest_of_spain = dgt[~dgt.catalonia]
    cat = dgt[dgt.catalonia]
    city = dgt[dgt.barcelona_city]
    rest_cat = dgt[dgt.catalonia & ~dgt.barcelona_city]
    pairs = [
        ("Catalonia vs Spain outside Catalonia", cat, rest_of_spain),
        ("Barcelona city vs rest of Catalonia", city, rest_cat),
        ("Barcelona city vs Spain outside Catalonia", city, rest_of_spain),
    ]
    shares, outcome_rows = [], []
    for comparison, a, b in pairs:
        shares.append(compare(a, b, comparison, "injury crashes"))
        shares.append(
            compare(
                a[a.severe_24h],
                b[b.severe_24h],
                comparison,
                "crashes with a death or serious injury (24 h)",
            )
        )
        outcome_rows.extend(outcomes(a, b, comparison))
    return pd.concat(shares, ignore_index=True), pd.DataFrame(outcome_rows)


def province_rates() -> pd.DataFrame:
    """Severe (24 h) crashes per 100,000 residents by province and year: DGT counts over INE."""
    dgt = dgt_frame()
    counts = (
        dgt[dgt.severe_24h]
        .groupby(["year", "province_code"])
        .agg(severe_crashes=("fatal_24h", "size"), fatal_crashes=("fatal_24h", "sum"))
        .reset_index()
    )
    population = io_population.read_population()
    population = population[
        population.all_ages & population.sex.eq("total") & population.reference.eq("1 January")
    ].copy()
    population["province_code"] = pd.to_numeric(population.province_code, errors="coerce")
    population = population.dropna(subset=["province_code"])[
        ["year", "province_code", "province", "population"]
    ]
    out = counts.merge(
        population.astype({"year": int, "province_code": int}),
        on=["year", "province_code"],
        how="inner",
        validate="one_to_one",
    )
    out["severe_per_100k_residents"] = out.severe_crashes / out.population * 1e5
    out["fatal_share_of_severe"] = out.fatal_crashes / out.severe_crashes
    out["catalan_province"] = out.province_code.isin(CATALAN)
    out["rank_severe_per_resident"] = (
        out.groupby("year")
        .severe_per_100k_residents.rank(ascending=False, method="min")
        .astype(int)
    )
    out["provinces_in_year"] = out.groupby("year").province_code.transform("size")
    return out.sort_values(["year", "province_code"])


def population_context() -> pd.DataFrame:
    population = io_population.read_population()
    year = int(population.year.max())
    frame = population[
        (population.year == year)
        & population.reference.eq("1 January")
        & population.sex.eq("total")
        & ~population.all_ages
    ].copy()
    frame["province_code"] = pd.to_numeric(frame.province_code, errors="coerce")
    rows = []
    domains = {
        "Barcelona province": frame.province_code.eq(8),
        "Catalonia (4 provinces)": frame.province_code.isin(CATALAN),
        "Spain outside Catalonia": frame.province_code.notna() & ~frame.province_code.isin(CATALAN),
    }
    for name, mask in domains.items():
        part = frame[mask]
        total = part.population.sum()
        rows.append(
            {
                "year": year,
                "domain": name,
                "residents": int(total),
                "share_aged_65_plus": float(part[part.age_low >= 65].population.sum() / total),
                "share_aged_75_plus": float(part[part.age_low >= 75].population.sum() / total),
                "share_aged_under_25": float(
                    part[part.age_high.fillna(200) < 25].population.sum() / total
                ),
            }
        )
    return pd.DataFrame(rows)


CROSS_SOURCE_REGISTER = pd.DataFrame(
    [
        {
            "comparison": "Catalan file vs DGT microdata, crash counts",
            "key": "province (INE code 08, 17, 25, 43 = demarcation) x calendar year, 2016-2023",
            "cardinality": "one-to-one province-years (32)",
            "unit_before": "one crash in each source",
            "unit_after": "one province-year",
            "dgt_definition": "crashes with TOTAL_MU24H > 0 (death within 24 h) / TOTAL_MU24H + TOTAL_HG24H"
            " > 0; also the 30-day columns",
            "other_definition": "Catalan file: D_GRAVETAT 'Accident mortal' / every row (death or "
            "serious injury); window not stated in the file",
            "transformation": "count crashes per province-year on both sides",
            "denominator": "none (counts compared)",
            "exclusions": "years outside 2016-2023; no record-level matching",
            "definition_compatibility": "validated: Catalan counts equal DGT 24-hour counts (fatal: every "
            "province-year; fatal-or-serious: within one crash); they do not "
            "match the 30-day counts",
        },
        {
            "comparison": "Catalan file per resident",
            "key": "province x year, 2010-2023",
            "cardinality": "one-to-one province-years (56)",
            "unit_before": "one crash; one INE population row",
            "unit_after": "one province-year",
            "dgt_definition": "-",
            "other_definition": "INE table 56947, residents on 1 January, all ages, both sexes",
            "transformation": "crashes / residents x 100,000",
            "denominator": "residents of the province (not exposure: no trips or kilometres)",
            "exclusions": "none",
            "definition_compatibility": "same geography and year; a rate per resident, not a risk",
        },
        {
            "comparison": "DGT severe crashes per resident, all provinces",
            "key": "province x year, 2016-2024",
            "cardinality": "one-to-one province-years",
            "unit_before": "one DGT crash; one INE population row",
            "unit_after": "one province-year",
            "dgt_definition": "crashes with a death or serious injury within 24 h",
            "other_definition": "INE residents on 1 January",
            "transformation": "crashes / residents x 100,000",
            "denominator": "residents of the province where the crash happened (residents and "
            "crash-involved people are different populations)",
            "exclusions": "rows without a province code",
            "definition_compatibility": "same source for every province",
        },
        {
            "comparison": "Catalan model on DGT crashes (cross-source tests)",
            "key": "none: no record is matched; the model is applied to DGT rows",
            "cardinality": "-",
            "unit_before": "one crash",
            "unit_after": "one crash",
            "dgt_definition": "crashes with a death or serious injury within 24 h; target death within "
            "24 h",
            "other_definition": "Catalan file inclusion rule (24 h, validated)",
            "transformation": "ten harmonised variables (harmonise.DGT_FIELDS), each validated on the "
            "2016-2023 crashes both sources hold",
            "denominator": "-",
            "exclusions": "road class and junction (failed the overlap check), "
            "speed limit and unit types (absent or outcome counts in DGT)",
            "definition_compatibility": "validated field by field (ml_common_feature_validation.csv)",
        },
        {
            "comparison": "Catalan model on Barcelona 2025",
            "key": "none: no record is matched",
            "cardinality": "-",
            "unit_before": "one crash",
            "unit_after": "one crash",
            "dgt_definition": "-",
            "other_definition": "Barcelona crashes with Numero_morts (24 h) or "
            "Numero_lesionats_greus (hospitalised over 24 h) "
            "> 0, both checked against the person table",
            "transformation": "eight harmonised variables (harmonise.BCN_FIELDS)",
            "denominator": "-",
            "exclusions": "crashes with only minor injuries or none",
            "definition_compatibility": "inclusion rule consistent with the 24 h definitions; too few "
            "fatal crashes for a discrimination test",
        },
    ]
)


# ----------------------------------------------------------------------------- outward path
STAGES = {
    1: "internal: held-out rows of the same source and domain",
    2: "later years (or months) of the same source",
    3: "another region inside the training source",
    4: "another independently recorded Spanish dataset",
    5: "national aggregates: does the training population resemble Spain?",
}
# Declared before any result is read. A transfer test passes when its ROC-AUC interval stays
# above 0.5 and, where an in-domain reference exists, it is at most MAX_TRANSFER_GAP below it.
# The training population resembles Spain when no shared variable's mix differs by more than
# MAX_RESEMBLANCE_JSD (Jensen-Shannon divergence, DGT records, one definition everywhere).
MAX_TRANSFER_GAP = 0.05
MAX_RESEMBLANCE_JSD = 0.02

PATH: dict[str, dict[int, tuple]] = {
    "catalonia_crash_severity": {
        1: ("stability", "5-fold CV, random rows (stratified)"),
        2: ("selected", "context"),
        3: (
            "transport",
            (
                "leave out Barcelona demarcation",
                "leave out Girona demarcation",
                "leave out Lleida demarcation",
                "leave out Tarragona demarcation",
                "rest of Catalonia -> Barcelona municipality",
            ),
        ),
        4: ("none", "no other source records the full Catalan feature set"),
        5: ("resemblance", "Catalonia vs Spain outside Catalonia"),
    },
    "catalonia_common_dgt": {
        1: ("stability", "5-fold CV, random rows (stratified)"),
        2: ("selected", "common"),
        3: (
            "transport",
            tuple(
                f"leave out {d} demarcation (DGT-common features)"
                for d in ("Barcelona", "Girona", "Lleida", "Tarragona")
            ),
        ),
        4: (
            "transport",
            (
                "Catalonia -> Spain outside Catalonia",
                "Catalonia early years -> Spain outside Catalonia later",
            ),
        ),
        5: ("resemblance", "Catalonia vs Spain outside Catalonia"),
    },
    "catalonia_common_bcn": {
        1: ("stability", "5-fold CV, random rows (stratified)"),
        2: ("selected", "common"),
        3: (
            "transport",
            ("rest of Catalonia -> Barcelona municipality (Barcelona-common features)",),
        ),
        4: ("transport", ("Catalonia -> Barcelona 2",)),
        5: ("resemblance", "Catalonia vs Spain outside Catalonia"),
    },
    "barcelona_person_severity": {
        1: ("stability", "5-fold CV, grouped by crash"),
        2: ("selected", "context"),
        3: ("transport", ("leave one district out",)),
        4: (
            "none",
            "no other person-level crash data in the repository (it would need person "
            "microdata from another recording source, such as DGT's victim register)",
        ),
        5: ("resemblance", "Barcelona city vs Spain outside Catalonia"),
    },
    "barcelona_crash_severity": {
        1: ("stability", "5-fold CV, random rows (stratified)"),
        2: ("selected", "context"),
        3: ("transport", ("leave one district out",)),
        4: (
            "none",
            "the Catalan file holds only serious or fatal crashes, so it cannot test a model "
            "of serious-or-fatal against lower severity",
        ),
        5: ("resemblance", "Barcelona city vs Spain outside Catalonia"),
    },
}


def _ci(row) -> str:
    low, high = row.get("roc_auc_low", math.nan), row.get("roc_auc_high", math.nan)
    return "" if pd.isna(low) else f" ({low:.3f}-{high:.3f})"


def _test_passes(row) -> bool:
    low = row.get("roc_auc_low", math.nan)
    gap = row.get("transfer_gap", math.nan)
    above = (low > 0.5) if pd.notna(low) else (row.roc_auc > 0.5)
    return bool(above and (pd.isna(gap) or gap <= MAX_TRANSFER_GAP))


def _resemblance(tables: dict[str, pd.DataFrame], comparison: str) -> tuple[str, str, float]:
    shares = tables["gen_representativeness"]
    universe = shares.universe.str.startswith("crashes with")
    if comparison.startswith("Barcelona"):
        universe = shares.universe.eq("injury crashes")
    part = shares[shares.comparison.eq(comparison) & universe]
    jsd = part.drop_duplicates("variable").set_index("variable").variable_jsd
    over = jsd[jsd > MAX_RESEMBLANCE_JSD].sort_values(ascending=False)
    outcome = tables["gen_outcomes"]
    fatal = outcome[
        outcome.comparison.eq(comparison) & outcome.outcome.str.startswith("fatal (24 h)")
    ]
    gap_text = ""
    if not fatal.empty:
        f = fatal.iloc[0]
        gap_text = f"; fatal share of severe crashes {f.share_a:.1%} against {f.share_b:.1%}"
    status = "passed" if over.empty else "failed"
    evidence = (
        f"{comparison} ({part.universe.iloc[0] if not part.empty else ''}): "
        + (
            "every shared variable within the limit"
            if over.empty
            else "differs on " + ", ".join(f"{v} (JSD {d:.3f})" for v, d in over.items())
        )
        + gap_text
    )
    return status, evidence, float(jsd.max()) if len(jsd) else math.nan


def outward_path(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """For each model, each stage of the outward path: tested or not, passed or not, evidence."""
    selected = tables["ml_selected"]
    stability = tables["ml_stability"]
    moved = tables["ml_transport_validation"]
    rows = []
    for model, stages in PATH.items():
        primary = selected[selected.model.eq(model) & selected.primary]
        chosen = primary.estimator.iloc[0] if not primary.empty else None
        for stage in range(1, 6):
            kind, detail = stages[stage]
            status, evidence, value = "not run", detail, math.nan
            if kind == "stability":
                part = stability[stability.model.eq(model) & stability.evaluation.eq(detail)]
                if not part.empty:
                    value = float(part.roc_auc.mean())
                    status = "passed" if part.roc_auc.min() > 0.5 else "failed"
                    evidence = (
                        f"{detail}: ROC-AUC {value:.3f} (folds {part.roc_auc.min():.3f}-"
                        f"{part.roc_auc.max():.3f})"
                    )
            elif kind == "selected":
                part = selected[selected.model.eq(model) & selected.feature_set.eq(detail)]
                if not part.empty:
                    row = part.iloc[0]
                    value = float(row.roc_auc)
                    enough = row.positives >= 30 and row.n - row.positives >= 30
                    status = (
                        "not testable"
                        if not enough
                        else ("passed" if row.roc_auc_low > 0.5 else "failed")
                    )
                    evidence = (
                        f"{row.design}: ROC-AUC {row.roc_auc:.3f}{_ci(row)}; n={int(row.n):,}, "
                        f"positives={int(row.positives):,}"
                    )
            elif kind == "transport":
                part = moved[
                    moved.model.eq(model)
                    & moved.estimator.ne("baseline_prior")
                    & moved.experiment.apply(lambda e: any(e.startswith(d) for d in detail))
                ]
                if chosen is not None and part.estimator.eq(chosen).any():
                    part = part[part.estimator.eq(chosen)]
                if not part.empty:
                    reported = part[part.status.eq("reported")]
                    if reported.empty:
                        status = "not testable"
                        evidence = "; ".join(
                            f"{r.experiment}: {int(r.test_positives)} positives, too few for a "
                            "discrimination test"
                            for r in part.drop_duplicates("experiment").itertuples()
                        )
                    else:
                        passes = [_test_passes(r) for _, r in reported.iterrows()]
                        status = (
                            "passed" if all(passes) else ("partly" if any(passes) else "failed")
                        )
                        value = float(reported.roc_auc.min())
                        evidence = "; ".join(
                            f"{r.experiment}: ROC-AUC {r.roc_auc:.3f}{_ci(r)}"
                            + (
                                f", in-domain {r.in_domain_cv_roc_auc:.3f}, gap "
                                f"{r.transfer_gap:+.3f}"
                                if pd.notna(r.get("in_domain_cv_roc_auc", math.nan))
                                else ""
                            )
                            + ("" if ok else " [fails]")
                            for (_, r), ok in zip(reported.iterrows(), passes)
                        )
            elif kind == "resemblance":
                status, evidence, value = _resemblance(tables, detail)
            rows.append(
                {
                    "model": model,
                    "stage": stage,
                    "stage_name": STAGES[stage],
                    "status": status,
                    "value": value,
                    "evidence": evidence,
                }
            )
    out = pd.DataFrame(rows)
    verdicts = {}
    for model, group in out.groupby("model", sort=False):
        status = group.set_index("stage").status
        highest = 0
        for stage in range(1, 6):
            if status[stage] != "passed":
                break
            highest = stage
        if highest == 5:
            verdict = "potentially nationally transferable"
        elif highest >= 4:
            verdict = (
                "keeps its ranking on independently recorded Spanish crashes, but the training "
                "population differs from Spain's: national use not established"
            )
        else:
            verdict = f"supported up to stage {highest} ({STAGES[highest] if highest else 'none'})"
        verdicts[model] = (highest, verdict)
    out["highest_consecutive_stage"] = out.model.map(lambda m: verdicts[m][0])
    out["verdict"] = out.model.map(lambda m: verdicts[m][1])
    return out


# ----------------------------------------------------------------------------- document
def _md(frame: pd.DataFrame, pct: tuple[str, ...] = (), dec: tuple[str, ...] = ()) -> str:
    def fmt(value, column):
        if column in pct and isinstance(value, float):
            return f"{value:.1%}"
        if column in dec and isinstance(value, float):
            return f"{value:.3f}"
        if isinstance(value, float):
            return f"{value:,.2f}"
        if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
            return f"{int(value):,}"
        return str(value).replace("|", "/")

    header = "| " + " | ".join(frame.columns) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = [
        "| " + " | ".join(fmt(v, c) for v, c in zip(row, frame.columns)) + " |"
        for row in frame.itertuples(index=False)
    ]
    return "\n".join([header, rule, *rows])


def _diagnosis_text(verdicts: pd.DataFrame, components: pd.DataFrame) -> list[str]:
    lines = []
    for row in verdicts.itertuples():
        lines.append(
            f"- {row.features}, {modelling_label(row.estimator)}: the drop "
            f"{row.total_drop:+.3f} splits into training size {row.training_size_cost:+.3f}, "
            f"intrinsic difference {row.intrinsic_difference:+.3f} and transport gap "
            f"{row.transport_gap:+.3f}. Material (interval excludes 0 and at least 0.02): "
            f"{row.material_components}. Against the rest of Catalonia's urban crashes at the "
            f"same training size the intrinsic difference is "
            f"{row.intrinsic_difference_against_urban:+.3f} ("
            + (
                "interval excludes 0"
                if row.urban_comparison_excludes_zero
                else "interval "
                "includes 0: Barcelona is about as hard to rank as other urban crashes"
            )
            + ")."
        )
    loss = components[components.component.str.startswith("feature loss")]
    for row in loss.itertuples():
        lines.append(
            f"- {row.component}, {modelling_label(row.estimator)}: {row.value:+.3f} "
            f"({row.low:+.3f} to {row.high:+.3f})."
        )
    return lines


def modelling_label(estimator: str) -> str:
    return {"logistic": "logistic regression", "boosted_trees": "boosted trees"}.get(
        estimator, estimator
    )


def _strategy_text(strategies: pd.DataFrame) -> list[str]:
    lines = []
    for (domain, estimator), group in strategies.groupby(
        ["target_domain", "estimator"], sort=False
    ):
        specific = group[group.strategy.str.startswith("domain-specific")].iloc[0]
        others = group[~group.strategy.str.startswith("domain-specific")]
        better = others[others.gain_over_specific_low > 0]
        worse = others[others.gain_over_specific_high < 0]
        parts = [f"domain-specific {specific.roc_auc:.3f}"]
        parts += [
            f"{r.strategy} {r.roc_auc:.3f} ({r.gain_over_specific:+.3f})"
            for r in others.itertuples()
        ]
        reading = (
            "pooling or transfer beats the domain-specific model: " + ", ".join(better.strategy)
            if not better.empty
            else "nothing beats the domain-specific model"
        )
        if not worse.empty:
            reading += "; worse than domain-specific: " + ", ".join(worse.strategy)
        lines.append(
            f"- {domain}, {modelling_label(estimator)}: " + "; ".join(parts) + f". {reading}."
        )
    return lines


def document(tables: dict[str, pd.DataFrame]) -> str:
    shares, outcome_rows = tables["gen_representativeness"], tables["gen_outcomes"]
    transport = tables["ml_transport_validation"]
    provinces = tables["ml_transport_provinces"]
    path = tables["ml_outward_path"]
    shift = tables["ml_domain_shift"]
    validation = tables["ml_common_feature_validation"]
    pop = tables["gen_population_context"]
    rates = tables["gen_province_rates"]
    scores = tables["ml_barcelona_diagnosis"]
    components = tables["ml_barcelona_diagnosis_components"]
    verdicts = tables["ml_barcelona_diagnosis_verdicts"]
    strategies = tables["ml_domain_strategies"]
    national = tables["dgt_audit_transfer"]

    divergence = shares.drop_duplicates(["comparison", "universe", "variable"]).pivot_table(
        index="variable", columns=["comparison"], values="variable_jsd", aggfunc="max"
    )
    divergence = divergence.reset_index()
    severe_shares = shares[shares.universe.str.startswith("crashes with")]
    largest = (
        severe_shares.assign(abs_diff=severe_shares.difference.abs())
        .sort_values("abs_diff", ascending=False)
        .groupby("comparison")
        .head(6)[["comparison", "variable", "level", "share_a", "share_b", "difference"]]
    )
    alignment = severe_shares[
        severe_shares.comparison.eq("Catalonia vs Spain outside Catalonia")
        & severe_shares.variable.eq("alignment_recorded")
        & severe_shares.level.eq("unknown")
    ]
    t = transport[transport.estimator.ne("baseline_prior")]
    t_cols = [
        "experiment",
        "estimator",
        "train_n",
        "test_n",
        "test_positives",
        "test_prevalence",
        "roc_auc",
        "roc_auc_low",
        "roc_auc_high",
        "in_domain_cv_roc_auc",
        "in_domain_train_n",
        "transfer_gap",
        "calibration_slope",
        "status",
    ]
    t_cols = [c for c in t_cols if c in t.columns]
    reported_provinces = provinces[provinces.reported]
    latest = int(rates.year.max())
    latest_rates = rates[rates.year == latest]
    cat_rates = latest_rates[latest_rates.catalan_province][
        [
            "province",
            "severe_crashes",
            "population",
            "severe_per_100k_residents",
            "rank_severe_per_resident",
            "fatal_share_of_severe",
        ]
    ]
    others = latest_rates[~latest_rates.catalan_province].severe_per_100k_residents
    bcn_shift = shift[shift.comparison.str.startswith("Barcelona municipality vs rest")]
    bcn_shift = bcn_shift[bcn_shift.kind.eq("categorical")].sort_values("jsd", ascending=False)
    shift_cols = ["feature", "jsd", "psi", "largest_difference_level", "share_a", "share_b"]
    overlap = validation.attrs.get("overlap", {})
    stage_table = path.pivot_table(
        index="model", columns="stage", values="status", aggfunc="first"
    ).reset_index()
    stage_table.columns = ["model", *[f"stage {c}" for c in stage_table.columns[1:]]]
    stage_table["verdict"] = stage_table.model.map(
        path.drop_duplicates("model").set_index("model").verdict
    )
    furthest = (
        path.drop_duplicates("model")
        .sort_values("highest_consecutive_stage", ascending=False)
        .iloc[0]
    )
    strat_cols = [
        "target_domain",
        "strategy",
        "estimator",
        "train_n",
        "n",
        "positives",
        "roc_auc",
        "roc_auc_low",
        "roc_auc_high",
        "gain_over_specific",
        "gain_over_specific_low",
        "gain_over_specific_high",
        "calibration_slope",
    ]
    lines = [
        "# Generalisability: representativeness and transportability, measured separately",
        "",
        "Generated by `python scripts/microdata.py validate`; do not edit by hand. Every number",
        "is computed from files in `data/raw` in the same run.",
        "",
        "Two different questions, answered separately:",
        "",
        "- **Representativeness** (part A): how do the crash populations differ? No model is",
        "  involved: the DGT microdata record the same variables with one definition everywhere,",
        "  and INE counts residents.",
        "- **Transportability** (part B): does a model trained in one domain keep its ranking on",
        "  held-out records of another? Every transferred score sits beside the same kind of model",
        "  trained *inside* the target domain, and the difference (the transfer gap) is reported.",
        "",
        "Neither implies the other: a model can transfer to a population that differs, and a",
        "similar population can still defeat a model. Part C combines them into the outward path",
        "toward Spain. Transfer of a prediction is not a causal finding.",
        "",
        "## A. Representativeness (no model involved)",
        "",
        "Outcome shares with 95% intervals (DGT microdata):",
        "",
        _md(
            outcome_rows[["comparison", "outcome", "n_a", "share_a", "n_b", "share_b"]],
            pct=("share_a", "share_b"),
        ),
        "",
        "Divergence of each variable's mix (Jensen-Shannon, 0 = identical), larger of the two "
        "universes:",
        "",
        _md(divergence, dec=tuple(divergence.columns[1:])),
        "",
        "Largest differences among crashes with a death or serious injury:",
        "",
        _md(largest, pct=("share_a", "share_b", "difference")),
        "",
    ]
    if not alignment.empty:
        a = alignment.iloc[0]
        lines += [
            f"DGT's 'alignment unknown' code covers {a.share_a:.1%} of these crashes in Catalonia "
            f"and {a.share_b:.1%} elsewhere: a difference in how crashes are recorded, not in the "
            "roads. Recording differences are themselves a reason a model may not transfer (see "
            "[`DGT_MICRODATA_AUDIT.md`](DGT_MICRODATA_AUDIT.md)).",
            "",
        ]
    lines += [
        f"Residents ({int(pop.year.iloc[0])}, INE):",
        "",
        _md(pop, pct=("share_aged_65_plus", "share_aged_75_plus", "share_aged_under_25")),
        "",
        f"Severe crashes per resident, {latest} (DGT counts, INE residents): across the "
        f"{int(len(latest_rates))} provinces the rate per 100,000 residents ranges "
        f"{latest_rates.severe_per_100k_residents.min():.1f}-"
        f"{latest_rates.severe_per_100k_residents.max():.1f}; outside Catalonia its median is "
        f"{others.median():.1f}. A rate per resident is not a risk per trip or kilometre.",
        "",
        _md(cat_rates, pct=("fatal_share_of_severe",), dec=("severe_per_100k_residents",)),
        "",
        "## B. Transportability (held-out records)",
        "",
        "### Every transfer test, with its in-domain reference",
        "",
        _md(
            t[t_cols],
            pct=("test_prevalence",),
            dec=(
                "roc_auc",
                "roc_auc_low",
                "roc_auc_high",
                "in_domain_cv_roc_auc",
                "transfer_gap",
                "calibration_slope",
            ),
        ),
        "",
        "`in_domain_cv_roc_auc`: the same kind of model trained and cross-validated inside the",
        "test domain (on `in_domain_train_n` rows per fold). `transfer_gap` = in-domain minus",
        "transferred; positive means moving domain cost ranking ability. A negative gap means the",
        "larger foreign training set outweighed the change of domain, so read it with the",
        "training sizes.",
        "",
        "### Why the Catalan model ranks Barcelona's crashes less well",
        "",
        "Measured with the Catalan file only (Barcelona municipality against the rest of",
        "Catalonia). Each score is out-of-fold or transferred, on real held-out crashes:",
        "",
        _md(
            scores[
                [
                    "code",
                    "score",
                    "features",
                    "estimator",
                    "train_n",
                    "test_n",
                    "test_positives",
                    "roc_auc",
                    "roc_auc_low",
                    "roc_auc_high",
                ]
            ],
            dec=("roc_auc", "roc_auc_low", "roc_auc_high"),
        ),
        "",
        "The components (they telescope: total drop = training size + intrinsic difference +",
        "transport gap):",
        "",
        _md(
            components[
                ["features", "estimator", "component", "definition", "value", "low", "high"]
            ],
            dec=("value", "low", "high"),
        ),
        "",
        *_diagnosis_text(verdicts, components),
        "",
        "### Domain-specific, pooled and universal models",
        "",
        "For each target domain, five-fold splits of that domain; every model is scored on the",
        "same held-out crashes, and its gain over the domain-specific model has a paired",
        "interval. The universal model is the pooled model on the Barcelona-common features.",
        "",
        _md(
            strategies[[c for c in strat_cols if c in strategies.columns]],
            dec=(
                "roc_auc",
                "roc_auc_low",
                "roc_auc_high",
                "gain_over_specific",
                "gain_over_specific_low",
                "gain_over_specific_high",
                "calibration_slope",
            ),
        ),
        "",
        *_strategy_text(strategies),
        "",
        "### The national test: what it measures",
        "",
        _md(national[["check", "criterion", "evidence", "passed"]]),
        "",
        "### Province by province (Catalan common-feature model on DGT crashes outside Catalonia)",
        "",
        f"{len(reported_provinces)} of {len(provinces)} provinces have at least 30 fatal and 30 "
        "non-fatal serious crashes; their ROC-AUC: median "
        f"{reported_provinces.roc_auc.median():.3f}, interquartile range "
        f"{reported_provinces.roc_auc.quantile(0.25):.3f}-"
        f"{reported_provinces.roc_auc.quantile(0.75):.3f}, lowest "
        f"{reported_provinces.roc_auc.min():.3f}, highest {reported_provinces.roc_auc.max():.3f}.",
        "",
        "### The DGT mapping check",
        "",
        f"On {overlap.get('years', '')} the Catalan file holds {overlap.get('catalan_rows', 0):,} "
        f"crashes ({overlap.get('catalan_fatal', 0):,} fatal) and the DGT microdata "
        f"{overlap.get('dgt_rows', 0):,} ({overlap.get('dgt_fatal', 0):,} fatal) in the four "
        "provinces. A field enters the cross-source model only if its mapped distribution is the "
        f"same on both sides (Jensen-Shannon divergence at most {harmonise.MAX_OVERLAP_JSD}):",
        "",
        _md(validation, dec=("overlap_jsd",)),
        "",
        "Barcelona against the rest of Catalonia in the Catalan file, largest divergences first:",
        "",
        _md(bcn_shift[shift_cols].head(12), pct=("share_a", "share_b"), dec=("jsd", "psi")),
        "",
        "## C. The outward path toward Spain",
        "",
        "Five stages, each on real held-out records or published aggregates. A transfer stage",
        f"passes when the ROC-AUC interval stays above 0.5 and the score is at most "
        f"{MAX_TRANSFER_GAP} below the in-domain reference; stage 5 passes when no shared "
        f"variable's mix differs between the training population and Spain by more than "
        f"{MAX_RESEMBLANCE_JSD} (Jensen-Shannon). Only a model that passes all five would be",
        "called potentially nationally transferable; no model jumps from Barcelona or Catalonia",
        "to Spain without the stages between.",
        "",
        "| Stage | Meaning |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in STAGES.items()],
        "",
        _md(stage_table),
        "",
        f"The furthest-reaching model is `{furthest.model}`: {furthest.verdict}.",
        "",
        "Evidence for every stage:",
        "",
        _md(path[["model", "stage", "status", "evidence"]]),
        "",
        "## Cross-source register",
        "",
        "Every place two sources meet, with the key, definitions and what was validated:",
        "",
        _md(CROSS_SOURCE_REGISTER),
        "",
        "## What this does not establish",
        "",
        "- That Catalonia or Barcelona is representative of Spain: part A shows where they differ.",
        "- National validity of the full Catalan model, of either Barcelona model, or of any",
        "  person-level result: no other source in the repository carries those variables.",
        "- Any causal effect: every transfer result is predictive.",
        "- Barcelona 2025 as an external benchmark for fatal against serious crashes: too few",
        "  fatal crashes (see the transfer table).",
    ]
    return "\n".join(lines) + "\n"


def run(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    shares, outcome_rows = representativeness()
    out = {
        "gen_representativeness": shares,
        "gen_outcomes": outcome_rows,
        "gen_province_rates": province_rates(),
        "gen_population_context": population_context(),
        "gen_cross_source_register": CROSS_SOURCE_REGISTER,
    }
    merged = {**tables, **out}
    out["ml_outward_path"] = outward_path(merged)
    merged.update(out)
    for name, frame in out.items():
        frame.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.6g")
    DOC.write_text(document(merged), encoding="utf-8")
    return out


def write_metrics_json(tables: dict[str, pd.DataFrame]) -> None:
    def records(frame: pd.DataFrame) -> list[dict]:
        return json.loads(frame.to_json(orient="records", double_precision=6))

    payload = {
        "description": "Severity models trained on crash-level microdata: test metrics, rule "
        "baselines, transfer tests with in-domain references, the Barcelona diagnosis, the "
        "outward path and the model decisions. Generated; do not edit.",
        "selected_models": records(tables["ml_selected"]),
        "transport_validation": records(tables["ml_transport_validation"]),
        "subgroup_validation": records(tables["ml_subgroup_validation"]),
        "outward_path": records(tables["ml_outward_path"]),
        "rule_comparison": records(tables["ml_rule_comparison"]),
        "barcelona_diagnosis": records(tables["ml_barcelona_diagnosis_components"]),
        "domain_strategies": records(tables["ml_domain_strategies"]),
        "model_decisions": records(tables["ml_model_decisions"]),
    }
    METRICS_JSON.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
