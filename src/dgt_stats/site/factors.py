"""The other recorded factors, read only within runs of years without a recording break."""

from __future__ import annotations

import pandas as pd

from dgt_stats import factors
from dgt_stats.site.components import (
    _fmt_int,
    _fmt_pct,
    _join,
    _signed_pct,
    conclusion,
    downloads,
    figure,
    key_figures,
    limits,
    read_table,
    render_page,
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
    alcohol_inter = _window(windows, "interurban", "Alcohol", 2023)
    alcohol_urban = _window(windows, "urban", "Alcohol", 2023)
    speed_all = _window(windows, "all", "Inappropriate speed", 2023)
    distraction_inter = _window(windows, "interurban", "Distraction or inattention", 2023)
    urban_distraction = changes[
        (changes.zone == "urban") & (changes.factor == "Distraction or inattention") & changes.jump
    ]
    manoeuvres = _window(windows, "interurban", "Illegal manoeuvres", 2023)
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
    checks = {
        "urban distraction has one jump up and a later one down": len(urban_distraction) == 2
        and rise.share_ratio > 1 > fall.share_ratio,
        "interurban distraction has no break": not inter_distraction.is_break.any(),
        "urban alcohol jumps in the year urban distraction does": list(urban_alcohol_jump.to_year)
        == [int(rise.to_year)],
        "the driver tables' unknown speed status jumps in the year of the urban breaks": (
            status_jump == int(rise.to_year)
        ),
        "drugs fall most in one year, to the end of the series": drugs_collapse > drugs_peak_year,
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"factors page: the tables no longer support: {failed}")

    body = key_figures(
        [
            (
                "Alcohol, interurban",
                f"{_fmt_pct(float(alcohol_inter.share_first))} → "
                f"{_fmt_pct(float(alcohol_inter.share_last))}",
                f"of injury crashes, {int(alcohol_inter.first_year)}–"
                f"{int(alcohol_inter.last_year)}, no break",
            ),
            (
                "Inappropriate speed, all roads",
                f"{_fmt_pct(float(speed_all.share_first))} → "
                f"{_fmt_pct(float(speed_all.share_last))}",
                f"{int(speed_all.first_year)}–{int(speed_all.last_year)}, no break",
            ),
            (
                "Urban distraction",
                f"{len(urban_distraction)} breaks",
                "in "
                + _join([str(int(year)) for year in urban_distraction.to_year])
                + ": not comparable across",
            ),
            ("Drugs", "not comparable", f"too few crashes and a collapse in {drugs_collapse}"),
        ]
    )
    body += (
        '<p class="answer">DGT publishes, for each year, how many injury crashes had each of '
        f"{len(FACTOR_ORDER)} concurrent factors recorded by the police. Before any trend is "
        "read, every year-to-year change in each factor's share is tested for a recording "
        f"break: a rise of more than {_fmt_pct(factors.BREAK_RATIO - 1, 0)} or a fall of more "
        f"than {_fmt_pct(1 - 1 / factors.BREAK_RATIO, 0)} in a single year, which no change in "
        f"behaviour produces across tens of thousands of crashes. {n_breaks} of the "
        f"{len(changes)} year-to-year changes fail that test or are too small to test (fewer "
        f"than {factors.MIN_CRASHES} crashes in either year). Within "
        "the runs that pass, two trends are clear. Recorded alcohol rose on interurban roads, "
        f"from {_fmt_pct(float(alcohol_inter.share_first))} to "
        f"{_fmt_pct(float(alcohol_inter.share_last))} of crashes between "
        f"{int(alcohol_inter.first_year)} and {int(alcohol_inter.last_year)}, and recorded "
        f"inappropriate speed fell, from {_fmt_pct(float(speed_all.share_first))} to "
        f"{_fmt_pct(float(speed_all.share_last))} of all injury crashes.</p>"
    )
    body += figure(
        "f2_factor_shares",
        "Share of injury crashes with each factor recorded, broken at recording breaks",
        captions,
    )
    shown = windows[(windows.zone != "all") & (windows.n_years >= 3)].copy()
    shown["order"] = shown.factor.map({name: i for i, name in enumerate(FACTOR_ORDER)})
    shown = shown.sort_values(["order", "zone", "first_year"])
    rows = [
        {
            "Factor": row.factor,
            "Zone": row.zone_label,
            "Comparable years": f"{int(row.first_year)}–{int(row.last_year)}",
            "Share, first year": row.share_first,
            "Share, last year": row.share_last,
            "Change in share": _signed_pct(float(row.change_in_share), 0),
        }
        for row in shown.itertuples(index=False)
    ]
    body += table(
        pd.DataFrame(rows),
        "Runs of three or more comparable years, by factor and zone. Source: DGT Informe "
        "temático Factor Velocidad, Spain without Cataluña and País Vasco",
        {"Share, first year": "pct", "Share, last year": "pct"},
    )
    body += (
        "<p>The alcohol rise on interurban roads runs across the whole decade without a break, "
        "and the urban series rises too once its own 2016 break is set aside, from "
        f"{_fmt_pct(float(alcohol_urban.share_first))} in {int(alcohol_urban.first_year)} to "
        f"{_fmt_pct(float(alcohol_urban.share_last))}. More recorded alcohol can mean more "
        "drinking drivers or more testing after a crash; DGT's enforcement statistics, which "
        "would tell the two apart, are not in these files. Interurban distraction is stable at "
        f"about {_fmt_pct(float(distraction_inter.share_last), 0)} of crashes. Illegal "
        "manoeuvres, a composite of priority, distance, overtaking and negligent driving, rose "
        f"on interurban roads from {_fmt_pct(float(manoeuvres.share_first), 0)} to "
        f"{_fmt_pct(float(manoeuvres.share_last), 0)}, most of it before 2018, which passes "
        "the rule but is the kind of drift a gradual change in recording also produces.</p>"
    )
    body += (
        "<p>Three series fail. Urban distraction's share changes by "
        f"{_signed_pct(float(rise.share_ratio) - 1)} in {int(rise.to_year)} and by "
        f"{_signed_pct(float(fall.share_ratio) - 1)} in {int(fall.to_year)}, while the "
        "interurban series has no break, so the urban series is read as having a break in how "
        "it was recorded and is not compared across it (the files do not say what changed). "
        f"Urban alcohol has the same {int(rise.to_year)} jump "
        f"({_signed_pct(float(urban_alcohol_jump.share_ratio.iloc[0]) - 1)}). Drugs are "
        f"recorded in at most {_fmt_int(drugs.max())} crashes a year, climb "
        f"{drugs_multiple:.0f}-fold from {int(drugs.index.min())} to {drugs_peak_year} and "
        f"collapse in {drugs_collapse}: nothing about drug-driving can be read from them. "
        f"{status_jump} is also the year the driver tables stop recording a speed status for "
        f"{_fmt_pct(float(status.loc[status_jump]), 0)} of all drivers, which is why it keeps "
        "appearing.</p>"
    )
    body += downloads(
        [
            ("factor_shares", "shares by year, zone and factor"),
            ("factor_changes", "every year-to-year change and the break test"),
            ("factor_windows", "comparable runs"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        f"Of DGT's {len(FACTOR_ORDER)} recorded factors, three can be compared across years "
        "once recording "
        "breaks are taken out: recorded alcohol has risen on interurban roads, recorded "
        "inappropriate speed has fallen, and interurban distraction has held steady. Urban "
        "distraction and urban alcohol can only be compared within their own runs of years, and "
        "drugs cannot be compared at all. None of these shares is a measure of how often "
        "drivers drink, speed or look at a phone; each is how often the police recorded it in a "
        "crash that injured someone."
    )
    body += limits(
        "A crash can have several factors recorded, so the shares do not add up. The rule for "
        "a break is a threshold, not a test with a known error rate; every change is published "
        "so another threshold can be applied. The report covers Spain without Cataluña and País "
        "Vasco and ends in 2023. It gives crashes by factor but not deaths, so the severity of "
        "alcohol or distraction crashes cannot be compared the way speed is."
    )
    return render_page(
        "factors",
        "Alcohol, distraction and other recorded factors",
        "Which of DGT's recorded crash factors can be compared from year to year, and what do "
        "the comparable ones show?",
        body,
    )
