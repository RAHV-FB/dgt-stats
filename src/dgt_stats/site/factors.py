"""Police-recorded inappropriate speed and its severity, and the other recorded crash factors,
compared only within runs of years without an abrupt jump in the series. How the speed report
and the crash records are combined, the model behind the adjusted ratio and the break rule are
technical notes on the methodology page (``technical_notes``). Every number is read from the
factor and speed tables and every qualitative sentence is checked against them."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pandas as pd

from dgt_stats import factors
from dgt_stats.site.components import (
    ALL_PAGES,
    DOCS_URL,
    _fmt_int,
    _fmt_pct,
    _join,
    _ratio_ci,
    downloads,
    figure,
    read_table,
    render_page,
    summary,
    table,
)
from dgt_stats.site.numbers import _factor_numbers, _speed_numbers, _window

TITLES = dict(ALL_PAGES)
# The section of the methodology page that holds this page's technical notes.
NOTES = "factors-method"


def _share(value: object, decimals: int = 1) -> str:
    return _fmt_pct(float(value), decimals)


def _run(row: pd.Series) -> str:
    return f"{int(row.first_year)}–{int(row.last_year)}"


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, with the checks that the sentences
    built on them still hold."""
    speed = _speed_numbers()
    pooled, all_roads = speed["pooled"], speed["all_roads"]
    adjusted = pooled.loc["adjusted"]
    last_speed = int(all_roads.index.max())
    latest = all_roads.loc[last_speed]
    yearly = speed["yearly"]
    by_type = yearly[yearly.totals_source == "microdata"]
    types_span = f"{int(by_type.year.min())}–{int(by_type.year.max())}"
    crude, rate = float(adjusted.crude_ratio), float(adjusted.rate_ratio)
    adjusted_ci = f"{float(adjusted.ratio_low):.2f}–{float(adjusted.ratio_high):.2f}"
    where_share = 1 - math.log(rate) / math.log(crude)
    types = pooled.drop(index="adjusted")
    urban = pooled.loc["urban"]
    dual = pooled.loc["dual_carriageway"]

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
    urban_alcohol_year = int(urban_alcohol_jump.to_year.iloc[0])
    urban_alcohol_ratio = float(urban_alcohol_jump.share_ratio.iloc[0])
    urban_runs = windows[
        (windows.zone == "urban") & (windows.factor == "Distraction or inattention")
    ].sort_values("first_year")
    urban_runs = urban_runs[urban_runs.first_year >= int(rise.to_year)]
    alcohol_changes = changes[
        (changes.zone == "interurban") & (changes.factor == "Alcohol")
    ].set_index("to_year")
    alcohol_shared = alcohol_changes.loc[int(rise.to_year)]
    alcohol_shares = shares.xs(("interurban", "Alcohol"))
    alcohol_since = float(alcohol_shares.loc[last] / alcohol_shares.loc[int(rise.to_year)] - 1)
    # The interurban speed series: flat to 2020, then a fall.
    inter_series = shares.xs(("interurban", "Inappropriate speed"))
    flat_to = 2020
    fall_to = flat_to + 2
    inter_flat = float(inter_series.loc[flat_to] / inter_series.loc[first] - 1)
    inter_late_fall = float(inter_series.loc[fall_to] / inter_series.loc[flat_to] - 1)
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
    speed_all_fall = 1 - float(speed_all.share_last) / float(speed_all.share_first)
    speed_same_mix_fall = 1 - speed_same_mix / float(speed_all.share_first)
    zone_breaks = changes[changes.is_break & (changes.zone != "all")].sort_values(
        ["zone", "factor", "to_year"]
    )
    unbroken = windows[
        (windows.zone != "all")
        & ~(
            (windows.zone == "urban")
            & windows.factor.isin(["Alcohol", "Distraction or inattention"])
        )
    ]
    unknown_after = status.loc[status_jump:]
    speed_changes = changes[changes.factor == "Inappropriate speed"]
    checks = {
        "speed crashes are a larger share of deaths than of crashes": float(latest.share_of_deaths)
        > float(latest.share_of_crashes),
        "the adjusted ratio is above one and below the crude one": 1 < rate < crude,
        "the adjusted ratio is about two": 1.8 <= rate <= 2.2,
        "the adjusted ratio's interval excludes no difference": float(adjusted.ratio_low) > 1,
        "speed crashes concentrate where every crash is more often fatal": bool(
            types.speed_crashes.idxmax() == "other_interurban"
            and types.loc["other_interurban", "speed_crashes"] / types.speed_crashes.sum()
            > types.loc["other_interurban", "other_crashes"] / types.other_crashes.sum()
            and types.other_deaths_per_100.idxmax() == "other_interurban"
        ),
        "every road type's interval lies above one": bool((types.ratio_low > 1).all()),
        "urban streets carry the largest ratio and the lowest ordinary death rate": bool(
            types.rate_ratio.idxmax() == "urban" and types.other_deaths_per_100.idxmin() == "urban"
        ),
        "dual carriageways carry the smallest ratio": types.rate_ratio.idxmin()
        == "dual_carriageway",
        "the adjusted model has extra variation to allow for": float(adjusted.dispersion) > 1,
        "the road-type ratios differ by more than chance": float(adjusted.heterogeneity_p) < 0.001,
        "letting the ratio differ by road type removes most of the extra variation": float(
            adjusted.dispersion_by_road_type
        )
        < float(adjusted.dispersion) / 2,
        "the adjusted ratio lies between the road-type ratios": float(types.rate_ratio.min())
        < rate
        < float(types.rate_ratio.max()),
        "most deaths in speed crashes are on other interurban roads": float(
            types.loc["other_interurban", "speed_deaths"]
        )
        > types.speed_deaths.sum() / 2,
        "the road-type intervals allow for year-to-year variation": bool(
            (types.dispersion >= 1).all()
        ),
        "the unknown speed status jumps and stays near half": bool(
            (unknown_after > 2 * status.iloc[0]).all() and unknown_after.between(0.45, 0.55).all()
        ),
        "the crash series with speed recorded has no break": not bool(speed_changes.is_break.any()),
        "recorded alcohol rose on interurban roads across the whole series": float(
            alcohol_inter.share_last
        )
        > float(alcohol_inter.share_first)
        and int(alcohol_inter.first_year) == first
        and int(alcohol_inter.last_year) == last,
        "recorded inappropriate speed fell on all roads": float(speed_all.share_last)
        < float(speed_all.share_first),
        "recorded inappropriate speed on both kinds of road is one run, without a break": all(
            int(run.first_year) == first and int(run.last_year) == last
            for run in (speed_inter, speed_urban)
        ),
        "interurban speed was flat to 2020": abs(inter_flat) < 0.05,
        "interurban speed fell by a fifth or more from 2020 to 2022": inter_late_fall < -0.2,
        "interurban speed fell in 2021 and did not recover by the last year": bool(
            inter_series.loc[flat_to + 1] < inter_series.loc[flat_to]
            and inter_series.loc[last] < inter_series.loc[flat_to] * 0.85
        ),
        "urban alcohol rose after its break": float(alcohol_urban.share_last)
        > float(alcohol_urban.share_first),
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
        "urban distraction splits into two runs after its first break": len(urban_runs) == 2,
        "interurban alcohol rose in the year of the urban breaks without breaking the rule": bool(
            1 < float(alcohol_shared.share_ratio) < factors.BREAK_RATIO
            and not alcohol_shared.is_break
        ),
        "interurban alcohol kept rising after that year": alcohol_since > 0,
        "the all-roads fall is larger than the fall on either kind of road": speed_all_fall
        > max(
            1 - float(run.share_last) / float(run.share_first) for run in (speed_inter, speed_urban)
        ),
        "more of the crashes were on urban streets at the end": last_interurban < first_interurban,
        "speed is rarely recorded on urban streets": float(speed_urban.share_last)
        < float(speed_inter.share_last) / 3,
        "the driver tables leave about half of drivers without a speed status from that year": (
            0.45 <= float(status.loc[status_jump]) <= 0.55
        ),
        "the only breaks by kind of road are urban alcohol and urban distraction": set(
            zone_breaks.factor
        )
        == {"Alcohol", "Distraction or inattention"}
        and set(zone_breaks.zone) == {"urban"},
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
    alcohol_urban = f.alcohol_urban
    speed_all, speed_urban = f.speed_all, f.speed_urban
    manoeuvres, rise, fall = f.manoeuvres, f.rise, f.fall
    urban, dual, status = f.urban, f.dual, f.status
    status_jump = f.status_jump
    notes = f'<a href="data.html#{NOTES}">technical notes</a>'

    body = summary(
        "Outside Catalonia and the Basque Country, injury crashes where police recorded "
        f"inappropriate speed had {f.crude:.2f} times as many deaths per crash as other "
        f"crashes in {f.types_span}. By road type it ran from "
        f"{float(dual.rate_ratio):.2f} times on dual carriageways to "
        f"{float(urban.rate_ratio):.2f} times on urban streets; their weighted summary is "
        f"{f.rate:.2f} times (95% interval {f.adjusted_ci}). These are associations in police "
        "records, not estimates of what speed causes. Recorded speed was not in steady decline: "
        f"interurban roads were flat to {f.flat_to} and fell in {f.flat_to + 1}–{f.fall_to}, "
        "and a change in recording cannot be excluded."
    )

    body += '<h2 id="road-types">More deaths per crash on every road type</h2>'
    body += (
        f"<p>In {f.last_speed}, police recorded inappropriate speed in "
        f"{_fmt_pct(float(f.latest.share_of_crashes))} of injury crashes outside Catalonia and "
        "the Basque Country, and those crashes accounted for "
        f"{_fmt_pct(float(f.latest.share_of_deaths))} of the deaths. They are concentrated on "
        "interurban roads other than motorways and dual carriageways, where any crash is more "
        "often fatal and where most of their deaths occur, so comparing them with other crashes "
        "on the same kind of road and in the same year lowers the ratio.</p>"
    )
    body += figure(
        "f1_speed_severity",
        "Dot chart, on a logarithmic scale, of the ratio of deaths per 100 injury crashes with "
        "speed recorded to deaths per 100 other crashes, with 95% intervals, for four road types "
        "and for all roads adjusted for road type and year. Every interval lies above one. "
        f"Urban streets have the largest ratio, {float(urban.rate_ratio):.1f}, and the adjusted "
        f"ratio is {f.rate:.1f}.",
        captions,
    )
    rows = []
    for key in ("urban", "motorway", "dual_carriageway", "other_interurban"):
        row = f.pooled.loc[key]
        rows.append(
            {
                "Road type": row.road_type_label,
                "Crashes with speed recorded": row.speed_crashes,
                "Deaths per 100 crashes with speed recorded": row.speed_deaths_per_100,
                "Deaths per 100 other crashes": row.other_deaths_per_100,
                "Ratio (95% interval)": _ratio_ci(
                    float(row.rate_ratio), float(row.ratio_low), float(row.ratio_high)
                ),
            }
        )
    body += table(
        pd.DataFrame(rows),
        f"Deaths per 100 injury crashes with and without speed recorded, by road type, Spain "
        f"outside Catalonia and the Basque Country, {f.types_span}. The intervals allow for the "
        "ratio varying from year to year more than chance alone would make it.",
        {
            "Crashes with speed recorded": "int",
            "Deaths per 100 crashes with speed recorded": "dec2",
            "Deaths per 100 other crashes": "dec2",
        },
    )
    body += (
        "<p>The ratio was largest on urban streets, where an ordinary injury crash rarely kills "
        f"({float(urban.other_deaths_per_100):.2f} deaths per 100 crashes, against "
        f"{float(urban.speed_deaths_per_100):.2f} with speed recorded), and smallest on dual "
        "carriageways. The road-type ratios differ by more than chance, so the all-roads "
        f"summary of {f.rate:.2f} describes no single kind of road: it is weighted towards other "
        "interurban roads, and its interval is widened to allow for how much the ratios differ. "
        f"How the ratios are estimated is set out in the {notes}.</p>"
        "<p>Deaths per 100 injury crashes on each road type, for every recorded crash in Spain, "
        'can be explored by region and year in the <a href="crash-explorer.html">crash '
        "statistics explorer</a>.</p>"
    )

    body += '<h2 id="recorded-factors">A recorded factor is a police judgement about a crash</h2>'
    body += (
        "<p>Each share below is the proportion of injury crashes in which officers recorded the "
        "factor: a judgement made after the crash, usually once its outcome is known, not a "
        "finding that the factor caused it. A crash can carry several factors, so the shares "
        "overlap. They describe the police record of crashes, not how often drivers drink, speed "
        "or are distracted on the road.</p>"
        "<p>No file records how fast anyone was travelling, so the ratio above shows that crashes with speed recorded were deadlier than other crashes on "
        "the same kind of road, not that speed caused those crashes or their deaths.</p>"
        "<p>Recording could bias the ratio either way. Police may look harder for speed when "
        "someone has died, which would raise it, while speed that played a part but went "
        "unrecorded leaves those crashes among the others, which would lower it. The data "
        "cannot measure either bias.</p>"
    )

    body += '<h2 id="trends">Recorded alcohol rose; recorded speed fell late</h2>'
    break_phrases = [
        f"{zone} {factor.split(' or ')[0].lower()} in "
        + _join([str(int(y)) for y in group.to_year])
        for (zone, factor), group in f.zone_breaks.groupby(["zone", "factor"], sort=False)
    ]
    body += figure(
        "f2_factor_shares",
        "One panel per factor, each showing by year the share of injury crashes with that "
        "factor recorded on interurban roads and on urban streets. The lines break where "
        f"recording stops being comparable: {'; '.join(break_phrases)}. "
        "On interurban roads alcohol and illegal manoeuvres rise; inappropriate speed is flat "
        "to 2020 and then falls.",
        captions,
    )
    body += (
        "<p>Recorded inappropriate speed on interurban roads stayed between "
        f"{_share(f.inter_series.loc[: f.flat_to].min())} and "
        f"{_share(f.inter_series.loc[: f.flat_to].max())} of crashes until {f.flat_to}, then fell "
        f"{_fmt_pct(-f.inter_late_fall, 0)} to {f.fall_to}. On urban streets it fell from "
        f"{_share(speed_urban.share_first)} to {_share(speed_urban.share_last)}. On all roads it "
        f"fell from {_share(speed_all.share_first)} to {_share(speed_all.share_last)}, more than "
        "on either kind of road, because crashes shifted to urban streets, where speed is rarely "
        "recorded. A fall in recorded speed can reflect less speeding, a change in how officers "
        "record it, or both; these data cannot separate them.</p>"
        "<p>Recorded alcohol on interurban roads rose from "
        f"{_share(f.alcohol_inter.share_first)} of crashes in {int(f.alcohol_inter.first_year)} "
        f"to {_share(f.alcohol_inter.share_last)} in {int(f.alcohol_inter.last_year)}. The "
        "series has no break, but its share rose "
        f"{_fmt_pct(float(f.alcohol_shared.share_ratio) - 1, 0)} in {int(rise.to_year)}, the "
        f"year other series broke, and a further {_fmt_pct(f.alcohol_since, 0)} from "
        f"{int(rise.to_year)} to {f.last}. On urban streets recorded alcohol rose within the "
        f"run that starts in {f.urban_alcohol_year}, from {_share(alcohol_urban.share_first)} "
        f"to {_share(alcohol_urban.share_last)}. More recorded alcohol can reflect more "
        "drinking drivers, more breath tests after crashes, or both.</p>"
        "<p>Distraction or inattention on interurban roads has no break and stayed between "
        f"{_share(f.distraction_band.min())} and {_share(f.distraction_band.max())} of crashes. "
        "Illegal manoeuvres, which the report defines as failing to give way, too short a "
        "following distance, illegal overtaking, an improper turn, or negligent or reckless "
        f"driving, rose on interurban roads from {_share(manoeuvres.share_first)} to "
        f"{_share(manoeuvres.share_last)}, a level they had already reached by "
        f"{f.manoeuvres_reached}.</p>"
    )
    body += '<h2 id="series-that-break">Where recording is not comparable</h2>'
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
        f"in {f.urban_alcohol_year} too; the reason for the shared timing is unknown.</p>"
        '<h3 id="driver-tables">The driver tables cannot show a trend in speeding</h3>'
        "<p>DGT's yearbook tables record for each driver in an injury crash whether the police "
        f"noted a speed infraction, but from {status_jump} about half of drivers have no speed "
        f"status ({_fmt_pct(status.loc[status_jump - 1], 0)} in {status_jump - 1}, "
        f"{_fmt_pct(status.loc[status_jump], 0)} in {status_jump}), so no trend in speeding "
        "can be read from them. The speed report's crash series, used above, has no break of "
        "this kind.</p>"
    )
    body += downloads(
        [
            ("speed_severity_pooled", f"severity ratios, pooled {f.types_span}, and adjusted"),
            ("speed_severity", "severity ratios by year and road type"),
            ("factor_shares", "shares by year, zone and factor"),
            ("q9_infraction_shares", "speed status in the driver tables"),
        ],
        method=(f"data.html#{NOTES}", "how the ratios and the break rule work"),
    )
    return render_page(
        "factors",
        "Speed and other recorded factors",
        "Deaths per injury crash where the police recorded inappropriate speed, and how often "
        f"they recorded speed, alcohol, distraction and illegal manoeuvres from {f.first} to "
        f"{f.last}.",
        body,
    )


def technical_notes(captions: dict[str, str]) -> str:
    """The speed report, the adjusted ratio and the break rule: one section for the methodology
    page."""
    del captions
    f = _facts()
    adjusted = f.adjusted
    page = f'<a href="factors.html">{TITLES["factors"]}</a>'
    document = f'<a href="{DOCS_URL}/methodology.md">methods document</a>'
    return (
        f'<h2 id="{NOTES}">{TITLES["factors"]}: the speed report, the adjusted ratio and the '
        "break rule</h2>"
        f"<p>These notes support {page}; the {document} gives the full account. The data are "
        'DGT\'s <span lang="es">Informe temático Factor Velocidad</span>, which leaves out '
        "Catalonia and the Basque Country and gives crashes and deaths with speed recorded by "
        "road type, and the injury crashes with each of four factors recorded. Totals of all "
        "crashes by road type come from DGT's crash records for the same provinces, which "
        f"reproduce the report's totals exactly in every year from {f.first} to {f.last}; the "
        "report's interurban categories are matched to the records' road types by name, a match "
        "checked only through the interurban total.</p>"
        "<p>The adjusted ratio is the speed coefficient of a quasi-Poisson model of deaths with "
        f"crashes as exposure and road type and year as terms. It brings the crude ratio of "
        f"{f.crude:.2f} down to {f.rate:.2f}. It assumes one ratio for every road type, which "
        "the data reject (likelihood-ratio statistic "
        f"{float(adjusted.heterogeneity_lr):.0f} on {int(adjusted.heterogeneity_df)} degrees of "
        "freedom), so it is a weighted summary of unequal ratios and its interval is widened by "
        f"the square root of the Pearson dispersion ({float(adjusted.dispersion):.1f}). The "
        "road-type intervals are Poisson intervals widened the same way by each road type's own "
        "dispersion across years.</p>"
        "<p>The break rule marks a rise of more than "
        f"{_fmt_pct(factors.BREAK_RATIO - 1, 0)} or a fall of more than "
        f"{_fmt_pct(1 - 1 / factors.BREAK_RATIO, 0)} in one year, or fewer than "
        f"{_fmt_int(factors.MIN_CRASHES)} crashes in either year, as a break; {f.n_breaks} of "
        f"the {len(f.changes)} year-to-year changes are breaks or too small to test. The "
        "threshold is a convention, and an unbroken run is not proof that recording stayed the "
        "same: the rule rules out only single-year jumps. The drug series is left out because "
        "every change in it breaks the rule.</p>"
    )
