"""Recorded crash factors, compared only within runs of years without an abrupt jump in the
series. The break rule, the breaks and the effect of the mix of roads on the all-roads speed share
are technical notes on the methodology page (``technical_notes``)."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from dgt_stats import factors
from dgt_stats.site.components import (
    ALL_PAGES,
    DOCS_URL,
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
TITLES = dict(ALL_PAGES)
# The section of the methodology page that holds this page's technical notes.
NOTES = "factors-method"


def _share(value: object, decimals: int = 1) -> str:
    return _fmt_pct(float(value), decimals)


def _run(row: pd.Series) -> str:
    return f"{int(row.first_year)}–{int(row.last_year)}"


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the factor tables, with the
    checks that the sentences built on them still hold."""
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
    speed_same_mix_fall = 1 - speed_same_mix / float(speed_all.share_first)
    # The breaks the figure draws on each kind of road, outside the drug series.
    zone_breaks = changes[
        changes.is_break & (changes.zone != "all") & (changes.factor != "Drugs")
    ].sort_values(["zone", "factor", "to_year"])
    # The series by kind of road that the notes call unbroken: all but the drug series and the
    # two urban series that break.
    unbroken = windows[
        (windows.zone != "all")
        & (windows.factor != "Drugs")
        & ~(
            (windows.zone == "urban")
            & windows.factor.isin(["Alcohol", "Distraction or inattention"])
        )
    ]
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
        "the driver tables leave about half of drivers without a speed status from that year": (
            0.45 <= float(status.loc[status_jump]) <= 0.55
        ),
        "outside the drug series, the only breaks by kind of road are urban alcohol and urban "
        "distraction": set(zone_breaks.factor) == {"Alcohol", "Distraction or inattention"}
        and set(zone_breaks.zone) == {"urban"},
        "at the first year's mix the all-roads fall matches the within-zone falls": abs(
            speed_same_mix_fall - sum(speed_falls) / 2
        )
        < 0.03,
        "every other series by kind of road is one run from the first year to the last": bool(
            unbroken.groupby(["zone", "factor"]).size().eq(1).all()
            and unbroken.first_year.eq(first).all()
            and unbroken.last_year.eq(last).all()
        ),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"factors page: the tables no longer support: {failed}")
    return SimpleNamespace(**locals())


def page_factors(captions: dict[str, str]) -> str:
    f = _facts()
    alcohol_inter, alcohol_urban = f.alcohol_inter, f.alcohol_urban
    speed_all, speed_inter, speed_urban = f.speed_all, f.speed_inter, f.speed_urban
    manoeuvres, rise, fall = f.manoeuvres, f.rise, f.fall
    notes = f'<a href="data.html#{NOTES}">technical notes</a>'

    body = summary(
        "In injury crashes in Spain outside Catalonia and the Basque Country, police recorded "
        f"alcohol in {_share(alcohol_inter.share_first)} of interurban crashes in "
        f"{int(alcohol_inter.first_year)} and {_share(alcohol_inter.share_last)} in "
        f"{int(alcohol_inter.last_year)}. Recorded inappropriate speed fell by about a quarter "
        f"on each kind of road, from {_share(speed_inter.share_first)} to "
        f"{_share(speed_inter.share_last)} on interurban roads and from "
        f"{_share(speed_urban.share_first)} to {_share(speed_urban.share_last)} on urban streets "
        f"({_share(speed_all.share_first)} to {_share(speed_all.share_last)} on all roads, as "
        "crashes shifted to urban streets, where speed is rarely recorded). Recorded factors are "
        "police judgements, not findings of cause."
    )

    body += '<h2 id="recorded-factors">A recorded factor is a police judgement about a crash</h2>'
    body += (
        "<p>Each share is the proportion of injury crashes in which officers recorded the "
        "factor: a judgement made after the crash, not a finding that the factor caused it. A "
        "crash can carry several factors, so the shares overlap. The shares describe the police "
        "record of crashes, not how often drivers drink, speed or are distracted on the road. "
        "The report gives deaths only for crashes with speed recorded, which "
        f'<a href="speed.html">{TITLES["speed"]}</a> compares with other crashes.</p>'
    )

    body += '<h2 id="trends">Recorded alcohol rose and recorded speed fell</h2>'
    break_phrases = [
        f"{zone} {factor.split(' or ')[0].lower()} in "
        + _join([str(int(y)) for y in group.to_year])
        for (zone, factor), group in f.zone_breaks.groupby(["zone", "factor"], sort=False)
    ]
    body += figure(
        "f2_factor_shares",
        "One panel per factor, each showing by year the share of injury crashes with that "
        "factor recorded on interurban roads and on urban streets. The lines break where "
        f"recording stops being comparable: {'; '.join(break_phrases)}; drugs in every year. "
        "On interurban roads alcohol and illegal manoeuvres rise; inappropriate speed falls on "
        "both kinds of road.",
        captions,
    )
    body += (
        "<p>The interurban alcohol series has no break, but its share rose "
        f"{_fmt_pct(float(f.alcohol_shared.share_ratio) - 1, 0)} in {int(rise.to_year)}, the "
        f"year other series broke, and a further {_fmt_pct(f.alcohol_since, 0)} from "
        f"{int(rise.to_year)} to {f.last}. On urban streets recorded alcohol rose within the "
        f"run that starts in {f.urban_alcohol_year}, from {_share(alcohol_urban.share_first)} "
        f"to {_share(alcohol_urban.share_last)}. More recorded alcohol can reflect more "
        "drinking drivers, more breath tests after crashes, or both; these data cannot separate "
        "them.</p>"
        "<p>Distraction or inattention on interurban roads has no break and stayed between "
        f"{_share(f.distraction_band.min())} and {_share(f.distraction_band.max())} of crashes. "
        "Illegal manoeuvres, which the report defines as failing to give way, too short a "
        "following distance, illegal overtaking, an improper turn, or negligent or reckless "
        f"driving, rose on interurban roads from {_share(manoeuvres.share_first)} to "
        f"{_share(manoeuvres.share_last)}, a level they had already reached by "
        f"{f.manoeuvres_reached}.</p>"
    )
    shown = f.windows[(f.windows.zone != "all") & (f.windows.n_years >= 3)].copy()
    shown["order"] = shown.factor.map({name: i for i, name in enumerate(FACTOR_ORDER)})
    shown = shown.sort_values(["order", "zone", "first_year"])
    rows = [
        {
            "Factor": row.factor,
            "Roads": row.zone_label,
            "Comparable years": _run(row),
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

    body += '<h2 id="series-that-break">The urban distraction and drug series break</h2>'
    body += (
        "<p>A share can move because something changed on the road, because the way crashes "
        "are recorded changed, or both. A fixed rule therefore marks an abrupt rise or fall "
        "between two years, or too few crashes to test, as a break in comparability, and each "
        f"series is compared only within the runs of years between its breaks ({notes}). The "
        "rule finds discontinuities; it cannot say whether a break, or a trend within a run, "
        "comes from behaviour, from recording or from both.</p>"
        "<p>Recorded distraction on urban streets rose "
        f"{_fmt_pct(float(rise.share_ratio) - 1, 0)} in {int(rise.to_year)} and fell "
        f"{_fmt_pct(1 - float(fall.share_ratio), 0)} in {int(fall.to_year)} while the "
        "interurban series moved smoothly, so it is compared only within "
        + _join([_run(row) for row in f.urban_runs.itertuples(index=False)])
        + f". Recorded alcohol on urban streets rose {_fmt_pct(f.urban_alcohol_ratio - 1, 0)} "
        f"in {f.urban_alcohol_year} too, the year from which DGT's driver tables leave about "
        'half of drivers without a speed status (<a href="speed.html#driver-tables">'
        f"{TITLES['speed']}</a>); the reason for the shared timing is unknown.</p>"
        f"<p>Drugs were recorded in at most {_fmt_int(f.drugs.max())} crashes a year, and every "
        "year-to-year change in the drug series breaks the rule or has too few crashes to test, "
        "so it is not interpreted.</p>"
    )
    body += downloads(
        [
            ("factor_shares", "shares by year, zone and factor"),
            ("factor_changes", "every year-to-year change and the break test"),
            ("factor_windows", "comparable runs"),
        ],
        method=(f"data.html#{NOTES}", "the break rule and the series it splits"),
    )
    return render_page(
        "factors",
        "Recorded crash factors",
        "How often the police recorded alcohol, inappropriate speed, distraction, illegal "
        f"manoeuvres and drugs in injury crashes from {f.first} to {f.last}, and which of those "
        "series can be compared from year to year.",
        body,
    )


def technical_notes(captions: dict[str, str]) -> str:
    """The break rule, where the series break, and the mix of roads behind the all-roads fall in
    recorded speed: one section for the methodology page."""
    del captions
    f = _facts()
    speed_all = f.speed_all
    page = f'<a href="factors.html">{TITLES["factors"]}</a>'
    document = f'<a href="{DOCS_URL}/methodology.md">methods document</a>'
    return (
        f'<h2 id="{NOTES}">{TITLES["factors"]}: the break rule and the series it splits</h2>'
        f"<p>These notes support {page}; the {document} gives the full account, in its section "
        "on other recorded factors. The shares come from DGT's speed report, which counts for "
        f"each year from {f.first} to {f.last} the injury crashes in Spain outside Catalonia "
        "and the Basque Country in which the police recorded each of five factors.</p>"
        '<h3 id="factors-rule">The break rule</h3>'
        "<p>Every year-to-year change in every series was tested against a fixed rule: a rise "
        f"of more than {_fmt_pct(factors.BREAK_RATIO - 1, 0)} or a fall of more than "
        f"{_fmt_pct(1 - 1 / factors.BREAK_RATIO, 0)} in a single year, or fewer than "
        f"{_fmt_int(factors.MIN_CRASHES)} crashes in either year, marks a break in "
        "comparability, and a series is compared only within the runs of years between its "
        f"breaks. Of the {len(f.changes)} year-to-year changes, {f.n_breaks} are breaks or too "
        "small to test.</p>"
        "<p>The threshold is a convention, and every change is published with its test so that "
        "another threshold can be applied. An unbroken run is not proof that recording stayed "
        "the same: the rule rules out only single-year jumps.</p>"
        '<h3 id="factors-breaks">Where the series break</h3>'
        "<p>Outside the drug series, the only breaks by kind of road are those of "
        + _join(
            [
                f"{zone} {factor.split(' or ')[0].lower()} ("
                + _join([str(int(y)) for y in group.to_year])
                + ")"
                for (zone, factor), group in f.zone_breaks.groupby(["zone", "factor"], sort=False)
            ]
        )
        + f". Every other series by kind of road runs unbroken from {f.first} to {f.last}.</p>"
        f"<p>Drugs were recorded in at most {_fmt_int(f.drugs.max())} crashes a year. The count "
        f"rose {f.drugs_multiple:.0f}-fold from {int(f.drugs.index.min())} to "
        f"{f.drugs_peak_year}, then fell to {_fmt_int(f.drugs.loc[f.drugs_collapse])} in "
        f"{f.drugs_collapse}; every year-to-year change breaks the rule or has too few crashes "
        "to test.</p>"
        '<h3 id="factors-mix">The mix of roads and the all-roads fall in recorded speed</h3>'
        "<p>Recorded inappropriate speed fell "
        f"{_fmt_pct(f.speed_falls[0], 0)} on interurban roads and "
        f"{_fmt_pct(f.speed_falls[1], 0)} on urban streets from {f.first} to {f.last}, but "
        f"{_fmt_pct(f.speed_all_fall, 0)} on all roads, because the mix of crashes moved towards "
        "urban streets, where speed is rarely recorded: "
        f"{_fmt_pct(f.first_interurban)} of injury crashes were on interurban roads in "
        f"{f.first} and {_fmt_pct(f.last_interurban)} in {f.last}. At the {f.first} mix, the "
        f"{f.last} share on all roads would be {_fmt_pct(f.speed_same_mix)} rather than "
        f"{_share(speed_all.share_last)}, a fall of {_fmt_pct(f.speed_same_mix_fall, 0)} from "
        f"{_share(speed_all.share_first)}, close to the falls within each kind of road.</p>"
    )
