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

  // Expected speed above the limit per car, after scaling every speed by `scale`.
  function excess(site, limit, scale) {
    const mu = site.mu + Math.log(scale);
    const s = site.sigma;
    const above = normCdf((mu + s * s - Math.log(limit)) / s);
    const beyond = normCdf((mu - Math.log(limit)) / s);
    return Math.exp(mu + (s * s) / 2) * above - limit * beyond;
  }

  function newMeanSpeed(P, key, scenario) {
    const site = P.sites[key];
    const limits = scenario.limits || {};
    const limit = site.lever !== null && site.lever in limits ? limits[site.lever] : site.limit;
    const change = limit - site.limit;
    const share = scenario.responseShare;
    const shift = share === null || share === undefined ? typicalResponse(P, change) : share * change;
    const shifted = site.mean + shift;
    return shifted - (scenario.compliance || 0) * excess(site, limit, shifted / site.mean);
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

  function simulate(P, scenario) {
    const interurban = INTERURBAN.map(function (key) {
      const site = P.sites[key];
      const v1 = newMeanSpeed(P, key, scenario);
      const r = ratios(P, key, v1);
      const row = { road_class: key, mean_speed: site.mean, new_mean_speed: v1 };
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
    for (const row of interurban) {
      for (const name in row) {
        if (typeof row[name] === "number") total[name] = (total[name] || 0) + row[name];
      }
    }
    sortEnds(total);
    const tau = P.detect.tauInterurban;
    total.mde_deaths = minimumDetectable(P, total.deaths_before, tau) * total.deaths_before;
    total.mde_rise_deaths = minimumDetectableRise(P, total.deaths_before, tau) * total.deaths_before;
    total.power_in_one_year = detectionPower(P, total.deaths_change, total.deaths_before, tau);
    const urban = URBAN.map(function (key) {
      const v1 = newMeanSpeed(P, key, scenario);
      const r = ratios(P, key, v1);
      const row = { site: key, mean_speed: P.sites[key].mean, new_mean_speed: v1 };
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

  function signed(value, digits) {
    const text = Math.abs(value).toLocaleString("en-GB", {
      maximumFractionDigits: digits,
      minimumFractionDigits: digits,
    });
    if (Number(text.replace(/,/g, "")) === 0) return "0";
    return (value < 0 ? MINUS : "+") + text;
  }

  function range(low, high, digits) {
    return signed(low, digits) + " to " + signed(high, digits);
  }

  function percent(value) {
    return signed(value * 100, 0) + "%";
  }

  function euros(value) {
    return signed(value / 1e6, 0) + " million";
  }

  function readScenario(form) {
    const limits = {};
    for (const select of form.querySelectorAll("select[data-lever]")) {
      limits[select.dataset.lever] = Number(select.value);
    }
    const typical = form.querySelector('input[name="response"][value="typical"]').checked;
    const share = Number(form.querySelector("#response-share").value) / 100;
    const compliance = Number(form.querySelector("#compliance").value) / 100;
    return { limits: limits, responseShare: typical ? null : share, compliance: compliance };
  }

  function setScenario(form, scenario) {
    for (const select of form.querySelectorAll("select[data-lever]")) {
      const key = select.dataset.lever;
      select.value = String(key in scenario.limits ? scenario.limits[key] : select.dataset.limit);
    }
    const typical = scenario.responseShare === null || scenario.responseShare === undefined;
    form.querySelector('input[name="response"][value="typical"]').checked = typical;
    form.querySelector('input[name="response"][value="set"]').checked = !typical;
    if (!typical) form.querySelector("#response-share").value = String(scenario.responseShare * 100);
    form.querySelector("#compliance").value = String((scenario.compliance || 0) * 100);
  }

  function put(scope, name, text) {
    for (const cell of scope.querySelectorAll('[data-out="' + name + '"]')) cell.textContent = text;
  }

  function render(doc, P, form) {
    const scenario = readScenario(form);
    put(doc, "response-share", form.querySelector("#response-share").value + "%");
    put(doc, "compliance", form.querySelector("#compliance").value + "%");
    const result = simulate(P, scenario);
    for (const row of result.interurban) {
      const scope = doc.querySelector('[data-class="' + row.road_class + '"]');
      put(scope, "speed", row.mean_speed.toFixed(1) + " → " + row.new_mean_speed.toFixed(1));
      put(scope, "deaths", signed(row.deaths_change, 0));
      put(scope, "deaths-range", range(row.deaths_change_low, row.deaths_change_high, 0));
      put(scope, "serious", signed(row.seriously_injured_change, 0));
      put(scope, "slight", signed(row.slightly_injured_change, 0));
      put(scope, "value", euros(row.value_euros));
      put(scope, "hours", signed(row.vehicle_hours_change / 1e6, 1) + " million");
    }
    const t = result.total;
    const totals = doc.querySelector('[data-class="total"]');
    put(totals, "deaths", signed(t.deaths_change, 0));
    put(totals, "deaths-range", range(t.deaths_change_low, t.deaths_change_high, 0));
    put(totals, "serious", signed(t.seriously_injured_change, 0));
    put(totals, "slight", signed(t.slightly_injured_change, 0));
    put(totals, "value", euros(t.value_euros));
    put(totals, "hours", signed(t.vehicle_hours_change / 1e6, 1) + " million");
    for (const row of result.urban) {
      const scope = doc.querySelector('[data-site-row="' + row.site + '"]');
      put(scope, "speed", row.mean_speed.toFixed(1) + " → " + row.new_mean_speed.toFixed(1));
      put(scope, "deaths", percent(row.deaths_change));
      put(scope, "deaths-range", percent(row.deaths_change_low) + " to " + percent(row.deaths_change_high));
      put(scope, "serious", percent(row.seriously_injured_change));
    }
    const moved = result.interurban.some((row) => Math.abs(row.deaths_change) >= 0.5);
    const urbanMoved = result.urban.some((row) => Math.abs(row.deaths_change) > 1e-9);
    let verdict;
    if (!moved && !urbanMoved) {
      verdict = "Nothing changes, so there is nothing to detect.";
    } else if (!moved) {
      const street = result.urban.find((row) => row.site === "urban_50");
      verdict =
        "Only urban streets change: deaths on the streets now at 50 km/h change by " +
        percent(street.deaths_change) + ". DGT does not publish deaths by the limit of the " +
        "street, so there is no count to watch: the effect would have to be checked by " +
        "measuring speeds.";
    } else if (Number.isNaN(t.power_in_one_year)) {
      verdict =
        "The changes on the three kinds of road cancel out to less than one death a year in " +
        "all, which no count could show.";
    } else {
      const power = t.power_in_one_year;
      const fall = t.deaths_change < 0;
      const threshold = fall ? t.mde_deaths : t.mde_rise_deaths;
      const rises = result.interurban.some((row) => row.deaths_change >= 0.5);
      const falls = result.interurban.some((row) => row.deaths_change <= -0.5);
      verdict = rises && falls ? "Rises on some roads offset falls on others. " : "";
      verdict +=
        "A change of " + signed(t.deaths_change, 0) +
        (Math.abs(Math.round(t.deaths_change)) === 1 ? " death" : " deaths") +
        " a year on autopistas, autovías and conventional roads would " +
        (power >= 0.99
          ? "almost certainly stand out from an ordinary year in the first year's count"
          : "stand out from an ordinary year in the first year's count with a chance of about " +
            Math.round(power * 100) + "%") +
        "; the count picks up a " + (fall ? "fall" : "rise") + " of " + Math.round(threshold) +
        " four times in five. ";
      if (power >= 0.8) {
        verdict += "The count would most likely show it on its own.";
      } else if (power >= 0.5) {
        verdict +=
          "More often than not the count would show it, but a year that did not would not " +
          (fall ? "mean the law had failed." : "mean the law was harmless.");
      } else {
        verdict +=
          "More often than not it would be lost in ordinary variation, and the forecast only " +
          "drifts further in later years: it would have to be checked by measuring speeds.";
      }
    }
    put(doc, "verdict", verdict);
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
    form.querySelector("#response-share").addEventListener("input", function () {
      form.querySelector('input[name="response"][value="set"]').checked = true;
    });
    for (const button of doc.querySelectorAll("button[data-preset]")) {
      button.addEventListener("click", function () {
        const preset = P.presets.find((p) => p.key === button.dataset.preset);
        setScenario(form, preset);
        render(doc, P, form);
      });
    }
    render(doc, P, form);
  }

  return {
    normCdf: normCdf,
    typicalResponse: typicalResponse,
    excess: excess,
    newMeanSpeed: newMeanSpeed,
    ratios: ratios,
    minimumDetectable: minimumDetectable,
    minimumDetectableRise: minimumDetectableRise,
    detectionPower: detectionPower,
    simulate: simulate,
    attach: attach,
  };
});
