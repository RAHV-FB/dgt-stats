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
    # The interurban alcohol series has no break, but its rise includes the year other series
    # jumped; the page gives that year's change and the rise from it.
    alcohol_changes = changes[
        (changes.zone == "interurban") & (changes.factor == "Alcohol")
    ].set_index("to_year")
    alcohol_shared = alcohol_changes.loc[int(rise.to_year)]
    alcohol_shares = shares.xs(("interurban", "Alcohol"))
    alcohol_since = float(alcohol_shares.loc[last] / alcohol_shares.loc[int(rise.to_year)] - 1)
    # How much of the all-roads fall in recorded speed is the shift of crashes towards urban
    # streets: the last year's zone shares weighted by the first year's mix of crashes.
    crashes = numbers["shares"].all_crashes
    first_interurban = float(
        crashes.loc[("interurban", "Inappropriate speed", first)]
        / crashes.loc[("all", "Inappropriate speed", first)]
    )
    last_interurban = float(
        crashes.loc[("interurban", "Inappropriate speed", last)]
        / crashes.loc[("all", "Inappropriate speed", last)]
    )
    speed_same_mix = first_interurban * float(speed_inter.share_last) + (
        1 - first_interurban
    ) * float(speed_urban.share_last)
    speed_falls = [
        1 - float(run.share_last) / float(run.share_first) for run in (speed_inter, speed_urban)
    ]
    speed_all_fall = 1 - float(speed_all.share_last) / float(speed_all.share_first)
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
        "interurban alcohol rose in the year of the urban breaks without breaking the rule": bool(
            1 < float(alcohol_shared.share_ratio) < factors.BREAK_RATIO
            and not alcohol_shared.is_break
        ),
        "interurban alcohol kept rising after that year": alcohol_since > 0,
        # The summary gives the falls within each kind of road and says the all-roads fall is
        # larger because the mix of crashes moved towards urban streets.
        "recorded speed fell by about a quarter on each kind of road": all(
            0.15 < fall < 0.35 for fall in speed_falls
        ),
        "the all-roads fall is larger than either within-zone fall": speed_all_fall
        > max(speed_falls),
        "more of the crashes were on urban streets at the end": last_interurban < first_interurban,
        "speed is rarely recorded on urban streets": float(speed_urban.share_last)
        < float(speed_inter.share_last) / 3,
        "at the first year's mix the all-roads fall matches the within-zone falls": abs(
            (1 - speed_same_mix / float(speed_all.share_first)) - sum(speed_falls) / 2
        )
        < 0.03,
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"factors page: the tables no longer support: {failed}")

    def share(value: object, decimals: int = 1) -> str:
        return _fmt_pct(float(value), decimals)

    def run(row: pd.Series) -> str:
        return f"{int(row.first_year)}–{int(row.last_year)}"

    body = summary(
        f"DGT's speed report counts, for each year from {first} to {last}, the injury crashes in "
        "Spain outside Catalonia and the Basque Country in which the police recorded each of "
        "five factors: alcohol, inappropriate speed, distraction, illegal manoeuvres and drugs. "
        "Following each series only across years with no abrupt jump from one year to the "
        "next, recorded alcohol rose on interurban roads from "
        f"{share(alcohol_inter.share_first)} of injury crashes in "
        f"{int(alcohol_inter.first_year)} to {share(alcohol_inter.share_last)} in "
        f"{int(alcohol_inter.last_year)}. Recorded inappropriate speed fell by about a quarter "
        f"on each kind of road, from {share(speed_inter.share_first)} to "
        f"{share(speed_inter.share_last)} of crashes on interurban roads and from "
        f"{share(speed_urban.share_first)} to {share(speed_urban.share_last)} on urban streets; "
        f"across all roads it fell further, from {share(speed_all.share_first)} to "
        f"{share(speed_all.share_last)}, because more of the crashes were on urban streets, "
        "where speed is rarely recorded. Distraction on urban streets and drug-related crashes "
        "cannot be followed across the period: their series jump abruptly from one year to the "
        "next, and the data cannot say whether recording or behaviour changed."
    )
    body += (
        "<p>Each share is the proportion of injury crashes in which officers recorded the "
        "factor. A crash can carry several factors, so the shares overlap, and a recorded factor "
        "is a police judgement about the crash, not a finding that it caused the crash. The "
        "shares describe the police record of crashes that happened; they do not measure how "
        "often drivers drink, speed or are distracted on the road. The report gives deaths only "
        'for crashes with speed recorded, which <a href="speed.html">Speed</a> compares with '
        "other crashes; for the other factors deaths per crash cannot be computed.</p>"
    )

    body += "<h2>Which years can be compared</h2>"
    body += (
        "<p>A factor's share can move because something changed on the road, because the way "
        "crashes are recorded changed, or both. Every year-to-year change in every series was tested "
        f"against a fixed rule: a rise of more than {_fmt_pct(factors.BREAK_RATIO - 1, 0)} or a "
        f"fall of more than {_fmt_pct(1 - 1 / factors.BREAK_RATIO, 0)} in a single year, or "
        f"fewer than {_fmt_int(factors.MIN_CRASHES)} crashes in either year, marks a break in "
        "comparability, and a series is compared only within the runs of years between its "
        f"breaks. Of the {len(changes)} year-to-year changes, {n_breaks} are breaks or too small "
        "to test. The rule finds discontinuities; it cannot say whether a break, or a trend "
        "within a run, comes from behaviour, from recording or from both. The threshold is a convention, and "
        "every change is published with its test so that another threshold can be applied.</p>"
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
        "injury crashes. The rule finds no abrupt jump in it, but the share rose "
        f"{_fmt_pct(float(alcohol_shared.share_ratio) - 1, 0)} in {int(rise.to_year)}, the "
        f"year other series broke (below); from {int(rise.to_year)} to {last} it rose "
        f"{_fmt_pct(alcohol_since, 0)}. On urban streets the series breaks in {urban_alcohol_year} and rises "
        f"within the later run, from {share(alcohol_urban.share_first)} in "
        f"{int(alcohol_urban.first_year)} to {share(alcohol_urban.share_last)} in "
        f"{int(alcohol_urban.last_year)}. More recorded alcohol can reflect more drinking "
        "drivers, more breath tests after crashes, or both, and these data cannot separate "
        "them.</p>"
    )
    body += (
        "<p>Recorded inappropriate speed fell on both kinds of road without a break: from "
        f"{share(speed_inter.share_first)} to {share(speed_inter.share_last)} of injury crashes "
        f"on interurban roads and from {share(speed_urban.share_first)} to "
        f"{share(speed_urban.share_last)} on urban streets. Distraction or inattention on "
        "interurban roads has no break and stayed between "
        f"{share(distraction_band.min())} and {share(distraction_band.max())} of crashes. "
        "Illegal manoeuvres, which the report defines as failing to give way, too short a "
        "following distance, illegal overtaking, an improper turn, or negligent or reckless "
        f"driving, rose on interurban roads from {share(manoeuvres.share_first)} to "
        f"{share(manoeuvres.share_last)}, a level they had already reached by "
        f"{manoeuvres_reached}.</p>"
    )

    body += "<h2>Series that break</h2>"
    body += (
        "<p>Recorded distraction on urban streets rose "
        f"{_fmt_pct(float(rise.share_ratio) - 1, 0)} in {int(rise.to_year)} and fell "
        f"{_fmt_pct(1 - float(fall.share_ratio), 0)} in {int(fall.to_year)}, while the "
        "interurban series moved smoothly, so the urban series is compared only within "
        + _join([run(row) for row in urban_runs.itertuples(index=False)])
        + ". Recorded alcohol on urban streets rose "
        f"{_fmt_pct(urban_alcohol_ratio - 1, 0)} in the same year, {urban_alcohol_year}, which "
        "is also the year the share of drivers with no speed status recorded in DGT's driver "
        "tables, which cover all of Spain, rose from "
        f"{_fmt_pct(float(status.loc[status_jump - 1]), 0)} to "
        f"{_fmt_pct(float(status.loc[status_jump]), 0)}; the reason for the shared timing is "
        f"unknown. Drugs were recorded in at most {_fmt_int(drugs.max())} crashes a "
        f"year, and the count climbed {drugs_multiple:.0f}-fold from {int(drugs.index.min())} to "
        f"{drugs_peak_year} before collapsing in {drugs_collapse}. Every year-to-year change in "
        "the drug series breaks the rule or has too few crashes, so it is not interpreted.</p>"
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
        "How often the police recorded alcohol, inappropriate speed, distraction, illegal "
        f"manoeuvres and drugs in injury crashes from {first} to {last}, and which of those "
        "series can be compared from year to year.",
        body,
    )
