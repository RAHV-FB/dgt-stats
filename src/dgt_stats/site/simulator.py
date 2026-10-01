"""What a speed law would do: the interactive simulator and the model behind its verdicts."""

from __future__ import annotations

import pandas as pd

from dgt_stats import forecast, simulator
from dgt_stats.site.components import (
    _chance,
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

OUTCOME_LABELS = {
    "deaths": "Deaths",
    "seriously_injured": "Admitted to hospital",
    "slightly_injured": "Other injured",
    "injury_crashes": "Injury crashes",
}


def _power(power: float) -> str:
    """A chance of detection for a table, where nothing changes saying so, and no false 100%."""
    if pd.isna(power):
        return "no change on these roads"
    return "over 99%" if power > 0.995 else _fmt_pct(float(power), 0)


def _source(evidence: pd.DataFrame, name: str, applies_to: str, text: str) -> str:
    """``text`` linked to the URL the register gives for one published value."""
    row = evidence[(evidence.parameter == name) & (evidence.applies_to == applies_to)].iloc[0]
    return f'<a href="{esc(row.url)}">{esc(text)}</a>'


def _evidence_tables(evidence: pd.DataFrame, speeds: pd.DataFrame) -> str:
    """The measured speeds and the Power Model exponents, the two sets of values behind the page."""
    rows = [
        {
            "Road": row.site_label,
            "Mean speed, km/h": _fmt_dec(row.mean_speed),
            "Within the limit": _fmt_pct(row.share_within_limit, 0),
            "85th percentile, km/h": _fmt_dec(row.v85, 0),
            "Fitted mean, km/h": _fmt_dec(row.implied_mean),
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
        "a count changes by the ratio of mean speeds raised to this power",
    )
    return out


def _simulator_controls(parameters: dict) -> str:
    """The form: one select per limit a law sets, then how drivers respond and comply."""
    selects = []
    for lever, spec in parameters["levers"].items():
        options = "".join(
            f'<option value="{limit:g}"{" selected" if limit == spec["limit"] else ""}>'
            f"{limit:g} km/h</option>"
            for limit in spec["options"]
        )
        selects.append(
            f'<label class="control"><span>{esc(spec["label"])}</span>'
            f'<select data-lever="{lever}" data-limit="{spec["limit"]:g}">{options}</select>'
            "</label>"
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
        "As they typically do: the curve fitted to 143 before-and-after results</label>"
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
    for key in simulator.INTERURBAN_SITES:
        label = simulator.ROAD_CLASSES[key]
        base = parameters["baseline"][key]
        rows += (
            f'<tr data-class="{key}"><th scope="row">{esc(label)}</th>'
            f'<td data-out="speed"></td><td>{_fmt_int(base["deaths"])}</td>'
            '<td data-out="deaths"></td><td data-out="deaths-range"></td>'
            '<td data-out="serious"></td><td data-out="slight"></td>'
            '<td data-out="value"></td><td data-out="hours"></td></tr>'
        )
    total = sum(parameters["baseline"][k]["deaths"] for k in simulator.INTERURBAN_SITES)
    rows += (
        '<tr data-class="total" class="total"><th scope="row">All three</th><td></td>'
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
        'interurban roads" aria-live="polite"><table><caption>Autopistas, autovías and '
        "conventional roads: the change a year under the law set above; the range spans the 95% "
        "intervals of the Power Model exponents; hours are those of cars and other light "
        "vehicles</caption>"
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
    mde, mde_rise = float(comply.mde_deaths), float(comply.mde_rise_deaths)
    trees = read_table("forecast_selection")
    trees = trees[
        (trees.family == "trees")
        & (trees.outcome == "deaths_all")
        & (trees.method != forecast.TREE_METHOD)
    ].pivot_table(index="method", columns="set", values="rmse")
    flat_tree = trees.loc[trees.holdout.idxmin()]
    everything = read_table("forecast_selection")
    everything = everything[(everything.outcome == "deaths_all") & (everything.set == "holdout")]
    if everything.loc[everything.rmse.idxmin(), "method"] != flat_tree.name:
        raise ValueError("simulator page: the best forecast of the held-back years has changed")
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
    autopista_speed, autovia_speed = speeds.loc["autopista"], speeds.loc["autovia"]
    urban_30 = sites.loc[("urban_30", "urban_50")]
    grid = read_table("simulator_limit_grid")

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
                f"deaths a year, of {_fmt_int(interurban_total)} on autopistas, autovías and "
                "conventional roads",
            ),
            (
                "Conventional roads 90 → 80 km/h",
                _fmt_int(conventional.deaths_change),
                "deaths a year, if drivers respond as they typically do",
            ),
            (
                "Fall a year's count picks up 4 times in 5",
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
    single = grid[grid.levers_changed == 1].sort_values("deaths_change").iloc[0]
    beyond = grid[grid.deaths_change < float(comply.deaths_change)]
    if (beyond.levers_changed < 2).any():
        raise ValueError("simulator page: a single new limit saves more than full compliance")
    deepest = grid.sort_values("deaths_change").iloc[0]
    today = {lever: parameters["levers"][lever]["limit"] for lever in ("motorway", "conventional")}
    conventional_only = grid[
        (grid.levers_changed == 1) & (grid.motorway_limit == today["motorway"])
    ].sort_values("conventional_limit")
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

    body += (
        '<p class="answer">Speed is the lever on the severity of crashes that the evidence '
        "measures best, and in Spain most cars on conventional roads drive above the limit: "
        f"only {_fmt_pct(float(conv_speed.share_within_limit), 0)} of those measured in 2022 "
        "kept to 90 km/h. Applied to the deaths on Spain's autopistas, autovías and "
        "conventional roads, the published Power Model says that if every driver now above "
        f"the limit kept to it, about {_fmt_int(-comply.deaths_change)} fewer people a year "
        f"would die there (between {_fmt_int(-comply.deaths_change_high)} and "
        f"{_fmt_int(-comply.deaths_change_low)}). With drivers responding to a new limit as they "
        "typically do, that is more than any single new limit on this page achieves, the "
        f"largest being {lever_change(single)} "
        f"({_fmt_int(-single.deaths_change)}); only lowering both limits at once saves more, "
        f"up to {_fmt_int(-deepest.deaths_change)} with {lever_change(deepest)}. Lowering the "
        f"limit on conventional roads from 90 to 80 km/h would save about "
        f"{_fmt_int(-conventional.deaths_change)}. The first "
        f"year's death count on these roads would show full compliance "
        f"{_chance(comply.power_in_one_year)}, but a fall of "
        f"{_fmt_int(-conventional.deaths_change)} only {_chance(conventional.power_in_one_year)}: "
        f"it picks up a fall of {_fmt_int(mde)} four times in five, and smaller ones less "
        "often.</p>"
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
                "Chance a year's count shows it": _power(row.power_in_one_year),
                "Deaths on 50 km/h streets": _signed_pct(float(urban.deaths_ratio) - 1),
            }
        )
    body += table(
        pd.DataFrame(rows),
        "The laws the page offers as starting points, computed with drivers responding as "
        "they typically do: casualties on autopistas, autovías and conventional roads, their "
        "value, the time on those roads of cars and other light vehicles, the chance the first year's "
        "death count on those roads shows the change, and the change on urban streets now at "
        "50 km/h",
    )
    body += (
        "<p>Read the rows against each other. Raising the limit on autopistas and autovías to "
        "130 km/h would cost "
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
        f"{_times(risk_ratio)} as many people per kilometre as autopistas and autovías in "
        f"{risk_year}, and {_times(pooled_ratio)} over {int(risk.year.min())}–{risk_year}, "
        "although their traffic is slower: a mean of "
        f"{float(conv_speed.mean_speed):.1f} km/h against {float(autovia_speed.mean_speed):.1f} "
        f"on autovías and {float(autopista_speed.mean_speed):.1f} on autopistas. Speed alone "
        "does not explain the gap: conventional roads also differ in two-way traffic without a "
        "barrier, junctions and direct access, none of which these data measure. Within each "
        "kind of road, speed is what decides how hard a crash is, and that is what the Power "
        "Model measures. Conventional roads are where the most deaths meet the most speeding of "
        "any interurban road, by the share of cars above the limit and by how far above it they "
        "drive.</p>"
    )
    body += downloads([("simulator_class_risk", "deaths per vehicle-km by road class")])

    body += "<h2>How each number is made</h2>"
    elvik = _source(evidence, "exponent_deaths", "rural", "Elvik's 2009 meta-analysis")
    dgt_value = _source(evidence, "value_death", "all", "DGT's 2024 value of a life")
    body += (
        "<p>Four links, each with its source. <strong>The baseline</strong> is the mean deaths, "
        "admissions and other injured of "
        f"{parameters['baselineYears'][0]}–{parameters['baselineYears'][1]} by road class, from "
        "the crash microdata, which reconcile exactly with DGT's yearbook. <strong>Today's "
        "speeds</strong> are the free-flow speeds of cars measured by radar in Spain in 2022 for "
        f"the {_source(evidence, 'mean_speed', 'conventional', 'EU Baseline project')}: the "
        "mean, the share within the limit and the speed 85% of cars stay under. A log-normal "
        "distribution through the last two reproduces both, and its mean lands within "
        f"{float((speeds.implied_mean - speeds.mean_speed).abs().max()):.1f} km/h of the measured "
        "one on every kind of road. The limits are those of the "
        f"{_source(evidence, 'limit', 'autovia', 'Reglamento General de Circulación')} and "
        f"{_source(evidence, 'limit', 'urban_50', 'Real Decreto 970/2020')}. <strong>A new "
        "limit</strong> moves the average speed by part of the change: the curve fitted to "
        f"{_source(evidence, 'pass_through_b', 'all', '143 before-and-after results')} puts a "
        f"cut of 10 km/h at {_fmt_dec(simulator.typical_response(-10))} km/h and of 20 km/h at "
        f"{_fmt_dec(simulator.typical_response(-20))}. <strong>Compliance</strong> brings a share "
        "of the drivers above the limit down to it, which lowers the mean by that share of the "
        f"average excess: {float(conv_speed.excess_over_limit):.1f} km/h per car on conventional "
        f"roads, {float(autopista_speed.excess_over_limit):.1f} on autopistas and "
        f"{float(autovia_speed.excess_over_limit):.1f} on autovías. <strong>The Power "
        "Model</strong>, in "
        f"{elvik}, turns "
        "the change in mean speed into casualties, more steeply for deaths than for injuries. "
        "Casualties are valued at "
        f"{dgt_value} and "
        f"{_source(evidence, 'value_serious_injury', 'all', 'of an injury')}.</p>"
    )
    body += _evidence_tables(evidence, read_table("simulator_speed_sites"))
    body += downloads([("simulator_evidence", "every published value, its URL and a quote")])

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
        f"{_fmt_pct(float(selection.loc[forecast.TREE_METHOD, 'rmse']))} for gradient-boosted "
        "trees given the same inputs and tuned on the same years, which cannot extend a trend; "
        "the trees did worse than the model on every kind of road and in every set of years. "
        "In the lockdown years the model's error was "
        f"{_fmt_pct(float(pandemic.loc[chosen, 'rmse']))} against "
        f"{_fmt_pct(float(pandemic.loc['last_year', 'rmse']))}, because it knows the traffic "
        "fell. On the years held back, 2016–2019 and 2022–2024, it was "
        f"{_fmt_pct(float(holdout.loc[chosen, 'rmse']))} and last year's count "
        f"{_fmt_pct(float(holdout.loc['last_year', 'rmse']))}: in flat years last year's count "
        "did better than the model, which earns its place when the trend or the traffic moves, "
        "the years in which a law's effect has to be told apart from them. Its worst held-back "
        f"year is {int(worst_year.year)}, forecast from a window that includes the lockdowns. "
        "Trees with larger leaves, each holding at least "
        f"{flat_tree.name.rsplit('_', 1)[-1]} months, worse on the selection years "
        f"({_fmt_pct(float(flat_tree.selection))}), would have done best of all on the "
        f"held-back years ({_fmt_pct(float(flat_tree.holdout))}) and worse "
        f"than the model in the lockdowns ({_fmt_pct(float(flat_tree.pandemic))}): they "
        "forecast little more than the recent level, which wins only when nothing moves, and "
        "that cannot be known when the forecast is made.</p>"
    )
    body += figure("k1_forecast_check", "Each year's deaths against two forecasts", captions)
    body += (
        "<p>The forecast's own error sets how large an effect a before-and-after comparison "
        "picks up. For all deaths on interurban roads one year after a law, the fall it detects "
        "four times in five (a two-sided test at 5%) is "
        f"{_fmt_pct(float(one_year.mde), 0)}, about {_fmt_int(one_year.mde_deaths_per_year)} "
        f"of {_fmt_int(one_year.expected)} deaths a year; on the "
        f"{_fmt_int(interurban_total)} deaths of the autopistas, autovías and conventional "
        f"roads the simulator covers it is {_fmt_int(mde)}, and a rise needs to reach "
        f"{_fmt_int(mde_rise)}. Smaller changes are picked up less often, not never: the preset "
        "table gives each one's chance. Summed over five years the "
        f"threshold is {_fmt_pct(float(five_years.mde), 0)}, because the trend drifts further "
        "from any extrapolation the longer it runs. This is why the dated policy changes on the "
        '<a href="policy.html">2006 page</a> could not be settled from the counts, and why a '
        "speed law's effect is checked by measuring speeds, which the Power Model then turns "
        "into casualties.</p>"
    )
    body += figure(
        "k2_detectability",
        "The fall in deaths a comparison detects four times in five, by years after a law",
        captions,
    )
    body += downloads(
        [
            ("forecast_validation", "model against the naive forecasts"),
            ("forecast_selection", "every specification and window"),
            ("forecast_backtest", "each year's forecasts"),
            ("forecast_detectability", "effects detected four times in five"),
            ("forecast_coefficients", "what the model learned"),
        ]
    )

    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "On the evidence, and with drivers responding to a new limit as they typically do, the "
        "largest saving within reach of any one measure is not a new limit but the existing "
        "ones kept: if every driver now above the limit on autopistas, "
        "autovías and conventional roads kept to it, about "
        f"{_fmt_int(-comply.deaths_change)} fewer people would die each year, "
        f"{_fmt_pct(-comply.deaths_change / interurban_total, 0)} of the deaths on those roads, "
        f"worth about €{comply.value_euros / 1e9:,.1f} billion a year at DGT's own values. "
        "The largest saving from a new limit is on conventional roads, the deadliest per "
        "kilometre. Raising "
        "the motorway limit trades lives for hours at a rate the page shows but does not judge. "
        "Full compliance would show in the first year's death count on those roads "
        f"{_chance(comply.power_in_one_year)}. Of the new limits, conventional roads at "
        f"{conventional_only.iloc[0].conventional_limit:g} km/h would show "
        f"{_chance(conventional_only.iloc[0].power_in_one_year)} and at "
        f"{conventional_only.iloc[1].conventional_limit:g} km/h "
        f"{_chance(conventional_only.iloc[1].power_in_one_year)}, and no change of the motorway limit alone "
        f"more than {_fmt_pct(float(motorway_only.power_in_one_year.max()), 0)} of the time. "
        "A speed law has to be judged by the speeds it produces, not by waiting for the "
        "deaths."
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
        "interurban kilometres of cars and other light vehicles, which leave out municipal "
        "interurban roads; free motorways are timed at the speeds of autovías, with which the "
        "Ministry's traffic table counts them. Other interurban "
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
