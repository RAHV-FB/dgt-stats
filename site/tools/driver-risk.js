/* The driver risk comparison: two groups of car drivers side by side. Every value, interval and
   range comes from driver-risk.json; the script only chooses which to show and says what they are. */
(function () {
  "use strict";

  var root = document.querySelector('[data-tool="driver-risk"]');
  if (!root || !window.Tools) return;
  var T = window.Tools;
  var form = root.querySelector("[data-controls]");
  var field = function (name) { return form.elements[name]; };
  var show = function (name, visible) { root.querySelector('[data-field="' + name + '"]').hidden = !visible; };
  var out = {
    headline: root.querySelector("[data-headline]"),
    detail: root.querySelector("[data-detail]"),
    condition: root.querySelector("[data-condition]"),
    chart: root.querySelector("[data-chart]"),
    note: root.querySelector("[data-note]"),
    assumptions: root.querySelector("[data-assumptions]"),
  };
  var announce = T.announcer(root.querySelector("[data-status]"));
  var data = null;
  var PER_KM = { involved_per_km: true, killed_per_km: true };

  function measures() {
    var list = data.age.map(function (m) { return { value: m.id, label: m.label }; });
    if (field("mode").value === "sex") {
      return list.filter(function (m) { return PER_KM[m.value] || data.sex.observed[m.value]; });
    }
    return list;
  }
  function measure() {
    var id = field("measure").value;
    for (var i = 0; i < data.age.length; i += 1) if (data.age[i].id === id) return data.age[i];
    return null;
  }
  function ratio(v) { return T.number(v, 2); }
  function ageLabel(g) { return data.age_labels[g]; }
  function drivers(g) { return "drivers aged " + ageLabel(g); }

  // The estimate per km for one age group under the chosen assumptions.
  function perKm(m, g) {
    var group = m.groups[g];
    if (group.by_profile) return group.by_profile[field("profile").value];
    return group.by_split[field("split").value];
  }

  function controls(keep) {
    var mode = field("mode").value;
    T.options(field("measure"), measures(), keep ? undefined : "involved_per_km");
    var m = measure();
    var sex = mode === "sex";
    show("a", !sex); show("b", !sex);
    show("band", sex && !PER_KM[m.id]);
    if (!sex) {
      var groups = data.ages.filter(function (g) { return m.groups[g]; }).map(function (g) { return { value: g, label: ageLabel(g) }; });
      T.options(field("a"), groups, keep ? undefined : "75+");
      T.options(field("b"), groups, keep ? undefined : data.reference);
    }
    var a = field("a").value, b = field("b").value;
    var profile = !sex && PER_KM[m.id] && [a, b].some(function (g) { return m.groups[g] && m.groups[g].by_profile && g !== data.reference; });
    var split = !sex && m.id === "involved_per_km" && [a, b].some(function (g) { return m.groups[g] && m.groups[g].by_split; });
    show("profile", profile); show("split", split);
    out.assumptions.hidden = !(profile || split);
  }

  function renderPerKmAge(m) {
    var a = field("a").value, b = field("b").value;
    var verb = m.id === "killed_per_km" ? "were killed" : "were involved in injury crashes";
    var sentences = [], details = [];
    [a, b].forEach(function (g) {
      if (g === data.reference) return;
      var e = perKm(m, g), range = m.groups[g].range;
      sentences.push("Per kilometre driven, " + drivers(g) + " " + verb + " " + ratio(e.value) +
        " times as often as " + drivers(data.reference) + ".");
      details.push(ageLabel(g) + ": 95% sampling interval " + e.interval + "; sensitivity range " +
        ratio(range[0]) + "–" + ratio(range[1]) + ".");
    });
    if (!sentences.length) sentences.push(drivers(data.reference).replace(/^d/, "D") + " are the reference: every per-kilometre figure is a ratio to their rate.");
    if (a !== data.reference && b !== data.reference && a !== b) {
      details.push("The estimate for " + ageLabel(a) + " is " + ratio(perKm(m, a).value / perKm(m, b).value) + " times that for " + ageLabel(b) + ".");
    }
    out.headline.textContent = sentences.join(" ");
    out.detail.textContent = details.join(" ");
    // Ages 75 and over: the condition the estimate rests on, and what the range establishes.
    var older = [a, b].indexOf("75+") >= 0 && m.groups["75+"];
    out.condition.hidden = !older;
    if (older) {
      var chosen = perKm(m, "75+");
      var text = field("split").value === data.central_split ? data.condition :
        "This figure rests on the chosen split of the 65-and-over kilometres.";
      if (chosen.at_odds) text += " This split is at odds with surveys of men's driving.";
      out.condition.textContent = text + " " + data.older_conclusion;
    }
    var bars = data.ages.filter(function (g) { return m.groups[g]; }).map(function (g) {
      var e = perKm(m, g), range = m.groups[g].range;
      return { label: ageLabel(g), value: e.value, low: e.low, high: e.high,
        rangeLow: range ? range[0] : null, rangeHigh: range ? range[1] : null,
        muted: g !== a && g !== b };
    });
    T.barChart(out.chart, { bars: bars, format: ratio, log: true, reference: 1, style: "dot",
      xLabel: "Times the rate of drivers aged " + ageLabel(data.reference) + " (log scale). Line: 95% sampling interval; band: sensitivity range.",
      description: m.label + " by age, as a ratio to drivers aged " + ageLabel(data.reference) });
    out.note.textContent = "Estimate for Spain, " + data.year + ", private-car drivers. Assumptions not shown are at their central choice.";
  }

  function renderObservedAge(m) {
    var a = field("a").value, b = field("b").value;
    var f = function (v) { return T.number(v, m.decimals); };
    var ga = m.groups[a], gb = m.groups[b];
    var line = function (g, x) { return ageLabel(g) + ": " + f(x.value) + " " + m.scale + " (95% interval " + f(x.ci[0]) + "–" + f(x.ci[1]) + ")"; };
    out.headline.textContent = line(a, ga) + ".";
    if (a === b) {
      out.detail.textContent = "Choose two different groups to compare them.";
    } else {
      var r = m.pairs[a + "|" + b];
      out.detail.textContent = line(b, gb) + ". " + ageLabel(a) + " against " + ageLabel(b) + ": " +
        ratio(r[0]) + " times (95% interval " + ratio(r[1]) + "–" + ratio(r[2]) + ").";
    }
    out.condition.hidden = true;
    var bars = data.ages.filter(function (g) { return m.groups[g]; }).map(function (g) {
      var x = m.groups[g];
      return { label: ageLabel(g), value: x.value, low: x.ci[0], high: x.ci[1], muted: g !== a && g !== b };
    });
    T.barChart(out.chart, { bars: bars, format: f, xLabel: m.label + ". Line: 95% interval.",
      description: m.label + " by age" });
    out.note.textContent = "Observed, Spain, " + data.year + ", private-car drivers.";
  }

  function renderSex(m) {
    out.condition.hidden = true;
    if (PER_KM[m.id]) {
      var k = data.sex.per_km[m.id];
      var verb = m.id === "killed_per_km" ? "were killed" : "were involved in injury crashes";
      out.headline.textContent = "Per kilometre driven, men " + verb + " " + ratio(k.ratio) + " times as often as women.";
      out.detail.textContent = "95% sampling interval " + k.interval + "; across the regional age profiles of the kilometres, " +
        ratio(k.range[0]) + " to " + ratio(k.range[1]) + ".";
      T.barChart(out.chart, { bars: [{ label: "Men against women", value: k.ratio, low: k.low, high: k.high, rangeLow: k.range[0], rangeHigh: k.range[1] }],
        format: ratio, log: true, reference: 1, style: "dot", xLabel: "Ratio of men to women (log scale). Line: 95% sampling interval; band: sensitivity range.",
        description: m.label + ", men against women" });
      out.note.textContent = "Estimate for Spain, " + data.year + ", private-car drivers aged 18 and over.";
      return;
    }
    var band = data.sex.observed[m.id][field("band").value];
    var f = function (v) { return T.number(v, m.decimals); };
    var part = function (who, x) { return who + " " + f(x[0]) + " (95% interval " + f(x[1]) + "–" + f(x[2]) + ")"; };
    out.headline.textContent = band.label + ": " + part("men", band.men) + ", " + part("women", band.women) + " " + m.scale + ".";
    out.detail.textContent = "Men against women: " + ratio(band.ratio[0]) + " times (95% interval " + ratio(band.ratio[1]) + "–" + ratio(band.ratio[2]) + ").";
    T.barChart(out.chart, { bars: [
      { label: "Men", value: band.men[0], low: band.men[1], high: band.men[2] },
      { label: "Women", value: band.women[0], low: band.women[1], high: band.women[2] },
    ], format: f, xLabel: m.label + ", " + band.label + ". Line: 95% interval.", description: m.label + ", men and women aged " + band.label });
    out.note.textContent = "Observed, Spain, " + data.sex.years + " pooled, private-car drivers.";
  }

  function render() {
    var m = measure();
    if (field("mode").value === "sex") renderSex(m);
    else if (PER_KM[m.id]) renderPerKmAge(m);
    else renderObservedAge(m);
    announce(out.headline.textContent);
  }

  function reset() {
    T.options(field("mode"), [{ value: "age", label: "Age groups" }, { value: "sex", label: "Men and women" }], "age");
    T.options(field("profile"), data.profiles, data.central_profile);
    T.options(field("split"), data.splits, data.central_split);
    T.options(field("band"), data.sex.bands.map(function (b) { return { value: b, label: data.sex.observed.involved_per_licence[b].label }; }), data.sex.bands[0]);
    controls(false);
    render();
  }

  T.load(root.getAttribute("data-src"), root, function (loaded) {
    data = loaded;
    reset();
    field("mode").addEventListener("change", function () { controls(false); render(); });
    ["measure", "a", "b"].forEach(function (name) {
      field(name).addEventListener("change", function () { controls(true); render(); });
    });
    ["profile", "split", "band"].forEach(function (name) { field(name).addEventListener("change", render); });
    form.querySelector("[data-reset]").addEventListener("click", reset);
    T.onResize(render);
  });
})();
