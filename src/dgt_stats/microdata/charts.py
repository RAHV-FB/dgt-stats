"""Figures for the regional pages, drawn from the committed result tables with the site's plots.

Every figure is a single-series dot-and-interval chart in the project's fixed palette, with its N
in the caption, and the same numbers in a table on the page. Nothing is recomputed here: the
tables in ``reports/tables`` are the input, so a figure cannot disagree with the table beside it.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd

from dgt_stats import plots
from dgt_stats.paths import TABLES_DIR

MIN_N = 30
CAT_SOURCE = "Servei Català de Trànsit, crashes with a death or serious injury"
BCN_SOURCE = "Ajuntament de Barcelona, Guàrdia Urbana crash records"

# Barcelona road users as the person table names them (role and vehicle type), where English has
# a natural word; the other labels are shown as recorded. The regional page uses the same map.
ROAD_USER_LABELS = {
    "bicycle driver": "cyclist",
    "motorcycle driver": "motorcyclist",
    "moped driver": "moped rider",
    "personal mobility vehicle driver": "personal mobility vehicle rider",
}


# Catalan category labels shortened for the charts, so the label column leaves room for the data.
CAT_SHORT_LABELS = {
    "other unit": "other",
    "hit an object without leaving the road": "hit an object on the road",
}


def _ranges(text: str) -> str:
    """A range written with a hyphen between numbers (age 0-15, 10-30 km/h) with an en dash."""
    return re.sub(r"(?<=\d)-(?=\d)", "–", text)


def _caption(shown: str, source: str, n: int | str | None = None) -> str:
    """A figure caption: what is shown (population and period included), source, count."""
    text = f"{shown}. Source: {source}."
    if n is not None:
        text += f" n = {n:,}." if isinstance(n, int) else f" n = {n}."
    return text


def table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


def _labelled(frame: pd.DataFrame, label: str = "label") -> pd.DataFrame:
    frame = frame[frame.n >= MIN_N].copy()
    frame["row"] = (
        frame[label].astype(str).map(_ranges) + "  (n=" + frame.n.map("{:,}".format) + ")"
    )
    return frame


def _roc_limits(highs: pd.Series) -> tuple[float, float]:
    """A ROC-AUC axis from just below chance to just above the highest interval."""
    return 0.45, math.ceil((float(highs.max()) + 0.02) * 20) / 20


def _shares(
    frame: pd.DataFrame,
    dimension: str,
    path: Path,
    title: str,
    xlabel: str,
    reference: float,
    keep_order: bool = False,
    order: list[str] | None = None,
    xlim: tuple[float, float] | None = None,
    groups: dict[str, str] | None = None,
) -> Path:
    """One chart of fatal or severe shares by the levels of ``dimension``. ``order`` fixes the
    rows (first at the top) and ``groups`` heads blocks of them, by level."""
    # The overall share is the dotted reference line, not a row of its own.
    block = _labelled(frame[(frame.dimension == dimension) & (frame.level != "all")])
    if order:
        block = block.set_index("level").reindex([o for o in order if o in set(block.level)])
        block = block.reset_index()
    if groups:
        block["block"] = block.level.map(groups)
    return plots.dot_interval(
        block,
        "row",
        "share",
        "ci_low",
        "ci_high",
        path,
        title,
        xlabel=xlabel,
        reference=reference,
        reference_label="all",
        percent=True,
        keep_order=keep_order,
        xlim=xlim,
        group="block" if groups else None,
    )


# The speed-limit chart: the posted limits in order, then the crashes with no limit recorded.
POSTED_LIMIT = "Posted limit"
NO_POSTED_LIMIT = "No posted limit recorded"
GENERIC_LIMIT = "generic limit for the road (value not recorded)"
IMPLAUSIBLE_LIMIT = "posted, implausible value"


def _speed_limit_rows(shares: pd.DataFrame) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """The speed-limit levels in chart order (posted limits from the lowest, the generic limit
    last), the heading of each, and each level's row label."""
    levels = set(shares[(shares.dimension == "speed limit") & (shares.level != "all")].level)
    posted = [level for level in levels if re.fullmatch(r"posted \d+-\d+ km/h", level)]
    others = levels - set(posted) - {GENERIC_LIMIT, IMPLAUSIBLE_LIMIT}
    if others or GENERIC_LIMIT not in levels:
        raise ValueError(f"cat2: unexpected speed-limit levels {sorted(others)}")
    order = sorted(posted, key=lambda level: int(re.search(r"\d+", level).group()))
    groups = {level: POSTED_LIMIT for level in order} | {GENERIC_LIMIT: NO_POSTED_LIMIT}
    labels = {level: level.removeprefix("posted ") for level in order}
    labels[GENERIC_LIMIT] = "generic limit for the road"
    return [*order, GENERIC_LIMIT], groups, labels


def catalonia_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    shares = table("cat_fatal_share")
    # The file's 'other unit' is any vehicle outside the named types; the figure says 'other'.
    shares["label"] = shares.label.replace(CAT_SHORT_LABELS)
    overall = shares[(shares.dimension == "unit type involved") & (shares.level == "all")]
    base = float(overall.share.iloc[0])
    n = f"{int(overall.n.iloc[0]):,} crashes"
    years = shares[shares.dimension == "year"].level.astype(int)
    period = f"{years.min()}–{years.max()}"
    charts = (
        ("cat1_fatal_by_road", "road type", "Fatal share by road type", "road type"),
        (
            "cat2_fatal_by_speed_limit",
            "speed limit",
            "Fatal share by posted speed limit (the road's limit, not vehicle speed)",
            "posted speed limit (the limit signposted on the road, not a measured speed)",
        ),
        (
            "cat3_fatal_by_unit",
            "unit type involved",
            "Fatal share by type of road user or vehicle involved (a crash can involve several)",
            "type of road user or vehicle involved",
        ),
        ("cat4_fatal_by_crash_type", "crash subtype", "Fatal share by crash type", "crash type"),
    )
    # The four charts share one scale, so the overall line and the axis line up down the page.
    shown = _labelled(shares[shares.dimension.isin([c[1] for c in charts])])
    top = math.ceil(float(shown.ci_high.max()) * 20) / 20
    # Speed limits are ordered: the posted ones run from the lowest, and the crashes with no
    # posted limit recorded, most of the file, come last under a heading of their own.
    limit_order, limit_groups, limit_labels = _speed_limit_rows(shares)
    is_limit = (shares.dimension == "speed limit") & shares.level.isin(limit_labels)
    shares.loc[is_limit, "label"] = shares.loc[is_limit, "level"].map(limit_labels)
    generic = shares[(shares.dimension == "speed limit") & (shares.level == GENERIC_LIMIT)]
    no_limit = float(generic.n.iloc[0] / overall.n.iloc[0])
    if not no_limit > 0.5:
        raise ValueError("cat2 caption: most crashes no longer lack a posted limit")
    notes = {
        "cat2_fatal_by_speed_limit": (
            f"; {no_limit:.0%} of the crashes have no posted limit recorded, and the generic "
            "limit for the type of road applied"
        )
    }
    for name, dimension, title, by in charts:
        limits = dimension == "speed limit"
        _shares(
            shares,
            dimension,
            figures_dir / f"{name}.svg",
            title,
            "Fatal crashes among serious and fatal crashes",
            base,
            xlim=(0, top),
            order=limit_order if limits else None,
            keep_order=limits,
            groups=limit_groups if limits else None,
        )
        captions[name] = _caption(
            f"Fatal crashes as a share of crashes with a death or serious injury, by {by}, "
            f"Catalonia, {period}, with 95% intervals; groups of fewer than {MIN_N} crashes "
            f"are left out{notes.get(name, '')}",
            CAT_SOURCE,
            n,
        )


def barcelona_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    people = table("bcn_person_severity_share")
    year = str(people.dataset.iloc[0]).replace("Barcelona ", "")
    is_road_user = people.dimension == "road user"
    people.loc[is_road_user, "label"] = people.loc[is_road_user, "label"].replace(ROAD_USER_LABELS)
    road_users = people[is_road_user]
    base = float(road_users.events.sum() / road_users.n.sum())
    n = f"{int(road_users.n.sum()):,} people"

    def people_caption(by: str) -> str:
        return _caption(
            "People seriously or fatally injured as a share of the people in recorded crashes "
            f"with a recorded injury outcome, by {by}, Barcelona, {year}, with 95% intervals; "
            f"groups of fewer than {MIN_N} people are left out",
            BCN_SOURCE,
            n,
        )

    _shares(
        people,
        "road user",
        figures_dir / "bcn1_severity_by_road_user.svg",
        "Serious or fatal injury by road user (role and vehicle type on the record)",
        "Share of people in recorded crashes",
        base,
    )
    captions["bcn1_severity_by_road_user"] = people_caption("road-user role and vehicle type")
    ages = ["0-15", "16-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]
    _shares(
        people,
        "age band",
        figures_dir / "bcn2_severity_by_age.svg",
        "Serious or fatal injury by age band",
        "Share of people in recorded crashes",
        base,
        keep_order=True,
        order=ages,
    )
    captions["bcn2_severity_by_age"] = people_caption("age band")
    crashes = table("bcn_crash_severity_share")
    crash_base = crashes[(crashes.dimension == "cause recorded") & (crashes.level == "all")]
    # One crash type far above the rest is written out at the axis end, so that the scale is set
    # by the others.
    types = _labelled(crashes[crashes.dimension == "crash type"]).sort_values("share")
    limit = None
    if float(types.share.iloc[-1]) > 2 * float(types.ci_high.iloc[-2]):
        limit = (0, math.ceil(float(types.ci_high.iloc[-2]) * 1.15 * 20) / 20)
    _shares(
        crashes,
        "crash type",
        figures_dir / "bcn4_crash_severity_by_type.svg",
        "Crashes with a serious or fatal injury, by crash type",
        "Share of crashes",
        float(crash_base.share.iloc[0]),
        xlim=limit,
    )
    captions["bcn4_crash_severity_by_type"] = _caption(
        "Crashes with at least one death or serious injury as a share of recorded crashes, by "
        f"crash type, Barcelona, {year}, with 95% intervals; types of fewer than {MIN_N} "
        "crashes are left out",
        BCN_SOURCE,
        f"{int(crash_base.n.iloc[0]):,} crashes",
    )


# The model's held-out tests, as a reader would name them.
TEST_LABELS = {
    "rest of Catalonia -> Barcelona municipality": "Rest of Catalonia to Barcelona city",
}


def severity_test_figure(figures_dir: Path, captions: dict[str, str]) -> None:
    """The Catalan severity model's ROC-AUC on years and places left out of its fitting, beside
    the same model fitted and cross-validated in the test population."""
    tests = table("sev_tests")
    last = tests.experiment.str.extract(r"test (\d{4})$")[0]
    label = tests.experiment.map(TEST_LABELS)
    label = label.fillna(
        tests.experiment.str.extract(r"leave out (\w+) demarcation")[0] + " left out"
    )
    label = label.where(last.isna(), "Last year (" + last.fillna("") + ") from the years before it")
    tests = tests.assign(test=label)
    tested = tests.assign(
        row="Model tested, n=" + tests.test_n.map("{:,.0f}".format),
        kind="focal",
        low=tests.roc_auc_low,
        high=tests.roc_auc_high,
    )
    references = tests.assign(
        row="Fitted in the test population",
        kind="reference",
        roc_auc=tests.in_domain_cv_roc_auc,
        low=tests.in_domain_cv_roc_auc,
        high=tests.in_domain_cv_roc_auc,
    )
    drawn = pd.concat([tested, references]).sort_index(kind="stable")
    plots.dot_interval(
        drawn,
        "row",
        "roc_auc",
        "low",
        "high",
        figures_dir / "sev2_held_out.svg",
        "The Catalan severity model on held-out years and places",
        xlabel="ROC-AUC on the held-out crashes",
        reference=0.5,
        reference_label="chance",
        style="kind",
        group="test",
        xlim=_roc_limits(drawn.high),
    )
    captions["sev2_held_out"] = _caption(
        "ROC-AUC of the Catalan severity model refitted without the crashes it is tested on (the "
        "last year from the years before it, each province in turn, Barcelona city from the rest "
        "of Catalonia), with 95% intervals, beside the same model fitted and cross-validated in "
        "the test population (hollow). The n beside each tested model is its number of test "
        "crashes",
        CAT_SOURCE,
    )


def build(figures_dir: Path, captions: dict[str, str]) -> None:
    """Every regional figure; skipped quietly when the microdata tables are not built."""
    needed = (
        "bcn_crash_severity_share",
        "bcn_person_severity_share",
        "cat_fatal_share",
        "sev_tests",
    )
    if not all((TABLES_DIR / f"{name}.csv").exists() for name in needed):
        return
    catalonia_figures(figures_dir, captions)
    barcelona_figures(figures_dir, captions)
    severity_test_figure(figures_dir, captions)
