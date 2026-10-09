/* Shared helpers of the interactive tools: number formats, select lists, the status line, and two
   charts (lines over years, horizontal bars with intervals) drawn as SVG in the site's own colours.
   Every number shown comes from the tool's JSON file; this script holds no statistic of its own. */
(function (global) {
  "use strict";

  var MINUS = "−";
  var SVG = "http://www.w3.org/2000/svg";

  // Numbers as the site writes them: commas between thousands, a typographic minus.
  function number(value, decimals) {
    if (value === null || value === undefined || !isFinite(value)) return "–";
    var text = Math.abs(value).toLocaleString("en-GB", {
      minimumFractionDigits: decimals || 0,
      maximumFractionDigits: decimals || 0,
    });
    return (value < 0 && Number(text.replace(/,/g, "")) !== 0 ? MINUS : "") + text;
  }
  function percent(value, decimals) {
    if (value === null || value === undefined || !isFinite(value)) return "–";
    return number(value * 100, decimals === undefined ? 1 : decimals) + "%";
  }
  function signedPercent(value, decimals) {
    if (value === null || value === undefined || !isFinite(value)) return "–";
    var text = percent(value, decimals);
    return value > 0 && text.replace(/[^1-9]/g, "") !== "" ? "+" + text : text;
  }
  function range(low, high, format) {
    return format(low) + "–" + format(high);
  }

  function element(tag, attributes, text) {
    var node = document.createElement(tag);
    Object.keys(attributes || {}).forEach(function (key) { node.setAttribute(key, attributes[key]); });
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function svgElement(tag, attributes, text) {
    var node = document.createElementNS(SVG, tag);
    Object.keys(attributes || {}).forEach(function (key) { node.setAttribute(key, attributes[key]); });
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // Replace a select's options, keeping the current value when it is still offered.
  function options(select, items, preferred) {
    var current = preferred !== undefined ? preferred : select.value;
    select.textContent = "";
    items.forEach(function (item) {
      var option = element("option", { value: item.value }, item.label);
      if (item.disabled) option.disabled = true;
      select.appendChild(option);
    });
    var offered = items.filter(function (item) { return !item.disabled; }).map(function (item) { return String(item.value); });
    select.value = offered.indexOf(String(current)) >= 0 ? String(current) : offered[0];
    return select.value;
  }

  // A polite live region, so a screen reader hears the new result once, not every keystroke.
  function announcer(node) {
    var timer = null;
    return function (text) {
      if (!node) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(function () { node.textContent = text; }, 250);
    };
  }

  // Round tick values for an axis from low to high.
  function ticks(low, high, count) {
    if (!(high > low)) { high = low + 1; }
    var span = high - low;
    var step = Math.pow(10, Math.floor(Math.log(span / count) / Math.LN10));
    var err = (span / count) / step;
    if (err >= 7.5) step *= 10; else if (err >= 3.5) step *= 5; else if (err >= 1.5) step *= 2;
    var first = Math.ceil(low / step) * step;
    var out = [];
    for (var value = first; value <= high + step * 1e-9; value += step) out.push(Math.round(value / step) * step);
    return out;
  }

  // The width a chart has, so its text is drawn at the size it is read (no scaling of the SVG).
  function widthOf(container) {
    return Math.max(260, Math.floor(container.getBoundingClientRect().width || 320));
  }

  /* Lines over years.
     spec = { series: [{ label, points: [[year, value], ...] }], yLabel, format, zero, years: [a, b] }
     A missing value breaks the line; nothing is interpolated. */
  function lineChart(container, spec) {
    container.textContent = "";
    var width = widthOf(container);
    var narrow = width < 480;
    var height = narrow ? 240 : 300;
    var margin = { top: 12, right: 16, bottom: 34, left: narrow ? 58 : 70 };
    var all = [];
    spec.series.forEach(function (s) { s.points.forEach(function (p) { if (p[1] !== null && isFinite(p[1])) all.push(p); }); });
    if (!all.length) { container.appendChild(element("p", { class: "tool-empty" }, spec.empty || "No data for this selection.")); return; }
    var xs = all.map(function (p) { return p[0]; });
    var ys = all.map(function (p) { return p[1]; });
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
    if (x0 === x1) { x0 -= 1; x1 += 1; }
    var yMin = Math.min.apply(null, ys), yMax = Math.max.apply(null, ys);
    if (spec.zero !== false) yMin = Math.min(0, yMin);
    var pad = (yMax - yMin) * 0.06 || Math.abs(yMax) * 0.1 || 1;
    var yTicks = ticks(yMin, yMax + pad, narrow ? 4 : 5);
    var lo = Math.min(yMin, yTicks[0]), hi = Math.max(yMax, yTicks[yTicks.length - 1]);
    var plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
    var X = function (v) { return margin.left + (v - x0) / (x1 - x0) * plotW; };
    var Y = function (v) { return margin.top + (1 - (v - lo) / (hi - lo)) * plotH; };
    var svg = svgElement("svg", { viewBox: "0 0 " + width + " " + height, width: width, height: height, role: "img", "aria-label": spec.description || spec.yLabel || "Chart", class: "tool-svg" });
    yTicks.forEach(function (t) {
      svg.appendChild(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: Y(t), y2: Y(t), class: "grid" }));
      svg.appendChild(svgElement("text", { x: margin.left - 6, y: Y(t) + 5, "text-anchor": "end", class: "tick" }, (spec.tick || spec.format)(t)));
    });
    var span = x1 - x0;
    var step = span <= 12 ? (narrow && span > 6 ? 2 : 1) : span <= 30 ? (narrow ? 10 : 5) : 10;
    for (var year = Math.ceil(x0 / step) * step; year <= x1; year += step) {
      svg.appendChild(svgElement("text", { x: X(year), y: height - margin.bottom + 20, "text-anchor": "middle", class: "tick" }, String(year)));
    }
    svg.appendChild(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: margin.top + plotH, y2: margin.top + plotH, class: "axis" }));
    spec.series.forEach(function (s, index) {
      var d = "", started = false;
      s.points.forEach(function (p) {
        if (p[1] === null || !isFinite(p[1])) { started = false; return; }
        d += (started ? "L" : "M") + X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1);
        started = true;
      });
      svg.appendChild(svgElement("path", { d: d, class: "series series-" + index, fill: "none" }));
      s.points.forEach(function (p) {
        if (p[1] === null || !isFinite(p[1])) return;
        var dot = svgElement("circle", { cx: X(p[0]), cy: Y(p[1]), r: spec.marks && spec.marks.indexOf(p[0]) >= 0 ? 4.5 : 2.5, class: "dot series-" + index });
        dot.appendChild(svgElement("title", {}, s.label + ", " + p[0] + ": " + spec.format(p[1])));
        svg.appendChild(dot);
      });
    });
    (spec.marks || []).forEach(function (year) {
      if (year < x0 || year > x1) return;
      svg.appendChild(svgElement("line", { x1: X(year), x2: X(year), y1: margin.top, y2: margin.top + plotH, class: "mark" }));
    });
    container.appendChild(svg);
    if (spec.yLabel) container.appendChild(element("p", { class: "tool-axis-label" }, spec.yLabel));
  }

  /* Horizontal bars, each with an optional interval and an optional range drawn behind it.
     spec = { bars: [{ label, value, low, high, rangeLow, rangeHigh, note }], format, reference, referenceLabel, xLabel, log } */
  function barChart(container, spec) {
    container.textContent = "";
    var bars = spec.bars.filter(function (b) { return b.value !== null && isFinite(b.value); });
    if (!bars.length) { container.appendChild(element("p", { class: "tool-empty" }, spec.empty || "No data for this selection.")); return; }
    var width = widthOf(container);
    var narrow = width < 480;
    var labelW = narrow ? 0 : Math.min(220, Math.round(width * 0.34));
    var rowH = narrow ? 52 : 34;
    var margin = { top: 8, right: 18, bottom: 34, left: labelW + 8 };
    var height = margin.top + margin.bottom + rowH * bars.length;
    var values = [];
    bars.forEach(function (b) {
      [b.value, b.low, b.high, b.rangeLow, b.rangeHigh].forEach(function (v) { if (v !== null && v !== undefined && isFinite(v)) values.push(v); });
    });
    if (spec.reference !== undefined) values.push(spec.reference);
    var log = Boolean(spec.log);
    var tr = log ? function (v) { return Math.log(v); } : function (v) { return v; };
    var lo = Math.min.apply(null, values), hi = Math.max.apply(null, values);
    if (!log) lo = Math.min(0, lo);
    var tickValues = log ? [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8].filter(function (t) { return t >= lo * 0.95 && t <= hi * 1.05; }) : ticks(lo, hi, narrow ? 4 : 5);
    if (log) { lo = Math.min(lo, tickValues[0] || lo) * 0.92; hi = Math.max(hi, tickValues[tickValues.length - 1] || hi) * 1.06; }
    else { lo = Math.min(lo, tickValues[0]); hi = Math.max(hi, tickValues[tickValues.length - 1]); }
    var plotW = width - margin.left - margin.right;
    var X = function (v) { return margin.left + (tr(v) - tr(lo)) / (tr(hi) - tr(lo)) * plotW; };
    var svg = svgElement("svg", { viewBox: "0 0 " + width + " " + height, width: width, height: height, role: "img", "aria-label": spec.description || "Chart", class: "tool-svg" });
    tickValues.forEach(function (t) {
      svg.appendChild(svgElement("line", { x1: X(t), x2: X(t), y1: margin.top, y2: height - margin.bottom, class: "grid" }));
      svg.appendChild(svgElement("text", { x: X(t), y: height - margin.bottom + 20, "text-anchor": "middle", class: "tick" }, (spec.tick || spec.format)(t)));
    });
    if (spec.reference !== undefined) {
      svg.appendChild(svgElement("line", { x1: X(spec.reference), x2: X(spec.reference), y1: margin.top, y2: height - margin.bottom, class: "mark" }));
    }
    bars.forEach(function (b, i) {
      var top = margin.top + i * rowH;
      var mid = top + (narrow ? rowH * 0.66 : rowH / 2);
      var label = svgElement("text", narrow ? { x: margin.left, y: top + 16, class: "label" } : { x: labelW, y: mid + 5, "text-anchor": "end", class: "label" }, b.label);
      svg.appendChild(label);
      if (b.rangeLow !== undefined && b.rangeLow !== null && isFinite(b.rangeLow)) {
        svg.appendChild(svgElement("rect", { x: X(b.rangeLow), y: mid - 8, width: Math.max(1, X(b.rangeHigh) - X(b.rangeLow)), height: 16, class: "range" }));
      }
      var start = log ? X(spec.reference !== undefined ? spec.reference : lo) : X(Math.max(0, lo));
      if (!log && spec.style !== "dot") {
        svg.appendChild(svgElement("rect", { x: Math.min(start, X(b.value)), y: mid - 5, width: Math.max(1, Math.abs(X(b.value) - start)), height: 10, class: "bar" + (b.muted ? " muted" : "") }));
      }
      if (b.low !== undefined && b.low !== null && isFinite(b.low)) {
        svg.appendChild(svgElement("line", { x1: X(b.low), x2: X(b.high), y1: mid, y2: mid, class: "whisker" }));
      }
      var dot = svgElement("circle", { cx: X(b.value), cy: mid, r: 5, class: "dot" + (b.muted ? " muted" : "") });
      dot.appendChild(svgElement("title", {}, b.label + ": " + spec.format(b.value)));
      svg.appendChild(dot);
    });
    container.appendChild(svg);
    if (spec.xLabel) container.appendChild(element("p", { class: "tool-axis-label" }, spec.xLabel));
  }

  // Redraw a chart when its column changes width.
  function onResize(draw) {
    var last = 0, timer = null;
    window.addEventListener("resize", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        var now = window.innerWidth;
        if (now !== last) { last = now; draw(); }
      }, 150);
    });
  }

  // Load a tool's data; on failure, say so where the tool would be.
  function load(url, root, start) {
    function fail() {
      root.hidden = true;
      var fallback = document.querySelector("[data-tool-fallback]");
      if (fallback) fallback.textContent = "The tool could not load its data. Reload the page to try again.";
    }
    fetch(url, { cache: "no-cache" })
      .then(function (response) { if (!response.ok) throw new Error(response.status); return response.json(); })
      .then(function (data) {
        root.hidden = false;
        var fallback = document.querySelector("[data-tool-fallback]");
        if (fallback) fallback.hidden = true;
        start(data);
      })
      .catch(fail);
  }

  global.Tools = {
    number: number,
    percent: percent,
    signedPercent: signedPercent,
    range: range,
    element: element,
    options: options,
    announcer: announcer,
    lineChart: lineChart,
    barChart: barChart,
    onResize: onResize,
    load: load,
  };
})(window);
