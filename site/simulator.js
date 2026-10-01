/* What a speed law would do: the browser half of dgt_stats/simulator.py.
 *
 * A line-by-line port of the Python, reading the same parameters, which the page carries as a
 * JSON block built from the committed result tables and the evidence register. A test runs this
 * file under Node on the same scenarios as the Python and requires the two to agree. Nothing here
 * is computed that the Python does not compute.
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
  const INTERURBAN = ["motorway", "conventional"];
  const URBAN = ["urban_50", "urban_30"];
  const MINUS = "−";

  // ------------------------------------------------------------------ arithmetic

  // Complementary error function (Numerical Recipes, erfcc): fractional error below 1.2e-7.
  function erfc(x) {
    const z = Math.abs(x);
    const t = 1 / (1 + 0.5 * z);
    const r =
      t *
      Math.exp(
        -z * z -
          1.26551223 +
          t *
            (1.00002368 +
              t *
                (0.37409196 +
                  t *
                    (0.09678418 +
                      t *
                        (-0.18628806 +
                          t *
                            (0.27886807 +
                              t *
                                (-1.13520398 +
                                  t * (1.48851587 + t * (-0.82215223 + t * 0.17087277))))))))
      );
    return x >= 0 ? r : 2 - r;
  }

  function normCdf(x) {
    return 0.5 * erfc(-x / Math.SQRT2);
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
    const limit = key in limits ? limits[key] : site.limit;
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
    return 1 - Math.exp(-P.detect.z * Math.sqrt(1 / expected + tau * tau));
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
    const mde = minimumDetectable(P, total.deaths_before, P.detect.tauInterurban);
    total.mde_deaths = mde * total.deaths_before;
    total.visible_in_one_year = Math.abs(total.deaths_change) / total.deaths_before >= mde;
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
    for (const select of form.querySelectorAll("select[data-site]")) {
      limits[select.dataset.site] = Number(select.value);
    }
    const typical = form.querySelector('input[name="response"][value="typical"]').checked;
    const share = Number(form.querySelector("#response-share").value) / 100;
    const compliance = Number(form.querySelector("#compliance").value) / 100;
    return { limits: limits, responseShare: typical ? null : share, compliance: compliance };
  }

  function setScenario(form, scenario) {
    for (const select of form.querySelectorAll("select[data-site]")) {
      const key = select.dataset.site;
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
    let verdict;
    if (Math.abs(t.deaths_change) < 0.5) {
      verdict = "Nothing changes, so there is nothing to detect.";
    } else if (t.visible_in_one_year) {
      verdict =
        "A change of " + signed(t.deaths_change, 0) + " deaths a year is larger than the " +
        Math.round(t.mde_deaths) + " the interurban death count can show in its first year, so " +
        "the counts alone could confirm it.";
    } else {
      verdict =
        "A change of " + signed(t.deaths_change, 0) + " deaths a year is smaller than the " +
        Math.round(t.mde_deaths) + " the interurban death count can show in its first year, and " +
        "waiting longer does not help: it would be invisible in the counts, real or not. It " +
        "would have to be checked by measuring speeds.";
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
    simulate: simulate,
    attach: attach,
  };
});
