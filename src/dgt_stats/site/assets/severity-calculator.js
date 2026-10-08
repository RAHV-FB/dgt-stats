/*
 * The crash-severity calculator's page: reads the form, asks the engine (severity-engine.js)
 * for the predicted share of fatal crashes and its interval, and compares the crash with a
 * second one the reader keeps. Every number comes from the exported model
 * (models/severity_model.json); this file only moves values between the form and the engine.
 * Without scripting the form stays hidden and the page's tables of worked examples remain.
 */
(function () {
  "use strict";

  var root = document.getElementById("calculator");
  if (!root || !window.SeverityEngine) return;
  var form = root.querySelector("form");
  var output = root.querySelector("[data-output]");
  var baselineBox = root.querySelector("[data-baseline]");
  var keep = root.querySelector("[data-keep]");
  var clear = root.querySelector("[data-clear]");
  var status = root.querySelector("[data-status]");
  var engine = null;
  var model = null;
  var baseline = null;

  function percent(value, decimals) {
    return (100 * value).toFixed(decimals === undefined ? 1 : decimals) + "%";
  }

  function points(value) {
    var shown = (100 * value).toFixed(1);
    if (Number(shown) === 0) shown = (0).toFixed(1);
    return (value > 0 ? "+" : "") + shown.replace("-", "−") + " points";
  }

  function text(tag, content, className) {
    var node = document.createElement(tag);
    node.textContent = content;
    if (className) node.className = className;
    return node;
  }

  function scenarioFromForm() {
    var scenario = {};
    Object.keys(model.inputs).forEach(function (name) {
      var input = model.inputs[name];
      if (input.type === "flags") {
        input.levels.forEach(function (level) {
          var box = form.querySelector('input[name="users"][value="' + level.value + '"]');
          scenario[level.value] = Boolean(box && box.checked);
        });
      } else {
        scenario[name] = form.elements[name].value;
      }
    });
    return scenario;
  }

  function describe(scenario) {
    var parts = [];
    Object.keys(model.inputs).forEach(function (name) {
      var input = model.inputs[name];
      if (input.type === "flags") {
        var ticked = input.levels.filter(function (level) { return scenario[level.value]; });
        parts.push(input.label + ": " + ticked.map(function (l) { return l.label; }).join(", "));
      } else {
        var level = input.levels.filter(function (l) { return l.value === scenario[name]; })[0];
        parts.push(input.label + ": " + (level ? level.label : scenario[name]));
      }
    });
    return parts.join("; ");
  }

  function ruleText(id, rare) {
    var rule = model.rules.filter(function (r) { return r.id === id; })[0];
    if (!rule) return id;
    var words = rule.text.replace("{threshold}", String(rule.threshold || ""));
    if (id === "rare_level") {
      var labels = rare.map(function (name) {
        if (model.inputs[name]) return model.inputs[name].label.toLowerCase();
        var level = model.inputs.users.levels.filter(function (l) { return l.value === name; })[0];
        return level ? level.label.toLowerCase() : name;
      });
      words = words.replace("{input}", labels.join(", "));
    }
    return words;
  }

  function render() {
    var scenario = scenarioFromForm();
    var checked = engine.check(scenario);
    output.textContent = "";
    if (checked.errors.length) {
      output.appendChild(text("p", "No estimate for this combination:", "calc-error-title"));
      var list = document.createElement("ul");
      checked.errors.forEach(function (id) { list.appendChild(text("li", ruleText(id))); });
      output.appendChild(list);
      output.setAttribute("data-state", "error");
      keep.disabled = true;
      return;
    }
    keep.disabled = false;
    output.setAttribute("data-state", "ok");
    var result = engine.predict(scenario);
    var similar = engine.similar(scenario);
    output.appendChild(text("p", percent(result.probability), "calc-value"));
    output.appendChild(
      text(
        "p",
        "of crashes like this one, among those with a death or serious injury, are predicted to " +
          "have been fatal (95% interval " + percent(result.low) + "–" + percent(result.high) +
          ").",
        "calc-label"
      )
    );
    output.appendChild(
      text(
        "p",
        similar.crashes +
          " recorded crashes in " + model.training.years[0] + "–" + model.training.years[1] +
          " share this zone, crash type, road users and number involved" +
          (similar.crashes ? ", of which " + similar.fatal + " were fatal." : "."),
        "calc-note"
      )
    );
    if (checked.warnings.length) {
      var warnings = document.createElement("ul");
      warnings.className = "calc-warnings";
      checked.warnings.forEach(function (id) {
        warnings.appendChild(text("li", ruleText(id, checked.rare)));
      });
      output.appendChild(warnings);
    }
    renderComparison(scenario, result);
  }

  function renderComparison(scenario, result) {
    baselineBox.textContent = "";
    if (!baseline) {
      clear.hidden = true;
      baselineBox.appendChild(
        text(
          "p",
          "Keep this crash for comparison, then change any input to see how the predicted share " +
            "changes.",
          "calc-note"
        )
      );
      return;
    }
    clear.hidden = false;
    var kept = engine.predict(baseline);
    var comparison = engine.compare(scenario, baseline);
    baselineBox.appendChild(
      text(
        "p",
        "Kept crash: " + percent(kept.probability) + " (" + percent(kept.low) + "–" +
          percent(kept.high) + ").",
        "calc-note"
      )
    );
    baselineBox.appendChild(
      text(
        "p",
        "This crash against the kept one: " + comparison.ratio.toFixed(2) + " times the share " +
          "(95% interval " + comparison.ratio_low.toFixed(2) + "–" +
          comparison.ratio_high.toFixed(2) + "), a difference of " + points(comparison.difference) +
          " (" + points(comparison.difference_low) + " to " + points(comparison.difference_high) +
          ").",
        "calc-compare"
      )
    );
    baselineBox.appendChild(text("p", "Kept crash: " + describe(baseline) + ".", "calc-kept"));
  }

  function start(exported) {
    model = exported;
    engine = window.SeverityEngine.create(model);
    root.hidden = false;
    var fallback = document.getElementById("calculator-fallback");
    if (fallback) fallback.hidden = true;
    form.addEventListener("change", render);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      render();
    });
    keep.addEventListener("click", function () {
      baseline = scenarioFromForm();
      render();
      status.textContent = "Crash kept for comparison.";
    });
    clear.addEventListener("click", function () {
      baseline = null;
      render();
      status.textContent = "Comparison cleared.";
      keep.focus();
    });
    form.addEventListener("reset", function () {
      window.setTimeout(render, 0);
    });
    render();
  }

  fetch(root.getAttribute("data-model"))
    .then(function (response) {
      if (!response.ok) throw new Error("model not found");
      return response.json();
    })
    .then(start)
    .catch(function () {
      var fallback = document.getElementById("calculator-fallback");
      if (fallback) {
        fallback.hidden = false;
        fallback.textContent =
          "The calculator could not load its model. The worked examples below give its estimates " +
          "for typical crashes.";
      }
    });
})();
