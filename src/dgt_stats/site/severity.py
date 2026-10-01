"""Supporting analysis: the crash-severity models."""

from __future__ import annotations

from dgt_stats.site.components import (
    SUPPORTING_NOTES,
    _fmt_pct,
    conclusion,
    downloads,
    figure,
    key_figures,
    limits,
    note,
    read_table,
    render_page,
    table,
)
from dgt_stats.site.numbers import _severity_numbers

# Original research behind the mechanisms box. Peer-reviewed papers only, cited so a reader can
# check them; none of them is evidence about Spain, and the page says so.
LITERATURE = {
    "theofilatos": (
        "Theofilatos & Yannis (2014), “A review of the effect of traffic and weather "
        "characteristics on road safety”, <i>Accident Analysis &amp; Prevention</i> 72, 244–256",
        "https://doi.org/10.1016/j.aap.2014.06.017",
    ),
    "ahmed": (
        "Ahmed &amp; Ghasemzadeh (2018), “The impacts of heavy rain on speed and headway "
        "behaviors”, <i>Transportation Research Part C</i> 91, 371–384",
        "https://doi.org/10.1016/j.trc.2018.04.012",
    ),
    "kilpelainen": (
        "Kilpeläinen &amp; Summala (2007), “Effects of weather and weather forecasts on driver "
        "behaviour”, <i>Transportation Research Part F</i> 10(4), 288–299",
        "https://doi.org/10.1016/j.trf.2006.11.002",
    ),
    "elvik": (
        "Elvik, Vadeby, Hels &amp; van Schagen (2019), “Updated estimates of the relationship "
        "between speed and road safety”, <i>Accident Analysis &amp; Prevention</i> 123, 114–122",
        "https://doi.org/10.1016/j.aap.2018.11.014",
    ),
    "rosen": (
        "Rosén &amp; Sander (2009), “Pedestrian fatality risk as a function of car impact speed”, "
        "<i>Accident Analysis &amp; Prevention</i> 41, 536–542",
        "https://doi.org/10.1016/j.aap.2009.02.002",
    ),
}


def _cite(key: str) -> str:
    text, url = LITERATURE[key]
    return f'<a href="{url}">{text}</a>'


def page_severity(captions: dict[str, str]) -> str:
    numbers = _severity_numbers()
    adverse = numbers["adverse"]
    coefficients = numbers["coefficients"]
    fatal = coefficients[coefficients.outcome == "fatal"].set_index(["predictor", "level"])
    serious_adverse = read_table("q3_adverse_conditions")
    serious_adverse = serious_adverse[serious_adverse.outcome == "serious"].set_index(
        ["variant", "level"]
    )

    def orr(variant: str, level: str, frame=adverse) -> str:
        row = frame.loc[(variant, level)]
        return f"{row.odds_ratio:.2f} ({row.or_low:.2f}–{row.or_high:.2f})"

    wet_alone = float(adverse.loc[("no_weather", "wet"), "odds_ratio"])
    junction_full = float(adverse.loc[("full", "at a junction"), "odds_ratio"])

    body = key_figures(
        [
            ("Injury crashes modelled", f"{numbers['n']:,}", "2016–2024, none dropped"),
            ("Fatal", _fmt_pct(numbers["fatal_share"], 2), "at least one death within 30 days"),
            (
                "Wet road, fatal odds",
                f"{wet_alone:.2f}×",
                "against a dry road, everything else held constant",
            ),
            (
                "Holdout discrimination",
                f"{numbers['auc_fatal']:.2f}",
                "area under the ROC curve, 2023–2024 scored by a 2016–2022 fit",
            ),
        ]
    )

    body += (
        '<p class="answer">Once an injury crash has happened, the conditions a driver would '
        "call dangerous go with a <em>lower</em> chance that someone dies. A wet road carries "
        f"{wet_alone:.2f} times the odds of a death of a dry one, a junction {junction_full:.2f} "
        "times the odds of a stretch away from one. Rain and a wet surface are one effect counted "
        "twice, worth about "
        f"{wet_alone:.2f} on its own. All of this concerns how badly a crash ends, given that one "
        "has happened. It says nothing about how often crashes happen.</p>"
    )

    body += "<h2>Testing the finding</h2>"
    body += (
        "<p>The models are two logistic regressions on every injury crash of 2016 to 2024, "
        "one for a death and one for a death or a hospitalisation. The predictors are the "
        "circumstances the police record: zone, road type, crash type, junction, lighting, "
        "weather, surface, alignment, time of day, weekend, number of vehicles and year.</p>"
        "<p>The first objection is that weather and road surface measure much the same thing, so "
        "a model carrying both splits one effect between two columns. That is what happens. With "
        f"surface dropped, rain moves from {orr('full', 'rain')} to {orr('no_surface', 'rain')}. "
        f"With weather dropped, a wet surface moves from {orr('full', 'wet')} to "
        f"{orr('no_weather', 'wet')}. The right reading is a single wet-conditions effect of "
        f"about {wet_alone:.2f}.</p>"
    )
    body += (
        "<p>The second objection is that adverse weather falls in particular places. Fitting "
        "interurban roads and urban streets separately holds the road context fixed instead of "
        f"adjusting for it. The wet-surface effect stays: {orr('interurban', 'wet')} on interurban "
        f"roads and {orr('street', 'wet')} on urban streets. The junction effect, "
        f"{orr('full', 'at a junction')} overall, is present in every stratum too. Hail and snow "
        f"behave differently. They give {orr('full', 'hail or snow')} in the full model but "
        f"{orr('conventional', 'hail or snow')} on conventional roads alone, where the interval "
        "covers no effect at all.</p>"
    )
    body += figure(
        "s2_adverse_conditions",
        "Odds ratios for wet, rain, hail or snow and junctions under eight model variants",
        captions,
    )

    variants = read_table("q3_adverse_conditions")
    shown = variants[variants.outcome.isin(["fatal", "serious"])].copy()
    shown["ci"] = shown.apply(
        lambda r: f"{r.odds_ratio:.2f} ({r.or_low:.2f}–{r.or_high:.2f})", axis=1
    )
    wide = shown.pivot_table(
        index=["variant_label", "level"], columns="outcome", values="ci", aggfunc="first"
    ).reset_index()
    wide = wide.rename(
        columns={
            "variant_label": "Model",
            "level": "Condition",
            "fatal": "Fatal (95% interval)",
            "serious": "Serious (95% interval)",
        }
    )
    order = list(dict.fromkeys(variants.variant_label))
    conditions = ["wet", "rain", "hail or snow", "at a junction"]
    wide["_model"] = wide.Model.map({label: i for i, label in enumerate(order)})
    wide["_condition"] = wide.Condition.map({name: i for i, name in enumerate(conditions)})
    wide = wide.sort_values(["_condition", "_model"]).drop(columns=["_model", "_condition"])
    body += table(
        wide,
        "Odds ratios for the adverse conditions under every model variant, both outcomes. A blank "
        "cell is a level the variant does not contain",
    )
    body += downloads(
        [
            ("q3_adverse_conditions", "sensitivity fits"),
            ("q3_adverse_composition", "where hail and snow crashes happen"),
            ("q3_adverse_exclusions", "hail and snow with the top provinces removed"),
        ]
    )

    composition = read_table("q3_adverse_composition")
    snow = composition[(composition.level == "hail or snow") & (composition.dimension == "zone")]
    interurban_share = float(snow[snow.category == "interurban road"].share_of_level.iloc[0])
    exclusions = read_table("q3_adverse_exclusions")
    widest = exclusions.iloc[-1]
    body += (
        f"<p>Hail and snow are only "
        f"{int(adverse.loc[('full', 'hail or snow'), 'n_level']):,} crashes, and "
        f"{interurban_share:.0%} of them are on interurban roads, so it is fair to suspect a few "
        "mountain provinces. That is not the explanation. Dropping the three provinces that "
        f"record most of them moves the odds ratio only to {widest.odds_ratio:.2f} "
        f"({widest.or_low:.2f}–{widest.or_high:.2f}). The road type is what moves it, and on "
        "conventional roads alone the effect disappears.</p>"
    )

    body += "<h2>Why might visibly dangerous conditions produce less severe crashes?</h2>"
    body += note(
        "These are mechanisms the literature proposes, not results this analysis demonstrates. "
        "The DGT microdata carry no speed, no driver and no vehicle information, so nothing here "
        "can show which of them is at work."
    )
    body += (
        "<p>Drivers appear to compensate when the risk is visible. Naturalistic-driving data show "
        f"lower speeds and longer headways in heavy rain ({_cite('ahmed')}); survey work finds "
        "drivers also postpone or re-route trips, avoid overtaking and drive more cautiously when "
        f"the weather is bad or forecast to be ({_cite('kilpelainen')}). A modest speed reduction "
        "matters more than it sounds, because the relationship between speed and fatal outcomes "
        f"is steeply non-linear ({_cite('elvik')}; for pedestrians, {_cite('rosen')}). At "
        "junctions the plausible mechanisms are similar and more mundane: approach speeds are "
        "lower, conflict points are expected and signalled, and drivers are more often already "
        "braking when the impact happens.</p>"
    )
    body += (
        "<p>Compensation is not the only candidate. Which trips are made changes with the "
        "weather, and so does who makes them. Traffic is denser and slower. The mix of vehicles "
        "and of road types differs. A police officer's judgement of the conditions is recorded "
        "after the event. The review literature on weather and road safety treats all of these as "
        f"open ({_cite('theofilatos')}).</p>"
    )

    body += "<h2>The other coefficients</h2>"
    body += figure(
        "s1_forest_fatal",
        "Odds ratios for a fatal outcome by crash circumstance, with 95% intervals",
        captions,
    )
    head_on = fatal.loc[("crash_type", "head-on collision")]
    pedestrian = fatal.loc[("crash_type", "pedestrian struck")]
    body += (
        "<p>The large effects are the expected ones. A head-on collision carries "
        f"{head_on.odds_ratio:.1f} times the odds of a death of a side collision, and a pedestrian "
        f"struck {pedestrian.odds_ratio:.1f} times, against {junction_full:.2f} for a junction and "
        f"{wet_alone:.2f} for a wet road. Fitted on 2016 to 2022 and scored on 2023 and 2024, the "
        f"fatal model reaches an area under the ROC curve of {numbers['auc_fatal']:.2f} and the "
        f"serious model {numbers['auc_serious']:.2f}.</p>"
    )
    profiles = read_table("q3_profiles").rename(
        columns={"profile": "Crash profile", "fatal": "Fatal", "serious": "Serious"}
    )
    body += table(
        profiles,
        "Predicted probability of each outcome for named crash profiles (2024; circumstances not "
        "named are at their reference level)",
        {"Fatal": "pct2", "Serious": "pct"},
    )
    body += downloads(
        [
            ("q3_model_coefficients", "all coefficients"),
            ("q3_marginal_effects", "average marginal effects"),
            ("q3_calibration", "holdout calibration"),
            ("q3_year_stability", "year-by-year refits"),
            ("q3_groupings", "how DGT's codes map to model levels"),
        ]
    )

    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Wet conditions and junctions are associated with materially lower odds that an injury "
        f"crash kills someone: about {wet_alone:.2f} and {junction_full:.2f} times the reference "
        "odds, holding the other recorded circumstances constant. Both survive every sensitivity "
        "fit run here, so treat them as established associations. The hail and snow result does "
        "not survive, so treat it as unresolved. None of this identifies a mechanism, and none of "
        "it says anything about how likely a crash is in the first place."
    )

    stability = read_table("q3_year_stability")
    outside = int(
        (~stability[stability.outcome == "fatal"].within_full_interval.astype(bool)).sum()
    )
    total = int(len(stability[stability.outcome == "fatal"]))
    body += limits(
        "The microdata are one row per crash with no driver, vehicle or person fields, so nothing "
        "here says who was driving, how fast or whether alcohol was involved, and the factor "
        "interactions this project was first framed around cannot be estimated. A model of "
        "recorded crashes describes which recorded crashes end badly, not the risk of crashing. "
        f"Refitting one year at a time, {outside} of the {total} year-by-term estimates fall "
        "outside the full model's interval, mostly in 2024, when DGT changed how urban road types "
        'are coded (see the <a href="data.html">data page</a>); road type and zone have to be read '
        "together. Four levels that stand for a missing value track which force recorded the "
        "crash rather than what the road was like, and are marked as such in the full coefficient "
        "table."
    )
    return render_page(
        "severity",
        "Crash severity",
        "Which recorded circumstances make an injury crash fatal, and why the "
        "dangerous-looking ones point the wrong way.",
        note(SUPPORTING_NOTES["severity"]) + body,
    )
