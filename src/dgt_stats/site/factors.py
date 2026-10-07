"""Recorded crash factors, compared only across years in which the recording is consistent."""

from __future__ import annotations

import pandas as pd

from dgt_stats import factors
from dgt_stats.site.components import (
    _fmt_int,
    _fmt_pct,
    _join,
    _signed_pct,
    downloads,
    figure,
    limitation,
    read_table,
    render_page,
    summary,
    table,
)
from dgt_stats.site.numbers import _factor_numbers, _window

FACTOR_ORDER = (
    "Alcohol",
    "Inappropriate speed",
    "Distraction or inattention",
    "Illegal manoeuvres",
    "Drugs",
)


def page_factors(captions: dict[str, str]) -> str:
    numbers = _factor_numbers()
    windows, changes = numbers["windows"], numbers["changes"]
    first, last = int(windows.first_year.min()), int(windows.last_year.max())
    alcohol_inter = _window(windows, "interurban", "Alcohol", last)
    alcohol_urban = _window(windows, "urban", "Alcohol", last)
    speed_all = _window(windows, "all", "Inappropriate speed", last)
    speed_inter = _window(windows, "interurban", "Inappropriate speed", last)
    speed_urban = _window(windows, "urban", "Inappropriate speed", last)
    urban_distraction = changes[
        (changes.zone == "urban") & (changes.factor == "Distraction or inattention") & changes.jump
    ]
    manoeuvres = _window(windows, "interurban", "Illegal manoeuvres", last)
    n_breaks = int(changes.is_break.sum())
    drugs = numbers["shares"].xs(("all", "Drugs"), level=["zone", "factor"]).crashes
    drugs_peak_year = int(drugs.idxmax())
    drugs_multiple = float(drugs.max() / drugs.loc[drugs.index.min()])
    drugs_fall = drugs.diff()
    drugs_collapse = int(drugs_fall.idxmin())
    urban_alcohol_jump = changes[
        (changes.zone == "urban") & (changes.factor == "Alcohol") & changes.jump
    ]
    status = read_table("q9_infraction_shares")
    status = status[status.zone == "all"].set_index("year").share_unknown
    status_jump = int(status.diff().idxmax())
    rise, fall = urban_distraction.iloc[0], urban_distraction.iloc[-1]
    inter_distraction = changes[
        (changes.zone == "interurban") & (changes.factor == "Distraction or inattention")
    ]
    shares = numbers["shares"].share
    distraction_band = shares.xs(("interurban", "Distraction or inattention"))
    manoeuvre_shares = shares.xs(("interurban", "Illegal manoeuvres"))
    manoeuvres_reached = int(
        manoeuvre_shares[manoeuvre_shares >= float(manoeuvres.share_last)].index.min()
    )
    drug_changes = changes[changes.factor == "Drugs"]
    urban_alcohol_year = int(urban_alcohol_jump.to_year.iloc[0])
    urban_alcohol_ratio = float(urban_alcohol_jump.share_ratio.iloc[0])
    urban_runs = windows[
        (windows.zone == "urban") & (windows.factor == "Distraction or inattention")
    ].sort_values("first_year")
    urban_runs = urban_runs[urban_runs.first_year >= int(rise.to_year)]
    checks = {
        "recorded alcohol rose on interurban roads across the whole series": float(
            alcohol_inter.share_last
        )
        > float(alcohol_inter.share_first)
        and int(alcohol_inter.first_year) == first
        and int(alcohol_inter.last_year) == last,
        "recorded inappropriate speed fell on all roads": float(speed_all.share_last)
        < float(speed_all.share_first),
        "recorded inappropriate speed fell on both kinds of road, without a break": all(
            float(run.share_last) < float(run.share_first)
            and int(run.first_year) == first
            and int(run.last_year) == last
            for run in (speed_inter, speed_urban)
        ),
        "urban alcohol rose after its break": float(alcohol_urban.share_last)
        > float(alcohol_urban.share_first),
        "every year-to-year change in drugs breaks the rule": bool(drug_changes.is_break.all()),
        "illegal manoeuvres on interurban roads rose": float(manoeuvres.share_last)
        > float(manoeuvres.share_first),
        "urban distraction has one jump up and a later one down": len(urban_distraction) == 2
        and rise.share_ratio > 1 > fall.share_ratio,
        "interurban distraction has no break": not inter_distraction.is_break.any(),
        "urban alcohol jumps up in the year urban distraction does": list(
            urban_alcohol_jump.to_year
        )
        == [int(rise.to_year)]
        and urban_alcohol_ratio > 1,
        "the driver tables' unknown speed status jumps in the year of the urban breaks": (
            status_jump == int(rise.to_year)
        ),
        "drugs fall most in one year, to the end of the series": drugs_collapse > drugs_peak_year,
        "urban distraction splits into two runs after its first break": len(urban_runs) == 2,
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"factors page: the tables no longer support: {failed}")

    def share(value: object, decimals: int = 1) -> str:
        return _fmt_pct(float(value), decimals)

    def run(row: pd.Series) -> str:
        return f"{int(row.first_year)}–{int(row.last_year)}"

    body = summary(
        "Within years of consistent recording, the share of injury crashes in which the police "
        "recorded alcohol rose on interurban roads from "
        f"{share(alcohol_inter.share_first)} in {int(alcohol_inter.first_year)} to "
        f"{share(alcohol_inter.share_last)} in {int(alcohol_inter.last_year)}, and the share "
        f"with inappropriate speed recorded fell from {share(speed_all.share_first)} to "
        f"{share(speed_all.share_last)} across all roads. The series for distraction on urban "
        "streets breaks twice and is compared only within the runs between its breaks; the drug "
        "series breaks, or is too small to test, between every pair of consecutive years."
    )
    body += (
        "<p>Each share is the proportion of injury crashes in which officers recorded the "
        "factor; a crash can carry several factors, so the shares overlap. The shares describe "
        "the police record of crashes that happened and do not measure how often drivers drink, "
        'speed or are distracted on the road (<a href="data.html#records">Methodology</a>).</p>'
    )

    body += "<h2>Comparable years</h2>"
    body += (
        "<p>A factor's share can move because something changed on the road or because the way "
        "crashes are recorded changed. Every year-to-year change in every factor's share was "
        "therefore tested "
        f"against a fixed rule: a rise of more than {_fmt_pct(factors.BREAK_RATIO - 1, 0)} or a "
        f"fall of more than {_fmt_pct(1 - 1 / factors.BREAK_RATIO, 0)} in a single year (the "
        "same ratio in either direction), or fewer than "
        f"{_fmt_int(factors.MIN_CRASHES)} crashes in either year, marks a break in "
        "comparability. A series is compared only within the runs of years between its breaks. "
        f"Of the {len(changes)} year-to-year changes, {n_breaks} are breaks or too small to test. "
        "The rule locates a discontinuity; whether a break, or a trend within a run, is "
        "behavioural or recording-related is left open. The threshold is a convention, and "
        "every change is published with its test result so that another threshold can be "
        "applied.</p>"
    )
    body += figure(
        "f2_factor_shares",
        "One panel per factor, each showing by year the share of injury crashes with that "
        "factor recorded on interurban roads and on urban streets; the lines are broken where "
        "the recording stops being comparable.",
        captions,
    )

    body += "<h2>Trends within comparable years</h2>"
    shown = windows[(windows.zone != "all") & (windows.n_years >= 3)].copy()
    shown["order"] = shown.factor.map({name: i for i, name in enumerate(FACTOR_ORDER)})
    shown = shown.sort_values(["order", "zone", "first_year"])
    rows = [
        {
            "Factor": row.factor,
            "Roads": row.zone_label,
            "Comparable years": run(row),
            "First year": row.share_first,
            "Last year": row.share_last,
            "Relative change": _signed_pct(float(row.change_in_share), 0),
        }
        for row in shown.itertuples(index=False)
    ]
    body += table(
        pd.DataFrame(rows),
        "Share of injury crashes with each factor recorded, at the start and end of every run "
        "of three or more comparable years, Spain outside Catalonia and the Basque Country.",
        {"First year": "pct", "Last year": "pct"},
    )
    body += (
        "<p>Recorded alcohol rose on interurban roads across the whole period without a break, "
        f"from {share(alcohol_inter.share_first)} to {share(alcohol_inter.share_last)} of "
        f"injury crashes. On urban streets the series breaks in {urban_alcohol_year} and rises "
        f"within the later run, from {share(alcohol_urban.share_first)} in "
        f"{int(alcohol_urban.first_year)} to {share(alcohol_urban.share_last)} in "
        f"{int(alcohol_urban.last_year)}. More recorded alcohol can mean more drinking drivers or "
        "more breath tests after crashes; DGT's enforcement statistics, which would separate the "
        "two, are outside this study.</p>"
    )
    body += (
        "<p>Recorded inappropriate speed fell on both kinds of road without a break: from "
        f"{share(speed_inter.share_first)} to {share(speed_inter.share_last)} of injury crashes "
        f"on interurban roads and from {share(speed_urban.share_first)} to "
        f"{share(speed_urban.share_last)} on urban streets. Distraction or inattention on "
        "interurban roads has no break and stayed between "
        f"{share(distraction_band.min())} and {share(distraction_band.max())} of crashes. "
        "Illegal manoeuvres, a composite of priority, distance, overtaking and negligent "
        f"driving, rose on interurban roads from {share(manoeuvres.share_first)} to "
        f"{share(manoeuvres.share_last)}, a level they had already reached by "
        f"{manoeuvres_reached}.</p>"
    )

    body += "<h2>Series with breaks in recording</h2>"
    body += (
        "<p>Recorded distraction on urban streets rose "
        f"{_fmt_pct(float(rise.share_ratio) - 1, 0)} in {int(rise.to_year)} and fell "
        f"{_fmt_pct(1 - float(fall.share_ratio), 0)} in "
        f"{int(fall.to_year)}, while the interurban series has no break. The urban series is "
        "therefore compared only within "
        + _join([run(row) for row in urban_runs.itertuples(index=False)])
        + ". Recorded alcohol on urban streets rose "
        f"{_fmt_pct(urban_alcohol_ratio - 1, 0)} in the same year, {urban_alcohol_year}. Drugs "
        f"were recorded in at most {_fmt_int(drugs.max())} crashes a year; the count climbed "
        f"{drugs_multiple:.0f}-fold from {int(drugs.index.min())} to {drugs_peak_year} and "
        f"collapsed in {drugs_collapse}. "
        "Every year-to-year change in the drug series either has too few crashes or breaks the "
        "rule, so the drug series is left uninterpreted. In "
        f"{status_jump}, too, the share of drivers with no speed status in DGT's driver tables "
        f"jumped to {_fmt_pct(float(status.loc[status_jump]), 0)}, from "
        f"{_fmt_pct(float(status.loc[status_jump - 1]), 0)} the year before; the reason for the "
        "shared timing is unknown.</p>"
    )

    body += limitation(
        "The report gives deaths only for crashes with inappropriate speed recorded, which "
        '<a href="speed.html">Speed</a> compares with other crashes. Deaths per crash with '
        "alcohol, distraction or the other factors recorded cannot be computed from it."
    )
    body += downloads(
        [
            ("factor_shares", "shares by year, zone and factor"),
            ("factor_changes", "every year-to-year change and the break test"),
            ("factor_windows", "comparable runs"),
        ],
        method=("data.html#records", "police-recorded factors"),
    )
    return render_page(
        "factors",
        "Recorded crash factors",
        f"DGT's thematic report on speed counts, for each year from {first} to {last}, the "
        "injury crashes in Spain outside Catalonia and the Basque Country in which the police "
        "recorded alcohol, inappropriate speed, distraction, illegal manoeuvres or drugs.",
        body,
    )
