/*
 * The crash-severity calculator's page. The reader describes what happened, where and in what
 * conditions; SeverityBuilder.crash turns the description into the model's inputs (crash type,
 * kinds of road user, number involved), SeverityBuilder.settle keeps the conditions possible, and
 * the engine (severity-engine.js) gives the estimated share of fatal crashes, its interval and
 * the comparison of two scenarios. Every number comes from the exported model
 * (models/severity_model.json); this file only moves values between the form and the engine.
 * Under Node, require() returns SeverityBuilder alone (tests/test_severity_engine.py).
 * Without scripting the form stays hidden and the fallback line remains.
 */
(function (global) {
  "use strict";

  // ------------------------------------------------------------------ the crash description
  // A description is {what, type, vehicle, second, count, another}, the values of the selects
  // shown for that kind of crash (tool_calculator.GROUPS):
  //   collision   the type of collision is the crash type; two vehicles, then a third kind;
  //   pedestrian  "pedestrian_struck": a pedestrian and the vehicle, then another vehicle;
  //   single      what happened is the crash type; one vehicle, nobody else (one involved);
  //   other       "other": a vehicle, then another kind of road user (a pedestrian included).
  // "another" counts only where the number involved leaves room for a further kind.
  function takesAnother(choice) {
    if (choice.what === "collision" || choice.what === "pedestrian") {
      return choice.count === "3" || choice.count === "4+";
    }
    return choice.what === "other" && choice.count !== "1";
  }

  function crash(choice) {
    var users = [];
    function add(user) {
      if (user && users.indexOf(user) < 0) users.push(user);
    }
    var type;
    var units;
    if (choice.what === "collision") {
      type = choice.type;
      add(choice.vehicle);
      add(choice.second);
      units = choice.count;
    } else if (choice.what === "pedestrian") {
      type = "pedestrian_struck";
      add("pedestrian");
      add(choice.vehicle);
      units = choice.count;
    } else if (choice.what === "single") {
      type = choice.type;
      add(choice.vehicle);
      units = "1";
    } else if (choice.what === "other") {
      type = "other";
      add(choice.vehicle);
      units = choice.count;
    } else {
      throw new Error("unknown kind of crash: " + choice.what);
    }
    if (takesAnother(choice)) add(choice.another);
    return { crash_type: type, units: units, users: users };
  }

  // ------------------------------------------------------------------ the conditions
  // The surfaces and lightings the engine's conditions rules allow with the rest of the scenario,
  // and the changes a change of weather or time forces: heavy rain, hail or snow turns a dry
  // surface wet (the first surface left); a time that rules out the lighting chosen sets daylight
  // when only daylight remains, and otherwise leaves the lighting to the reader ("").
  function settle(engine, scenario) {
    var s = copy(scenario);
    function allowed(name, rule) {
      return engine.levels(name).filter(function (value) {
        var candidate = copy(s);
        candidate[name] = value;
        return engine.check(candidate).errors.indexOf(rule) < 0;
      });
    }
    var changed = [];
    var surface = allowed("surface", "heavy_rain_on_dry_surface");
    if (surface.indexOf(s.surface) < 0) {
      s.surface = surface[0];
      changed.push("surface");
    }
    var lighting = allowed("lighting", "lighting_outside_hours");
    if (lighting.indexOf(s.lighting) < 0) {
      var daylight = lighting.every(function (value) { return engine.daylight.indexOf(value) >= 0; });
      s.lighting = daylight ? lighting[0] : "";
      if (daylight) changed.push("lighting");
    }
    return { scenario: s, surface: surface, lighting: lighting, changed: changed };
  }

  function copy(object) {
    var out = {};
    Object.keys(object).forEach(function (key) { out[key] = object[key]; });
    return out;
  }

  var builder = { crash: crash, takesAnother: takesAnother, settle: settle };
  if (typeof module === "object" && module.exports) {
    module.exports = builder;
    return;
  }
  global.SeverityBuilder = builder;

  // ------------------------------------------------------------------ the page
  var root = document.getElementById("calculator");
  var fallback = document.getElementById("calculator-fallback");
  var FAILED =
    "The calculator could not load. The severity model page gives its estimates for typical " +
    "crashes.";

  function fail() {
    if (root) root.hidden = true;
    if (fallback) {
      fallback.hidden = false;
      fallback.textContent = FAILED;
    }
  }

  if (!root) return;
  if (!global.SeverityEngine) {
    fail();
    return;
  }
  var form = root.querySelector("form");
  var output = root.querySelector("[data-output]");
  var baselineBox = root.querySelector("[data-baseline]");
  var derived = root.querySelector("[data-derived]");
  var adjusted = root.querySelector("[data-adjusted]");
  var save = root.querySelector("[data-save]");
  var clear = root.querySelector("[data-clear]");
  var status = root.querySelector("[data-status]");
  var sticky = root.querySelector("[data-sticky]");
  // The model's own inputs the reader sets directly; the crash type, the road users and the
  // number involved come from the description of the crash.
  var DIRECT = ["province", "road", "junction", "speed_limit", "hour", "lighting", "weather", "surface"];
  // The two conditions rules' own words (the exported model's list of rules predates them).
  var CONDITION_RULES = {
    heavy_rain_on_dry_surface: "Heavy rain, hail or snow does not leave a road dry and clean.",
    lighting_outside_hours: "This lighting does not occur at this time of day in Catalonia."
  };

  var engine = null;
  var model = null;
  var baseline = null; // scenario A, once saved
  var current = null; // the scenario on the form, while it has an estimate

  function pin(message) {
    if (sticky) sticky.textContent = message;
  }

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

  function ruleText(id, rare) {
    var found = model.rules.filter(function (r) { return r.id === id; })[0];
    if (!found) return CONDITION_RULES[id] || id;
    var words = found.text.replace("{threshold}", String(found.threshold || ""));
    if (id === "rare_level") {
      // One phrase per rare item: an input's value, or a kind of road user involved.
      // Inputs whose label does not read after "have this".
      var own = {
        junction: "have this position relative to a junction",
        units: "involve this number of vehicles and pedestrians",
      };
      var phrases = rare.map(function (name) {
        if (own[name]) return own[name];
        if (model.inputs[name]) return "have this " + model.inputs[name].label.toLowerCase();
        return "involve " + levelLabel("users", name).toLowerCase();
      });
      // Each item is counted on its own, so the threshold is repeated for every item after the
      // first: "have this type of crash, and fewer than 20 involve a bicycle".
      var more = phrases.slice(1).map(function (phrase) {
        return "fewer than " + String(found.threshold || "") + " " + phrase;
      });
      var joined = [phrases[0]].concat(more.slice(0, -1)).join(", ") +
        (more.length ? ", and " + more[more.length - 1] : "");
      words = words.replace("{input}", joined);
    }
    return words;
  }

  function levelLabel(name, value) {
    var level = model.inputs[name].levels.filter(function (l) { return l.value === value; })[0];
    return level ? level.label : value;
  }

  function lower(label) {
    return label.charAt(0).toLowerCase() + label.slice(1);
  }

  function listed(items) {
    if (items.length < 2) return items.join("");
    return items.slice(0, -1).join(", ") + " and " + items[items.length - 1];
  }

  function users(scenario) {
    return model.inputs.users.levels
      .filter(function (level) { return scenario[level.value]; })
      .map(function (level) { return lower(level.label); });
  }

  function shown(name, scenario) {
    var type = model.inputs[name].type;
    if (type === "flags") return listed(users(scenario)) || "none";
    // A province keeps its capital; every other label reads in lower case within a sentence.
    if (type === "place") return levelLabel(name, scenario[name]);
    return lower(levelLabel(name, scenario[name]));
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

  // An observed share with its count and 95% interval, e.g. "16 of 103, 95% interval …%".
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

  // ------------------------------------------------------------------ form to scenario
  function readChoice() {
    var choice = { what: form.elements.what.value };
    var group = form.querySelector('[data-group="' + choice.what + '"]');
    Array.prototype.forEach.call(group.querySelectorAll("select[data-field]"), function (select) {
      choice[select.getAttribute("data-field")] = select.value;
    });
    return choice;
  }

  // Show the selects of the kind of crash chosen, and the further kind of road user only where
  // the number involved leaves room for it.
  function showChoice(choice) {
    Array.prototype.forEach.call(form.querySelectorAll("[data-group]"), function (group) {
      group.hidden = group.getAttribute("data-group") !== choice.what;
    });
    var another = form.querySelector('[data-group="' + choice.what + '"] [data-another]');
    if (another) another.hidden = !builder.takesAnother(choice);
  }

  function scenarioFromForm(choice) {
    var described = builder.crash(choice);
    var scenario = { crash_type: described.crash_type, units: described.units };
    DIRECT.forEach(function (name) { scenario[name] = form.elements[name].value; });
    model.inputs.users.levels.forEach(function (level) {
      scenario[level.value] = described.users.indexOf(level.value) >= 0;
    });
    return scenario;
  }

  function offer(select, allowed) {
    Array.prototype.forEach.call(select.options, function (option) {
      if (option.value !== "") option.disabled = allowed.indexOf(option.value) < 0;
    });
  }

  // Apply the conditions rules to the form: disable what they rule out, make the changes they
  // force, and say why in one line.
  function applyConditions(scenario) {
    var settled = builder.settle(engine, scenario);
    var s = settled.scenario;
    offer(form.elements.surface, settled.surface);
    offer(form.elements.lighting, settled.lighting);
    form.elements.surface.value = s.surface;
    if (s.lighting === "") form.elements.lighting.options[0].selected = true;
    else form.elements.lighting.value = s.lighting;
    var notes = [];
    if (settled.changed.indexOf("surface") >= 0) {
      notes.push(
        "Heavy rain, hail or snow leaves no road dry and clean: road surface set to " +
          lower(levelLabel("surface", s.surface)) + "."
      );
    }
    if (settled.changed.indexOf("lighting") >= 0) {
      notes.push(
        "At " + levelLabel("hour", s.hour) + " it is daylight all year: lighting set to " +
          lower(levelLabel("lighting", s.lighting)) + "."
      );
    }
    adjusted.textContent = notes.join(" ");
    adjusted.hidden = !notes.length;
    return { scenario: s, notes: notes };
  }

  // ------------------------------------------------------------------ result
  function render(prefix) {
    var choice = readChoice();
    showChoice(choice);
    var settled = applyConditions(scenarioFromForm(choice));
    var scenario = settled.scenario;
    var lead = [prefix].concat(settled.notes).filter(Boolean).join(" ");
    lead = lead ? lead + " " : "";
    derived.textContent = "In the model: " + shown("crash_type", scenario) + "; road users: " +
      shown("users", scenario) + "; number involved: " + shown("units", scenario) + ".";
    output.textContent = "";
    current = null;
    save.disabled = true;
    if (scenario.lighting === "") {
      var choose = "Choose the lighting to see the estimate.";
      output.setAttribute("data-state", "pending");
      output.appendChild(text("p", choose, "calc-pending"));
      noComparison("No comparison until scenario B has an estimate.", scenario);
      pin(choose);
      announce(lead + choose);
      return;
    }
    var checked = engine.check(scenario);
    if (checked.errors.length) {
      // The form offers no such combination; a scenario from elsewhere is refused in words.
      output.setAttribute("data-state", "error");
      output.appendChild(text("p", "No estimate for this combination:", "calc-error-title"));
      var list = document.createElement("ul");
      checked.errors.forEach(function (id) { list.appendChild(text("li", ruleText(id))); });
      output.appendChild(list);
      noComparison("No comparison until scenario B has an estimate.", scenario);
      pin("No estimate for this combination: see below.");
      announce(lead + "No estimate: " + checked.errors.map(function (id) { return ruleText(id); }).join(" "));
      return;
    }
    var zone = engine.zoneOf(scenario.road);
    var averages = model.zone_average;
    var local = averages[zone + "|" + scenario.province];
    var place = zoneLabel(zone) + " in the province of " + levelLabel("province", scenario.province);
    if (checked.warnings.indexOf("through_town") >= 0) {
      // The model cannot rank crashes on these roads: show what was observed on them instead.
      output.setAttribute("data-state", "average");
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
      pin("Roads through towns: " + percent(local) + " fatal on average (see below).");
      announce(lead + "Roads through towns: " + percent(local) + " were fatal on average.");
      return;
    }
    current = scenario;
    save.disabled = false;
    output.setAttribute("data-state", "ok");
    var result = engine.predict(scenario);
    output.appendChild(text("p", percent(result.probability), "calc-value"));
    output.appendChild(
      text("p", "95% confidence interval: " + range(result.low, result.high), "calc-interval")
    );
    output.appendChild(
      text(
        "p",
        "Estimated share fatal (a death within 24 hours) among crashes like this one with a " +
          "death or serious injury in Catalonia: a share of crashes already recorded, not the " +
          "chance of a crash or of a death on a journey.",
        "calc-label"
      )
    );
    output.appendChild(
      text(
        "p",
        // Averages over the fitted crashes, which leave out the conventional roads whose owning
        // network is not named (the notes below the calculator say so).
        "For comparison, " + percent(averages.all) + " of the crashes the model was fitted on " +
          "were fatal, and " + percent(local) + " of those on " + place + " (" +
          counted(zone + "|" + scenario.province) + ").",
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
    var comparison = renderComparison(scenario);
    var warned = !warnings.length
      ? ""
      : warnings.length === 1
        ? "with a warning"
        : "with " + warnings.length + " warnings";
    // With scenario A saved, the line also gives the difference, which otherwise changes out of
    // view.
    pin(
      "Estimate " + percent(result.probability) + " fatal (" + range(result.low, result.high) +
        ")" + (warned ? ", " + warned : "") + (comparison ? "; " + comparison : "") +
        ": details below."
    );
    announce(
      lead + "Estimate " + percent(result.probability) + ", interval " + percent(result.low) +
        " to " + percent(result.high) + "." + (comparison ? " " + comparison + "." : "") +
        (warned ? " " + warned.charAt(0).toUpperCase() + warned.slice(1) + "." : "")
    );
  }

  // ------------------------------------------------------------------ scenarios A and B
  // Scenario A named by the inputs in which it differs from the form (scenario B).
  function describeA(scenario) {
    var parts = [];
    Object.keys(model.inputs).forEach(function (name) {
      var a = shown(name, baseline);
      if (a !== shown(name, scenario)) parts.push(lower(model.inputs[name].label) + " (" + a + ")");
    });
    if (!parts.length) return "Scenario A has the same inputs as scenario B.";
    return "Scenario A differs from B in " + parts.join("; ") + ".";
  }

  function estimateOfA() {
    var a = engine.predict(baseline);
    return "Scenario A: " + percent(a.probability) + " (95% confidence interval " +
      range(a.low, a.high) + ").";
  }

  // The comparison area when scenario B has no estimate: scenario A alone, named by what differs.
  function noComparison(message, scenario) {
    baselineBox.textContent = "";
    clear.hidden = !baseline;
    if (!baseline) return;
    baselineBox.appendChild(text("p", estimateOfA(), "calc-compare"));
    baselineBox.appendChild(text("p", message, "calc-note"));
    baselineBox.appendChild(text("p", describeA(scenario), "calc-kept"));
  }

  function cell(tag, content) {
    return text(tag, content);
  }

  function row(head, value, interval) {
    var tr = document.createElement("tr");
    var th = cell("th", head);
    th.setAttribute("scope", "row");
    tr.appendChild(th);
    tr.appendChild(cell("td", value));
    tr.appendChild(cell("td", interval));
    return tr;
  }

  function renderComparison(scenario) {
    baselineBox.textContent = "";
    clear.hidden = !baseline;
    if (!baseline) {
      baselineBox.appendChild(
        text(
          "p",
          "To compare two crashes, save this one as scenario A, then change the form to " +
            "describe scenario B.",
          "calc-note"
        )
      );
      return "";
    }
    var a = engine.predict(baseline);
    var b = engine.predict(scenario);
    var c = engine.compare(scenario, baseline);
    var table = document.createElement("table");
    table.className = "calc-ab";
    var caption = text("caption", "Scenario A (saved) and scenario B (the form)");
    table.appendChild(caption);
    var head = document.createElement("tr");
    ["", "Estimate", "95% confidence interval"].forEach(function (label) {
      var th = cell("th", label);
      th.setAttribute("scope", "col");
      head.appendChild(th);
    });
    var thead = document.createElement("thead");
    thead.appendChild(head);
    table.appendChild(thead);
    var body = document.createElement("tbody");
    body.appendChild(row("Scenario A", percent(a.probability), range(a.low, a.high)));
    body.appendChild(row("Scenario B", percent(b.probability), range(b.low, b.high)));
    body.appendChild(
      row(
        "Difference, B − A",
        points(c.difference) + " points",
        points(c.difference_low) + " to " + points(c.difference_high)
      )
    );
    body.appendChild(
      row(
        "Ratio, B ÷ A",
        c.ratio.toFixed(2),
        c.ratio_low.toFixed(2) + "–" + c.ratio_high.toFixed(2)
      )
    );
    table.appendChild(body);
    baselineBox.appendChild(table);
    baselineBox.appendChild(text("p", describeA(scenario), "calc-kept"));
    baselineBox.appendChild(
      text(
        "p",
        "The difference is an association between recorded crashes like A and like B, not the " +
          "effect of changing a circumstance on a real road.",
        "calc-note"
      )
    );
    return "B − A " + points(c.difference) + " percentage points";
  }

  // ------------------------------------------------------------------ start
  function start(exported) {
    if (exported.model_id !== root.getAttribute("data-model-id")) {
      // The page and the model file come from different builds: compute nothing.
      fail();
      return;
    }
    model = exported;
    engine = global.SeverityEngine.create(model);
    root.hidden = false;
    if (fallback) fallback.hidden = true;
    // A link to #calculator arrives while the section is still hidden, so the browser's jump to
    // it finds nothing; jump once it is shown.
    if (window.location.hash === "#" + root.id) root.scrollIntoView();
    form.addEventListener("change", function () { render(""); });
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      render("");
    });
    save.addEventListener("click", function () {
      if (!current) return;
      baseline = current;
      render("Scenario A saved; the form now describes scenario B.");
    });
    clear.addEventListener("click", function () {
      baseline = null;
      render("Scenario A cleared.");
      save.focus();
    });
    form.addEventListener("reset", function () {
      window.setTimeout(function () { render("Inputs reset."); }, 0);
    });
    render("");
  }

  fetch(root.getAttribute("data-model") + "?v=" + encodeURIComponent(root.getAttribute("data-model-id")))
    .then(function (response) {
      if (!response.ok) throw new Error("model not found");
      return response.json();
    })
    .then(start)
    .catch(fail);
})(typeof self !== "undefined" ? self : this);
