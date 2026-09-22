"""Crash-severity logistic models: fitting, tidy odds ratios, marginal effects and diagnostics.

The design is main effects only, built by hand from the ordered categoricals of
:mod:`dgt_stats.features` (reference level dropped), fitted by iteratively reweighted least squares
with cluster-robust covariance by province. The fits take about half a minute on the full table and
live behind ``scripts/model.py``, which writes the result tables the site reads.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from dgt_stats import codes, features

log = logging.getLogger(__name__)

HOLDOUT_YEARS = (2023, 2024)
STABILITY_TERMS = 10
PROFILE_YEAR = "2024"
# Road types that only exist outside towns: the predicted grid puts these on the interurban zone.
INTERURBAN_ROAD_TYPES = ("conventional", "dual carriageway", "motorway")

# Named crash profiles for the predicted-probability table; unspecified predictors sit at reference.
PROFILES: dict[str, dict[str, str]] = {
    "Urban street, side collision, daylight, two vehicles": {},
    "Urban street, pedestrian struck, dark with lighting": {
        "crash_type": "pedestrian struck",
        "lighting": "dark, street lighting",
    },
    "Conventional road, head-on collision, daylight, two vehicles": {
        "zone": "interurban road",
        "road": "conventional",
        "crash_type": "head-on collision",
        "alignment": "straight",
    },
    "Conventional road, run-off in a curve, dark without lighting, one vehicle, 00:00–06:59": {
        "zone": "interurban road",
        "road": "conventional",
        "crash_type": "run-off or overturn",
        "alignment": "curve",
        "lighting": "dark, no lighting",
        "vehicles": "1 vehicle",
        "hour_band": "00-06",
    },
    "Motorway, rear-end collision, daylight, two vehicles": {
        "zone": "interurban road",
        "road": "motorway",
        "crash_type": "rear-end or chain collision",
        "alignment": "straight",
    },
    "Dual carriageway, run-off, dark without lighting, one vehicle, weekend, 00:00–06:59": {
        "zone": "interurban road",
        "road": "dual carriageway",
        "crash_type": "run-off or overturn",
        "alignment": "straight",
        "lighting": "dark, no lighting",
        "vehicles": "1 vehicle",
        "weekend": "weekend",
        "hour_band": "00-06",
    },
}


@dataclass
class Fit:
    outcome: str
    predictors: tuple[str, ...]
    columns: list[str]  # design columns after the intercept, "predictor=level"
    params: pd.Series
    cov: pd.DataFrame
    n: int
    events: int
    separated: list[str]  # levels with no events (or only events) in this fit, left out
    # levels that repeat another column of this design exactly (a rank-deficient subset), left out
    aliased: list[str] = dataclasses.field(default_factory=list)


def design_matrix(frame: pd.DataFrame, predictors: tuple[str, ...]) -> pd.DataFrame:
    """Intercept plus one 0/1 column per non-reference level, named ``predictor=level``.

    Levels with no crash in ``frame`` (a subset of years, say) get no column, so the design
    never carries an all-zero column into the fit.
    """
    blocks = [pd.Series(1.0, index=frame.index, name="intercept")]
    for name in predictors:
        column = frame[name]
        for level in column.cat.categories[1:]:
            indicator = (column == level).astype(float)
            if indicator.any():
                blocks.append(indicator.rename(f"{name}={level}"))
    return pd.concat(blocks, axis=1)


def _irls(
    design: np.ndarray, y: np.ndarray, max_iter: int = 25, tol: float = 1e-8
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Logistic regression by iteratively reweighted least squares, written to keep memory low.

    Returns the coefficients, the fitted probabilities and the inverse information matrix
    (the model-based covariance, the "bread" of the sandwich). Raises when the iterations do not
    converge, rather than returning a drifting estimate.
    """
    n, k = design.shape
    beta = np.zeros(k)
    beta[0] = np.log(y.mean() / (1 - y.mean()))

    def log_likelihood(coefficients: np.ndarray) -> float:
        eta = np.clip(design @ coefficients, -30, 30)
        return float(np.sum(y * eta - np.log1p(np.exp(eta))))

    probability = np.empty(n)
    converged = False
    current = log_likelihood(beta)
    for _ in range(max_iter):
        linear = design @ beta
        np.clip(linear, -30, 30, out=linear)
        probability = 1 / (1 + np.exp(-linear))
        weights = probability * (1 - probability)
        information = design.T @ (design * weights[:, None])
        gradient = design.T @ (y - probability)
        step = np.linalg.solve(information, gradient)
        # A full Newton step can overshoot on a level with a handful of events; halve it until
        # the likelihood improves, which leaves the converged estimate unchanged. The step that is
        # applied is the one whose likelihood was evaluated, and a step that lowers the likelihood
        # is never taken.
        accepted: tuple[float, float] | None = None
        scale = 1.0
        for _halving in range(12):
            candidate = log_likelihood(beta + scale * step)
            if candidate >= current:
                accepted = (scale, candidate)
                break
            scale /= 2
        if accepted is None:
            raise RuntimeError("IRLS line search failed to improve the likelihood")
        scale, candidate = accepted
        beta = beta + scale * step
        improvement = candidate - current
        current = candidate
        # Converged when the coefficients stop moving, judged on the undamped Newton step so that
        # a small damping factor cannot pass for a small estimate, or when the likelihood has
        # stopped rising.
        if np.max(np.abs(step)) < tol or abs(improvement) < 1e-9 * max(1.0, abs(current)):
            converged = True
            break
    if not converged:
        raise RuntimeError(f"IRLS did not converge in {max_iter} iterations")
    linear = np.clip(design @ beta, -30, 30)
    probability = 1 / (1 + np.exp(-linear))
    weights = probability * (1 - probability)
    information = design.T @ (design * weights[:, None])
    return beta, probability, np.linalg.inv(information)


def _dependent_columns(matrix: np.ndarray, names: list[str], tol: float = 1e-9) -> list[str]:
    """Columns that are an exact linear combination of the columns before them.

    Two levels can coincide inside a single year (in 2023 "lighting not specified" and "surface
    not specified" are the same 31 crashes) and the information matrix is then singular, so the
    iterations drift instead of converging. The later column of such a pair is dropped and reported
    like a separated level. The test is an incremental Cholesky of the Gram matrix: a column is
    dependent when the variance left after projecting it on the kept columns is a negligible share
    of its own.
    """
    gram = matrix.T @ matrix
    kept: list[int] = []
    factor = np.zeros((0, 0))
    dependent: list[str] = []
    for index, name in enumerate(names):
        projected = (
            np.linalg.solve(factor, gram[np.ix_(kept, [index])]).ravel() if kept else np.zeros(0)
        )
        residual = float(gram[index, index] - projected @ projected)
        if residual <= tol * float(gram[index, index]):
            dependent.append(name)
            continue
        extended = np.zeros((len(kept) + 1, len(kept) + 1))
        extended[:-1, :-1] = factor
        extended[-1, :-1] = projected
        extended[-1, -1] = np.sqrt(residual)
        factor = extended
        kept.append(index)
    return dependent


def _cluster_covariance(
    design: np.ndarray, residual: np.ndarray, bread: np.ndarray, groups: np.ndarray
) -> np.ndarray:
    """Cluster-robust (sandwich) covariance with the usual small-sample factor."""
    n, k = design.shape
    n_groups = int(groups.max()) + 1
    scores = np.zeros((n_groups, k))
    np.add.at(scores, groups, design * residual[:, None])
    meat = scores.T @ scores
    factor = (n_groups / (n_groups - 1)) * ((n - 1) / (n - k))
    return factor * bread @ meat @ bread


def fit_severity(
    frame: pd.DataFrame,
    outcome: str,
    predictors: tuple[str, ...] | None = None,
    cluster: str | None = "province",
) -> Fit:
    """Logistic regression (IRLS) with cluster-robust covariance; returns the parameters and cov."""
    predictors = predictors or tuple(features.PREDICTORS)
    design = design_matrix(frame, predictors)
    y = frame[outcome].astype(float).to_numpy()
    # A level whose crashes all share one outcome cannot be estimated (the odds ratio would run
    # to zero or infinity); it is left out of the design and its crashes count as the reference.
    events_per_column = y @ design.to_numpy(dtype=float)
    crashes_per_column = design.sum(axis=0).to_numpy()
    separated = [
        column
        for column, events, crashes in zip(design.columns, events_per_column, crashes_per_column)
        if column != "intercept" and (events == 0 or events == crashes)
    ]
    design = design.drop(columns=separated)
    # A level that repeats another column exactly cannot be estimated either; it is dropped so the
    # information matrix stays invertible and reported like a separated level.
    aliased = _dependent_columns(design.to_numpy(dtype=float), list(design.columns))
    if aliased:
        log.info("%s: dropping aliased columns %s", outcome, ", ".join(aliased))
        design = design.drop(columns=aliased)
    matrix = design.to_numpy(dtype=float)
    beta, probability, bread = _irls(matrix, y)
    if cluster is not None:
        groups = pd.factorize(frame[cluster])[0]
        cov = _cluster_covariance(matrix, y - probability, bread, groups)
    else:
        cov = bread
    params = pd.Series(beta, index=design.columns)
    return Fit(
        outcome=outcome,
        predictors=predictors,
        columns=list(design.columns[1:]),
        params=params,
        cov=pd.DataFrame(cov, index=design.columns, columns=design.columns),
        n=len(frame),
        events=int(y.sum()),
        separated=separated,
        aliased=aliased,
    )


def odds_ratios(fit: Fit, alpha: float = 0.05) -> pd.DataFrame:
    """Tidy table: predictor, level, reference, odds ratio with interval, p-value, and the
    reference rows themselves (odds ratio 1) so forest plots show every level."""
    from scipy import stats

    z = stats.norm.ppf(1 - alpha / 2)
    records = []
    for name in fit.predictors:
        for column in fit.columns:
            if not column.startswith(f"{name}="):
                continue
            level = column.split("=", 1)[1]
            estimate = float(fit.params[column])
            se = float(np.sqrt(fit.cov.loc[column, column]))
            records.append(
                {
                    "outcome": fit.outcome,
                    "predictor": name,
                    "predictor_label": features.PREDICTOR_LABELS.get(name, name),
                    "level": level,
                    "is_reference": False,
                    "log_odds": estimate,
                    "se": se,
                    "odds_ratio": float(np.exp(estimate)),
                    "or_low": float(np.exp(estimate - z * se)),
                    "or_high": float(np.exp(estimate + z * se)),
                    "p_value": float(2 * stats.norm.sf(abs(estimate / se))) if se > 0 else np.nan,
                }
            )
    return pd.DataFrame.from_records(records)


def _reference_rows(frame: pd.DataFrame, fit: Fit) -> pd.DataFrame:
    records = []
    for name in fit.predictors:
        reference = str(frame[name].cat.categories[0])
        records.append(
            {
                "outcome": fit.outcome,
                "predictor": name,
                "predictor_label": features.PREDICTOR_LABELS.get(name, name),
                "level": reference,
                "is_reference": True,
                "log_odds": 0.0,
                "se": 0.0,
                "odds_ratio": 1.0,
                "or_low": 1.0,
                "or_high": 1.0,
                "p_value": np.nan,
            }
        )
    return pd.DataFrame.from_records(records)


def _left_out_rows(fit: Fit) -> pd.DataFrame:
    """Rows for the levels the fit could not estimate: separated levels and aliased ones."""
    records = []
    for column in [*fit.separated, *fit.aliased]:
        name, level = column.split("=", 1)
        records.append(
            {
                "outcome": fit.outcome,
                "predictor": name,
                "predictor_label": features.PREDICTOR_LABELS.get(name, name),
                "level": level,
                "is_reference": False,
                "log_odds": np.nan,
                "se": np.nan,
                "odds_ratio": np.nan,
                "or_low": np.nan,
                "or_high": np.nan,
                "p_value": np.nan,
            }
        )
    return pd.DataFrame.from_records(records)


def coefficient_table(frame: pd.DataFrame, fit: Fit) -> pd.DataFrame:
    """Odds ratios plus the reference rows (and any level left out for having no events, or for
    repeating another column), in predictor and level order, with level counts."""
    parts = [_reference_rows(frame, fit), odds_ratios(fit), _left_out_rows(fit)]
    table = pd.concat([part for part in parts if not part.empty], ignore_index=True)
    counts = []
    shares = []
    for row in table.itertuples():
        mask = frame[row.predictor] == row.level
        counts.append(int(mask.sum()))
        shares.append(float(frame.loc[mask, fit.outcome].mean()) if mask.any() else np.nan)
    table["crashes"] = counts
    table["observed_share"] = shares
    order = {name: i for i, name in enumerate(fit.predictors)}
    level_order = {
        (name, level): i
        for name in fit.predictors
        for i, level in enumerate(frame[name].cat.categories)
    }
    table["_p"] = table.predictor.map(order)
    table["_l"] = [level_order[(p, lv)] for p, lv in zip(table.predictor, table.level)]
    table = table.sort_values(["_p", "_l"]).drop(columns=["_p", "_l"]).reset_index(drop=True)
    table["n"] = fit.n
    table["events"] = fit.events
    return table


def predict(fit: Fit, design: pd.DataFrame) -> np.ndarray:
    """Fitted probability for each row; levels the fit never saw count as the reference."""
    aligned = design.reindex(columns=fit.params.index, fill_value=0.0)
    linear = np.clip(aligned.to_numpy() @ fit.params.to_numpy(), -30, 30)
    return 1 / (1 + np.exp(-linear))


def marginal_effects(frame: pd.DataFrame, fit: Fit) -> pd.DataFrame:
    """Average marginal effect of each level against its reference, in probability points.

    For each predictor and level, every crash is set to that level (all else as observed) and the
    mean predicted probability is compared with the mean when every crash is set to the reference.
    A level the fit left out (no event of its own, or an exact repeat of another column) has no
    effect to report and carries NaN, not zero.
    """
    design = design_matrix(frame, fit.predictors).reindex(columns=fit.params.index, fill_value=0.0)
    matrix = design.to_numpy(dtype=float)
    beta = fit.params.to_numpy()
    records = []
    for name in fit.predictors:
        level_columns = [c for c in fit.columns if c.startswith(f"{name}=")]
        # Linear predictor with this predictor at its reference for every crash; a level is then
        # one added coefficient, so no copy of the design is needed.
        indices = [design.columns.get_loc(c) for c in level_columns]
        eta_reference = matrix @ beta - matrix[:, indices] @ beta[indices]
        p_reference = (1 / (1 + np.exp(-np.clip(eta_reference, -30, 30)))).mean()
        records.append(
            {
                "outcome": fit.outcome,
                "predictor": name,
                "predictor_label": features.PREDICTOR_LABELS.get(name, name),
                "level": str(frame[name].cat.categories[0]),
                "is_reference": True,
                "probability": float(p_reference),
                "effect": 0.0,
            }
        )
        for column in level_columns:
            eta_level = eta_reference + fit.params[column]
            p_level = (1 / (1 + np.exp(-np.clip(eta_level, -30, 30)))).mean()
            records.append(
                {
                    "outcome": fit.outcome,
                    "predictor": name,
                    "predictor_label": features.PREDICTOR_LABELS.get(name, name),
                    "level": column.split("=", 1)[1],
                    "is_reference": False,
                    "probability": float(p_level),
                    "effect": float(p_level - p_reference),
                }
            )
        for column in [*fit.separated, *fit.aliased]:
            if not column.startswith(f"{name}="):
                continue
            records.append(
                {
                    "outcome": fit.outcome,
                    "predictor": name,
                    "predictor_label": features.PREDICTOR_LABELS.get(name, name),
                    "level": column.split("=", 1)[1],
                    "is_reference": False,
                    "probability": np.nan,
                    "effect": np.nan,
                }
            )
    return pd.DataFrame.from_records(records)


def holdout_check(
    frame: pd.DataFrame, outcome: str, holdout_years: tuple[int, ...] = HOLDOUT_YEARS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit on the years before ``holdout_years``, score the held-out years.

    Returns (calibration by decile, summary with Brier score, AUC and base rates). The year
    predictor is excluded from the holdout fit, so the model has to carry across years unaided.
    """
    predictors = tuple(name for name in features.PREDICTORS if name != "year")
    train = frame[~frame.crash_year.isin(holdout_years)]
    test = frame[frame.crash_year.isin(holdout_years)]
    fit = fit_severity(train, outcome, predictors, cluster=None)
    scores = predict(fit, design_matrix(test, predictors))
    y = test[outcome].astype(int).to_numpy()
    deciles = pd.qcut(scores, 10, labels=False, duplicates="drop")
    calibration = (
        pd.DataFrame({"decile": deciles + 1, "predicted": scores, "observed": y})
        .groupby("decile")
        .agg(
            crashes=("observed", "size"),
            predicted=("predicted", "mean"),
            observed=("observed", "mean"),
        )
        .reset_index()
    )
    calibration["outcome"] = outcome
    summary = pd.DataFrame(
        [
            {
                "outcome": outcome,
                "train_years": f"{train.crash_year.min()}–{train.crash_year.max()}",
                "test_years": f"{test.crash_year.min()}–{test.crash_year.max()}",
                "train_crashes": len(train),
                "test_crashes": len(test),
                "test_events": int(y.sum()),
                "base_rate_train": float(train[outcome].mean()),
                "base_rate_test": float(y.mean()),
                "mean_predicted": float(scores.mean()),
                "brier": float(brier_score_loss(y, scores)),
                "brier_base_rate": float(brier_score_loss(y, np.full_like(scores, y.mean()))),
                "auc": float(roc_auc_score(y, scores)),
            }
        ]
    )
    return calibration, summary


def year_stability(frame: pd.DataFrame, full: Fit, terms: int = STABILITY_TERMS) -> pd.DataFrame:
    """Refit per year (without the year predictor) for the largest effects of the full model.

    The three missing states, not specified, not applicable and a field's explicit unknown code,
    are left out of the selection: their odds ratios reflect reporting practice, which is exactly
    what changes from year to year. The per-year fits are clustered by province, like the full
    model, so the intervals are comparable.
    """
    ranked = odds_ratios(full)
    ranked = ranked[(ranked.predictor != "year") & (~ranked.level.isin(features.MISSING_LEVELS))]
    ranked = ranked.reindex(ranked.log_odds.abs().sort_values(ascending=False).index)
    keep = ranked.head(terms)
    predictors = tuple(name for name in full.predictors if name != "year")
    records = []
    for year, group in frame.groupby("crash_year"):
        fit = fit_severity(group, full.outcome, predictors)
        table = odds_ratios(fit).set_index(["predictor", "level"])
        for row in keep.itertuples():
            key = (row.predictor, row.level)
            if key not in table.index:
                continue
            got = table.loc[key]
            records.append(
                {
                    "outcome": full.outcome,
                    "year": int(year),
                    "predictor": row.predictor,
                    "predictor_label": row.predictor_label,
                    "level": row.level,
                    "odds_ratio": float(got.odds_ratio),
                    "or_low": float(got.or_low),
                    "or_high": float(got.or_high),
                    "full_model_odds_ratio": float(row.odds_ratio),
                    "full_model_or_low": float(row.or_low),
                    "full_model_or_high": float(row.or_high),
                }
            )
    out = pd.DataFrame.from_records(records)
    out["within_full_interval"] = (out.odds_ratio >= out.full_model_or_low) & (
        out.odds_ratio <= out.full_model_or_high
    )
    return out


def _profile_design(frame: pd.DataFrame, fit: Fit, settings: dict[str, str]) -> pd.DataFrame:
    row = {"intercept": 1.0}
    for column in fit.columns:
        row[column] = 0.0
    for name in fit.predictors:
        level = settings.get(name)
        if name == "year" and level is None:
            level = PROFILE_YEAR
        if level is None or level == str(frame[name].cat.categories[0]):
            continue
        column = f"{name}={level}"
        if column not in row:
            raise ValueError(f"profile level not in the model: {column}")
        row[column] = 1.0
    return pd.DataFrame([row])


def profiles(frame: pd.DataFrame, fits: dict[str, Fit]) -> pd.DataFrame:
    """Predicted probability of each outcome for the named crash profiles (year 2024)."""
    records = []
    for name, settings in PROFILES.items():
        record: dict[str, object] = {"profile": name}
        for outcome, fit in fits.items():
            record[outcome] = float(predict(fit, _profile_design(frame, fit, settings))[0])
        records.append(record)
    return pd.DataFrame.from_records(records)


def predicted_grid(
    frame: pd.DataFrame, fit: Fit, rows: str = "road", columns: str = "lighting"
) -> pd.DataFrame:
    """Predicted probability over every combination of two predictors, others at reference.

    The road types that only exist outside towns are placed on the interurban zone; "other road"
    is not one of them (from 2024 most of its crashes are Barcelona streets), so it stays on the
    zone reference.
    """
    records = []
    for row_level in frame[rows].cat.categories:
        for column_level in frame[columns].cat.categories:
            settings = {rows: str(row_level), columns: str(column_level)}
            if rows == "road" and row_level in INTERURBAN_ROAD_TYPES:
                settings["zone"] = "interurban road"
            probability = float(predict(fit, _profile_design(frame, fit, settings))[0])
            records.append(
                {
                    "outcome": fit.outcome,
                    rows: str(row_level),
                    columns: str(column_level),
                    "probability": probability,
                }
            )
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------- adverse conditions, tested

# The levels the severity page leads with: conditions a reader would expect to make a crash worse,
# whose adjusted odds of a fatal outcome are below the reference.
ADVERSE_LEVELS: tuple[tuple[str, str], ...] = (
    ("weather", "rain"),
    ("weather", "hail or snow"),
    ("surface", "wet"),
    ("junction", "at a junction"),
)

# Model variants that test the two obvious explanations: that weather and surface are measuring
# each other, and that the effect is really about where adverse weather falls.
ADVERSE_VARIANTS: dict[str, dict[str, object]] = {
    "full": {"label": "Full model", "drop": (), "subset": None},
    "no_surface": {"label": "Without road surface", "drop": ("surface",), "subset": None},
    "no_weather": {"label": "Without weather", "drop": ("weather",), "subset": None},
    "no_weather_or_surface": {
        "label": "Without weather or surface",
        "drop": ("weather", "surface"),
        "subset": None,
    },
    "no_lighting": {"label": "Without lighting", "drop": ("lighting",), "subset": None},
    "interurban": {
        "label": "Interurban roads only",
        "drop": ("zone",),
        "subset": ("zone", "interurban road"),
    },
    "street": {
        "label": "Urban streets only",
        "drop": ("zone", "road"),
        "subset": ("zone", "street"),
    },
    "conventional": {
        "label": "Conventional roads only",
        "drop": ("zone", "road"),
        "subset": ("road", "conventional"),
    },
}


def adverse_conditions(frame: pd.DataFrame, outcome: str = "fatal") -> pd.DataFrame:
    """The adverse-condition odds ratios refitted under each variant of ``ADVERSE_VARIANTS``.

    Weather and road surface describe overlapping things (it rains, the road is wet), so a model
    carrying both can be splitting one effect between two predictors. Dropping each in turn says
    whether either result depends on the other. The three subsets say whether the result is really
    about *where* adverse weather falls: a stratified fit holds the road context fixed by
    construction instead of adjusting for it.
    """
    records = []
    for key, spec in ADVERSE_VARIANTS.items():
        drop = tuple(spec["drop"])  # type: ignore[arg-type]
        subset = spec["subset"]
        rows = frame
        if subset is not None:
            column, level = subset  # type: ignore[misc]
            rows = frame[frame[column] == level]
            rows = rows.assign(
                **{
                    name: rows[name].cat.remove_unused_categories()
                    for name in rows.columns
                    if isinstance(rows[name].dtype, pd.CategoricalDtype)
                }
            )
        predictors = tuple(name for name in features.PREDICTORS if name not in drop)
        fit = fit_severity(rows, outcome, predictors=predictors)
        table = odds_ratios(fit).set_index(["predictor", "level"])
        for predictor, level in ADVERSE_LEVELS:
            if predictor in drop or (predictor, level) not in table.index:
                continue
            row = table.loc[(predictor, level)]
            crashes = int((rows[predictor] == level).sum())
            records.append(
                {
                    "outcome": outcome,
                    "variant": key,
                    "variant_label": spec["label"],
                    "predictor": predictor,
                    "predictor_label": features.PREDICTOR_LABELS[predictor],
                    "level": level,
                    "n_crashes": len(rows),
                    "n_level": crashes,
                    "odds_ratio": float(row.odds_ratio),
                    "or_low": float(row.or_low),
                    "or_high": float(row.or_high),
                }
            )
    return pd.DataFrame.from_records(records)


def level_composition(
    frame: pd.DataFrame, predictor: str, level: str, top: int = 5
) -> pd.DataFrame:
    """Where the crashes at one level actually are: province, zone and road type shares.

    Hail and snow are 1,577 crashes out of 875,013 and they do not fall evenly over Spain, so the
    question of whether the coefficient is a weather effect or a mountain-province effect has to be
    asked of the data rather than assumed away.
    """
    rows = frame[frame[predictor] == level]
    names = codes.labels_for("COD_PROVINCIA")
    records = []
    for name, column in (("province", "province"), ("zone", "zone"), ("road", "road")):
        counts = rows[column].value_counts().head(top)
        overall = frame[column].value_counts()
        for key, count in counts.items():
            label = names.get(str(key).lstrip("0"), names.get(str(key), str(key)))
            records.append(
                {
                    "predictor": predictor,
                    "level": level,
                    "dimension": name,
                    "category": str(label) if name == "province" else str(key),
                    "crashes": int(count),
                    "share_of_level": float(count) / len(rows),
                    "share_overall": float(overall.get(key, 0)) / len(frame),
                }
            )
    out = pd.DataFrame.from_records(records)
    out.attrs["n_level"] = len(rows)
    return out


def level_exclusions(
    frame: pd.DataFrame, predictor: str, level: str, outcome: str = "fatal", top: int = 3
) -> pd.DataFrame:
    """The same odds ratio refitted with the level's most concentrated provinces left out.

    If a level's effect is really the effect of the few places that record it, dropping those
    places should move it.
    """
    rows = frame[frame[predictor] == level]
    provinces = list(rows.province.value_counts().head(top).index)
    records = []
    for cut in range(top + 1):
        excluded = provinces[:cut]
        kept = frame[~frame.province.isin(excluded)]
        kept = kept.assign(
            **{
                name: kept[name].cat.remove_unused_categories()
                for name in kept.columns
                if isinstance(kept[name].dtype, pd.CategoricalDtype)
            }
        )
        fit = fit_severity(kept, outcome)
        table = odds_ratios(fit).set_index(["predictor", "level"])
        if (predictor, level) not in table.index:
            continue
        row = table.loc[(predictor, level)]
        records.append(
            {
                "outcome": outcome,
                "predictor": predictor,
                "level": level,
                "excluded_provinces": ", ".join(excluded) if excluded else "none",
                "n_excluded": cut,
                "n_crashes": len(kept),
                "n_level": int((kept[predictor] == level).sum()),
                "odds_ratio": float(row.odds_ratio),
                "or_low": float(row.or_low),
                "or_high": float(row.or_high),
            }
        )
    return pd.DataFrame.from_records(records)
