"""What a speed law would do: what the model is, the interactive simulator, a worked example of a
higher limit everyone keeps to, what the model concludes, and the forecast behind its verdicts."""

from __future__ import annotations

import pandas as pd

from dgt_stats import forecast, simulator
from dgt_stats.site.components import (
    _chance,
    _fmt_dec,
    _fmt_int,
    _fmt_pct,
    _join,
    _minus,
    _signed_int,
    _signed_pct,
    _times,
    conclusion,
    downloads,
    esc,
    figure,
    key_figures,
    limits,
    read_table,
    render_page,
    table,
)

OUTCOME_LABELS = {
    "deaths": "Deaths",
    "seriously_injured": "Admitted to hospital",
    "slightly_injured": "Other injured",
    "injury_crashes": "Injury crashes",
}

# The starting points, grouped by the question each answers, with the short label on its button.
PRESET_GROUPS = (
    (
        "Keep to today's limits",
        (
            ("all_comply", "Everyone, everywhere"),
            ("half_comply", "Half of today's speeders"),
            ("conventional_comply", "Conventional roads only"),
            ("motorway_comply", "Autopistas and autovías only"),
        ),
    ),
    (
        "Change a limit",
        (
            ("conventional_80", "Conventional 90 → 80"),
            ("motorway_110", "Motorways 120 → 110"),
            ("motorway_130", "Motorways 120 → 130"),
            ("motorway_140", "Motorways 120 → 140"),
            ("urban_30", "Urban 50 → 30"),
        ),
    ),
    (
        "A higher limit everyone keeps to",
        (
            ("motorway_130_comply", "Motorways at 130"),
            ("motorway_140_comply", "Motorways at 140"),
        ),
    ),
)


def _power(power: float) -> str:
    """A chance of detection for a table, where nothing changes saying so, and no false 100%."""
    if pd.isna(power):
        return "no change on these roads"
    return "over 99%" if power > 0.995 else _fmt_pct(float(power), 0)


def _source(evidence: pd.DataFrame, name: str, applies_to: str, text: str) -> str:
    """``text`` linked to the URL the register gives for one published value."""
    row = evidence[(evidence.parameter == name) & (evidence.applies_to == applies_to)].iloc[0]
    return f'<a href="{esc(row.url)}">{esc(text)}</a>'


def _deaths(row: pd.Series) -> str:
    return (
        f"{_signed_int(row.deaths_change)} ({_signed_int(row.deaths_change_low)} to "
        f"{_signed_int(row.deaths_change_high)})"
    )


# --------------------------------------------------------------------------- the explainer


def _explainer(parameters: dict, speeds: pd.DataFrame) -> str:
    """What the model is, what goes in, what comes out, and what it is not."""
    years = parameters["baselineYears"]
    conventional = speeds.loc["conventional"]
    rural_deaths = simulator.exponent("deaths", "rural")
    rural_crashes = simulator.exponent("injury_crashes", "rural")
    steps = [
        (
            "Today's casualties",
            f"Deaths, hospital admissions, other injuries and injury crashes a year on each kind of "
            f"road, the mean of {years[0]}–{years[1]} in DGT's crash microdata.",
        ),
        (
            "Today's speeds",
            "Car speeds measured by radar on Spanish roads in 2022 for the EU Baseline project: "
            "the average, the share within the limit and the speed 85% of cars stay under. On "
            f"conventional roads the average is {conventional.mean_speed:.1f} km/h and "
            f"{_fmt_pct(1 - float(conventional.share_within_limit), 0)} of cars are above 90.",
        ),
        (
            "The law",
            "A new limit moves the average speed by only part of the change, as 143 "
            "before-and-after results of limit changes found; compliance brings a share of the "
            "drivers above the limit in force down to it.",
        ),
        (
            "Casualties",
            "The Power Model: when the average speed changes, deaths change by the ratio of the "
            f"speeds to the power {rural_deaths:g} on interurban roads, injury crashes to the power "
            f"{rural_crashes:g}. A 1% rise in the average speed means about "
            f"{_fmt_pct(1.01**rural_deaths - 1)} more deaths.",
        ),
        (
            "Could it be seen?",
            "A forecasting model fitted to Spain's monthly deaths, and tested against machine "
            "learning and naive forecasts on years it had not seen, says how large a change the "
            "yearly death count would show.",
        ),
    ]
    chain = "".join(
        f"<li><strong>{esc(title if title.endswith('?') else title + '.')}</strong> {esc(text)}</li>"
        for title, text in steps
    )
    return (
        "<h2>What the model is</h2>"
        "<p>A calculation, not a model fitted to Spanish crashes. Spanish crash records carry no "
        "speeds, so the effect of speed cannot be estimated from them; it is taken from published "
        "international evidence and applied to Spanish casualties and Spanish speeds. Each link "
        "is a sourced, published value:</p>"
        f'<ol class="chain">{chain}</ol>'
        "<p><strong>What you set:</strong> a limit for each kind of road, how far drivers' "
        "average speed follows a new limit, and how many drivers above the limit keep to it. "
        "<strong>What comes out:</strong> the new average speed and spread of speeds, deaths, "
        "admissions, other injuries and injury crashes a year, their value at DGT's own figures, "
        "the change in travel time, and the chance the next year's death count shows it. "
        "<strong>What it is not:</strong> a forecast of what a government will achieve. Links 1 "
        "to 4 say what follows if drivers behave as set; only link 5 is fitted to Spanish data, "
        "and it judges whether a change could be seen, not how large it is.</p>"
    )


# --------------------------------------------------------------------------- the form


def _today_line(group: str, parameters: dict, speeds: pd.DataFrame) -> str:
    """The limit in force today and how the measured traffic sits against it."""
    sites = parameters["groups"][group]["sites"]
    limits_now = sorted({int(speeds.loc[site, "limit"]) for site in sites}, reverse=True)
    names = [parameters["sites"][site]["short"].lower() for site in sites]
    means = [f"{speeds.loc[site, 'mean_speed']:.1f}" for site in sites]
    above = [_fmt_pct(1 - float(speeds.loc[site, "share_within_limit"]), 0) for site in sites]
    if len(limits_now) == 1:
        limit_text = f"Current limit: <strong>{limits_now[0]} km/h</strong>."
    else:
        limit_text = (
            f"Current limits: <strong>{limits_now[0]} km/h</strong> on most streets, "
            f"{limits_now[1]} on some; a new limit applies to the streets now at {limits_now[0]}."
        )
    if len(sites) == 1:
        measured = f"In 2022 cars averaged {means[0]} km/h and {above[0]} were above the limit."
    else:
        measured = (
            f"In 2022 cars averaged {_join([f'{m} km/h on {n}' for m, n in zip(means, names)])}; "
            f"{_join(above)} were above the limit."
        )
    return f'<p class="today">{limit_text} {esc(measured)}</p>'


def _road_controls(parameters: dict, speeds: pd.DataFrame) -> str:
    """One box per kind of road: today's limit, a new one, the response to it, and compliance."""
    boxes = []
    for group, spec in parameters["groups"].items():
        lever = parameters["levers"].get(group)
        rows = _today_line(group, parameters, speeds)
        if lever:
            current = lever["limit"]
            options = [f"{current:g}"] + [f"{o:g}" for o in lever["options"] if o != current]
            choices = "".join(
                f'<label><input type="radio" name="limit-{group}" value="{value}"'
                f"{' checked' if index == 0 else ''}>"
                f"<span>{'No change' if index == 0 else value + ' km/h'}</span></label>"
                for index, value in enumerate(options)
            )
            rows += (
                f'<div class="setting"><span class="setting-label" id="limit-{group}-label">'
                f"New limit</span>"
                f'<div class="segmented" role="radiogroup" aria-labelledby="limit-{group}-label">'
                f"{choices}</div>"
                f'<p class="state" data-out="state-{group}" aria-live="polite">No new limit: '
                f"{current:g} km/h stays.</p></div>"
                f'<div class="setting response" data-response="{group}" hidden>'
                f'<span class="setting-label" id="response-{group}-label">How far the average '
                "speed follows the new limit</span>"
                f'<div class="choices" role="radiogroup" aria-labelledby="response-{group}-label">'
                f'<label><input type="radio" name="response-{group}" value="typical" checked> '
                "As drivers typically respond</label>"
                f'<label><input type="radio" name="response-{group}" value="set"> '
                "A share I set</label></div>"
                f'<div class="slider"><input type="range" id="response-{group}" min="0" '
                f'max="100" step="1" value="0" aria-labelledby="response-{group}-label">'
                f'<output data-out="response-{group}" for="response-{group}"></output></div>'
                f'<p class="hint" data-out="response-hint-{group}"></p></div>'
            )
        rows += (
            f'<div class="setting"><label class="setting-label" for="compliance-{group}">'
            "Drivers above the limit who slow to it</label>"
            f'<div class="slider"><input type="range" id="compliance-{group}" min="0" max="100" '
            f'step="5" value="0"><output data-out="compliance-{group}" '
            f'for="compliance-{group}">0%</output></div>'
            f'<p class="hint" data-out="compliance-hint-{group}"></p></div>'
        )
        boxes.append(
            f'<fieldset class="road" data-group="{group}" data-state="unchanged">'
            f"<legend>{esc(spec['label'])}</legend>{rows}</fieldset>"
        )
    return "".join(boxes)


def _presets(parameters: dict) -> str:
    keys = {p["key"] for p in parameters["presets"]}
    rows = []
    for title, buttons in PRESET_GROUPS:
        missing = {key for key, _ in buttons} - keys
        if missing:
            raise ValueError(f"simulator page: no preset {sorted(missing)}")
        rows.append(
            f'<div class="preset-row"><span>{esc(title)}</span><div class="preset-buttons">'
            + "".join(
                f'<button type="button" data-preset="{key}" aria-pressed="false">'
                f"{esc(label)}</button>"
                for key, label in buttons
            )
            + "</div></div>"
        )
    return (
        '<div class="presets"><p class="presets-title">Start from a question, or set each road '
        "below.</p>"
        + "".join(rows)
        + '<div class="preset-row"><span></span><div class="preset-buttons"><button type="button" '
        'data-preset="current" aria-pressed="false">Back to today</button></div></div></div>'
    )


def _results(parameters: dict) -> str:
    years = parameters["baselineYears"]
    total = sum(parameters["baseline"][k]["deaths"] for k in simulator.INTERURBAN_SITES)
    headline = (
        '<div class="result-head" aria-live="polite">'
        '<p class="headline"><span class="big" data-out="headline-deaths">0</span> deaths a year '
        f"on autopistas, autovías and conventional roads, against {_fmt_int(total)} today "
        '<span class="range">(evidence range <span data-out="headline-range">0 to 0</span>)'
        "</span></p>"
        '<ul class="also"><li>Injury crashes <strong data-out="headline-crashes">0</strong></li>'
        '<li>Admitted to hospital <strong data-out="headline-serious">0</strong></li>'
        '<li><strong data-out="headline-value">€0 million</strong></li>'
        '<li>Time in cars and vans <strong data-out="headline-hours">0</strong> vehicle-hours a '
        "year</li></ul>"
        '<div data-out="why"></div>'
        '<p class="verdict" data-out="verdict"></p></div>'
    )
    speed_rows = "".join(
        f'<tr data-speeds="{site}"><th scope="row">{esc(spec["short"])}</th>'
        '<td data-out="limit"></td><td data-out="speed"></td><td data-out="limit-shift"></td>'
        '<td data-out="compliance-cut"></td><td data-out="above"></td>'
        '<td data-out="spread"></td></tr>'
        for site, spec in parameters["sites"].items()
    )
    speeds = (
        '<div class="table-wrap" role="region" tabindex="0" aria-label="Speeds under the law">'
        "<table><caption>Speeds under the law set above: the average moves by the response to a "
        "new limit and by compliance with the limit in force; the share above the limit and the "
        "spread (standard deviation) describe the flow of traffic, which the Power Model does not "
        "count</caption>"
        '<thead><tr><th scope="col">Road</th><th scope="col">Limit, km/h</th>'
        '<th scope="col">Average speed, km/h</th><th scope="col">From the new limit</th>'
        '<th scope="col">From compliance</th><th scope="col">Cars above the limit</th>'
        '<th scope="col">Spread of speeds, km/h</th></tr></thead>'
        f"<tbody>{speed_rows}</tbody></table></div>"
    )
    rows = ""
    for key in simulator.INTERURBAN_SITES:
        rows += (
            f'<tr data-class="{key}"><th scope="row">{esc(simulator.ROAD_CLASSES[key])}</th>'
            f"<td>{_fmt_int(parameters['baseline'][key]['deaths'])}</td>"
            '<td data-out="deaths"></td><td data-out="deaths-range"></td>'
            '<td data-out="crashes"></td><td data-out="serious"></td><td data-out="slight"></td>'
            '<td data-out="value"></td><td data-out="hours"></td></tr>'
        )
    rows += (
        '<tr data-class="total" class="total"><th scope="row">All three</th>'
        f'<td>{_fmt_int(total)}</td><td data-out="deaths"></td><td data-out="deaths-range"></td>'
        '<td data-out="crashes"></td><td data-out="serious"></td><td data-out="slight"></td>'
        '<td data-out="value"></td><td data-out="hours"></td></tr>'
    )
    casualties = (
        '<div class="table-wrap" role="region" tabindex="0" aria-label="Casualties a year under '
        'the law"><table><caption>Autopistas, autovías and conventional roads: the change a year '
        "under the law set above; the evidence range spans the 95% intervals of the Power Model "
        "exponents; hours are those of cars and other light vehicles</caption>"
        '<thead><tr><th scope="col">Road</th>'
        f'<th scope="col">Deaths a year, {years[0]}–{years[1]}</th>'
        '<th scope="col">Change in deaths</th><th scope="col">Evidence range</th>'
        '<th scope="col">Injury crashes</th><th scope="col">Admitted to hospital</th>'
        '<th scope="col">Other injured</th><th scope="col">Value saved a year, €</th>'
        '<th scope="col">Extra vehicle-hours a year</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )
    urban_rows = "".join(
        f'<tr data-site-row="{site}"><th scope="row">{esc(parameters["sites"][site]["label"])}</th>'
        '<td data-out="deaths"></td><td data-out="deaths-range"></td>'
        '<td data-out="serious"></td><td data-out="crashes"></td></tr>'
        for site in simulator.URBAN_SITES
    )
    urban = (
        '<div class="table-wrap" role="region" tabindex="0" aria-label="Urban streets under the '
        'law"><table><caption>Urban streets: the change on each kind of street, as a share; no '
        "national count, because DGT does not publish how many urban casualties happen on "
        "each</caption>"
        '<thead><tr><th scope="col">Street</th><th scope="col">Deaths</th>'
        '<th scope="col">Evidence range</th><th scope="col">Admitted to hospital</th>'
        '<th scope="col">Injury crashes</th></tr></thead>'
        f"<tbody>{urban_rows}</tbody></table></div>"
    )
    return headline + speeds + casualties + urban


# --------------------------------------------------------------------------- the worked example


def _worked_example(
    presets: pd.DataFrame, roads: pd.DataFrame, even: pd.DataFrame
) -> tuple[str, dict[str, float]]:
    """Autopistas and autovías at 140 km/h with everyone keeping to it, step by step."""
    kept_140 = roads.loc["motorway_140_comply"].loc[list(simulator.GROUPS["motorway"])]
    kept_120 = roads.loc["motorway_comply"].loc[list(simulator.GROUPS["motorway"])]
    p140_kept = presets.loc["motorway_140_comply"]
    p130_kept, p120_kept = presets.loc["motorway_130_comply"], presets.loc["motorway_comply"]
    at_140 = even.set_index("new_limit").loc[140]
    break_even_limit = float(at_140.break_even_limit)
    # The paragraphs below say the rise in the mean beats the cut on both roads and that the
    # higher limit kept still costs lives; stop if the tables no longer say so.
    if not (
        (kept_140.limit_shift > -kept_140.compliance_cut).all()
        and float(p140_kept.deaths_change) > 0
        and float(p120_kept.deaths_change) < 0
        and float(at_140.break_even_share) < float(at_140.typical_share)
        and 120 < break_even_limit < 140
    ):
        raise ValueError("simulator page: the worked example no longer reads as described")

    names = {"autopista": "Autopistas", "autovia": "Autovías"}
    steps = [
        ("Average speed today, with the 120 limit, km/h", lambda r: _fmt_dec(r.mean_speed)),
        ("Cars above 120 km/h today", lambda r: _fmt_pct(r.share_above_limit, 0)),
        (
            "Limit raised to 140: drivers' typical response, km/h",
            lambda r: _minus(f"{r.limit_shift:+.1f}"),
        ),
        ("Everyone keeps to 140, km/h", lambda r: _minus(f"{r.compliance_cut:+.1f}")),
        ("Average speed after, km/h", lambda r: _fmt_dec(r.new_mean_speed)),
        (
            "Spread of speeds, km/h: today → after",
            lambda r: f"{r.speed_sd:.1f} → {r.new_speed_sd:.1f}",
        ),
        ("Deaths a year today", lambda r: _fmt_int(r.deaths_before)),
        (
            "Change in deaths a year",
            lambda r: (
                f"{_signed_int(r.deaths_change)} ({_signed_pct(r.deaths_change / r.deaths_before)})"
            ),
        ),
        ("Change in injury crashes a year", lambda r: _signed_int(r.injury_crashes_change)),
    ]
    frame = pd.DataFrame(
        [
            {"Step": label, **{names[site]: fn(kept_140.loc[site]) for site in names}}
            for label, fn in steps
        ]
    )
    motorway_deaths = float(kept_140.deaths_before.sum())
    gap = float(p140_kept.deaths_change - p120_kept.deaths_change)
    hours_gap = float(p120_kept.vehicle_hours_change - p140_kept.vehicle_hours_change)
    autopista_140, autopista_120 = kept_140.loc["autopista"], kept_120.loc["autopista"]
    autovia_140 = kept_140.loc["autovia"]
    above_140 = simulator.speed_distribution("autopista").share_above(140.0)

    out = "<h2>A higher limit that everyone keeps to</h2>"
    out += (
        "<p>Would autopistas and autovías be safer at 140 km/h if everyone kept to it? The "
        "argument for it is that the average speed rises but nobody speeds and the traffic flows "
        "more evenly. The model can test the first two parts and measure the third.</p>"
    )
    out += table(
        frame,
        "Autopistas and autovías at 140 km/h, with drivers responding to the new limit as they "
        "typically do and every driver above 140 slowing to it; conventional roads unchanged",
    )
    out += (
        f"<p><strong>It costs lives.</strong> On the evidence, 140 km/h kept by everyone means "
        f"{_deaths(p140_kept)} deaths a year against today, and "
        f"{_signed_int(p140_kept.injury_crashes_change)} injury crashes, while saving "
        f"{-p140_kept.vehicle_hours_change / 1e6:.0f} million vehicle-hours. Two facts decide "
        "it. Raising a limit lifts the whole flow, not only the fast drivers: the 143 results "
        f"put the rise in the average at {_fmt_pct(float(at_140.typical_share), 0)} of the change "
        f"in the limit, {autopista_140.limit_shift:+.1f} km/h for +20. And few cars go above "
        f"140 today ({_fmt_pct(above_140, 0)} on autopistas), so keeping everyone to it takes "
        "off only "
        f"{-autopista_140.compliance_cut:.1f} km/h there and {-autovia_140.compliance_cut:.1f} on "
        "autovías. The rise beats the cut. Deaths would fall only if less than "
        f"{_fmt_pct(float(at_140.break_even_share), 0)} of the 20 km/h reached the average speed."
        "</p>"
    )
    out += (
        "<p><strong>Against the right comparison it costs more.</strong> If everyone can be made "
        "to keep to 140, everyone can be made to keep to 120, which saves "
        f"{_fmt_int(-p120_kept.deaths_change)} lives a year on these roads. Between the two, the "
        f"extra 20 km/h of limit costs {_fmt_int(gap)} lives a year for "
        f"{hours_gap / 1e6:.0f} million vehicle-hours, about {hours_gap / gap / 1e3:,.0f},000 "
        "hours for each life.</p>"
    )
    out += (
        "<p><strong>Where it would break even.</strong> With drivers responding as they "
        "typically do and everyone keeping to the limit, the limit could rise to about "
        f"{break_even_limit:.0f} km/h before deaths exceeded today's: at 130 kept by everyone "
        f"the change is {_signed_int(p130_kept.deaths_change)} a year, the speeders removed "
        "balancing everyone else speeding up. Above that, the higher limit costs lives even with "
        "perfect compliance.</p>"
    )
    out += (
        "<p><strong>The flow of traffic.</strong> Keeping everyone to 140 narrows the spread of "
        f"speeds on autopistas from {autopista_140.speed_sd:.1f} to "
        f"{autopista_140.new_speed_sd:.1f} km/h. The Power Model counts only the average. A "
        "review of the evidence finds more crashes where speeds vary more "
        '(<a href="https://doi.org/10.1016/j.aap.2005.07.004">Aarts &amp; van Schagen 2006</a>) '
        "but gives no dose-response that could be applied here, so the page shows the spread and "
        "does not turn it into casualties. For the narrower spread to cancel the rise it would "
        "have to cut deaths on these roads by "
        f"{_fmt_pct(float(p140_kept.deaths_change) / (motorway_deaths + float(p140_kept.deaths_change)), 0)} "
        "on its own. And everyone keeping to 120 narrows the spread far more, to "
        f"{autopista_120.new_speed_sd:.1f} km/h: on the average and on the spread, today's limit "
        "kept beats a higher limit kept.</p>"
    )
    return out, {"gap": gap, "break_even_limit": break_even_limit}


# --------------------------------------------------------------------------- the forecast


def _forecast_section(captions: dict[str, str], interurban_total: float, comply: pd.Series) -> str:
    validation = (
        read_table("forecast_validation").set_index(["outcome", "set", "method"]).sort_index()
    )
    detect = read_table("forecast_detectability").set_index(["outcome", "horizon"])
    backtest = read_table("forecast_backtest")
    coefficients = read_table("forecast_coefficients").set_index(["outcome", "term"])
    selection_table = read_table("forecast_selection")
    trees = selection_table[
        (selection_table.family == "trees") & (selection_table.outcome == "deaths_all")
    ].pivot_table(index="method", columns="set", values="rmse")
    flat_tree = trees.drop(index=forecast.TREE_METHOD).holdout.idxmin()
    holdout_all = selection_table[
        (selection_table.outcome == "deaths_all") & (selection_table.set == "holdout")
    ]
    if holdout_all.loc[holdout_all.rmse.idxmin(), "method"] != flat_tree:
        raise ValueError("simulator page: the best forecast of the held-back years has changed")
    chosen = forecast.CHOSEN
    holdout = validation.loc[("deaths_all", "holdout")]
    selection = validation.loc[("deaths_all", "selection")]
    pandemic = validation.loc[("deaths_all", "pandemic")]
    # The paragraphs below say which forecast wins in which years; stop if the tables move.
    if not (
        holdout.loc["last_year", "rmse"] < holdout.loc[chosen, "rmse"]
        and trees.loc[flat_tree, "selection"] > selection.loc[chosen, "rmse"]
        and trees.loc[flat_tree, "pandemic"] > pandemic.loc[chosen, "rmse"]
        and all(
            trees.loc[forecast.TREE_METHOD, kind]
            > validation.loc[("deaths_all", kind, chosen), "rmse"]
            for kind in ("selection", "holdout", "pandemic")
        )
    ):
        raise ValueError("simulator page: the forecast comparison no longer reads as described")
    one_year = detect.loc[("deaths_interurban", 1)]
    five_years = detect.loc[("deaths_interurban", 5)]
    mde, mde_rise = float(comply.mde_deaths), float(comply.mde_rise_deaths)
    worst = backtest[(backtest.outcome == "deaths_all") & (backtest.set == "holdout")]
    worst = worst.assign(error=lambda f: (f.observed / f.model - 1).abs()).sort_values("error")
    worst_year = int(worst.iloc[-1].year)
    leaf = flat_tree.rsplit("_", 1)[-1]

    def row(label: str, errors: dict[str, float]) -> dict[str, str]:
        return {
            "Forecast": label,
            "Years used to choose, 2006–2015": _fmt_pct(errors["selection"]),
            "Held-back years, 2016–2019 and 2022–2024": _fmt_pct(errors["holdout"]),
            "Lockdown years, 2020–2021": _fmt_pct(errors["pandemic"]),
        }

    def method(name: str) -> dict[str, float]:
        return {
            s: float(validation.loc[("deaths_all", s, name), "rmse"])
            for s in ("selection", "holdout", "pandemic")
        }

    rows = [
        row("Poisson model: month, trend, road fuel and weekend days (chosen)", method(chosen)),
        row("The same with month and trend only", method("trend")),
        row(
            "Gradient-boosted trees, same inputs, tuned on 2006–2015",
            method(forecast.TREE_METHOD),
        ),
        row(
            f"Gradient-boosted trees with leaves of at least {leaf} months",
            {s: float(trees.loc[flat_tree, s]) for s in ("selection", "holdout", "pandemic")},
        ),
        row("Last year's count", method("last_year")),
        row("Mean of the last three years", method("mean_3_years")),
    ]
    fuel = coefficients.loc[("deaths_all", "log_fuel")]
    saturday = coefficients.loc[("deaths_all", "saturdays")]
    out = "<h2>The forecasting model: could the counts show it?</h2>"
    out += (
        "<p>A law is judged by comparing the deaths after it with the deaths there would have "
        "been without it, and the second number is a forecast. Its error decides what the "
        "comparison can see. <strong>What it is:</strong> a Poisson regression of each month's "
        "deaths on the month of the year, a trend over the four years before, the month's road "
        "fuel (the traffic) and its number of Fridays, Saturdays and Sundays. Fitted on "
        f"{int(fuel.first_year)}–{int(fuel.last_year)}, it says a month with 1% more road fuel "
        f"has about {fuel.estimate:.1f}% more deaths ({fuel.low:.1f} to {fuel.high:.1f}), and "
        f"one more Saturday {_signed_pct(float(saturday.estimate) - 1)}. "
        "<strong>How it was chosen:</strong> four forms of the model and windows of three to "
        "eight years were scored on forecasts of 2006–2015 alone; the years after played no part "
        "and are the test. Beside it are scored two naive forecasts and a machine-learning "
        "model, gradient-boosted trees given the same inputs and tuned on the same years.</p>"
    )
    out += table(
        pd.DataFrame(rows),
        "Error of each forecast of a year's deaths on all roads (root mean square, as a share of "
        "the year's deaths): each year forecast from the four before it",
    )
    out += (
        "<p><strong>What the test shows.</strong> The model beats the trees in every set of "
        "years: a tree cannot extend a trend beyond the years it has seen, and with 48 monthly "
        "rows it fits the noise. In the lockdown years it beats last year's count by far "
        f"({_fmt_pct(float(pandemic.loc[chosen, 'rmse']))} against "
        f"{_fmt_pct(float(pandemic.loc['last_year', 'rmse']))}), because it knows the traffic "
        "fell. In the flat held-back years last year's count does slightly better "
        f"({_fmt_pct(float(holdout.loc['last_year', 'rmse']))} against "
        f"{_fmt_pct(float(holdout.loc[chosen, 'rmse']))}; the worst year is {worst_year}, "
        "forecast from a window that includes the lockdowns), and trees with large leaves best "
        f"of all ({_fmt_pct(float(trees.loc[flat_tree, 'holdout']))}), but they lose in the "
        "years when traffic or the trend moves, and whether the years ahead will be flat is not "
        "known when the forecast is made. A law's effect has to be told apart from moving "
        "traffic and trends, so the model is the one used.</p>"
    )
    out += figure("k1_forecast_check", "Each year's deaths against two forecasts", captions)
    out += (
        "<p><strong>What it concludes.</strong> On the "
        f"{_fmt_int(interurban_total)} deaths a year of the autopistas, autovías and conventional "
        "roads, the first year's count picks up a fall of "
        f"{_fmt_int(mde)} ({_fmt_pct(mde / interurban_total, 0)}) four times in five, and a rise "
        f"of {_fmt_int(mde_rise)}; smaller changes are picked up less often, not never. For all "
        f"{_fmt_int(one_year.expected)} interurban deaths the fall is "
        f"{_fmt_pct(float(one_year.mde), 0)}. Waiting does not help: summed over five years the "
        f"threshold is {_fmt_pct(float(five_years.mde), 0)}, because the trend drifts further "
        "from any extrapolation the longer it runs. So only the largest laws on this page would "
        "show in the counts, which is why the dated policy change on the "
        '<a href="policy.html">2006 page</a> could not be settled from them, and why a speed '
        "law is checked by measuring speeds.</p>"
    )
    out += figure(
        "k2_detectability",
        "The fall in deaths a comparison detects four times in five, by years after a law",
        captions,
    )
    out += downloads(
        [
            ("forecast_validation", "model against the naive forecasts"),
            ("forecast_selection", "every specification and window"),
            ("forecast_backtest", "each year's forecasts"),
            ("forecast_detectability", "effects detected four times in five"),
            ("forecast_coefficients", "what the model learned"),
        ]
    )
    return out


# --------------------------------------------------------------------------- the page


def page_simulator(captions: dict[str, str]) -> str:
    names = ("simulator_baseline", "simulator_speed_sites", "forecast_detectability")
    parameters = simulator.browser_parameters({name: read_table(name) for name in names})
    presets = read_table("simulator_presets").set_index("scenario")
    sites = read_table("simulator_preset_sites").set_index(["scenario", "site"])
    roads = read_table("simulator_preset_roads").set_index(["scenario", "road_class"])
    even = read_table("simulator_break_even")
    speeds = read_table("simulator_speed_sites").set_index("site")
    risk = read_table("simulator_class_risk")
    grid = read_table("simulator_limit_grid")
    evidence = simulator.evidence()
    base = read_table("simulator_baseline").set_index("road_class")

    comply = presets.loc["all_comply"]
    conventional_comply = presets.loc["conventional_comply"]
    conventional_80 = presets.loc["conventional_80"]
    kept_140 = presets.loc["motorway_140_comply"]
    interurban_total = float(comply.deaths_before)
    mde = float(comply.mde_deaths)
    latest_risk = risk[risk.year == risk.year.max()].set_index("road_class")
    risk_ratio = float(
        latest_risk.loc["conventional", "deaths_per_bn_km"]
        / latest_risk.loc["motorway", "deaths_per_bn_km"]
    )
    risk_year = int(risk.year.max())
    pooled = risk.groupby("road_class")[["deaths", "billion_vehicle_km"]].sum()
    pooled_ratio = float(
        (pooled.loc["conventional", "deaths"] / pooled.loc["conventional", "billion_vehicle_km"])
        / (pooled.loc["motorway", "deaths"] / pooled.loc["motorway", "billion_vehicle_km"])
    )
    conv_speed = speeds.loc["conventional"]
    autopista_speed, autovia_speed = speeds.loc["autopista"], speeds.loc["autovia"]

    single = grid[grid.levers_changed == 1].sort_values("deaths_change").iloc[0]
    beyond = grid[grid.deaths_change < float(comply.deaths_change)]
    if beyond.empty or (beyond.levers_changed < 2).any():
        raise ValueError(
            "simulator page: full compliance no longer sits between the best single limit and "
            "the best pair"
        )
    deepest = grid.sort_values("deaths_change").iloc[0]
    today = {lever: parameters["levers"][lever]["limit"] for lever in ("motorway", "conventional")}
    motorway_only = grid[
        (grid.levers_changed == 1) & (grid.conventional_limit == today["conventional"])
    ]

    def lever_change(row: pd.Series) -> str:
        """The limits a grid row changes, in words."""
        parts = []
        if row.motorway_limit != today["motorway"]:
            parts.append(f"autopistas and autovías at {row.motorway_limit:g} km/h")
        if row.conventional_limit != today["conventional"]:
            parts.append(f"conventional roads at {row.conventional_limit:g} km/h")
        return " and ".join(parts)

    conventional_share = float(conventional_comply.deaths_change / comply.deaths_change)
    body = key_figures(
        [
            (
                "Everyone keeps to today's limits",
                _signed_int(comply.deaths_change),
                f"deaths a year, of {_fmt_int(interurban_total)} on autopistas, autovías and "
                "conventional roads",
            ),
            (
                "Of which on conventional roads",
                _signed_int(conventional_comply.deaths_change),
                f"{_fmt_pct(conventional_share, 0)} of the saving, where "
                f"{_fmt_pct(1 - float(conv_speed.share_within_limit), 0)} of cars exceed 90 km/h",
            ),
            (
                "Motorways at 140, everyone keeps to it",
                _signed_int(kept_140.deaths_change),
                "deaths a year against today: a higher limit kept still costs lives",
            ),
            (
                "Smallest fall a year's count reliably shows",
                _fmt_int(mde),
                f"deaths a year on those roads, {_fmt_pct(mde / interurban_total, 0)}",
            ),
        ]
    )
    body += (
        '<p class="answer">On the published evidence, the largest saving is not a new limit but '
        "today's limits kept: if every driver now above the limit on autopistas, autovías and "
        f"conventional roads slowed to it, about {_fmt_int(-comply.deaths_change)} fewer people a "
        f"year would die there (between {_fmt_int(-comply.deaths_change_high)} and "
        f"{_fmt_int(-comply.deaths_change_low)}), {_fmt_int(-conventional_comply.deaths_change)} "
        "of them on conventional roads. Raising the motorway limit to 140 km/h would cost lives "
        f"even if every driver kept to it, {_signed_int(kept_140.deaths_change)} a year, because "
        "a higher limit lifts everyone's speed more than it removes speeding. And the yearly "
        f"death count shows a change reliably only from about {_fmt_int(mde)} deaths, so most "
        "speed laws have to be judged by the speeds they produce.</p>"
    )

    body += _explainer(parameters, speeds)

    body += "<h2>Set a law</h2>"
    body += (
        "<p>Each kind of road starts at today's limit and today's driving. Choose a new limit "
        "and the box asks how far the average speed follows it; leave it at <em>As drivers "
        "typically respond</em> to use the evidence, and the slider shows the share that is. "
        "The last slider makes drivers keep to the limit in force: 0% leaves driving as it is, "
        "100% means no car above the limit. Every number below is recomputed in your browser.</p>"
    )
    body += (
        '<div id="simulator-panel" hidden>'
        '<form id="simulator" class="simulator">'
        + _presets(parameters)
        + _road_controls(parameters, speeds)
        + "</form>"
        + _results(parameters)
        + "</div>"
        '<noscript><p class="note">The simulator needs JavaScript; the table below gives every '
        "starting point computed in advance.</p></noscript>"
    )

    example, numbers = _worked_example(presets, roads, even)
    body += example

    body += "<h2>What the model concludes</h2>"
    conventional_70 = (
        grid[(grid.levers_changed == 1) & (grid.motorway_limit == today["motorway"])]
        .sort_values("conventional_limit")
        .iloc[0]
    )
    urban_30 = sites.loc[("urban_30", "urban_50")]
    findings = [
        (
            "Enforcing today's limits saves more than any single new limit.",
            f"Everyone keeping to them: {_deaths(comply)} deaths a year, "
            f"{_fmt_pct(-comply.deaths_change / interurban_total, 0)} of those on these roads, "
            f"worth about €{comply.value_euros / 1e9:,.1f} billion a year at DGT's values. The "
            f"largest single new limit, {lever_change(single)}, saves "
            f"{_fmt_int(-single.deaths_change)} with the typical response; only lowering both "
            f"limits at once saves more, up to {_fmt_int(-deepest.deaths_change)} with "
            f"{lever_change(deepest)}.",
        ),
        (
            "The saving is on conventional roads.",
            f"{_fmt_int(-conventional_comply.deaths_change)} of the "
            f"{_fmt_int(-comply.deaths_change)}: they carry {_fmt_int(base.loc['conventional', 'deaths'])} "
            f"of the {_fmt_int(interurban_total)} deaths, {_fmt_pct(1 - float(conv_speed.share_within_limit), 0)} "
            f"of their cars are above 90 km/h, by {conv_speed.excess_over_limit:.1f} km/h a car on "
            f"average, and they kill {_times(risk_ratio)} as many people per kilometre driven as "
            "motorways.",
        ),
        (
            "Motorway limits move little either way, and a higher one kept still costs lives.",
            f"110 km/h saves {_fmt_int(-presets.loc['motorway_110', 'deaths_change'])}, 130 costs "
            f"{_fmt_int(presets.loc['motorway_130', 'deaths_change'])} and 140 costs "
            f"{_fmt_int(presets.loc['motorway_140', 'deaths_change'])} with the typical response; "
            f"140 kept by everyone costs {_fmt_int(kept_140.deaths_change)}, and the break-even "
            f"limit kept by everyone is about {numbers['break_even_limit']:.0f} km/h. No change of "
            "the motorway limit alone would show in a year's count more than "
            f"{_fmt_pct(float(motorway_only.power_in_one_year.max()), 0)} of the time.",
        ),
        (
            "80 km/h on conventional roads is a real saving that the counts may not show.",
            f"{_deaths(conventional_80)} deaths a year; 70 km/h "
            f"{_signed_int(conventional_70.deaths_change)}. The first year's count would show "
            f"the 80 km/h saving {_chance(conventional_80.power_in_one_year)}: a year without a "
            "visible fall would not mean the law had failed.",
        ),
        (
            "On urban streets the direction is clear and the size is not.",
            "Streets at 50 km/h brought to 30 would take the average car from "
            f"{urban_30.mean_speed:.1f} to {urban_30.new_mean_speed:.1f} km/h and deaths there by "
            f"{_signed_pct(float(urban_30.deaths_ratio) - 1)}, but the evidence for urban deaths "
            f"runs from {_signed_pct(float(urban_30.deaths_ratio_low) - 1)} to "
            f"{_signed_pct(float(urban_30.deaths_ratio_high) - 1)}; admissions to hospital, "
            "better pinned down, change by "
            f"{_signed_pct(float(urban_30.seriously_injured_ratio) - 1)} "
            f"({_signed_pct(float(urban_30.seriously_injured_ratio_low) - 1)} to "
            f"{_signed_pct(float(urban_30.seriously_injured_ratio_high) - 1)}).",
        ),
    ]
    body += (
        '<ol class="conclusions">'
        + "".join(f"<li><strong>{esc(head)}</strong> {esc(text)}</li>" for head, text in findings)
        + "</ol>"
    )

    rows = []
    for key, row in presets.iterrows():
        if key == "current":
            continue
        urban = sites.loc[(key, "urban_50")]
        rows.append(
            {
                "Law": row.scenario_label,
                "Deaths a year": _deaths(row),
                "Injury crashes": _signed_int(row.injury_crashes_change),
                "Admitted to hospital": _signed_int(row.seriously_injured_change),
                "Value saved a year, € million": _fmt_int(row.value_euros / 1e6),
                "Extra vehicle-hours a year, million": _fmt_dec(row.vehicle_hours_change / 1e6),
                "Chance a year's count shows it": _power(row.power_in_one_year),
                "Deaths on 50 km/h streets": _signed_pct(float(urban.deaths_ratio) - 1),
            }
        )
    body += "<h2>Every starting point side by side</h2>"
    body += table(
        pd.DataFrame(rows),
        "The starting points: casualties a year on autopistas, autovías and conventional roads "
        "against today, their value, the time of cars and other light vehicles on those roads, "
        "the chance the first year's death count shows the change, and the change on urban "
        "streets now at 50 km/h; a new limit takes the typical response",
    )
    body += downloads(
        [
            ("simulator_presets", "the starting points"),
            ("simulator_preset_roads", "road by road"),
            ("simulator_preset_sites", "speeds and ratios by kind of road"),
            ("simulator_break_even", "the break-even limit"),
            ("simulator_limit_grid", "every pair of limits"),
            ("simulator_baseline", "the baseline by road class"),
        ]
    )

    body += "<h2>Where the risk is</h2>"
    body += (
        "<p>Divided into the kilometres the Ministerio de Transportes measures on interurban "
        f"roads, conventional roads killed {_times(risk_ratio)} as many people per kilometre as "
        f"autopistas and autovías in {risk_year}, and {_times(pooled_ratio)} over "
        f"{int(risk.year.min())}–{risk_year}, although their traffic is slower: an average of "
        f"{conv_speed.mean_speed:.1f} km/h against {autovia_speed.mean_speed:.1f} on autovías and "
        f"{autopista_speed.mean_speed:.1f} on autopistas. Speed does not explain that gap: "
        "conventional roads also have two-way traffic without a barrier, junctions and direct "
        "access, which these data do not measure. What speed decides is how much each kind of "
        "road changes when its own speeds change, and that is what the simulator computes.</p>"
    )
    body += downloads([("simulator_class_risk", "deaths per vehicle-km by road class")])

    body += "<h2>How each number is made</h2>"
    elvik = _source(evidence, "exponent_deaths", "rural", "Elvik's 2009 meta-analysis")
    dgt_value = _source(evidence, "value_death", "all", "DGT's 2024 value of a life")
    body += (
        "<p><strong>The baseline</strong> is the mean deaths, admissions, other injured and "
        f"injury crashes of {parameters['baselineYears'][0]}–{parameters['baselineYears'][1]} by "
        "road class, from the crash microdata, which reconcile exactly with DGT's yearbook. "
        "<strong>Today's speeds</strong> are the free-flow speeds of cars measured by radar in "
        f"2022 for the {_source(evidence, 'mean_speed', 'conventional', 'EU Baseline project')}. "
        "A log-normal distribution through the share within the limit and the 85th percentile "
        "reproduces both, and its mean lands within "
        f"{float((speeds.implied_mean - speeds.mean_speed).abs().max()):.1f} km/h of the measured "
        "one on every kind of road; it gives the share above any limit and the spread. The "
        "limits are those of the "
        f"{_source(evidence, 'limit', 'autovia', 'Reglamento General de Circulación')} and "
        f"{_source(evidence, 'limit', 'urban_50', 'Real Decreto 970/2020')}. <strong>A new "
        "limit</strong> moves the average speed by the curve fitted to "
        f"{_source(evidence, 'pass_through_b', 'all', '143 before-and-after results')}: a cut of "
        f"10 km/h by {_fmt_dec(simulator.typical_response(-10))} km/h "
        f"({_fmt_pct(simulator.typical_response(-10) / -10, 0)}), a rise of 20 by "
        f"{_minus(f'{simulator.typical_response(20):+.1f}')} "
        f"({_fmt_pct(simulator.typical_response(20) / 20, 0)}); the whole distribution is "
        "scaled, so every driver moves in proportion. <strong>Compliance</strong> moves a share "
        "of the cars above the limit in force down to it, which lowers the average by that share "
        f"of the average excess: {conv_speed.excess_over_limit:.1f} km/h a car on conventional "
        f"roads, {autopista_speed.excess_over_limit:.1f} on autopistas and "
        f"{autovia_speed.excess_over_limit:.1f} on autovías at today's limits. <strong>The Power "
        f"Model</strong>, in {elvik}, turns the change in the average speed into casualties, more "
        f"steeply for deaths than for injuries. Casualties are valued at {dgt_value} and "
        f"{_source(evidence, 'value_serious_injury', 'all', 'of an injury')}.</p>"
    )
    body += _evidence_tables(read_table("simulator_speed_sites"))
    body += downloads([("simulator_evidence", "every published value, its URL and a quote")])

    body += _forecast_section(captions, interurban_total, comply)

    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "The evidence ranks the levers. Keeping to today's limits would save about "
        f"{_fmt_int(-comply.deaths_change)} lives a year on Spain's interurban roads, "
        f"{_fmt_int(-conventional_comply.deaths_change)} of them on conventional roads; lowering "
        f"the conventional limit to 80 km/h about {_fmt_int(-conventional_80.deaths_change)}; "
        "and raising the motorway limit to 140 km/h would cost about "
        f"{_fmt_int(kept_140.deaths_change)} even with every driver keeping to it, "
        f"{_fmt_int(numbers['gap'])} more than everyone keeping to 120. Only the largest of "
        f"these, from about {_fmt_int(mde)} deaths a year, would reliably show in the first "
        "year's death count, so a speed law has to be judged by the speeds it produces."
    )
    body += limits(
        "The Power Model is an aggregate relation estimated from before-and-after studies in "
        "other countries; it applies to the average speed of traffic and is less certain on urban "
        "streets, where its interval for deaths includes no effect. The speeds are free-flow "
        "speeds of cars on weekday daytime, measured in 2022; trucks, night traffic and "
        "congestion are not in them. Compliance moves each complying driver to exactly the limit, "
        "and the narrower spread it brings is shown but not counted, so the compliance figures "
        "are if anything low. The response to a new limit varies widely between roads, which is "
        "why it can be set by hand. Time is computed at free-flow speeds over the measured "
        "interurban kilometres of cars and other light vehicles, which leave out municipal "
        "interurban roads; free motorways are timed at the speeds of autovías, with which the "
        "Ministry's traffic table counts them. Other interurban roads "
        f"({_fmt_int(base.loc['other_interurban', 'deaths'])} deaths a year) and urban streets as "
        "a national count are left out because no speed or street split is published for them."
    )
    head = (
        '\n<script type="application/json" id="simulator-parameters">'
        + simulator.browser_parameters_json({name: read_table(name) for name in names}).replace(
            "</", "<\\/"
        )
        + '</script>\n<script src="simulator.js" defer></script>'
    )
    return render_page(
        "simulator",
        "What a speed law would do",
        "Set a speed limit for each kind of road and how many drivers keep to it, and see what "
        "the published evidence implies for deaths, injuries, crashes and travel time on Spain's "
        "roads, and whether the yearly death count could ever show it.",
        body,
        head=head,
    )


def _evidence_tables(speeds: pd.DataFrame) -> str:
    """The measured speeds and the Power Model exponents, the two sets of values behind the page."""
    rows = [
        {
            "Road": row.site_label,
            "Average speed, km/h": _fmt_dec(row.mean_speed),
            "Within the limit": _fmt_pct(row.share_within_limit, 0),
            "85th percentile, km/h": _fmt_dec(row.v85, 0),
            "Fitted average, km/h": _fmt_dec(row.implied_mean),
            "Excess over the limit per car, km/h": _fmt_dec(row.excess_over_limit),
        }
        for row in speeds.itertuples()
    ]
    out = table(
        pd.DataFrame(rows),
        "Free-flow car speeds measured in Spain in 2022 (EU Baseline project, weekday daytime), "
        "and the log-normal fitted through the share within the limit and the 85th percentile",
    )

    def exponent(outcome: str, environment: str) -> str:
        value, low, high = (
            simulator.exponent(outcome, environment, bound) for bound in ("value", "low", "high")
        )
        return _minus(f"{value:g} ({low:g} to {high:g})")

    rows = [
        {
            "Outcome": label,
            "Rural roads and motorways": exponent(outcome, "rural"),
            "Urban streets": exponent(outcome, "urban"),
        }
        for outcome, label in OUTCOME_LABELS.items()
    ]
    out += table(
        pd.DataFrame(rows),
        "Power Model exponents with 95% intervals (Elvik 2009, TØI report 1034/2009, table S1): "
        "a count changes by the ratio of average speeds raised to this power",
    )
    return out
