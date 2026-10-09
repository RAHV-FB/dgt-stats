"""The crash-severity calculator: the Catalan severity model's estimate for a crash the reader
describes, computed in the browser from the exported model (``reports/models/severity_model.json``)
by ``assets/severity-engine.js``, with the form in ``assets/severity-calculator.js``.

The reader describes what happened in plain words; the page script (``SeverityBuilder.crash``)
turns that description into the model's own inputs: the crash type, the kinds of road user
involved and the number of vehicles and pedestrians. The selects of that description are
declared here (``WHAT`` and ``GROUPS``); the mapping is documented in
``docs/research/SEVERITY_CALCULATOR.md`` ("The page's crash description")."""

from __future__ import annotations

import itertools
import json

from dgt_stats import severity_model as sm
from dgt_stats.paths import REPORTS_DIR
from dgt_stats.site.components import DOCS_URL, esc
from dgt_stats.site.tool_frame import tool_page

MODEL_PATH = REPORTS_DIR / "models" / "severity_model.json"
CALCULATOR_DOC = f"{DOCS_URL}/research/SEVERITY_CALCULATOR.md"

# "What happened?": the kinds of crash the reader chooses from, then the selects each one shows.
WHAT = (
    ("collision", "Collision between vehicles"),
    ("pedestrian", "Pedestrian struck"),
    ("single", "Single vehicle, no other road user"),
    ("other", "Other crash (animal, other or not specified)"),
)
# Vehicles, by the road-user flag each sets in the model.
VEHICLES = (
    ("light_vehicle", "Car or van"),
    ("motorcycle", "Motorcycle"),
    ("moped", "Moped"),
    ("bicycle", "Bicycle"),
    ("heavy_vehicle", "Heavy vehicle (lorry or bus)"),
    ("other_unit", "Other vehicle (tram, tractor and others)"),
)
NO_OTHER = ("", "No other kind")
# Each select: the field the page script reads, its id (calc-<id>), its label and its options
# (value, label). The first option is the default, except where DEFAULTS names another: the form
# opens on the worked examples' reference crash, two cars or vans in a side or angle collision.
GROUPS: dict[str, tuple[tuple[str, str, str, tuple[tuple[str, str], ...]], ...]] = {
    "collision": (
        (
            "type",
            "collision",
            "Type of collision",
            (
                ("head_on", "Head-on"),
                ("side_impact", "Side or angle"),
                ("rear_end", "Rear-end"),
                ("sideswipe", "Sideswipe"),
            ),
        ),
        ("vehicle", "first", "First vehicle", VEHICLES),
        ("second", "second", "Second vehicle", VEHICLES),
        (
            "count",
            "vehicles",
            "Number of vehicles",
            (("2", "Two"), ("3", "Three"), ("4+", "Four or more")),
        ),
        ("another", "collision-another", "Another kind of vehicle involved", (NO_OTHER, *VEHICLES)),
    ),
    "pedestrian": (
        ("vehicle", "struck-by", "Struck by", VEHICLES),
        (
            "count",
            "people",
            "People and vehicles involved",
            (("2", "One pedestrian and one vehicle"), ("3", "Three"), ("4+", "Four or more")),
        ),
        (
            "another",
            "pedestrian-another",
            "Another kind of vehicle involved",
            (NO_OTHER, *VEHICLES),
        ),
    ),
    "single": (
        (
            "type",
            "mishap",
            "What happened",
            (
                ("run_off_road", "Ran off the road"),
                ("fixed_object", "Hit an object on the road"),
                ("fall", "Rider or passenger fell"),
            ),
        ),
        ("vehicle", "single-vehicle", "Vehicle", VEHICLES),
    ),
    "other": (
        ("vehicle", "other-vehicle", "Vehicle", VEHICLES),
        (
            "count",
            "involved",
            "Vehicles and pedestrians involved",
            (("1", "One"), ("2", "Two"), ("3", "Three"), ("4+", "Four or more")),
        ),
        (
            "another",
            "other-another",
            "Another kind of road user involved",
            (NO_OTHER, *VEHICLES, ("pedestrian", "Pedestrian")),
        ),
    ),
}
DEFAULTS = {"collision": "side_impact"}
# The model's own inputs the reader sets directly, in the order the form asks for them.
PLACE_INPUTS = ("province", "road", "junction", "speed_limit")
CONDITION_INPUTS = ("hour", "lighting", "weather", "surface")


def builder_choices() -> list[dict[str, str]]:
    """Every description the "What happened?" selects can give: one dict per combination of the
    shown selects' options (the page script turns each into the model's inputs)."""
    out = []
    for what, _ in WHAT:
        fields = GROUPS[what]
        names = [field for field, *_ in fields]
        for values in itertools.product(*([v for v, _ in options] for *_, options in fields)):
            out.append({"what": what, **dict(zip(names, values))})
    return out


def _options(options, default: str | None = None) -> str:
    default = options[0][0] if default is None else default
    return "".join(
        f'<option value="{esc(value)}"{" selected" if value == default else ""}>'
        f"{esc(label)}</option>"
        for value, label in options
    )


def _field(control: str, label: str, select: str, extra: str = "") -> str:
    return (
        f'<div class="calc-field"{extra}><label for="calc-{control}">{esc(label)}</label>'
        f"{select}</div>"
    )


def _select(name: str, spec: dict) -> str:
    """A select of one of the model's own inputs, with its levels and default."""
    levels = tuple((level["value"], level["label"]) for level in spec["levels"])
    placeholder = ""
    if name == "lighting":
        # Shown when a change of time leaves more than one lighting possible.
        placeholder = '<option value="" disabled hidden>Choose the lighting</option>'
    select = (
        f'<select id="calc-{name}" name="{name}">{placeholder}'
        f"{_options(levels, spec['default'])}</select>"
    )
    return _field(name, spec["label"], select)


def _what() -> str:
    first = _field(
        "what",
        "Kind of crash",
        f'<select id="calc-what" name="what">{_options(WHAT)}</select>',
        ' data-wide=""',
    )
    groups = []
    for what, _ in WHAT:
        fields = []
        for field, control, label, options in GROUPS[what]:
            select = (
                f'<select id="calc-{control}" name="{control}" data-field="{field}">'
                f"{_options(options, DEFAULTS.get(control))}</select>"
            )
            # The other kind of road user is asked only when the number involved leaves room.
            extra = " data-another hidden" if field == "another" else ""
            fields.append(_field(control, label, select, extra))
        hidden = "" if what == WHAT[0][0] else " hidden"
        groups.append(
            f'<div class="calc-fields calc-group" data-group="{what}"{hidden}>{"".join(fields)}</div>'
        )
    return (
        '<fieldset><legend>What happened?</legend><div class="calc-fields">'
        f"{first}</div>{''.join(groups)}"
        '<p class="calc-derived" data-derived></p></fieldset>'
    )


def _form(model: dict) -> str:
    inputs = model["inputs"]
    place = "".join(_select(name, inputs[name]) for name in PLACE_INPUTS)
    conditions = "".join(_select(name, inputs[name]) for name in CONDITION_INPUTS)
    training = model["training"]
    first, last = training["years"]
    # The form, then the panel with the result and the comparison: beside the form on a wide
    # screen (it stays in view while the form scrolls), after it on a phone.
    return (
        '<section class="calculator" id="calculator" data-model="models/severity_model.json" '
        f'data-model-id="{esc(model["model_id"])}" aria-labelledby="calculator-title" hidden>'
        '<h2 id="calculator-title" class="visually-hidden">Describe a crash</h2>'
        '<div class="calc-layout">'
        "<form>"
        f"{_what()}"
        '<fieldset><legend>Where did it happen?</legend><div class="calc-fields">'
        f"{place}</div></fieldset>"
        '<fieldset><legend>Under what conditions?</legend><div class="calc-fields">'
        f'{conditions}</div><p class="calc-adjusted" data-adjusted hidden></p></fieldset>'
        '<div class="calc-actions">'
        '<button type="button" data-save>Save as scenario A</button>'
        '<button type="button" data-clear hidden>Clear scenario A</button>'
        '<button type="reset">Reset</button></div>'
        "</form>"
        # On a narrow screen the full result follows the form; this line keeps the estimate in
        # view while the form scrolls (the status line below announces it to screen readers).
        '<p class="calc-sticky" aria-hidden="true" data-sticky></p>'
        '<div class="calc-panel">'
        '<div class="calc-result" data-output></div>'
        '<div class="calc-baseline" data-baseline></div>'
        f'<p class="calc-meta">Model {esc(model["model_id"])}, fitted on '
        f"{training['crashes']:,} crashes recorded in {first}–{last}. "
        '<a href="severity-models.html">How it was built and tested</a></p>'
        "</div></div>"
        '<p class="visually-hidden" role="status" aria-live="polite" data-status></p>'
        "</section>"
        '<p id="calculator-fallback">The calculator needs JavaScript. The '
        '<a href="severity-models.html">severity model</a> page gives its estimates for '
        "typical crashes.</p>"
    )


def _model() -> dict:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


def describe() -> dict[str, str]:
    training = _model()["training"]
    first, last = training["years"]
    return {
        "title": "Crash severity calculator",
        "what": "The estimated share of crashes with a death or serious injury that were fatal, "
        "for a crash you describe: what happened, where and in what conditions.",
        "coverage": f"Catalonia, crashes recorded in {first}–{last}",
        "kind": "Model estimate with a 95% confidence interval",
    }


def data_files() -> dict[str, object]:
    """The calculator reads the exported model, which the build publishes in ``models/``."""
    return {}


def page_calculator(captions: dict[str, str]) -> str:
    del captions
    model = _model()
    training = model["training"]
    hours = {level["value"]: level["label"] for level in model["inputs"]["hour"]["levels"]}
    dark = " or ".join(hours[band] for band in sm.HOURS_WITHOUT_DAYLIGHT)
    light = " or ".join(hours[band] for band in sm.HOURS_OF_DAYLIGHT_ONLY)
    notes = (
        "<p>The estimate is the model's share of fatal crashes (a death within 24 hours) among "
        "crashes already recorded with a death or serious injury in Catalonia, not the chance "
        "that a crash happens. Its 95% interval covers only the uncertainty in the model's "
        "coefficients, not the differences between places and years. Tested on later years in "
        "Catalonia, the only region it was tested in, its estimates missed in some years and "
        "places, which the severity model page names.</p>"
        "<p>The description of the crash sets the model's inputs: its type, the kinds of road "
        "user involved and how many vehicles and pedestrians there were. Conditions that cannot "
        "occur together are not offered: heavy rain, hail or snow on a dry road, daylight at "
        f"{dark}, and dawn, dusk or night at {light}.</p>"
        "<p>The crashes the model was fitted on leave out the "
        f"{training['excluded_owner_not_recorded']:,} on conventional roads whose owning network "
        "is not named. How the model was built and tested is on the "
        '<a href="severity-models.html">severity model</a> page and in the '
        f'<a href="{CALCULATOR_DOC}">calculator report</a>.</p>'
    )
    return tool_page(
        "calculator",
        "Crash severity calculator",
        "The estimated fatal share of a crash with a death or serious injury in Catalonia, for "
        "a crash you describe.",
        _form(model),
        notes,
        ("models/severity-engine.js", "models/severity-calculator.js"),
        fallback=" ",
    )
