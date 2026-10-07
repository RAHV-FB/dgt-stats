/* Distraction, alcohol and drugs, and the three levers compared: the browser half of
 * dgt_stats/factor_models.py.
 *
 * A port of the Python, reading the same parameters, which each page carries as a JSON block built
 * from the committed result tables. A test runs this file under Node across the sliders' range and
 * requires it to agree with the Python. Nothing here is computed that the Python does not compute.
 */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.FactorModels = api;
    if (typeof document !== "undefined") {
      document.addEventListener("DOMContentLoaded", function () {
        api.attach(document);
      });
    }
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const ZONES = ["interurban", "urban"];
  const ROLES = ["driver", "passenger", "pedestrian"];
  const MINUS = "−";

  // ------------------------------------------------------------------ arithmetic

  // Deaths a year avoided by removing `share` of one factor, by zone and road user.
  function avoided(P, factor, share, bound) {
    const f = P.factors[factor];
    const out = {};
    for (const zone of ZONES) {
      out[zone] = {};
      for (const role of ROLES) {
        out[zone][role] = share * P.deaths[zone][role] * f.presence[zone] * f.af[bound];
      }
    }
    return out;
  }

  // The same for a group of factors removed by the same share each, or by one share per member.
  function groupAvoided(P, group, shares, bound) {
    const out = {};
    for (const zone of ZONES) {
      out[zone] = {};
      for (const role of ROLES) out[zone][role] = 0;
    }
    for (const factor of P.groups[group]) {
      const share = typeof shares === "object" ? shares[factor] : shares;
      const one = avoided(P, factor, share, bound);
      for (const zone of ZONES) for (const role of ROLES) out[zone][role] += one[zone][role];
    }
    return out;
  }

  function zoneTotals(byRole) {
    const out = {};
    for (const zone of ZONES) out[zone] = ROLES.reduce((sum, role) => sum + byRole[zone][role], 0);
    return out;
  }

  // Speed compliance on the simulator's curve, read by straight-line interpolation between its
  // points: interurban deaths, and urban deaths with every street at 50 (value), none (low) or
  // every street at 30 (high).
  function speedAt(P, compliance, bound) {
    const curve = P.speed;
    const last = curve.interurban_avoided.length - 1;
    const position = Math.min(Math.max(compliance, 0), 1) * last;
    const i = Math.min(Math.floor(position), last - 1);
    const t = position - i;
    const at = (column) => curve[column][i] + t * (curve[column][i + 1] - curve[column][i]);
    const suffix = bound === "value" ? "" : "_" + bound;
    const urbanDeaths = ROLES.reduce((sum, role) => sum + P.deaths.urban[role], 0);
    let urban = urbanDeaths * at("urban_50_fall");
    if (bound === "low") urban = 0;
    if (bound === "high") urban = urbanDeaths * at("urban_30_fall");
    return { interurban: at("interurban_avoided" + suffix), urban: urban };
  }

  // Share of deaths avoided by several factors acting independently: 1 − Π(1 − a).
  function combine(shares) {
    return 1 - shares.reduce((remaining, share) => remaining * (1 - share), 1);
  }

  // The three levers at the settings given, by zone, and all three together.
  function compare(P, settings, bound) {
    const out = {
      speed: speedAt(P, settings.speed, bound),
      alcohol_drugs: zoneTotals(groupAvoided(P, "alcohol_drugs", settings.alcohol_drugs, bound)),
      distraction: zoneTotals(groupAvoided(P, "distraction", settings.distraction, bound)),
    };
    out.combined = {};
    for (const zone of ZONES) {
      const deaths = ROLES.reduce((sum, role) => sum + P.deaths[zone][role], 0);
      const shares = Object.keys(P.levers).map((lever) => out[lever][zone] / deaths);
      out.combined[zone] = deaths * combine(shares);
    }
    return out;
  }

  // ------------------------------------------------------------------ the page

  function whole(value) {
    return Math.round(value).toLocaleString("en-GB");
  }

  function signedFall(value) {
    const text = whole(Math.abs(value));
    return text === "0" ? "0" : MINUS + text;
  }

  function put(scope, name, text) {
    for (const cell of scope.querySelectorAll('[data-out="' + name + '"]')) cell.textContent = text;
  }

  function sliderShare(form, name) {
    const input = form.querySelector('[data-slider="' + name + '"]');
    return input ? Number(input.value) / 100 : null;
  }

  function chosenBound(form) {
    const checked = form.querySelector('input[name="bound"]:checked');
    return checked ? checked.value : "value";
  }

  function renderFactorPage(doc, P, form, group) {
    const bound = chosenBound(form);
    const members = P.groups[group];
    const shares = {};
    for (const factor of members) {
      shares[factor] = sliderShare(form, factor);
      put(form, "share-" + factor, Math.round(shares[factor] * 100) + "%");
    }
    const byRole = groupAvoided(P, group, shares, bound);
    let total = 0;
    for (const zone of ZONES) {
      let zoneTotal = 0;
      for (const role of ROLES) {
        put(doc, "avoided-" + zone + "-" + role, signedFall(byRole[zone][role]));
        zoneTotal += byRole[zone][role];
      }
      put(doc, "avoided-" + zone, signedFall(zoneTotal));
      total += zoneTotal;
    }
    put(doc, "avoided-total", signedFall(total));
    for (const factor of members) {
      const one = zoneTotals(avoided(P, factor, shares[factor], bound));
      put(doc, "avoided-factor-" + factor, signedFall(one.interurban + one.urban));
      const crashes = P.crashes[factor];
      if (crashes !== undefined) {
        put(doc, "crashes-" + factor, signedFall(shares[factor] * crashes * P.factors[factor].af[bound]));
      }
    }
  }

  function renderComparison(doc, P, form) {
    const bound = chosenBound(form);
    const settings = {};
    for (const lever of Object.keys(P.levers)) {
      settings[lever] = sliderShare(form, lever);
      put(form, "share-" + lever, Math.round(settings[lever] * 100) + "%");
    }
    const result = compare(P, settings, bound);
    const ranked = [];
    for (const lever of Object.keys(result)) {
      let total = 0;
      for (const zone of ZONES) {
        put(doc, "lever-" + lever + "-" + zone, signedFall(result[lever][zone]));
        total += result[lever][zone];
      }
      put(doc, "lever-" + lever + "-all", signedFall(total));
      if (lever !== "combined") ranked.push([P.levers[lever], total]);
    }
    ranked.sort((a, b) => b[1] - a[1]);
    put(
      doc,
      "ranking",
      ranked.map((item) => item[0] + " " + signedFall(item[1])).join(" · ")
    );
  }

  function attach(doc) {
    const data = doc.getElementById("factor-parameters");
    const form = doc.getElementById("factor-model");
    if (!data || !form) return;
    const P = JSON.parse(data.textContent);
    const panel = doc.getElementById("factor-panel");
    if (panel) panel.hidden = false;
    const mode = form.dataset.mode;
    const render =
      mode === "compare"
        ? () => renderComparison(doc, P, form)
        : () => renderFactorPage(doc, P, form, mode);
    form.addEventListener("input", render);
    form.addEventListener("change", render);
    // A browser that restores the controls after Back does so after DOMContentLoaded: redraw then.
    if (doc.defaultView) doc.defaultView.addEventListener("pageshow", render);
    for (const button of doc.querySelectorAll("button[data-set]")) {
      button.addEventListener("click", function () {
        const value = Number(button.dataset.set);
        for (const input of form.querySelectorAll("[data-slider]")) input.value = String(value);
        render();
      });
    }
    render();
  }

  return {
    avoided: avoided,
    groupAvoided: groupAvoided,
    zoneTotals: zoneTotals,
    speedAt: speedAt,
    combine: combine,
    compare: compare,
    attach: attach,
  };
});
