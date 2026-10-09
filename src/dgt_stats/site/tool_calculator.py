"""The crash-severity calculator: the Catalan severity model's estimate for a crash the reader
describes, computed in the browser from the exported model (``reports/models/severity_model.json``)
by ``assets/severity-engine.js``, with the form in ``assets/severity-calculator.js``."""

from __future__ import annotations

import json

from dgt_stats.paths import REPORTS_DIR
from dgt_stats.site.components import DOCS_URL, esc
from dgt_stats.site.tool_frame import tool_page

MODEL_PATH = REPORTS_DIR / "models" / "severity_model.json"
CALCULATOR_DOC = f"{DOCS_URL}/research/SEVERITY_CALCULATOR.md"
# The inputs in the order the form asks for them, in two groups.
ROAD_INPUTS = (
    "province",
    "road",
    "speed_limit",
    "junction",
    "lighting",
    "weather",
    "surface",
    "hour",
)
CRASH_INPUTS = ("crash_type", "units")


def _select(name: str, spec: dict) -> str:
    options = "".join(
        f'<option value="{esc(level["value"])}"'
        f"{' selected' if level['value'] == spec['default'] else ''}>{esc(level['label'])}</option>"
        for level in spec["levels"]
    )
    return (
        f'<div class="calc-field"><label for="calc-{name}">{esc(spec["label"])}</label>'
        f'<select id="calc-{name}" name="{name}">{options}</select></div>'
    )


def _form(model: dict) -> str:
    inputs = model["inputs"]
    road = "".join(_select(name, inputs[name]) for name in ROAD_INPUTS)
    crash = "".join(_select(name, inputs[name]) for name in CRASH_INPUTS)
    users = inputs["users"]
    boxes = "".join(
        f'<li><label><input type="checkbox" name="users" value="{esc(level["value"])}"'
        f"{' checked' if level['value'] in users['default'] else ''}> {esc(level['label'])}"
        "</label></li>"
        for level in users["levels"]
    )
    # The form, then the panel with the result and the comparison: beside the form on a wide
    # screen (it stays in view while the form scrolls), after it on a phone.
    return (
        '<section class="calculator" id="calculator" data-model="models/severity_model.json" '
        f'data-model-id="{esc(model["model_id"])}" aria-labelledby="calculator-title" hidden>'
        '<h2 id="calculator-title">Describe a crash</h2>'
        '<div class="calc-layout">'
        "<form>"
        f'<fieldset><legend>The road and the conditions</legend><div class="calc-fields">{road}'
        "</div></fieldset>"
        f'<fieldset><legend>The crash</legend><div class="calc-fields">{crash}</div></fieldset>'
        f'<fieldset><legend>{esc(users["label"])}</legend><ul class="calc-users">{boxes}</ul>'
        "</fieldset>"
        '<div class="calc-actions">'
        '<button type="button" data-keep>Keep this crash for comparison</button>'
        '<button type="button" data-clear hidden>Clear the comparison</button>'
        '<button type="reset">Reset the inputs</button></div>'
        "</form>"
        # On a narrow screen the full result follows the form; this line keeps the estimate in
        # view while the form scrolls (the status line below announces it to screen readers).
        '<p class="calc-sticky" aria-hidden="true" data-sticky></p>'
        '<div class="calc-panel">'
        '<div class="calc-result" data-output></div>'
        '<div class="calc-baseline" data-baseline></div>'
        "</div></div>"
        '<p class="visually-hidden" role="status" aria-live="polite" data-status></p>'
        "</section>"
        '<p id="calculator-fallback">The calculator needs JavaScript. Without it, the worked '
        "examples below give the model's estimates for typical crashes.</p>"
    )


def _model() -> dict:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


def describe() -> dict[str, str]:
    training = _model()["training"]
    first, last = training["years"]
    return {
        "title": "Crash severity calculator",
        "what": "The estimated share of crashes with a death or serious injury that were fatal, "
        "for a crash you describe: the road, the conditions and who was involved.",
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
    notes = (
        "<p>The estimate is the model's share of fatal crashes among crashes already recorded "
        "with a death or serious injury in Catalonia, not the chance that a crash happens. The "
        "crashes the model was fitted on leave out the "
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
