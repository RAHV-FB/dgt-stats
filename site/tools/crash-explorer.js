/* The crash statistics explorer. It adds up the rows of tools/crash-explorer.json (built from
   reports/tables/explore_dgt_crashes.csv) that the reader selects, and shows the chosen outcome
   as a headline, a chart, the figures behind it and one line per caveat that applies. Every
   number comes from that file; this script only selects, adds and divides. */
(function () {
  "use strict";

  var root = document.querySelector('[data-tool="crash-explorer"]');
  if (!root || !window.Tools) return;
  var T = window.Tools;

  // A row: the positions of its year, region, road type and crash type in the label lists,
  // then injury crashes, fatal crashes, deaths within 30 days and deaths by road-user group.
  var CRASHES = 0, FATAL = 1, DEATHS = 2, USERS = 3, FIRST_COUNT = 4;
  var PER = 100;
  var ALL = "all", EACH = "each";
  // The filters that can also be the breakdown: their column in a row, the data file's list, the
  // option that selects everything, and the one shown while each level is drawn separately.
  var FILTERS = {
    region: { column: 1, list: "regions", all: "Spain", each: "Each region, shown separately" },
    road: { column: 2, list: "roads", all: "All road types", each: "Each road type, shown separately" },
    type: { column: 3, list: "types", all: "All crash types", each: "Each crash type, shown separately" },
  };
  var NOUNS = { year: "year", region: "region", road: "road type", type: "crash type" };
  var OUTCOMES = {
    crashes: { label: "Injury crashes", count: CRASHES },
    fatal: { label: "Fatal crashes", count: FATAL },
    deaths: { label: "Deaths within 30 days", count: DEATHS },
    fatal_share: { label: "Fatal crashes per 100 injury crashes", short: "Fatal per 100", share: FATAL },
    deaths_rate: { label: "Deaths per 100 injury crashes", short: "Deaths per 100", share: DEATHS },
    user: { label: "Deaths within 30 days", count: USERS },
  };

  T.load(root.getAttribute("data-src"), root, start);

  function start(data) {
    var form = root.querySelector("form");
    var controls = {};
    ["from", "to", "region", "road", "type", "outcome", "user", "by"].forEach(function (name) {
      controls[name] = form.querySelector('[name="' + name + '"]');
    });
    var userField = root.querySelector('[data-field="user"]');
    var headline = root.querySelector("[data-headline]");
    var scope = root.querySelector("[data-scope]");
    var chart = root.querySelector("[data-chart]");
    var figures = root.querySelector("[data-table]");
    var caveats = root.querySelector("[data-caveats]");
    var announce = T.announcer(root.querySelector("[data-status]"));
    var saved = {};

    function items(list) {
      return list.map(function (label, index) { return { value: String(index), label: String(label) }; });
    }
    function fillFilter(name) {
      var spec = FILTERS[name];
      var select = controls[name];
      if (controls.by.value === name) {
        if (!select.disabled) saved[name] = select.value;
        T.options(select, [{ value: EACH, label: spec.each }], EACH);
        select.disabled = true;
      } else if (select.disabled || !select.options.length) {
        T.options(select, [{ value: ALL, label: spec.all }].concat(items(data[spec.list])), saved[name] || ALL);
        select.disabled = false;
      }
    }
    var years = items(data.years);
    T.options(controls.from, years, "0");
    T.options(controls.to, years, String(years.length - 1));
    T.options(controls.user, items(data.users), "0");
    Object.keys(FILTERS).forEach(fillFilter);

    function chosen(name) {
      var value = controls[name].value;
      return value === ALL || value === EACH ? null : Number(value);
    }

    // The totals of the selected rows, by level of the breakdown.
    function totals() {
      var from = Number(controls.from.value), to = Number(controls.to.value);
      var by = controls.by.value;
      var filters = Object.keys(FILTERS)
        .filter(function (name) { return chosen(name) !== null; })
        .map(function (name) { return { column: FILTERS[name].column, level: chosen(name) }; });
      var zeros = function () { return data.rows[0].slice(FIRST_COUNT).map(function () { return 0; }); };
      var groups = {};
      data.rows.forEach(function (row) {
        if (row[0] < from || row[0] > to) return;
        for (var i = 0; i < filters.length; i++) {
          if (row[filters[i].column] !== filters[i].level) return;
        }
        var key = by === "year" ? row[0] : row[FILTERS[by].column];
        var sums = groups[key];
        if (!sums) sums = groups[key] = zeros();
        for (var j = FIRST_COUNT; j < row.length; j++) sums[j - FIRST_COUNT] += row[j];
      });
      var levels = by === "year"
        ? data.years.slice(from, to + 1).map(function (year, i) { return { key: from + i, label: String(year), year: year }; })
        : data[FILTERS[by].list].map(function (label, i) { return { key: i, label: label }; });
      return levels.map(function (level) {
        level.sums = groups[level.key] || zeros();
        return level;
      });
    }

    // The chosen outcome of a set of totals: a value, and for a fatal share its interval.
    function measure(sums) {
      var outcome = OUTCOMES[controls.outcome.value];
      var crashes = sums[CRASHES];
      if (outcome.count !== undefined) {
        var column = outcome.count === USERS ? USERS + Number(controls.user.value) : outcome.count;
        return { value: sums[column], crashes: crashes };
      }
      if (!crashes) return { value: null, crashes: 0 };
      var out = { value: (PER * sums[outcome.share]) / crashes, crashes: crashes };
      if (outcome.share === FATAL) {
        var interval = T.wilson(sums[FATAL], crashes, data.z);
        out.low = PER * interval.low;
        out.high = PER * interval.high;
      }
      return out;
    }

    function isShare() { return OUTCOMES[controls.outcome.value].share !== undefined; }
    function format(value) { return T.number(value, isShare() ? 2 : 0); }
    // Axis ticks with only the decimals they need.
    function tick(value) {
      var decimals = Number(value.toFixed(1)) === Math.round(value) ? 0 : Number(value.toFixed(2)) === Number(value.toFixed(1)) ? 1 : 2;
      return T.number(value, decimals);
    }
    function outcomeLabel() {
      var outcome = controls.outcome.value;
      if (outcome === "user") return OUTCOMES.user.label + ": " + data.users[Number(controls.user.value)].toLowerCase();
      return OUTCOMES[outcome].label;
    }
    function yearSpan() {
      var first = data.years[Number(controls.from.value)], last = data.years[Number(controls.to.value)];
      return first === last ? String(first) : first + "–" + last;
    }
    function scopeText() {
      var text = Object.keys(FILTERS).map(function (name) {
        var select = controls[name];
        var label = select.options[select.selectedIndex].text;
        if (select.value === EACH) return label.split(",")[0].toLowerCase();
        return name === "region" ? label : label.toLowerCase();
      }).concat([yearSpan()]).join(", ");
      return text.charAt(0).toUpperCase() + text.slice(1);
    }

    function cell(tag, text, attributes) { return T.element(tag, attributes || {}, text); }

    // The levels of the breakdown with their results: years in order, other levels from the
    // largest value down, with records that do not name the level last.
    function figuresOf(levels, by) {
      var rows = levels.map(function (level) {
        return { label: level.label, year: level.year, result: measure(level.sums) };
      });
      if (by !== "year") {
        rows.sort(function (a, b) {
          var lastA = a.label === data.notRecorded, lastB = b.label === data.notRecorded;
          if (lastA !== lastB) return lastA ? 1 : -1;
          var x = a.result.value === null ? -1 : a.result.value, y = b.result.value === null ? -1 : b.result.value;
          return y - x;
        });
      }
      return rows;
    }
    function lowSupport(result) { return result.crashes > 0 && result.crashes < data.minSupport; }

    function drawTable(rows, by) {
      figures.textContent = "";
      var outcome = controls.outcome.value;
      var interval = outcome === "fatal_share";
      var table = T.element("table");
      table.appendChild(cell("caption", outcomeLabel() + " by " + NOUNS[by] + ". " + scopeText(), { class: "visually-hidden" }));
      var head = T.element("tr");
      var columns = [NOUNS[by].charAt(0).toUpperCase() + NOUNS[by].slice(1), "Injury crashes"];
      if (outcome !== "crashes") columns.push(OUTCOMES[outcome].short || outcomeLabel());
      if (interval) columns.push("95% interval");
      columns.forEach(function (name, i) { head.appendChild(cell("th", name, i ? { scope: "col", class: "num" } : { scope: "col" })); });
      table.appendChild(T.element("thead")).appendChild(head);
      var body = table.appendChild(T.element("tbody"));
      rows.forEach(function (figure) {
        var result = figure.result;
        var row = T.element("tr");
        var label = cell("th", figure.label, { scope: "row" });
        if (lowSupport(result)) {
          label.appendChild(document.createTextNode(" "));
          label.appendChild(cell("span", "low support", { class: "tool-flag" }));
        }
        row.appendChild(label);
        row.appendChild(cell("td", T.number(result.crashes, 0), { class: "num" }));
        if (outcome !== "crashes") row.appendChild(cell("td", format(result.value), { class: "num" }));
        if (interval) {
          row.appendChild(cell("td", result.value === null ? "–" : T.range(result.low, result.high, format), { class: "num" }));
        }
        body.appendChild(row);
      });
      figures.appendChild(table);
    }

    function drawChart(rows, by) {
      var label = outcomeLabel();
      var description = label + " by " + NOUNS[by] + ". " + scopeText();
      if (by === "year") {
        T.lineChart(chart, {
          series: [{ label: label, points: rows.map(function (row) { return [row.year, row.result.value]; }) }],
          format: format,
          tick: tick,
          yLabel: label,
          description: description,
        });
        return;
      }
      var bars = rows.map(function (row) {
        var result = row.result;
        return { label: row.label, value: result.value, low: result.low, high: result.high, muted: lowSupport(result) };
      });
      T.barChart(chart, { bars: bars, format: format, tick: tick, xLabel: label, description: description });
    }

    function line(parts) {
      var item = T.element("li");
      parts.forEach(function (part) {
        if (typeof part === "string") item.appendChild(document.createTextNode(part));
        else item.appendChild(T.element("a", { href: part.href }, part.text));
      });
      caveats.appendChild(item);
    }

    function drawCaveats(results, by) {
      caveats.textContent = "";
      var outcome = controls.outcome.value;
      if (outcome !== "crashes") {
        line(["Deaths are those within 30 days of the crash; a fatal crash had at least one."]);
      }
      if (isShare()) {
        line(["Shares are among injury crashes recorded by the police, not rates per person, vehicle or kilometre driven."]);
      } else {
        line(["Only injury crashes recorded by the police are counted."]);
      }
      var region = chosen("region");
      var catalanRecords = region === null || region === data.catalonia;
      var roadInvolved = chosen("road") !== null || by === "road";
      if (region === data.catalonia || by === "region" || (roadInvolved && catalanRecords)) {
        var breaks = data.breaks;
        var junction = breaks.junction[0] === breaks.junction[1] ? String(breaks.junction[0]) : breaks.junction[0] + "–" + breaks.junction[1];
        line([
          "Catalonia's records code conventional roads as dual carriageways until " + breaks.dualUntil +
            ", many urban streets as other roads in " + breaks.otherFrom +
            ", and the junction flag the wrong way round in " + junction + " (",
          { href: "data.html#coding-breaks", text: "coding breaks" },
          ").",
        ]);
      }
      var low = results.some(lowSupport);
      if (low) {
        line(["Rows marked low support rest on fewer than " + data.minSupport + " injury crashes: numbers that small vary widely by chance."]);
      }
    }

    function render() {
      ["region", "road", "type"].forEach(fillFilter);
      userField.hidden = controls.outcome.value !== "user";
      var by = controls.by.value;
      var levels = totals();
      var all = levels[0].sums.map(function (_, j) {
        return levels.reduce(function (sum, level) { return sum + level.sums[j]; }, 0);
      });
      if (!all[CRASHES]) {
        headline.textContent = "No recorded crashes for this selection.";
        scope.textContent = "The records cover " + data.years[0] + "–" + data.years[data.years.length - 1] +
          "; none of their injury crashes matches " + scopeText() + ".";
        chart.textContent = "";
        figures.textContent = "";
        caveats.textContent = "";
        announce(headline.textContent);
        return;
      }
      var total = measure(all);
      headline.textContent = "";
      headline.appendChild(cell("strong", format(total.value)));
      var label = outcomeLabel();
      headline.appendChild(document.createTextNode(" " + label.charAt(0).toLowerCase() + label.slice(1)));
      if (total.low !== undefined) {
        headline.appendChild(document.createTextNode(" (95% interval " + T.range(total.low, total.high, format) + ")"));
      }
      scope.textContent = scopeText() + (isShare() ? "; " + T.number(total.crashes, 0) + " injury crashes." : ".");
      var rows = figuresOf(levels, by);
      drawChart(rows, by);
      drawTable(rows, by);
      drawCaveats(rows.map(function (row) { return row.result; }), by);
      announce(headline.textContent + ". " + scope.textContent);
    }

    function changed(event) {
      var target = event.target;
      if (target === controls.from && Number(controls.from.value) > Number(controls.to.value)) {
        controls.to.value = controls.from.value;
      }
      if (target === controls.to && Number(controls.to.value) < Number(controls.from.value)) {
        controls.from.value = controls.to.value;
      }
      render();
    }
    form.addEventListener("change", changed);
    form.addEventListener("submit", function (event) { event.preventDefault(); });
    T.onResize(function () {
      var by = controls.by.value;
      drawChart(figuresOf(totals(), by), by);
    });
    render();
  }
})();
