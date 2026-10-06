/* What a speed law would do: the browser half of dgt_stats/simulator.py.
 *
 * A line-by-line port of the Python, reading the same parameters, which the page carries as a
 * JSON block built from the committed result tables and the evidence register. A test runs this
 * file under Node on every combination of the page's limits, with the response and compliance
 * across their range, and requires it to agree with the Python to one part in a million. Nothing
 * here is computed that the Python does not compute.
 */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.SpeedLaw = api;
    if (typeof document !== "undefined") {
      document.addEventListener("DOMContentLoaded", function () {
        api.attach(document);
      });
    }
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const OUTCOMES = ["deaths", "seriously_injured", "slightly_injured", "injury_crashes"];
  const VALUED = ["deaths", "seriously_injured", "slightly_injured"];
  const INTERURBAN = ["autopista", "autovia", "conventional"];
  const URBAN = ["urban_50", "urban_30"];
  const MINUS = "−";

  // ------------------------------------------------------------------ arithmetic

  // Standard normal distribution function: W. J. Cody's rational Chebyshev approximations, as in
  // R's pnorm, accurate to about one part in 10^15 wherever the simulator evaluates it.
  const CODY_A = [
    2.2352520354606839287, 161.02823106855587881, 1067.6894854603709582, 18154.981253343561249,
    0.065682337918207449113,
  ];
  const CODY_B = [
    47.20258190468824187, 976.09855173777669322, 10260.932208618978205, 45507.789335026729956,
  ];
  const CODY_C = [
    0.39894151208813466764, 8.8831497943883759412, 93.506656132177855979, 597.27027639480026226,
    2494.5375852903726711, 6848.1904505362823326, 11602.651437647350124, 9842.7148383839780218,
    1.0765576773720192317e-8,
  ];
  const CODY_D = [
    22.266688044328115691, 235.38790178262499861, 1519.377599407554805, 6485.558298266760755,
    18615.571640885098091, 34900.952721145977266, 38912.003286093271411, 19685.429676859990727,
  ];
  const CODY_P = [
    0.21589853405795699, 0.1274011611602473639, 0.022235277870649807, 0.001421619193227893466,
    2.9112874951168792e-5, 0.02307344176494017303,
  ];
  const CODY_Q = [
    1.28426009614491121, 0.468238212480865118, 0.0659881378689285515, 0.00378239633202758244,
    7.29751555083966205e-5,
  ];

  function normCdf(x) {
    const y = Math.abs(x);
    if (y <= 0.67448975) {
      const square = x * x;
      let num = CODY_A[4] * square;
      let den = square;
      for (let i = 0; i < 3; i++) {
        num = (num + CODY_A[i]) * square;
        den = (den + CODY_B[i]) * square;
      }
      return 0.5 + (x * (num + CODY_A[3])) / (den + CODY_B[3]);
    }
    let tail;
    if (y <= Math.sqrt(32)) {
      let num = CODY_C[8] * y;
      let den = y;
      for (let i = 0; i < 7; i++) {
        num = (num + CODY_C[i]) * y;
        den = (den + CODY_D[i]) * y;
      }
      tail = (num + CODY_C[7]) / (den + CODY_D[7]);
    } else if (y < 37.5193) {
      const inverse = 1 / (y * y);
      let num = CODY_P[5] * inverse;
      let den = inverse;
      for (let i = 0; i < 4; i++) {
        num = (num + CODY_P[i]) * inverse;
        den = (den + CODY_Q[i]) * inverse;
      }
      tail = (1 / Math.sqrt(2 * Math.PI) - (inverse * (num + CODY_P[4])) / (den + CODY_Q[4])) / y;
    } else {
      return x > 0 ? 1 : 0;
    }
    // exp(-y²/2) in two factors, so that the square loses no precision.
    const rounded = Math.trunc(y * 16) / 16;
    tail *= Math.exp((-rounded * rounded) / 2) * Math.exp((-(y - rounded) * (y + rounded)) / 2);
    return x > 0 ? 1 - tail : tail;
  }

  function typicalResponse(P, change) {
    const range = P.response.range;
    if (change < range[0] || change > range[1]) {
      throw new RangeError("limit change " + change + " is outside the evidence");
    }
    return P.response.a * change * change + P.response.b * change;
  }

  // A response share or a compliance: one number for every kind of road, a mapping by kind of road
  // (a kind left out takes the default), or nothing (the default).
  function forGroup(setting, group, fallback) {
    if (setting === null || setting === undefined) return fallback;
    if (typeof setting === "object") {
      const value = setting[group];
      return value === null || value === undefined ? fallback : Number(value);
    }
    return Number(setting);
  }

  // Expected speed above the limit per car, after scaling every speed by `scale`.
  function excess(site, limit, scale) {
    const mu = site.mu + Math.log(scale);
    const s = site.sigma;
    const above = normCdf((mu + s * s - Math.log(limit)) / s);
    const beyond = normCdf((mu - Math.log(limit)) / s);
    return Math.exp(mu + (s * s) / 2) * above - limit * beyond;
  }

  // Share of cars above the limit once `compliance` of them have slowed to it.
  function shareAbove(site, limit, scale, compliance) {
    const mu = site.mu + Math.log(scale);
    return (1 - compliance) * normCdf((mu - Math.log(limit)) / site.sigma);
  }

  // Standard deviation of speeds once `compliance` of the cars above the limit have slowed to it.
  function spread(site, limit, scale, compliance) {
    const mu = site.mu + Math.log(scale);
    const s = site.sigma;
    const logLimit = Math.log(limit);
    const beyond = normCdf((mu - logLimit) / s);
    let first = Math.exp(mu + (s * s) / 2);
    let second = Math.exp(2 * mu + 2 * s * s);
    const firstAbove = first * normCdf((mu + s * s - logLimit) / s);
    const secondAbove = second * normCdf((mu + 2 * s * s - logLimit) / s);
    first -= compliance * (firstAbove - limit * beyond);
    second -= compliance * (secondAbove - limit * limit * beyond);
    return Math.sqrt(second - first * first);
  }

  // How a law moves the speeds on one kind of road, one step at a time.
  function speedSteps(P, key, scenario) {
    const site = P.sites[key];
    const limits = scenario.limits || {};
    const limit = site.lever !== null && site.lever in limits ? Number(limits[site.lever]) : site.limit;
    const change = limit - site.limit;
    const share = forGroup(scenario.responseShare, site.group, null);
    const compliance = forGroup(scenario.compliance, site.group, 0);
    const shift = share === null ? typicalResponse(P, change) : share * change;
    const shifted = site.mean + shift;
    const scale = shifted / site.mean;
    const cut = compliance * excess(site, limit, scale);
    return {
      limit: site.limit,
      new_limit: limit,
      mean_speed: site.mean,
      response_share: change ? shift / change : NaN,
      compliance: compliance,
      limit_shift: shift,
      compliance_cut: -cut,
      new_mean_speed: shifted - cut,
      share_above_limit: shareAbove(site, site.limit, 1, 0),
      new_share_above_limit: shareAbove(site, limit, scale, compliance),
      share_above_new_limit_before_compliance: shareAbove(site, limit, scale, 0),
      speed_sd: spread(site, site.limit, 1, 0),
      new_speed_sd: spread(site, limit, scale, compliance),
    };
  }

  function newMeanSpeed(P, key, scenario) {
    return speedSteps(P, key, scenario).new_mean_speed;
  }

  // Ratio of each outcome after to before: [estimate, at the low exponent, at the high exponent].
  // The ends stay in exponent order so that totals use the same end on every road.
  function ratios(P, key, v1) {
    const site = P.sites[key];
    const out = {};
    for (const outcome of OUTCOMES) {
      const e = P.exponents[outcome + "|" + site.environment];
      out[outcome] = e.map((p) => Math.pow(v1 / site.mean, p));
    }
    return out;
  }

  // The displayed range of each quantity: its two exponent ends, sorted.
  function sortEnds(row) {
    for (const stem of OUTCOMES.map((o) => o + "_change").concat(["value_euros"])) {
      const a = row[stem + "_at_low_exponent"];
      const b = row[stem + "_at_high_exponent"];
      if (a === undefined) continue;
      row[stem + "_low"] = Math.min(a, b);
      row[stem + "_high"] = Math.max(a, b);
    }
  }

  function minimumDetectable(P, expected, tau) {
    const z = P.detect.zAlpha + P.detect.zPower;
    return 1 - Math.exp(-z * Math.sqrt(1 / expected + tau * tau));
  }

  // The rise detected four times in five, as a proportion of the expected count.
  function minimumDetectableRise(P, expected, tau) {
    const z = P.detect.zAlpha + P.detect.zPower;
    return Math.expm1(z * Math.sqrt(1 / expected + tau * tau));
  }

  // Chance that the first year's count shows a change of `change` deaths in its own direction;
  // NaN for no change.
  function detectionPower(P, change, expected, tau) {
    if (Math.abs(change) < 0.5) return NaN;
    const sigma = Math.sqrt(1 / expected + tau * tau);
    const shift = Math.abs(Math.log1p(change / expected)) / sigma;
    return normCdf(shift - P.detect.zAlpha);
  }

  const SPEED_COLUMNS = [
    "limit",
    "new_limit",
    "response_share",
    "compliance",
    "limit_shift",
    "compliance_cut",
    "share_above_limit",
    "new_share_above_limit",
    "share_above_new_limit_before_compliance",
    "speed_sd",
    "new_speed_sd",
  ];

  function simulate(P, scenario) {
    const interurban = INTERURBAN.map(function (key) {
      const site = P.sites[key];
      const steps = speedSteps(P, key, scenario);
      const v1 = steps.new_mean_speed;
      const r = ratios(P, key, v1);
      const row = { road_class: key, mean_speed: site.mean, new_mean_speed: v1 };
      for (const column of SPEED_COLUMNS) row[column] = steps[column];
      const values = [0, 0, 0];
      for (const outcome of OUTCOMES) {
        const before = P.baseline[key][outcome];
        const changes = r[outcome].map((ratio) => before * (ratio - 1));
        row[outcome + "_before"] = before;
        row[outcome + "_change"] = changes[0];
        row[outcome + "_change_at_low_exponent"] = changes[1];
        row[outcome + "_change_at_high_exponent"] = changes[2];
        if (VALUED.indexOf(outcome) >= 0) {
          for (let i = 0; i < 3; i++) values[i] -= changes[i] * P.values[outcome];
        }
      }
      row.value_euros = values[0];
      row.value_euros_at_low_exponent = values[1];
      row.value_euros_at_high_exponent = values[2];
      sortEnds(row);
      row.vehicle_hours_change = P.vehicleKm[key] * (1 / v1 - 1 / site.mean);
      return row;
    });
    const total = {};
    const summed = [
      "vehicle_hours_change",
      "value_euros",
      "value_euros_at_low_exponent",
      "value_euros_at_high_exponent",
    ];
    for (const outcome of OUTCOMES) {
      for (const suffix of ["_before", "_change", "_change_at_low_exponent", "_change_at_high_exponent"]) {
        summed.push(outcome + suffix);
      }
    }
    for (const row of interurban) {
      for (const name of summed) total[name] = (total[name] || 0) + row[name];
    }
    sortEnds(total);
    const tau = P.detect.tauInterurban;
    total.mde_deaths = minimumDetectable(P, total.deaths_before, tau) * total.deaths_before;
    total.mde_rise_deaths = minimumDetectableRise(P, total.deaths_before, tau) * total.deaths_before;
    total.power_in_one_year = detectionPower(P, total.deaths_change, total.deaths_before, tau);
    const urban = URBAN.map(function (key) {
      const steps = speedSteps(P, key, scenario);
      const v1 = steps.new_mean_speed;
      const r = ratios(P, key, v1);
      const row = { site: key, mean_speed: P.sites[key].mean, new_mean_speed: v1 };
      for (const column of SPEED_COLUMNS) row[column] = steps[column];
      for (const outcome of OUTCOMES) {
        row[outcome + "_change"] = r[outcome][0] - 1;
        row[outcome + "_change_at_low_exponent"] = r[outcome][1] - 1;
        row[outcome + "_change_at_high_exponent"] = r[outcome][2] - 1;
      }
      sortEnds(row);
      return row;
    });
    return { interurban: interurban, total: total, urban: urban };
  }

  // ------------------------------------------------------------------ the page

  function fixed(value, digits) {
    return Math.abs(value).toLocaleString("en-GB", {
      maximumFractionDigits: digits,
      minimumFractionDigits: digits,
    });
  }

  function signed(value, digits) {
    const text = fixed(value, digits);
    if (Number(text.replace(/,/g, "")) === 0) return "0";
    return (value < 0 ? MINUS : "+") + text;
  }

  function range(low, high, digits) {
    return signed(low, digits) + " to " + signed(high, digits);
  }

  function percent(value) {
    return signed(value * 100, 0) + "%";
  }

  // A share in whole per cent; the nudge rounds a computed 37.4999…% the way its exact value
  // (37.5%) is printed elsewhere on the page.
  function share(value) {
    return fixed(value * 100 + 1e-9, 0) + "%";
  }

  function euros(value) {
    return signed(value / 1e6, 0) + " million";
  }

  function kmh(value) {
    return fixed(value, 1);
  }

  // "a → b" when a law moves a quantity, "a" when it does not.
  function moved(before, after, format) {
    const a = format(before);
    const b = format(after);
    return a === b ? a : a + " → " + b;
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function groupSites(P, group) {
    return P.groups[group].sites;
  }

  function chosenLimit(form, lever) {
    const checked = form.querySelector('input[name="limit-' + lever + '"]:checked');
    return Number(checked.value);
  }

  function typicalShare(P, change) {
    return change ? typicalResponse(P, change) / change : 0;
  }

  function readScenario(form, P) {
    const limits = {};
    const responseShare = {};
    const compliance = {};
    for (const group of Object.keys(P.groups)) {
      if (group in P.levers) limits[group] = chosenLimit(form, group);
      const typical = form.querySelector('input[name="response-' + group + '"][value="typical"]');
      const slider = form.querySelector("#response-" + group);
      responseShare[group] = !typical || typical.checked ? null : Number(slider.value) / 100;
      compliance[group] = Number(form.querySelector("#compliance-" + group).value) / 100;
    }
    return { limits: limits, responseShare: responseShare, compliance: compliance };
  }

  function setScenario(form, P, scenario) {
    for (const group of Object.keys(P.groups)) {
      if (group in P.levers) {
        const lever = P.levers[group];
        const wanted = String(group in scenario.limits ? scenario.limits[group] : lever.limit);
        for (const radio of form.querySelectorAll('input[name="limit-' + group + '"]')) {
          radio.checked = radio.value === wanted;
        }
      }
      const share = forGroup(scenario.responseShare, group, null);
      const typical = form.querySelector('input[name="response-' + group + '"][value="typical"]');
      const set = form.querySelector('input[name="response-' + group + '"][value="set"]');
      if (typical) {
        typical.checked = share === null;
        set.checked = share !== null;
        if (share !== null) form.querySelector("#response-" + group).value = String(share * 100);
      }
      const compliance = forGroup(scenario.compliance, group, 0);
      form.querySelector("#compliance-" + group).value = String(compliance * 100);
    }
  }

  function put(scope, name, text) {
    for (const cell of scope.querySelectorAll('[data-out="' + name + '"]')) cell.textContent = text;
  }

  function putHtml(scope, name, html) {
    for (const cell of scope.querySelectorAll('[data-out="' + name + '"]')) cell.innerHTML = html;
  }

  // Bring the controls of each kind of road in line with what is chosen: say whether the limit is
  // new, show how drivers respond only when it is, and hold the typical share on its slider.
  function syncControls(doc, P, form) {
    for (const group of Object.keys(P.groups)) {
      const box = form.querySelector('[data-group="' + group + '"]');
      const sites = groupSites(P, group);
      const lever = P.levers[group];
      const current = lever ? lever.limit : P.sites[sites[0]].limit;
      const limit = lever ? chosenLimit(form, group) : current;
      const change = limit - current;
      box.dataset.state = change ? "changed" : "unchanged";
      if (lever) {
        put(
          box,
          "state-" + group,
          change
            ? "New limit: " + limit + " km/h, " + signed(change, 0) + " km/h on today's " + current + "."
            : "No new limit: " + current + " km/h stays."
        );
      }
      const response = box.querySelector('[data-response="' + group + '"]');
      if (response) {
        response.hidden = !change;
        const slider = form.querySelector("#response-" + group);
        const typical = form.querySelector('input[name="response-' + group + '"][value="typical"]');
        const usual = typicalShare(P, change);
        if (change && typical.checked) slider.value = String(Math.round(usual * 100));
        const chosen = typical.checked ? usual : Number(slider.value) / 100;
        put(box, "response-" + group, share(chosen) + (typical.checked ? " (typical)" : " (your setting)"));
        if (change) {
          const usualText =
            share(usual) + " of a " + signed(change, 0) + " km/h change reaches the average speed (" +
            signed(usual * change, 1) + " km/h)";
          put(
            box,
            "response-hint-" + group,
            typical.checked
              ? "Typically " + usualText + ", from 143 before-and-after results of limit changes."
              : "Your setting moves the average by " + signed(chosen * change, 1) +
                " km/h. Typically " + usualText + "."
          );
        }
      }
      const compliance = Number(form.querySelector("#compliance-" + group).value) / 100;
      put(box, "compliance-" + group, share(compliance));
      const scenario = readScenario(form, P);
      const above = sites
        .map((key) => P.sites[key].short + " " + share(speedSteps(P, key, scenario).share_above_new_limit_before_compliance))
        .join(", ");
      const limits = sites.map((key) => (lever && lever.sites.indexOf(key) >= 0 ? limit : P.sites[key].limit));
      const sameLimit = limits.every((value) => value === limits[0]);
      const limitText = sameLimit ? limits[0] + " km/h" : "the limit";
      put(
        box,
        "compliance-hint-" + group,
        "Cars above " + limitText + (change ? " once drivers have responded to the new limit" : " today") +
          ": " + above + ". At 0% they stay there; at 100% no car is above " + limitText + "."
      );
    }
  }

  function explain(P, result, scenario) {
    const items = [];
    const rows = result.interurban.concat(result.urban);
    for (const row of rows) {
      const key = row.road_class || row.site;
      const site = P.sites[key];
      if (Math.abs(row.new_mean_speed - row.mean_speed) < 0.05) continue;
      const parts = [];
      if (row.new_limit !== row.limit) {
        parts.push(
          "the " + row.new_limit + " km/h limit moves the average by " + signed(row.limit_shift, 1) +
            " km/h (" + share(row.response_share) + " of the " + signed(row.new_limit - row.limit, 0) + ")"
        );
      }
      if (row.compliance > 0) {
        parts.push(
          share(row.compliance) + " of the drivers above " + row.new_limit + " km/h slowing to it take off " +
            fixed(row.compliance_cut, 1) + " km/h"
        );
      }
      const speedChange = row.new_mean_speed / row.mean_speed - 1;
      let text =
        "<strong>" + escapeHtml(site.short) + "</strong>: " + parts.join("; ") + ". The average goes from " +
        kmh(row.mean_speed) + " to " + kmh(row.new_mean_speed) + " km/h (" + percent(speedChange) +
        "), and the Power Model turns that into " + percent(row.road_class ? row.deaths_change / row.deaths_before : row.deaths_change) +
        " deaths";
      text += row.road_class ? " (" + signed(row.deaths_change, 0) + " a year)." : " on these streets.";
      items.push("<li>" + text + "</li>");
    }
    return items.length ? '<ul class="why">' + items.join("") + "</ul>" : "";
  }

  function verdictText(result) {
    const t = result.total;
    const moved = result.interurban.some((row) => Math.abs(row.deaths_change) >= 0.5);
    const urbanMoved = result.urban.some((row) => Math.abs(row.deaths_change) > 1e-9);
    if (!moved && !urbanMoved) return "Nothing changes, so there is nothing to detect.";
    if (!moved) {
      return (
        "Only urban streets change. DGT does not publish deaths by the limit of the street, so " +
        "there is no count to watch: the effect would have to be checked by measuring speeds."
      );
    }
    if (Number.isNaN(t.power_in_one_year)) {
      return (
        "The changes on the three kinds of road cancel out to less than one death a year in all, " +
        "which no count could show."
      );
    }
    const power = t.power_in_one_year;
    const fall = t.deaths_change < 0;
    const threshold = fall ? t.mde_deaths : t.mde_rise_deaths;
    const rises = result.interurban.some((row) => row.deaths_change >= 0.5);
    const falls = result.interurban.some((row) => row.deaths_change <= -0.5);
    let verdict = rises && falls ? "Rises on some roads offset falls on others. " : "";
    verdict +=
      "Would the first year's death count show it? " +
      (power >= 0.99
        ? "Almost certainly"
        : "With a chance of about " + Math.round(power * 100) + "%") +
      ": the forecasting model's error means a " + (fall ? "fall" : "rise") + " of " +
      Math.round(threshold) + " deaths a year is picked up four times in five. ";
    if (power >= 0.8) {
      verdict += "The count would most likely show it on its own.";
    } else if (power >= 0.5) {
      verdict +=
        "More often than not it would, but a year that did not would not " +
        (fall ? "mean the law had failed." : "mean the law was harmless.");
    } else {
      verdict +=
        "More often than not it would be lost in ordinary variation: it would have to be checked by " +
        "measuring speeds.";
    }
    return verdict;
  }

  function render(doc, P, form) {
    syncControls(doc, P, form);
    const scenario = readScenario(form, P);
    const result = simulate(P, scenario);
    const t = result.total;
    for (const row of result.interurban.concat(result.urban)) {
      const key = row.road_class || row.site;
      const scope = doc.querySelector('[data-speeds="' + key + '"]');
      put(scope, "limit", moved(row.limit, row.new_limit, (v) => String(v)));
      put(scope, "speed", moved(row.mean_speed, row.new_mean_speed, kmh));
      put(scope, "limit-shift", signed(row.limit_shift, 1));
      put(scope, "compliance-cut", signed(row.compliance_cut, 1));
      put(scope, "above", moved(row.share_above_limit, row.new_share_above_limit, share));
      put(scope, "spread", moved(row.speed_sd, row.new_speed_sd, kmh));
    }
    for (const row of result.interurban) {
      const scope = doc.querySelector('[data-class="' + row.road_class + '"]');
      put(scope, "deaths", signed(row.deaths_change, 0));
      put(scope, "deaths-range", range(row.deaths_change_low, row.deaths_change_high, 0));
      put(scope, "crashes", signed(row.injury_crashes_change, 0));
      put(scope, "serious", signed(row.seriously_injured_change, 0));
      put(scope, "slight", signed(row.slightly_injured_change, 0));
      put(scope, "value", euros(row.value_euros));
      put(scope, "hours", signed(row.vehicle_hours_change / 1e6, 1) + " million");
    }
    const totals = doc.querySelector('[data-class="total"]');
    put(totals, "deaths", signed(t.deaths_change, 0));
    put(totals, "deaths-range", range(t.deaths_change_low, t.deaths_change_high, 0));
    put(totals, "crashes", signed(t.injury_crashes_change, 0));
    put(totals, "serious", signed(t.seriously_injured_change, 0));
    put(totals, "slight", signed(t.slightly_injured_change, 0));
    put(totals, "value", euros(t.value_euros));
    put(totals, "hours", signed(t.vehicle_hours_change / 1e6, 1) + " million");
    for (const row of result.urban) {
      const scope = doc.querySelector('[data-site-row="' + row.site + '"]');
      put(scope, "deaths", percent(row.deaths_change));
      put(scope, "deaths-range", percent(row.deaths_change_low) + " to " + percent(row.deaths_change_high));
      put(scope, "serious", percent(row.seriously_injured_change));
      put(scope, "crashes", percent(row.injury_crashes_change));
    }
    put(doc, "headline-deaths", signed(t.deaths_change, 0));
    put(doc, "headline-range", range(t.deaths_change_low, t.deaths_change_high, 0));
    put(doc, "headline-crashes", signed(t.injury_crashes_change, 0));
    put(doc, "headline-serious", signed(t.seriously_injured_change, 0));
    put(
      doc,
      "headline-value",
      "€" + fixed(t.value_euros / 1e6, 0) + " million a year " + (t.value_euros >= 0 ? "saved" : "lost")
    );
    put(doc, "headline-hours", signed(t.vehicle_hours_change / 1e6, 1) + " million");
    putHtml(doc, "why", explain(P, result, scenario));
    put(doc, "verdict", verdictText(result));
  }

  function attach(doc) {
    const data = doc.getElementById("simulator-parameters");
    const form = doc.getElementById("simulator");
    if (!data || !form) return;
    const P = JSON.parse(data.textContent);
    doc.getElementById("simulator-panel").hidden = false;
    form.addEventListener("input", function () {
      render(doc, P, form);
    });
    form.addEventListener("change", function () {
      render(doc, P, form);
    });
    for (const group of Object.keys(P.groups)) {
      const slider = form.querySelector("#response-" + group);
      if (!slider) continue;
      slider.addEventListener("input", function () {
        form.querySelector('input[name="response-' + group + '"][value="set"]').checked = true;
      });
    }
    for (const button of doc.querySelectorAll("button[data-preset]")) {
      button.addEventListener("click", function () {
        const preset = P.presets.find((p) => p.key === button.dataset.preset);
        setScenario(form, P, preset);
        for (const other of doc.querySelectorAll("button[data-preset]")) {
          other.setAttribute("aria-pressed", String(other === button));
        }
        render(doc, P, form);
      });
    }
    // A preset stays marked only until the reader changes something.
    form.addEventListener("input", function () {
      for (const other of doc.querySelectorAll("button[data-preset]")) {
        other.setAttribute("aria-pressed", "false");
      }
    });
    render(doc, P, form);
  }

  return {
    normCdf: normCdf,
    typicalResponse: typicalResponse,
    excess: excess,
    newMeanSpeed: newMeanSpeed,
    speedSteps: speedSteps,
    spread: spread,
    shareAbove: shareAbove,
    ratios: ratios,
    minimumDetectable: minimumDetectable,
    minimumDetectableRise: minimumDetectableRise,
    detectionPower: detectionPower,
    simulate: simulate,
    attach: attach,
  };
});
