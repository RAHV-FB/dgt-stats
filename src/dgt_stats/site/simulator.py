"""What a speed law would do: the interactive simulator and the model behind its verdicts."""

from __future__ import annotations

import pandas as pd

from dgt_stats import forecast, simulator
from dgt_stats.site.components import (
    _fmt_dec,
    _fmt_int,
    _fmt_pct,
    _minus,
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

EVIDENCE_LABELS = {
    "exponent_deaths": "Power Model exponent, deaths",
    "exponent_seriously_injured": "Power Model exponent, admitted to hospital",
    "exponent_slightly_injured": "Power Model exponent, other injured",
    "exponent_injury_crashes": "Power Model exponent, injury crashes",
    "pass_through_a": "Response curve, squared term",
    "pass_through_b": "Response curve, linear term",
    "mean_speed": "Mean car speed today (km/h)",
    "v85": "85th percentile of car speed (km/h)",
    "share_within_limit": "Cars within the limit",
    "limit": "Legal limit (km/h)",
    "value_death": "Value of preventing a death (€)",
    "value_serious_injury": "Value of preventing a serious injury (€)",
    "value_slight_injury": "Value of preventing a slight injury (€)",
}


APPLIES_TO = {
    "rural": "rural roads and motorways",
    "urban": "urban streets",
    "all": "all roads",
    "motorway": "motorways and autovías",
    "conventional": "conventional roads",
    "urban_50": "urban streets at 50",
    "urban_30": "urban streets at 30",
}


def _evidence_value(row: pd.Series) -> str:
    def show(value: float) -> str:
        if row.parameter == "share_within_limit":
            return f"{value * 100:.1f}%"
        if row.parameter.startswith("value_"):
            return f"{value:,.0f}"
        if row.parameter.startswith("pass_through"):
            return f"{value:g}"
        return f"{value:g}"

    text = show(float(row.value))
    if pd.notna(row.low) and pd.notna(row.high) and row.parameter.startswith("exponent"):
        text += f" ({show(float(row.low))} to {show(float(row.high))})"
    return _minus(text)


def _simulator_controls(parameters: dict) -> str:
    """The form: one select per measured site with a limit to change, and the two levers."""
    selects = []
    for site in ("motorway", "conventional", "urban_50"):
        spec = parameters["sites"][site]
        options = "".join(
            f'<option value="{limit:g}"{" selected" if limit == spec["limit"] else ""}>'
            f"{limit:g} km/h</option>"
            for limit in spec["options"]
        )
        selects.append(
            f'<label class="control"><span>{esc(spec["label"])}</span>'
            f'<select data-site="{site}" data-limit="{spec["limit"]:g}">{options}</select></label>'
        )
    presets = "".join(
        f'<button type="button" data-preset="{esc(p["key"])}">{esc(p["label"])}</button>'
        for p in parameters["presets"]
    )
    return (
        '<form id="simulator" class="simulator" aria-describedby="simulator-help">'
        '<p id="simulator-help" class="help">Change a limit or a lever and every number below '
        "is recomputed in your browser from the published evidence.</p>"
        f"<fieldset><legend>New limits</legend>{''.join(selects)}</fieldset>"
        "<fieldset><legend>How drivers follow a new limit</legend>"
        '<label class="choice"><input type="radio" name="response" value="typical" checked> '
        "As they typically do: the average of 143 before-and-after studies</label>"
        '<label class="choice"><input type="radio" name="response" value="set"> '
        "A set share of the limit change reaches the average speed: "
        '<output data-out="response-share">35%</output></label>'
        '<input id="response-share" type="range" min="0" max="100" step="5" value="35" '
        'aria-label="Share of the limit change that reaches the average speed">'
        "</fieldset>"
        "<fieldset><legend>How many follow the limit</legend>"
        '<label class="choice" for="compliance">Share of the drivers now above the limit who '
        'slow to it: <output data-out="compliance">0%</output></label>'
        '<input id="compliance" type="range" min="0" max="100" step="5" value="0">'
        "</fieldset>"
        f'<div class="presets"><span>Try:</span>{presets}</div>'
        "</form>"
    )


def _simulator_results(parameters: dict) -> str:
    years = parameters["baselineYears"]
    rows = ""
    for key in ("motorway", "conventional"):
        label = simulator.ROAD_CLASSES[key]
        base = parameters["baseline"][key]
        rows += (
            f'<tr data-class="{key}"><th scope="row">{esc(label)}</th>'
            f'<td data-out="speed"></td><td>{_fmt_int(base["deaths"])}</td>'
            '<td data-out="deaths"></td><td data-out="deaths-range"></td>'
            '<td data-out="serious"></td><td data-out="slight"></td>'
            '<td data-out="value"></td><td data-out="hours"></td></tr>'
        )
    total = sum(parameters["baseline"][k]["deaths"] for k in ("motorway", "conventional"))
    rows += (
        '<tr data-class="total" class="total"><th scope="row">Both</th><td></td>'
        f'<td>{_fmt_int(total)}</td><td data-out="deaths"></td><td data-out="deaths-range"></td>'
        '<td data-out="serious"></td><td data-out="slight"></td><td data-out="value"></td>'
        '<td data-out="hours"></td></tr>'
    )
    head = (
        '<tr><th scope="col">Road</th><th scope="col">Mean speed, km/h</th>'
        f'<th scope="col">Deaths a year, {years[0]}–{years[1]}</th>'
        '<th scope="col">Change in deaths</th><th scope="col">Evidence range</th>'
        '<th scope="col">Admitted to hospital</th><th scope="col">Other injured</th>'
        '<th scope="col">Value saved a year, €</th><th scope="col">Extra vehicle-hours a year</th></tr>'
    )
    urban_rows = "".join(
        f'<tr data-site-row="{site}"><th scope="row">{esc(parameters["sites"][site]["label"])}</th>'
        '<td data-out="speed"></td><td data-out="deaths"></td><td data-out="deaths-range"></td>'
        '<td data-out="serious"></td></tr>'
        for site in ("urban_50", "urban_30")
    )
    return (
        '<div class="table-wrap" role="region" tabindex="0" aria-label="Simulated effect on '
        'interurban roads" aria-live="polite"><table><caption>Motorways and conventional roads: '
        "the change a year under the law set above; the range spans the 95% intervals of the "
        "Power Model exponents</caption>"
        f"<thead>{head}</thead><tbody>{rows}</tbody></table></div>"
        '<p class="verdict" aria-live="polite" data-out="verdict"></p>'
        '<div class="table-wrap" role="region" tabindex="0" aria-label="Simulated effect on '
        'urban streets" aria-live="polite"><table><caption>Urban streets: the change in the '
        "casualties on each kind of street, as a share; no national count, because DGT does "
        "not publish how many urban casualties happen on each</caption>"
        '<thead><tr><th scope="col">Street</th><th scope="col">Mean speed, km/h</th>'
        '<th scope="col">Deaths</th><th scope="col">Evidence range</th>'
        '<th scope="col">Admitted to hospital</th></tr></thead>'
        f"<tbody>{urban_rows}</tbody></table></div>"
    )


def page_simulator(captions: dict[str, str]) -> str:
    names = ("simulator_baseline", "simulator_speed_sites", "forecast_detectability")
    parameters = simulator.browser_parameters({name: read_table(name) for name in names})
    presets = read_table("simulator_presets").set_index("scenario")
    sites = read_table("simulator_preset_sites").set_index(["scenario", "site"])
    speeds = read_table("simulator_speed_sites").set_index("site")
    risk = read_table("simulator_class_risk")
    validation = (
        read_table("forecast_validation").set_index(["outcome", "set", "method"]).sort_index()
    )
    detect = read_table("forecast_detectability").set_index(["outcome", "horizon"])
    backtest = read_table("forecast_backtest")
    evidence = simulator.evidence()

    comply, half = presets.loc["all_comply"], presets.loc["half_comply"]
    conventional, faster = presets.loc["conventional_80"], presets.loc["motorway_130"]
    slower = presets.loc["motorway_110"]
    interurban_total = float(comply.deaths_before)
    mde = float(comply.mde_deaths)
    one_year = detect.loc[("deaths_interurban", 1)]
    five_years = detect.loc[("deaths_interurban", 5)]
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
    motor_speed = speeds.loc["motorway"]
    urban_30 = sites.loc[("urban_30", "urban_50")]

    def deaths(row: pd.Series) -> str:
        return (
            f"{_fmt_int(row.deaths_change)} ({_fmt_int(row.deaths_change_low)} to "
            f"{_fmt_int(row.deaths_change_high)})"
        )

    def per_death_hours(row: pd.Series) -> str:
        return f"{abs(float(row.vehicle_hours_change / row.deaths_change)) / 1e3:,.0f},000"

    body = key_figures(
        [
            (
                "If every speeder kept to today's limits",
                _fmt_int(comply.deaths_change),
                f"deaths a year on motorways and conventional roads, of {_fmt_int(interurban_total)}",
            ),
            (
                "Conventional roads 90 → 80 km/h",
                _fmt_int(conventional.deaths_change),
                "deaths a year, if drivers respond as they typically do",
            ),
            (
                "Smallest change a year's count can show",
                _fmt_int(mde),
                f"deaths a year on those roads, {_fmt_pct(mde / interurban_total, 0)}",
            ),
            (
                "Conventional against motorways",
                _times(risk_ratio),
                f"deaths per kilometre driven, {risk_year}",
            ),
        ]
    )
    body += (
        '<p class="answer">Speed is the lever on the severity of crashes that the evidence '
        "measures best, and in Spain most cars on conventional roads drive above the limit: "
        f"only {_fmt_pct(float(conv_speed.share_within_limit), 0)} of those measured in 2022 "
        "kept to 90 km/h. Applied to the deaths on Spain's motorways and conventional roads, "
        "the published Power Model says that if every driver now above the limit kept to it, "
        f"about {_fmt_int(-comply.deaths_change)} fewer people a year would die there "
        f"(between {_fmt_int(-comply.deaths_change_high)} and "
        f"{_fmt_int(-comply.deaths_change_low)}), more than any change of limit on this page "
        "achieves. Lowering the limit on conventional roads from 90 to 80 km/h, with drivers "
        "responding as they typically do, would save about "
        f"{_fmt_int(-conventional.deaths_change)}. Neither would be easy to see: a change "
        f"smaller than about {_fmt_int(mde)} deaths a year cannot be told from an ordinary year "
        "in the counts, and waiting longer makes it harder, not easier.</p>"
    )

    body += "<h2>Set a law</h2>"
    body += (
        '<div id="simulator-panel" hidden>'
        + _simulator_controls(parameters)
        + _simulator_results(parameters)
        + "</div>"
    )
    rows = []
    for key, row in presets.iterrows():
        if key == "current":
            continue
        urban = sites.loc[(key, "urban_50")]
        rows.append(
            {
                "Law": row.scenario_label,
                "Deaths a year": deaths(row),
                "Admitted to hospital": _fmt_int(row.seriously_injured_change),
                "Value saved a year, € million": _fmt_int(row.value_euros / 1e6),
                "Extra vehicle-hours a year, million": _fmt_dec(row.vehicle_hours_change / 1e6),
                "Visible in a year's count": "yes" if bool(row.visible_in_one_year) else "no",
                "Deaths on 50 km/h streets": _signed_pct(float(urban.deaths_ratio) - 1),
            }
        )
    body += table(
        pd.DataFrame(rows),
        "The laws the page offers as starting points, computed with drivers responding as "
        "they typically do: casualties on motorways and conventional roads, their value and the "
        "time they cost, and the change on urban streets now at 50 km/h",
    )
    body += (
        "<p>Read the rows against each other. Raising the motorway limit to 130 km/h would cost "
        f"about {_fmt_int(faster.deaths_change)} lives a year and save about "
        f"{_fmt_dec(-faster.vehicle_hours_change / 1e6, 0)} million vehicle-hours, about "
        f"{per_death_hours(faster)} hours for each life. Lowering it to 110 km/h would save "
        f"about {_fmt_int(-slower.deaths_change)} lives for "
        f"{_fmt_dec(slower.vehicle_hours_change / 1e6, 0)} million hours. Lowering the "
        f"conventional limit to 80 km/h saves {_fmt_int(-conventional.deaths_change)} lives "
        f"for {_fmt_dec(conventional.vehicle_hours_change / 1e6, 0)} million hours, about "
        f"{per_death_hours(conventional)} hours each. Half of today's speeders keeping to the "
        f"limit would save {_fmt_int(-half.deaths_change)}. The page puts no price on time: no "
        "Spanish official value of travel time was found to cite, and the trade-off is a "
        "choice, not a calculation. Lives are valued at DGT's own figure, "
        f"€{simulator.parameter('value_death'):,.0f} for each death prevented.</p>"
    )
    body += (
        "<p>On urban streets the page gives no national count, because DGT does not publish how "
        "many urban casualties happen on streets at 30 km/h and how many at 50. On the streets "
        "still at 50, a 30 km/h limit with the typical response would take the mean car speed "
        f"from {float(urban_30.mean_speed):.1f} to {float(urban_30.new_mean_speed):.1f} km/h and "
        f"change deaths there by {_signed_pct(float(urban_30.deaths_ratio) - 1)}; but the "
        "evidence for deaths on urban streets is weak enough that its interval runs from "
        f"{_signed_pct(float(urban_30.deaths_ratio_low) - 1)} to "
        f"{_signed_pct(float(urban_30.deaths_ratio_high) - 1)}. For admissions to hospital, "
        "which the evidence pins down better, the change is "
        f"{_signed_pct(float(urban_30.seriously_injured_ratio) - 1)} "
        f"({_signed_pct(float(urban_30.seriously_injured_ratio_low) - 1)} to "
        f"{_signed_pct(float(urban_30.seriously_injured_ratio_high) - 1)}).</p>"
    )
    body += downloads(
        [
            ("simulator_presets", "the preset laws"),
            ("simulator_preset_sites", "speeds and ratios by kind of road"),
            ("simulator_baseline", "the baseline by road class"),
        ]
    )

    body += "<h2>Where the risk is</h2>"
    body += (
        "<p>The Ministerio de Transportes measures how far traffic travels on Spain's interurban "
        "roads, by type of road. Divided into it, conventional roads killed "
        f"{_times(risk_ratio)} as many people per kilometre as motorways and autovías in "
        f"{risk_year}, and {_times(pooled_ratio)} over {int(risk.year.min())}–{risk_year}, "
        "although their traffic is slower: a mean of "
        f"{float(conv_speed.mean_speed):.1f} km/h against "
        f"{float(motor_speed.mean_speed):.1f}. Speed is not what separates the two kinds of road; "
        "two-way traffic with no barrier between the directions is. Within each kind of road, "
        "speed is what decides how hard a crash is, and that is what the Power Model measures. "
        "Conventional roads are where the most deaths and the most speeding meet.</p>"
    )
    body += downloads([("simulator_class_risk", "deaths per vehicle-km by road class")])

    body += "<h2>How each number is made</h2>"
    body += (
        "<p>Four links, each with its source. <strong>The baseline</strong> is the mean deaths, "
        "admissions and other injured of "
        f"{parameters['baselineYears'][0]}–{parameters['baselineYears'][1]} by road class, from "
        "the crash microdata, which reconcile exactly with DGT's yearbook. <strong>Today's "
        "speeds</strong> are the free-flow speeds of cars measured by radar in Spain in 2022 for "
        "the EU's Baseline project: the mean, the share within the limit and the speed 85% of "
        "cars stay under. A log-normal distribution through the last two reproduces both; its "
        "mean lands within "
        f"{float((speeds.implied_mean - speeds.mean_speed).abs().max()):.1f} km/h of the "
        "measured one on every kind of road. <strong>A new limit</strong> moves the average "
        "speed by part of the change: the curve fitted to 143 before-and-after results puts a "
        f"cut of 10 km/h at {_fmt_dec(simulator.typical_response(-10))} km/h and of 20 km/h at "
        f"{_fmt_dec(simulator.typical_response(-20))}. <strong>Compliance</strong> brings a share "
        "of the drivers above the limit down to it, which lowers the mean by that share of the "
        f"average excess: {float(conv_speed.excess_over_limit):.1f} km/h per car on conventional "
        f"roads, {float(motor_speed.excess_over_limit):.1f} on motorways. <strong>The Power "
        "Model</strong> turns the change in mean speed into casualties: a count changes by the "
        "ratio of the speeds raised to a power, larger for deaths than for injuries.</p>"
    )
    rows = [
        {
            "Value": EVIDENCE_LABELS[row.parameter],
            "Applies to": APPLIES_TO[row.applies_to],
            "Figure": _evidence_value(row),
            "Source": row.source,
            "Where": row.location,
        }
        for row in evidence.itertuples()
        if row.parameter in EVIDENCE_LABELS
    ]
    body += table(
        pd.DataFrame(rows),
        "Every published value the simulator uses; exponent intervals are 95%; the register "
        "below gives the URL and a verbatim quote for each row",
    )
    body += downloads([("simulator_evidence", "every value with its URL and a verbatim quote")])

    body += "<h2>Could the counts show it?</h2>"
    holdout = validation.loc[("deaths_all", "holdout")]
    selection = validation.loc[("deaths_all", "selection")]
    pandemic = validation.loc[("deaths_all", "pandemic")]
    chosen = forecast.CHOSEN
    worst = backtest[(backtest.outcome == "deaths_all") & (backtest.set == "holdout")]
    worst = worst.assign(error=lambda f: (f.observed / f.model - 1).abs()).sort_values("error")
    worst_year = worst.iloc[-1]
    body += (
        "<p>A law is judged by comparing the deaths after it with the deaths there would have "
        "been without it, and the second number is a forecast. To know how good a forecast "
        "can be, a simple model was built and tested on years it had not seen: a Poisson "
        "regression of monthly deaths on the month of the year, a four-year trend, the month's "
        "road fuel and its number of Fridays, Saturdays and Sundays. Its form was chosen on the "
        "forecasts of 2006–2015 alone. On those years its error was "
        f"{_fmt_pct(float(selection.loc[chosen, 'rmse']))}, against "
        f"{_fmt_pct(float(selection.loc['last_year', 'rmse']))} for simply repeating last year's "
        "count and "
        f"{_fmt_pct(float(selection.loc['boosted_trees', 'rmse']))} for gradient-boosted trees "
        "given the same inputs, which cannot extend a trend. In the lockdown years it was "
        f"{_fmt_pct(float(pandemic.loc[chosen, 'rmse']))} against "
        f"{_fmt_pct(float(pandemic.loc['last_year', 'rmse']))}, because it knows the traffic "
        "fell. On the years held back, 2016–2019 and 2022–2024, it was "
        f"{_fmt_pct(float(holdout.loc[chosen, 'rmse']))} and last year's count "
        f"{_fmt_pct(float(holdout.loc['last_year', 'rmse']))}: in flat years nothing beats "
        "last year, and the model only earns its place when the trend or the traffic moves, "
        "which is when a law's effect has to be told apart from them. Its worst held-back year "
        f"is {int(worst_year.year)}, forecast from a window that includes the lockdowns.</p>"
    )
    body += figure("k1_forecast_check", "Each year's deaths against two forecasts", captions)
    body += (
        "<p>The forecast's own error sets the smallest effect a before-and-after comparison can "
        "detect. For deaths on interurban roads one year after a law it is "
        f"{_fmt_pct(float(one_year.mde), 0)}, about {_fmt_int(one_year.mde_deaths_per_year)} "
        "deaths a year; summed over five years it is "
        f"{_fmt_pct(float(five_years.mde), 0)}, because the trend drifts further from any "
        "extrapolation the longer it runs. This is why the dated policy changes on the "
        '<a href="policy.html">2006 page</a> could not be settled from the counts, and why a '
        "speed law's effect is checked by measuring speeds, which the Power Model then turns "
        "into casualties.</p>"
    )
    body += figure(
        "k2_detectability",
        "The smallest detectable fall in deaths by years after a law",
        captions,
    )
    body += downloads(
        [
            ("forecast_validation", "model against the naive forecasts"),
            ("forecast_selection", "every specification and window"),
            ("forecast_backtest", "each year's forecasts"),
            ("forecast_detectability", "smallest detectable effects"),
            ("forecast_coefficients", "what the model learned"),
        ]
    )

    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "On the evidence, the largest saving within reach is not a new limit but the existing "
        "ones kept: if every driver now above the limit on motorways and conventional roads kept "
        f"to it, about {_fmt_int(-comply.deaths_change)} fewer people would die each year, "
        f"{_fmt_pct(-comply.deaths_change / interurban_total, 0)} of the deaths on those roads, "
        f"worth about €{comply.value_euros / 1e9:,.1f} billion a year at DGT's own values. "
        "The next largest is on conventional roads, the deadliest per kilometre. Raising "
        "motorway limits trades lives for hours at a rate the page shows but does not judge. "
        "Almost none of these changes would be visible in the national death count within a "
        "year, so a speed law has to be judged by the speeds it produces, not by waiting for "
        "the deaths."
    )
    body += limits(
        "The Power Model is an aggregate relation estimated from before-and-after studies in "
        "other countries; it applies to the mean speed of traffic and is less certain on urban "
        "streets, where its interval for deaths includes no effect. The speeds are free-flow "
        "speeds of cars on weekday daytime, measured in 2022; trucks, night traffic and "
        "congestion are not in them. Compliance that removes the highest speeds also narrows "
        "the spread of speeds, which the Power Model does not count, so the compliance figures "
        "are if anything low. The response to a new limit varies widely between roads, which is "
        "why it can be set by hand. Time is computed at free-flow speeds over the measured "
        "interurban kilometres, which leave out municipal interurban roads. Other interurban "
        f"roads ({_fmt_int(read_table('simulator_baseline').set_index('road_class').loc['other_interurban', 'deaths'])} "
        "deaths a year) and urban streets as a national count are left out because no speed or "
        "street split is published for them."
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
        "Set new speed limits, decide how far drivers follow them, and see what the published "
        "evidence implies for deaths and injuries on Spain's interurban roads, what that is "
        "worth, what it costs in time, and whether the death counts could ever show it.",
        body,
        head=head,
    )
