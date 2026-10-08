/*
 * The crash-severity calculator's page: reads the form, asks the engine (severity-engine.js)
 * for the estimated share of fatal crashes and its interval, and compares the crash with a
 * second one the reader keeps. Every number comes from the exported model
 * (models/severity_model.json); this file only moves values between the form and the engine.
 * Without scripting the form stays hidden and the page's worked examples remain.
 */
(function () {
  "use strict";

  var root = document.getElementById("calculator");
  var fallback = document.getElementById("calculator-fallback");
  var FAILED =
    "The calculator could not load. The worked examples on this page give the model's " +
    "estimates for typical crashes.";

  function fail() {
    if (root) root.hidden = true;
    if (fallback) {
      fallback.hidden = false;
      fallback.textContent = FAILED;
    }
  }

  if (!root) return;
  if (!window.SeverityEngine) {
    fail();
    return;
  }
  var form = root.querySelector("form");
  var output = root.querySelector("[data-output]");
  var baselineBox = root.querySelector("[data-baseline]");
  var keep = root.querySelector("[data-keep]");
  var clear = root.querySelector("[data-clear]");
  var status = root.querySelector("[data-status]");
  var engine = null;
  var model = null;
  var baseline = null;

  function percent(value) {
    return (100 * value).toFixed(1) + "%";
  }

  // An interval with the unit once, as on the rest of the site: "low–high%".
  function range(low, high) {
    return (100 * low).toFixed(1) + "–" + percent(high);
  }

  function points(value) {
    var shown = (100 * value).toFixed(1);
    if (Number(shown) === 0) shown = (0).toFixed(1);
    return (value > 0 ? "+" : "") + shown.replace("-", "−");
  }

  function text(tag, content, className) {
    var node = document.createElement(tag);
    node.textContent = content;
    if (className) node.className = className;
    return node;
  }

  function announce(message) {
    // Clear first so that an identical message is announced again.
    status.textContent = "";
    window.setTimeout(function () { status.textContent = message; }, 50);
  }

  function rule(id) {
    return model.rules.filter(function (r) { return r.id === id; })[0];
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

  function levelLabel(name, value) {
    var level = model.inputs[name].levels.filter(function (l) { return l.value === value; })[0];
    return level ? level.label : value;
  }

  function shown(name, scenario) {
    var input = model.inputs[name];
    if (input.type === "flags") {
      var ticked = input.levels.filter(function (level) { return scenario[level.value]; });
      return ticked.map(function (l) { return l.label; }).join(", ") || "none";
    }
    return levelLabel(name, scenario[name]);
  }

  // The kept crash, named by the inputs in which it differs from the crash on the form, so that
  // the comparison stays short beside the form and says what to change back.
  function describeKept(scenario) {
    var parts = [];
    Object.keys(model.inputs).forEach(function (name) {
      var kept = shown(name, baseline);
      if (kept !== shown(name, scenario)) {
        parts.push(model.inputs[name].label.toLowerCase() + " (" + kept + ")");
      }
    });
    if (!parts.length) return "The kept crash has the same inputs as this one.";
    return "The kept crash differs from this one in " + parts.join("; ") + ".";
  }

  function ruleText(id, rare) {
    var found = rule(id);
    if (!found) return id;
    var words = found.text.replace("{threshold}", String(found.threshold || ""));
    if (id === "rare_level") {
      var labels = rare.map(function (name) {
        if (model.inputs[name]) return model.inputs[name].label.toLowerCase();
        return levelLabel("users", name).toLowerCase();
      });
      words = words.replace("{input}", labels.join(", "));
    }
    return words;
  }

  function zoneLabel(zone) {
    return { urban: "urban streets", through_town: "roads through towns", interurban: "interurban roads" }[zone];
  }

  function count(value) {
    return Number(value).toLocaleString("en");
  }

  function years() {
    return model.training.years[0] + "–" + model.training.years[1];
  }

  // An observed share with its count and 95% interval: "16 of 103, 95% interval 9.8–23.8%".
  function observed(key) {
    var counts = model.zone_counts[key];
    return count(counts[1]) + " of " + count(counts[0]) + ", 95% interval " +
      range(counts[2], counts[3]);
  }

  // An observed share's count alone: "1,234 of 6,140".
  function counted(key) {
    var counts = model.zone_counts[key];
    return count(counts[1]) + " of " + count(counts[0]);
  }

  // The comparison area when the current crash has no estimate: no numbers, but the kept crash
  // is still named so that the reader can return to a valid crash or clear it.
  function noComparison(message, scenario) {
    baselineBox.textContent = "";
    if (!baseline) {
      clear.hidden = true;
      return;
    }
    clear.hidden = false;
    baselineBox.appendChild(text("p", message, "calc-note"));
    baselineBox.appendChild(text("p", describeKept(scenario), "calc-kept"));
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
      noComparison("No comparison until this crash has an estimate.", scenario);
      announce("No estimate: " + checked.errors.map(function (id) { return ruleText(id); }).join(" "));
      return;
    }
    var zone = engine.zoneOf(scenario.road);
    var averages = model.zone_average;
    var local = averages[zone + "|" + scenario.province];
    var place = zoneLabel(zone) + " in the province of " + levelLabel("province", scenario.province);
    if (checked.warnings.indexOf("through_town") >= 0) {
      // The model cannot rank crashes on these roads: show what was observed on them instead.
      output.setAttribute("data-state", "average");
      keep.disabled = true;
      output.appendChild(text("p", percent(local), "calc-value"));
      output.appendChild(
        text(
          "p",
          "of crashes with a death or serious injury on " + place + " in " + years() +
            " were fatal (" + observed(zone + "|" + scenario.province) + "). " +
            ruleText("through_town"),
          "calc-label"
        )
      );
      noComparison("No comparison: roads through towns have no estimate of their own.", scenario);
      announce("Roads through towns: " + percent(local) + " were fatal on average.");
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
        "of crashes like this one with a death or serious injury in Catalonia are estimated to " +
          "have been fatal (someone died within 24 hours): a share of crashes already recorded, " +
          "not the chance of a crash or of a death on a journey. 95% confidence interval: " +
          range(result.low, result.high) + ".",
        "calc-label"
      )
    );
    output.appendChild(
      text(
        "p",
        "The interval covers only the uncertainty in the model's coefficients, not the " +
          "differences between places and years described on this page.",
        "calc-note"
      )
    );
    output.appendChild(
      text(
        "p",
        // Averages over the fitted crashes, which leave out the conventional roads whose owning
        // network is not named (the page says so beside the calculator).
        "For comparison, " + percent(averages.all) + " of the crashes the model was fitted on " +
          "were fatal, and " + percent(local) + " of those on " + place + " (" +
          counted(zone + "|" + scenario.province) + ").",
        "calc-note"
      )
    );
    output.appendChild(
      text(
        "p",
        count(similar.crashes) + " recorded crashes in " + years() +
          " share this zone, crash type, road users and number involved" +
          (similar.crashes
            ? "; " + similar.fatal.toLocaleString("en") + " of them were fatal. Their other " +
              "inputs differ, so their share need not match the estimate."
            : "."),
        "calc-note"
      )
    );
    var warnings = checked.warnings.filter(function (id) { return id !== "through_town"; });
    if (warnings.length) {
      var list2 = document.createElement("ul");
      list2.className = "calc-warnings";
      warnings.forEach(function (id) {
        list2.appendChild(text("li", ruleText(id, checked.rare)));
      });
      output.appendChild(list2);
    }
    var comparison = renderComparison(scenario, result);
    announce(
      "Estimate " + percent(result.probability) + ", interval " + percent(result.low) + " to " +
        percent(result.high) + "." + (comparison ? " " + comparison : "") +
        (warnings.length ? " With a warning." : "")
    );
  }

  function renderComparison(scenario, result) {
    baselineBox.textContent = "";
    if (!baseline) {
      clear.hidden = true;
      baselineBox.appendChild(
        text(
          "p",
          "To compare two crashes, press “Keep this crash for comparison”, then change an input.",
          "calc-note"
        )
      );
      return "";
    }
    clear.hidden = false;
    var kept = engine.predict(baseline);
    var comparison = engine.compare(scenario, baseline);
    var ratio = comparison.ratio.toFixed(2);
    baselineBox.appendChild(
      text(
        "p",
        "This crash against the kept one (" + percent(kept.probability) + ", " +
          range(kept.low, kept.high) + "): " + ratio + " times the share (95% confidence " +
          "interval " + comparison.ratio_low.toFixed(2) + "–" + comparison.ratio_high.toFixed(2) +
          "), a difference of " + points(comparison.difference) + " percentage points (" +
          points(comparison.difference_low) + " to " + points(comparison.difference_high) + ").",
        "calc-compare"
      )
    );
    baselineBox.appendChild(text("p", describeKept(scenario), "calc-kept"));
    baselineBox.appendChild(
      text(
        "p",
        "The difference is an association in police records, not the effect of changing that " +
          "circumstance on a real road.",
        "calc-note"
      )
    );
    return ratio + " times the kept crash.";
  }

  function start(exported) {
    if (exported.model_id !== root.getAttribute("data-model-id")) {
      // The page and the model file come from different builds: compute nothing.
      fail();
      return;
    }
    model = exported;
    engine = window.SeverityEngine.create(model);
    root.hidden = false;
    if (fallback) fallback.hidden = true;
    form.addEventListener("change", render);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      render();
    });
    keep.addEventListener("click", function () {
      baseline = scenarioFromForm();
      render();
      announce("Crash kept for comparison.");
    });
    clear.addEventListener("click", function () {
      baseline = null;
      render();
      announce("Comparison cleared.");
      keep.focus();
    });
    form.addEventListener("reset", function () {
      window.setTimeout(function () {
        render();
        announce("Inputs reset.");
      }, 0);
    });
    render();
  }

  fetch(root.getAttribute("data-model") + "?v=" + encodeURIComponent(root.getAttribute("data-model-id")))
    .then(function (response) {
      if (!response.ok) throw new Error("model not found");
      return response.json();
    })
    .then(start)
    .catch(fail);
})();
