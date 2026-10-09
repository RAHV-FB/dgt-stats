"""The stylesheet: one small design system for a statistical publication.

Fonts and tokens first (colour, type, spacing, widths), then the frame (header, navigation, theme
switch, page grid, local contents, footer), then the components an article is built from (summary,
calculator, figure, table, technical details, limitation, data and method, pager), then the home
page, the dark theme, print and reduced motion. The text column is narrower than the figures and
tables, which break out of it; most elements have no box, no radius and no shadow, and hierarchy
comes from type size, weight and spacing, with thin rules where a separator is needed.

One typeface sets every HTML text: Avenir Next, or Nunito Sans where it is not installed. Tables,
captions and technical details are a step smaller, with tabular figures. The charts carry their
own embedded subset of STIX Two Text. The type scale is 13, 15, 16, 18, 20, 24 and 36 px. The
colours are defined once for each theme (``LIGHT``, ``DARK``): the dark theme follows the system
unless the reader picks one with the switch in the header.
"""

from __future__ import annotations

# Each theme's colours. The highlight is a light turquoise-blue: ``--mark`` for the rules and bars
# that mark the current page, section or headline number, ``--highlight`` as a tint behind a
# reference row or selected text, and a deeper ``--accent`` of the same hue for link text.
LIGHT = {
    "bg": "#ffffff",
    "text": "#1b1b1b",
    "text-muted": "#555555",
    "rule": "#e4e4e0",
    "rule-strong": "#c4c4be",
    "surface": "#f5f5f2",
    "highlight": "#e3f5f9",
    "selection": "#d4f0f6",
    "mark": "#1d9fbd",
    "accent": "#0b7285",
    "accent-strong": "#075866",
    "figure-bg": "#ffffff",
    "figure-focus": "#0b7285",
}
DARK = {
    "bg": "#141414",
    "text": "#e9e9e6",
    "text-muted": "#a9a9a4",
    "rule": "#2f2f2d",
    "rule-strong": "#4a4a46",
    "surface": "#1f1f1e",
    "highlight": "#0f2f37",
    "selection": "#123f49",
    "mark": "#4fc3db",
    "accent": "#7fd6e8",
    "accent-strong": "#a8e6f2",
    "figure-bg": "#ffffff",
    "figure-focus": "#0b7285",
}


# The characters the font subsets hold (scripts/build_fonts.py), so that no file is fetched for a
# character it does not contain.
UNICODE_RANGE = (
    "U+0020-007E, U+00A0-00FF, U+0131, U+0152-0153, U+0160-0161, U+0178, U+017D-017E, U+02C6, "
    "U+02DA, U+02DC, U+2009-200A, U+2010-2014, U+2018-201E, U+2022, U+2026, U+2030, "
    "U+2032-2033, U+2039-203A, U+2044, U+20AC, U+2122, U+2212, U+2215, U+2248, U+2260, U+2264-2265"
)


def _tokens(colours: dict[str, str], indent: str = "  ") -> str:
    return "\n".join(f"{indent}--{name}: {value};" for name, value in colours.items())


# The column widths, in rems, at which a figure may switch from its wide drawing to its narrow one
# (``components.figure_switch_rem``): one container query per width.
FIGURE_SWITCH_REMS = range(20, 65)


def _figure_switches() -> str:
    return "\n".join(
        f"@container figure (max-width: {rem}rem) {{ .figure-switch-{rem} .figure-wide "
        f"{{ display: none; }} .figure-switch-{rem} .figure-narrow {{ display: block; }} }}"
        for rem in FIGURE_SWITCH_REMS
    )


STYLE = (
    """
/* ------------------------------------------------------------------ fonts */
@font-face {
  font-family: "Nunito Sans"; font-style: normal; font-weight: 300 800; font-display: swap;
  src: url("fonts/NunitoSans.woff2") format("woff2");
  unicode-range: """
    + UNICODE_RANGE
    + """;
}
@font-face {
  font-family: "Nunito Sans"; font-style: italic; font-weight: 300 800; font-display: swap;
  src: url("fonts/NunitoSans-Italic.woff2") format("woff2");
  unicode-range: """
    + UNICODE_RANGE
    + """;
}

:root {
  /* Colour */
"""
    + _tokens(LIGHT)
    + """
  color-scheme: light;

  /* Type */
  --font: "Avenir Next", Avenir, "Nunito Sans", system-ui, -apple-system, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
  --text-xs: 0.8125rem;
  --text-sm: 0.9375rem;
  --text-base: 1.125rem;
  --text-md: 1.25rem;
  --text-lg: 1.5rem;
  --text-xl: 2.25rem;
  --text-small: 1rem;
  --leading: 1.55;
  --leading-tight: 1.22;

  /* Space */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.5rem;
  --space-6: 2rem;
  --space-7: 3rem;
  --space-8: 4.5rem;

  /* Widths */
  --measure: 38rem;
  --wide: 60rem;
  --page: 80rem;
  --toc: 12.5rem;
  --gutter: clamp(1rem, 4vw, 2rem);
  --radius: 2px;
}

/* ------------------------------------------------------------------ base */
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
[hidden] { display: none !important; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  font-size: var(--text-base);
  line-height: var(--leading);
  font-kerning: normal;
  -webkit-font-smoothing: antialiased;
}
::selection { background: var(--selection); }
img { max-width: 100%; height: auto; }
p, ul, ol, dl { margin: 0 0 var(--space-4); }
p, dd { max-width: var(--measure); }
p { text-wrap: pretty; }
ul, ol { padding-left: 1.25em; }
li { max-width: calc(var(--measure) - 1.25em); }
li + li { margin-top: var(--space-2); }
strong { font-weight: 600; }
a {
  color: var(--accent);
  text-decoration-line: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 0.18em;
}
a:hover { color: var(--accent-strong); text-decoration-thickness: 2px; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
h1, h2, h3 { font-weight: 600; line-height: var(--leading-tight); max-width: var(--measure); }
h1 { font-size: var(--text-xl); letter-spacing: -0.015em; margin: 0 0 var(--space-4); text-wrap: balance; }
h2 {
  font-size: var(--text-lg); letter-spacing: -0.008em; text-wrap: balance;
  margin: var(--space-7) 0 var(--space-4); scroll-margin-top: var(--space-5);
}
h3 { font-size: var(--text-md); margin: var(--space-6) 0 var(--space-3); }
.visually-hidden {
  position: absolute !important; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}
.skip-link {
  position: absolute; left: var(--gutter); top: -3rem; z-index: 100;
  background: var(--bg); color: var(--accent); padding: var(--space-2) var(--space-3);
  border: 1px solid var(--rule-strong); font-size: var(--text-sm);
}
.skip-link:focus { top: var(--space-2); }

/* ------------------------------------------------------------------ header and navigation */
.site-header { border-bottom: 1px solid var(--rule); background: var(--bg); }
.site-header-inner {
  max-width: var(--page); margin: 0 auto; padding: 0 var(--gutter);
  display: flex; align-items: center; gap: var(--space-5); min-height: 3.75rem;
}
.site-title {
  color: var(--text); text-decoration: none; font-weight: 600; font-size: 1.0625rem;
  white-space: nowrap; padding: var(--space-3) 0;
}
.site-title:hover { color: var(--text); text-decoration: none; }
.site-nav { margin-left: auto; }
.site-nav nav ul { list-style: none; margin: 0; padding: 0; }
.site-nav li + li { margin-top: 0; }
.nav-groups { display: flex; align-items: center; gap: var(--space-5); }
.nav-group { position: relative; }
.nav-top, .nav-trigger {
  display: inline-flex; align-items: center; gap: 0.4em;
  font: inherit; font-size: var(--text-sm); color: var(--text); text-decoration: none;
  background: none; border: 0; padding: var(--space-3) 0; cursor: pointer; white-space: nowrap;
}
.nav-top:hover, .nav-trigger:hover { color: var(--accent); text-decoration: none; }
.nav-trigger::after {
  content: ""; width: 0.38em; height: 0.38em; margin-top: -0.2em;
  border-right: 1.5px solid currentColor; border-bottom: 1.5px solid currentColor;
  transform: rotate(45deg); opacity: 0.7;
}
.nav-group.is-open > .nav-trigger::after { transform: rotate(-135deg); margin-top: 0.2em; }
.nav-top[aria-current="page"], .nav-group.is-current > .nav-trigger {
  box-shadow: inset 0 -2px 0 var(--mark);
}
.nav-label { display: none; }
.nav-menu {
  display: none; position: absolute; z-index: 20; top: 100%; left: calc(-1 * var(--space-4));
  min-width: 15rem; padding: var(--space-2) 0; background: var(--bg);
  border: 1px solid var(--rule-strong);
}
.nav-group:last-child .nav-menu { left: auto; right: calc(-1 * var(--space-4)); }
.nav-group.is-open > .nav-menu { display: block; }
html:not(.js) .nav-group:hover > .nav-menu,
html:not(.js) .nav-group:focus-within > .nav-menu { display: block; }
.nav-menu a {
  display: block; padding: var(--space-2) var(--space-4); color: var(--text);
  text-decoration: none; font-size: var(--text-sm); line-height: 1.4;
}
.nav-menu a:hover { background: var(--surface); color: var(--text); }
.nav-menu a[aria-current="page"] { font-weight: 600; box-shadow: inset 2px 0 0 var(--mark); }
.nav-toggle {
  display: none; margin-left: auto; font: inherit; font-size: var(--text-sm); color: var(--text);
  background: none; border: 1px solid var(--rule-strong); border-radius: var(--radius);
  padding: var(--space-1) var(--space-3); cursor: pointer;
}
.theme-toggle {
  display: inline-flex; align-items: center; justify-content: center; flex: none;
  width: 2rem; height: 2rem; padding: 0; margin-left: var(--space-1);
  color: var(--text-muted); background: none; border: 1px solid transparent; border-radius: 50%;
  cursor: pointer;
}
.theme-toggle:hover { color: var(--text); border-color: var(--rule-strong); }
.theme-toggle svg { width: 1rem; height: 1rem; }

@media (max-width: 59.99rem) {
  .site-header-inner { flex-wrap: wrap; gap: 0 var(--space-2); }
  .nav-toggle:not([hidden]) { display: inline-flex; order: 1; margin-left: auto; }
  .theme-toggle { order: 2; margin-left: var(--space-1); }
  .site-nav { flex-basis: 100%; margin: 0; order: 3; }
  html.js .site-nav:not(.is-open) { display: none; }
  .nav-groups { display: block; padding: 0 0 var(--space-5); }
  .nav-trigger { display: none; }
  .nav-label {
    display: block; margin: var(--space-4) 0 var(--space-1);
    font-size: var(--text-sm); color: var(--text-muted); font-weight: 600;
  }
  .nav-top { display: block; padding: var(--space-3) 0; }
  .nav-top[aria-current="page"] { box-shadow: none; font-weight: 600; }
  .nav-menu, html:not(.js) .nav-group:hover > .nav-menu {
    display: block; position: static; min-width: 0; padding: 0; border: 0; box-shadow: none;
  }
  .nav-menu a { padding: var(--space-2) 0; min-height: 2.5rem; display: flex; align-items: center; }
  .nav-menu a[aria-current="page"] { box-shadow: none; }
  .nav-menu a[aria-current="page"]::before {
    content: ""; width: 3px; height: 1.1em; background: var(--mark); margin-right: var(--space-2);
  }
}

/* ------------------------------------------------------------------ page grid */
.page { max-width: var(--page); margin: 0 auto; padding: 0 var(--gutter); }
main { padding: var(--space-7) 0 var(--space-7); min-width: 0; }
.toc-rail { display: none; }
@media (min-width: 72rem) {
  .page.has-toc {
    display: grid; grid-template-columns: minmax(0, var(--wide)) var(--toc);
    column-gap: var(--space-7); align-items: start;
  }
  .toc-rail { display: block; padding-top: var(--space-7); height: 100%; }
  .toc-inline { display: none; }
}

/* ------------------------------------------------------------------ page opening */
.page-header { margin: 0 0 var(--space-5); }
.eyebrow { margin: 0 0 var(--space-2); font-size: var(--text-sm); font-weight: 600; color: var(--text-muted); }
.lead { color: var(--text-muted); margin: 0; }
.summary { margin: 0 0 var(--space-6); }

/* ------------------------------------------------------------------ local contents */
.toc { position: sticky; top: var(--space-5); font-size: var(--text-sm); line-height: 1.4; }
.toc-title, .toc-inline > summary { font-size: var(--text-sm); font-weight: 600; color: var(--text-muted); }
.toc-title { margin: 0 0 var(--space-3); line-height: var(--leading); }
.toc ol { list-style: none; margin: 0; padding: 0; border-left: 1px solid var(--rule); }
.toc li { margin: 0; max-width: none; }
.toc a {
  display: block; padding: var(--space-1) 0 var(--space-1) var(--space-3);
  margin-left: -1px; border-left: 2px solid transparent;
  color: var(--text-muted); text-decoration: none;
}
.toc a:hover { color: var(--text); }
.toc a[aria-current="true"] { color: var(--text); border-left-color: var(--mark); }
.toc-inline {
  margin: 0 0 var(--space-6); max-width: var(--measure);
  border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule);
}
.toc-inline > summary { cursor: pointer; padding: var(--space-3) 0; list-style: none; }
.toc-inline > summary::-webkit-details-marker { display: none; }
.toc-inline > summary::before, details.technical > summary::before {
  content: ""; display: inline-block; width: 0.42em; height: 0.42em; margin: 0 0.6em 0.12em 0.1em;
  border-right: 1.5px solid currentColor; border-bottom: 1.5px solid currentColor;
  transform: rotate(-45deg);
}
.toc-inline[open] > summary::before, details.technical[open] > summary::before {
  transform: rotate(45deg); margin-bottom: 0.25em;
}
.toc-inline ol { margin: 0 0 var(--space-4); padding-left: 1.4em; font-size: var(--text-sm); }
.toc-inline li + li { margin-top: var(--space-1); }

/* ------------------------------------------------------------------ interactive tools */
/* The landing page lists the tools; each tool is a column of compact controls and a result with a
   chart and its figures. On a wide screen the controls sit beside the result. The charts are drawn
   by tools.js in the site's own colours, with their text at the size it is read. */
.tool-list { list-style: none; margin: var(--space-6) 0; padding: 0; max-width: var(--wide);
  display: grid; grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr)); gap: var(--space-5); }
.tool-card { margin: 0; padding: var(--space-4) 0 0; border-top: 2px solid var(--mark); max-width: none; }
.tool-card h2 { margin: 0 0 var(--space-2); font-size: var(--text-md); }
.tool-card p { margin: 0 0 var(--space-3); }
.tool-facts { margin: 0; font-size: var(--text-sm); }
.tool-facts div { display: flex; gap: var(--space-2); }
.tool-facts dt { color: var(--text-muted); min-width: 4.5rem; }
.tool-facts dd { margin: 0; }
.tool-landing-note { color: var(--text-muted); font-size: var(--text-sm); }
.tool { margin: var(--space-5) 0 var(--space-6); max-width: var(--wide); container-type: inline-size; }
.tool-layout { display: grid; gap: var(--space-5); }
.tool-controls { margin: 0; }
.tool-controls fieldset { margin: 0 0 var(--space-4); padding: 0; border: 0; min-width: 0; }
.tool-controls legend { padding: 0 0 var(--space-2); font-weight: 600; }
.tool-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3) var(--space-4); }
.tool-field { min-width: 0; }
.tool-field label, .tool-field .tool-field-label { display: block; margin-bottom: var(--space-1); font-size: var(--text-sm); color: var(--text-muted); }
.tool-field select, .tool-field input[type="number"] {
  width: 100%; min-height: 2.75rem; padding: 0 var(--space-2); font: inherit; font-size: var(--text-base);
  color: var(--text); background: var(--bg); border: 1px solid var(--rule-strong); border-radius: 0;
}
.tool-actions { display: flex; flex-wrap: wrap; gap: var(--space-3); margin: var(--space-3) 0 0; }
.tool-actions button, .tool-choice button {
  min-height: 2.75rem; padding: 0 var(--space-4); font: inherit; font-size: var(--text-sm);
  color: var(--text); background: var(--surface); border: 1px solid var(--rule-strong); cursor: pointer;
}
.tool-actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.tool select:focus-visible, .tool input:focus-visible, .tool button:focus-visible {
  outline: 3px solid var(--accent); outline-offset: 2px;
}
.tool-result { border-top: 1px solid var(--rule); padding-top: var(--space-4); min-width: 0; }
.tool-headline { margin: 0; font-size: var(--text-lg); line-height: var(--leading-tight); }
.tool-headline strong { font-size: var(--text-xl); font-weight: 500; font-variant-numeric: tabular-nums lining-nums; }
.tool-meaning { margin: var(--space-2) 0 0; }
.tool-note { margin: var(--space-2) 0 0; font-size: var(--text-sm); color: var(--text-muted); }
.tool-warning { margin: var(--space-3) 0 0; padding-left: var(--space-3); border-left: 3px solid var(--rule-strong); font-size: var(--text-sm); }
.tool-chart { margin: var(--space-4) 0 var(--space-2); min-width: 0; }
.tool-svg { display: block; max-width: 100%; height: auto; font-family: var(--font); }
.tool-svg text { fill: var(--text); font-size: 14px; }
.tool-svg .tick { fill: var(--text-muted); font-size: 13px; font-variant-numeric: tabular-nums; }
.tool-svg .grid { stroke: var(--rule); stroke-width: 1; }
.tool-svg .axis { stroke: var(--rule-strong); stroke-width: 1; }
.tool-svg .mark { stroke: var(--text-muted); stroke-width: 1; stroke-dasharray: 3 3; }
.tool-svg .series { stroke-width: 2.5; }
.tool-svg path.series { fill: none; }
.tool-svg .series-0 { stroke: var(--mark); fill: var(--mark); }
.tool-svg .series-1 { stroke: var(--text-muted); fill: var(--text-muted); }
.tool-svg path.series-1 { stroke-dasharray: 6 4; }
.tool-svg path.series { fill: none; }
.tool-svg .bar { fill: var(--mark); }
.tool-svg .bar.muted, .tool-svg .dot.muted { fill: var(--text-muted); }
.tool-svg .dot { fill: var(--mark); stroke: var(--bg); stroke-width: 1.5; }
.tool-svg .whisker { stroke: var(--text); stroke-width: 2; }
.tool-svg .range { fill: var(--rule-strong); opacity: 0.55; }
.tool-axis-label { margin: 0; font-size: var(--text-sm); color: var(--text-muted); }
.tool-empty { color: var(--text-muted); }
.tool-table { margin: var(--space-4) 0 0; }
.tool-notes { max-width: var(--measure); margin-top: var(--space-6); border-top: 1px solid var(--rule); padding-top: var(--space-4); font-size: var(--text-sm); }
.tool-notes p { margin: 0 0 var(--space-3); }
.tool-fallback { color: var(--text-muted); }
.tool-caveats { margin: var(--space-4) 0 0; padding-left: var(--space-4); font-size: var(--text-sm); color: var(--text-muted); }
.tool-caveats li + li { margin-top: var(--space-1); }
.tool-flag { font-size: var(--text-xs); color: var(--text-muted); white-space: nowrap; }
.tool-table tbody th[scope] { white-space: normal; min-width: 9ch; }
@container (min-width: 52rem) {
  .tool-layout { grid-template-columns: minmax(16rem, 20rem) minmax(0, 1fr); align-items: start; }
  .tool-fields { grid-template-columns: 1fr; }
}
@media (max-width: 30rem) {
  .tool-fields { grid-template-columns: 1fr; }
  .tool-table th, .tool-table td { padding-right: var(--space-2); }
  .tool-table .num { padding-left: var(--space-2); }
}

/* ------------------------------------------------------------------ calculator */
/* The form, then a panel with the result and the comparison. Where the calculator has room, the
   panel sits beside the form and stays in view while the form scrolls, so that changing an input
   never moves the estimate off the screen; on a phone it follows the form. */
.calculator { margin: var(--space-6) 0; max-width: var(--wide); container-type: inline-size; }
.calc-layout > form, .calc-panel { max-width: var(--measure); }
.calculator form { margin: 0; }
.calculator fieldset {
  margin: 0 0 var(--space-5); padding: 0; border: 0; border-top: 1px solid var(--rule);
}
.calculator legend { padding: var(--space-3) 0 var(--space-2); font-weight: 600; }
.calc-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4) var(--space-5); }
.calc-field label { display: block; margin-bottom: var(--space-1); font-size: var(--text-sm); color: var(--text-muted); }
.calc-field select {
  width: 100%; min-height: 2.75rem; padding: var(--space-2); font: inherit; font-size: var(--text-sm);
  color: var(--text); background: var(--bg); border: 1px solid var(--rule-strong); border-radius: 2px;
}
/* The kind of crash spans the form; the selects it shows follow it. */
.calc-field[data-wide] { grid-column: 1 / -1; }
.calc-group { margin-top: var(--space-4); }
/* What the description sets in the model, and a change the conditions forced, in one line each. */
.calc-derived, .calc-adjusted { margin: var(--space-3) 0 0; font-size: var(--text-sm); }
.calc-derived { color: var(--text-muted); }
.calc-adjusted { padding-left: var(--space-3); border-left: 3px solid var(--mark); }
.calc-actions { display: flex; flex-wrap: wrap; gap: var(--space-3); margin: var(--space-4) 0; }
.calc-actions button {
  min-height: 2.75rem; padding: var(--space-2) var(--space-4); font: inherit; font-size: var(--text-sm);
  color: var(--text); background: var(--surface); border: 1px solid var(--rule-strong); border-radius: 2px; cursor: pointer;
}
.calc-actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.calculator select:focus-visible, .calculator input:focus-visible, .calc-actions button:focus-visible {
  outline: 3px solid var(--mark); outline-offset: 2px;
}
.calc-result, .calc-baseline { border-top: 1px solid var(--rule); padding: var(--space-4) 0; }
.calc-value { margin: 0; font-size: 2.25rem; font-weight: 500; line-height: 1.05; font-variant-numeric: tabular-nums lining-nums; }
.calc-interval { margin: var(--space-1) 0 0; font-variant-numeric: tabular-nums lining-nums; }
.calc-label, .calc-compare { margin: var(--space-2) 0 0; font-size: var(--text-base); }
.calc-note, .calc-kept { margin: var(--space-2) 0 0; font-size: var(--text-sm); color: var(--text-muted); }
.calc-warnings { margin: var(--space-3) 0 0; padding-left: 1.2em; font-size: var(--text-sm); }
.calc-result[data-state="error"] { border-top-color: var(--rule-strong); }
.calc-error-title, .calc-pending { margin: 0; font-weight: 600; }
/* Scenarios A and B, their difference and their ratio: four short rows that fit a phone. */
.calc-ab { width: 100%; margin: 0; }
.calc-ab caption { text-align: left; padding-bottom: var(--space-2); font-weight: 600; }
.calc-ab th, .calc-ab td { padding-right: var(--space-3); }
.calc-ab tbody th { white-space: normal; }
.calc-meta { margin: 0; padding-top: var(--space-3); border-top: 1px solid var(--rule); font-size: var(--text-sm); color: var(--text-muted); }
/* The estimate pinned to the foot of the screen while the form scrolls, where the panel follows it. */
.calc-sticky {
  position: sticky; bottom: 0; z-index: 1; margin: 0; padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm); font-variant-numeric: tabular-nums lining-nums;
  background: var(--surface); border-top: 1px solid var(--rule-strong);
}
.calc-sticky:empty { display: none; }
/* While the line is pinned, the page keeps a focused control above it, so it never covers the
   control in use. The line shows below a 50rem calculator, in viewports up to about 64rem. */
@media (max-width: 64rem) {
  html:has(.calc-sticky:not(:empty)) { scroll-padding-bottom: 7rem; }
}
@container (min-width: 50rem) {
  .calc-sticky { display: none; }
  .calc-layout {
    display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
    column-gap: var(--space-6); align-items: start;
  }
  .calc-panel {
    position: sticky; top: var(--space-4);
    max-height: calc(100vh - 2 * var(--space-4)); overflow-y: auto;
  }
  .calc-baseline { padding-bottom: 0; }
  .calc-label, .calc-compare { font-size: var(--text-sm); }
}

/* ------------------------------------------------------------------ definition lists */
.facts {
  display: grid; grid-template-columns: max-content minmax(0, 1fr); column-gap: 0;
  margin: var(--space-4) 0 var(--space-6); max-width: var(--measure);
  border-top: 1px solid var(--rule-strong); font-size: var(--text-small); line-height: 1.45;
}
.facts > div { display: contents; }
.facts dt, .facts dd { margin: 0; padding: var(--space-2) 0; border-bottom: 1px solid var(--rule); }
.facts dt { color: var(--text-muted); padding-right: var(--space-5); }
.facts dd { font-variant-numeric: tabular-nums; }

/* ------------------------------------------------------------------ figures */
figure { margin: var(--space-6) 0 var(--space-7); max-width: var(--wide); }
.figure-title, .table-title {
  margin: 0 0 var(--space-3); max-width: var(--measure);
  font-size: 1.0625rem; font-weight: 500; line-height: 1.4;
}
.figure-label, .table-label { font-weight: 700; margin-right: 0.3em; }
.figure-media { overflow-x: auto; background: var(--figure-bg); width: fit-content; max-width: 100%; }
.figure-media a { display: block; width: max-content; max-width: 100%; }
.figure-media a:focus-visible { outline: 2px solid var(--figure-focus); outline-offset: -2px; }
/* A figure shows its wide drawing while the column leaves its smallest text at 11 px or more, and
   its narrow drawing, made for a phone's column, below that (components.figure_switch_rem): the
   switch follows the column, whatever the viewport, zoom or layout. Only the drawing shown is
   loaded, both being lazy. */
figure { container: figure / inline-size; }
.figure-media img { max-width: 100%; height: auto; }
.figure-wide { display: block; width: var(--w); min-width: var(--w-small); }
.figure-narrow { display: none; width: var(--w-narrow); }
"""
    + _figure_switches()
    + """
figcaption {
  margin-top: var(--space-3); max-width: var(--measure);
  font-size: var(--text-sm); line-height: 1.5; color: var(--text-muted);
}
figcaption p { margin: 0; }
.figure-source { margin-top: var(--space-1); }
.figure-tools { display: none; margin: 0 0 var(--space-2); font-size: var(--text-xs); color: var(--text-muted); }
@media (max-width: 64rem) {
  .figure-tools { display: block; }
}
@media (max-width: 40rem) {
  .figure-tools { display: none; }
}

/* ------------------------------------------------------------------ tables */
.table-block { margin: var(--space-5) 0 var(--space-6); max-width: var(--wide); }
.table-block .table-title { margin-bottom: var(--space-1); }
.table-note {
  margin: 0 0 var(--space-3); max-width: var(--measure);
  font-size: var(--text-sm); line-height: 1.5; color: var(--text-muted);
}
.table-tools { margin: 0 0 var(--space-2); font-size: var(--text-xs); color: var(--text-muted); }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; font-size: var(--text-sm); line-height: 1.45; font-variant-numeric: tabular-nums lining-nums; }
th, td {
  padding: var(--space-2) var(--space-4) var(--space-2) 0; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--rule);
}
th:last-child, td:last-child { padding-right: 0; }
thead th {
  vertical-align: bottom; font-weight: 600; font-size: 0.875rem;
  color: var(--text-muted); border-bottom: 1px solid var(--rule-strong);
}
tbody th { font-weight: 400; }
tbody th:not(.wrap) { white-space: nowrap; }
.num { text-align: right; padding-left: var(--space-3); font-variant-numeric: tabular-nums lining-nums; }
td.num { white-space: nowrap; }
.wrap { min-width: 14ch; max-width: 34ch; }
tr.is-reference > * { background: var(--highlight); }
tr.is-reference > th { font-weight: 600; }
.table-wrap:focus-visible, .figure-media:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
@media (max-width: 40rem) {
  .wrap { min-width: 16ch; }
  table.stack, table.stack tbody, table.stack tr, table.stack th, table.stack td { display: block; }
  table.stack thead {
    position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;
  }
  table.stack tr { padding: var(--space-3) 0; border-bottom: 1px solid var(--rule); }
  table.stack tr:first-child { border-top: 1px solid var(--rule-strong); }
  table.stack th, table.stack td { border: 0; padding: var(--space-1) 0; min-width: 0; max-width: none; }
  table.stack tbody th { font-weight: 600; white-space: normal; }
  table.stack td::before {
    content: attr(data-label); display: block; font-size: 0.875rem; font-weight: 600;
    color: var(--text-muted);
  }
}

/* ------------------------------------------------------------------ technical detail */
details.technical {
  margin: var(--space-5) 0; max-width: var(--wide);
  border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule);
}
details.technical + details.technical { margin-top: calc(-1 * var(--space-5) - 1px); }
details.technical > summary {
  list-style: none; cursor: pointer; padding: var(--space-3) 0 var(--space-3) 1.15em; text-indent: -1.15em;
  font-size: var(--text-sm); font-weight: 500; color: var(--text); max-width: var(--measure);
}
details.technical > summary::-webkit-details-marker { display: none; }
details.technical > summary:hover { color: var(--accent); }
.technical-body { padding: 0 0 var(--space-5); font-size: var(--text-small); line-height: 1.55; }
.technical-body table, .technical-body figcaption { font-size: var(--text-sm); }
.technical-body > p { max-width: var(--measure); }
.technical-body figure { margin: var(--space-4) 0; }
.technical-body .table-block { margin: var(--space-4) 0; }

/* ------------------------------------------------------------------ limitation, notes */
/* Limitations and evidence notes are ordinary paragraphs: they are what a reader most needs to
   weigh a result, so they are not set apart as asides. */
.limit { margin: var(--space-6) 0; max-width: var(--measure); }
.limit p { margin: 0; }
.limit-label { font-weight: 600; }
.evidence-note { margin: 0 0 var(--space-4); max-width: var(--measure); }
.evidence-note p { margin: 0; }

/* ------------------------------------------------------------------ data and method */
.data-method {
  margin: var(--space-8) 0 0; padding-top: var(--space-4); border-top: 1px solid var(--rule-strong);
  max-width: var(--measure); font-size: var(--text-sm);
}
.data-method > h2 { font-size: var(--text-base); margin: 0 0 var(--space-3); }
.data-method dl {
  display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: var(--space-2) var(--space-5);
  margin: 0;
}
.data-method dt { color: var(--text-muted); }
.data-method dd { margin: 0; max-width: none; }
.data-method ul { list-style: none; padding: 0; margin: 0; }
.data-method ul.many { columns: 2 16rem; column-gap: var(--space-6); }
.data-method li { margin: 0 0 var(--space-1); break-inside: avoid; }

/* ------------------------------------------------------------------ pager */
nav.pager {
  display: flex; justify-content: space-between; gap: var(--space-5);
  margin-top: var(--space-7); padding-top: var(--space-4); border-top: 1px solid var(--rule);
  font-size: var(--text-sm); max-width: var(--measure);
}
nav.pager a { color: var(--text); text-decoration: none; display: flex; flex-direction: column; gap: var(--space-1); }
nav.pager a:hover .pager-title { color: var(--accent); text-decoration: underline; }
nav.pager a[rel="next"] { margin-left: auto; text-align: right; }
.pager-label { font-size: var(--text-xs); color: var(--text-muted); }
nav.pager a[rel="prev"] .pager-title::before, nav.pager a[rel="next"] .pager-title::after {
  content: ""; display: inline-block; width: 0.42em; height: 0.42em; margin-bottom: 0.1em;
  border-right: 1.5px solid currentColor; border-bottom: 1.5px solid currentColor;
}
nav.pager a[rel="prev"] .pager-title::before { transform: rotate(135deg); margin-right: 0.45em; }
nav.pager a[rel="next"] .pager-title::after { transform: rotate(-45deg); margin-left: 0.45em; }

/* ------------------------------------------------------------------ footer */
.site-footer { border-top: 1px solid var(--rule); margin-top: var(--space-6); }
.site-footer-inner {
  max-width: var(--page); margin: 0 auto; padding: var(--space-5) var(--gutter) var(--space-7);
  font-size: var(--text-sm); line-height: 1.55; color: var(--text-muted);
}
.site-footer p { max-width: var(--measure); margin: 0 0 var(--space-2); }

/* ------------------------------------------------------------------ home page */
.home .page-header { margin-bottom: var(--space-6); }
.home h2 { margin-top: var(--space-7); }
.findings { list-style: none; padding: 0; margin: var(--space-4) 0 0; max-width: var(--measure); }
.findings > li { margin: 0; padding: var(--space-4) 0; border-top: 1px solid var(--rule); }
.findings > li:last-child { border-bottom: 1px solid var(--rule); }
.findings p { margin: 0 0 var(--space-2); }
.findings strong { font-weight: 600; }
.finding-more { font-size: var(--text-sm); }
.home h3 { font-size: var(--text-base); margin: var(--space-5) 0 var(--space-2); }
.page-list { margin: 0; padding-left: 1.2em; max-width: var(--measure); }
.page-list li { margin: 0 0 var(--space-1); }

/* ------------------------------------------------------------------ small screens */
@media (max-width: 40rem) {
  .calc-fields { grid-template-columns: 1fr; }
  body { font-size: 1.0625rem; }
  h1 { font-size: 1.875rem; }
  h2 { font-size: 1.3125rem; margin-top: var(--space-6); }
  main { padding-top: var(--space-6); }
  .facts { grid-template-columns: 1fr; }
  .facts dt { border-bottom: 0; padding-bottom: 0; padding-right: 0; }
  .data-method dl { grid-template-columns: 1fr; }
  .data-method dd { margin-bottom: var(--space-3); }
  .data-method ul { columns: 1; }
}

/* ------------------------------------------------------------------ dark theme */
/* The system's choice, unless the reader has picked light; or the reader's pick of dark. */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
"""
    + _tokens(DARK, "    ")
    + """
    color-scheme: dark;
  }
  :root:not([data-theme="light"]) .figure-media { padding: var(--space-3); }
}
:root[data-theme="dark"] {
"""
    + _tokens(DARK)
    + """
  color-scheme: dark;
}
:root[data-theme="dark"] .figure-media { padding: var(--space-3); }
/* Below a laptop's width the dark frame goes: the chart's white ground marks it off, a chart that
   fits its column in light fits it in dark, and the chart drawn for a phone keeps its text size. */
@media (prefers-color-scheme: dark) and (max-width: 64rem) {
  :root:not([data-theme="light"]) .figure-media { padding: 0; }
}
@media (max-width: 64rem) {
  :root[data-theme="dark"] .figure-media { padding: 0; }
}

/* ------------------------------------------------------------------ forced colours */
@media (forced-colors: active) {
  .nav-top[aria-current="page"], .nav-group.is-current > .nav-trigger {
    text-decoration: underline 2px; text-underline-offset: 0.4em;
  }
  .nav-menu a[aria-current="page"] { border-left: 2px solid CanvasText; }
  .toc a { border-left-color: Canvas; }
  .toc a[aria-current="true"] { border-left-color: Highlight; }
}

/* ------------------------------------------------------------------ motion */
@media (prefers-reduced-motion: no-preference) {
  html { scroll-behavior: smooth; }
}

/* ------------------------------------------------------------------ print */
@media print {
  @page { margin: 18mm 16mm; }
  :root, :root[data-theme], :root:not([data-theme="light"]) {
    --bg: #fff; --text: #000; --text-muted: #333; --rule: #ccc; --rule-strong: #888;
    --surface: #fff; --highlight: #eef5f7; --selection: #eef5f7; --mark: #000; --accent: #000;
    --figure-bg: #fff; color-scheme: light;
  }
  html { font-size: 9.5pt; }
  body { font-size: var(--text-base); line-height: 1.45; background: var(--bg); color: var(--text); }
  .site-header, .skip-link, .toc-rail, .toc-inline, nav.pager, .figure-tools, .table-tools, .nav-toggle, .theme-toggle { display: none !important; }
  .page, .page.has-toc { display: block; max-width: none; padding: 0; }
  main { padding: 0; }
  h1 { font-size: 20pt; }
  h2 { font-size: 14pt; margin-top: 18pt; break-after: avoid; }
  h3 { break-after: avoid; }
  p, li { orphans: 3; widows: 3; }
  a { color: var(--text); text-decoration: none; }
  figure, .table-block, .facts, .limit { break-inside: avoid; }
  figure { max-width: 100%; }
  .figure-media, :root[data-theme] .figure-media, :root:not([data-theme="light"]) .figure-media {
    overflow: visible; padding: 0;
  }
  .figure-media img { width: auto !important; max-width: 100% !important; min-width: 0 !important; }
  .figure-media .figure-wide { display: block !important; }
  .figure-media .figure-narrow { display: none !important; }
  .table-wrap { overflow: visible; }
  table { font-size: 8.5pt; }
  th, td { white-space: normal; }
  details.technical { border: 0; }
  .site-footer { margin-top: 12pt; }
  .site-footer-inner { padding: 6pt 0 0; font-size: 8.5pt; }
}
"""
)
