/* The trends and rates explorer: one indicator, or two as indices, over the years the reader
   chooses, with the change between the two ends. Every value comes from trends-explorer.json. */
(function () {
  "use strict";

  var root = document.querySelector('[data-tool="trends-explorer"]');
  if (!root || !window.Tools) return;
  var T = window.Tools;
  var form = root.querySelector("[data-controls]");
  var fields = {
    indicator: form.elements.indicator,
    compare: form.elements.compare,
    from: form.elements.from,
    to: form.elements.to,
  };
  var out = {
    headline: root.querySelector("[data-headline]"),
    change: root.querySelector("[data-change]"),
    chart: root.querySelector("[data-chart]"),
    note: root.querySelector("[data-note]"),
    table: root.querySelector("[data-table]"),
  };
  var announce = T.announcer(root.querySelector("[data-status]"));
  var data = null, byId = {};

  function last(indicator) { return indicator.first + indicator.values.length - 1; }
  function value(indicator, year) {
    var index = year - indicator.first;
    return index >= 0 && index < indicator.values.length ? indicator.values[index] : null;
  }
  function format(indicator) {
    return function (v) { return T.number(v, indicator.decimals); };
  }
  function years(a, b) {
    var list = [];
    for (var y = a; y <= b; y += 1) list.push({ value: y, label: String(y) });
    return list;
  }

  // The period both indicators cover, when two are compared.
  function span() {
    var main = byId[fields.indicator.value];
    var other = fields.compare.value ? byId[fields.compare.value] : null;
    var first = main.first, end = last(main);
    if (other) { first = Math.max(first, other.first); end = Math.min(end, last(other)); }
    return [first, end];
  }

  // The years each end may take: "from" before the last covered year, "to" after "from". An end
  // that falls outside the indicator's years moves to the nearest end of its range.
  function fillYears(keepFrom, keepTo) {
    var bounds = span();
    var wantFrom = Math.min(Math.max(Number(keepFrom), bounds[0]), bounds[1] - 1);
    var from = Number(T.options(fields.from, years(bounds[0], bounds[1] - 1), String(wantFrom)));
    var wantTo = keepTo !== undefined ? Number(keepTo) : bounds[1];
    wantTo = Math.min(Math.max(wantTo, from + 1), bounds[1]);
    T.options(fields.to, years(from + 1, bounds[1]), String(wantTo));
  }

  function fillCompare() {
    var main = fields.indicator.value;
    var items = [{ value: "", label: "Nothing" }];
    data.indicators.forEach(function (item) {
      if (item.id === main) return;
      var overlap = Math.min(last(item), last(byId[main])) - Math.max(item.first, byId[main].first);
      if (overlap >= 1) items.push({ value: item.id, label: item.label });
    });
    T.options(fields.compare, items);
  }

  function render() {
    var main = byId[fields.indicator.value];
    var other = fields.compare.value ? byId[fields.compare.value] : null;
    var from = Number(fields.from.value), to = Number(fields.to.value);
    var a = value(main, from), b = value(main, to);
    var ratio = b / a, count = to - from;
    var annual = Math.pow(ratio, 1 / count) - 1;
    out.headline.textContent = "";
    out.headline.appendChild(document.createTextNode(main.label + " in " + to + ": "));
    out.headline.appendChild(T.element("strong", {}, format(main)(b)));
    out.change.textContent = T.signedPercent(ratio - 1) + " since " + from + " (" + format(main)(a) +
      "), " + T.signedPercent(annual) + " a year on average.";
    var series, spec;
    if (other) {
      var base = value(other, from);
      var points = function (indicator, start) {
        var list = [];
        for (var y = from; y <= to; y += 1) list.push([y, value(indicator, y) / start * 100]);
        return list;
      };
      series = [
        { label: main.label, points: points(main, a) },
        { label: other.label, points: points(other, base) },
      ];
      var otherEnd = value(other, to) / base - 1;
      out.change.textContent += " " + other.label + ": " + T.signedPercent(otherEnd) + " over the same years.";
      spec = { series: series, format: function (v) { return T.number(v, 0); }, zero: false,
        yLabel: "Index, " + from + " = 100. Solid: " + main.label.toLowerCase() + "; dashed: " + other.label.toLowerCase() + ".",
        description: main.label + " and " + other.label + " as indices, " + from + " to " + to, marks: [from, to] };
    } else {
      var list = [];
      for (var y = from; y <= to; y += 1) list.push([y, value(main, y)]);
      series = [{ label: main.label, points: list }];
      spec = { series: series, format: format(main), zero: true, yLabel: main.label + " (" + main.unit + ")",
        description: main.label + ", " + from + " to " + to, marks: [from, to] };
    }
    T.lineChart(out.chart, spec);
    // Each indicator's note, without repeating a sentence the first one already says.
    var said = main.note;
    if (other) {
      other.note.split(/(?<=\.)\s+/).forEach(function (sentence) {
        if (said.indexOf(sentence) < 0) said += " " + sentence;
      });
    }
    out.note.textContent = said;
    // The figures behind the chart.
    out.table.textContent = "";
    var head = T.element("thead"), row = T.element("tr");
    row.appendChild(T.element("th", { scope: "col" }, "Year"));
    row.appendChild(T.element("th", { scope: "col", class: "num" }, main.label));
    if (other) row.appendChild(T.element("th", { scope: "col", class: "num" }, other.label));
    head.appendChild(row);
    out.table.appendChild(head);
    var body = T.element("tbody");
    for (var year = from; year <= to; year += 1) {
      var line = T.element("tr");
      line.appendChild(T.element("th", { scope: "row" }, String(year)));
      line.appendChild(T.element("td", { class: "num" }, format(main)(value(main, year))));
      if (other) line.appendChild(T.element("td", { class: "num" }, format(other)(value(other, year))));
      body.appendChild(line);
    }
    out.table.appendChild(body);
    announce(out.headline.textContent + ". " + out.change.textContent);
  }

  function reset() {
    T.options(fields.indicator, data.indicators.map(function (item) { return { value: item.id, label: item.label }; }), data.indicators[0].id);
    fillCompare();
    fields.compare.value = "";
    var main = byId[fields.indicator.value];
    fillYears(String(main.first), String(last(main)));
    render();
  }

  T.load(root.getAttribute("data-src"), root, function (loaded) {
    data = loaded;
    data.indicators.forEach(function (item) { byId[item.id] = item; });
    reset();
    fields.indicator.addEventListener("change", function () {
      var keepFrom = fields.from.value, keepTo = fields.to.value;
      fillCompare();
      fillYears(keepFrom, keepTo);
      render();
    });
    fields.compare.addEventListener("change", function () {
      fillYears(fields.from.value, fields.to.value);
      render();
    });
    fields.from.addEventListener("change", function () {
      fillYears(fields.from.value, fields.to.value);
      render();
    });
    fields.to.addEventListener("change", render);
    form.querySelector("[data-reset]").addEventListener("click", reset);
    T.onResize(render);
  });
})();
