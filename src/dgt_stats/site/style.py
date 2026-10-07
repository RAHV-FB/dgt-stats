"""The stylesheet: a statistical bulletin, not a dashboard."""

from __future__ import annotations

STYLE = """
/* A statistical bulletin, not a dashboard: serif for reading, sans for furniture and figures,
   hairline rules instead of boxes, and a text column narrower than the charts so that a figure
   or a table always breaks out of the prose. The paper colour is the same one the SVGs are drawn
   on, so a chart sits on the page with no visible edge. */
:root {
  --paper: #fcfcfb;
  --ink: #191817;
  --ink-2: #57544e;
  --rule: #ddd9d1;
  --rule-strong: #b4afa4;
  --accent: #1b5fae;
  --wash: #f4f2ec;
  --serif: Charter, "Bitstream Charter", "Sitka Text", Cambria, "Source Serif 4", Georgia, serif;
  --sans: "Helvetica Neue", Helvetica, Arial, system-ui, sans-serif;
  --measure: 34rem;
  --wide: 52rem;
}
* { box-sizing: border-box; }
html { background: var(--paper); }
body {
  margin: 0;
  color: var(--ink);
  background: var(--paper);
  font-family: var(--serif);
  font-size: 19px;
  line-height: 1.62;
  -webkit-font-smoothing: antialiased;
}
header, main, footer { max-width: var(--wide); margin: 0 auto; padding: 0 24px; }

/* Masthead */
header { padding-top: 28px; }
.masthead { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }
.masthead a { color: var(--ink); text-decoration: none; font-weight: 600; font-size: 1.05rem; letter-spacing: 0.01em; }
.masthead .strap { font-family: var(--sans); font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-2); }
/* Navigation: each section a small label followed by its links, ruled off from the next, so that
   a label never reads as a page. The supporting analyses sit inside the Spain section. */
nav[aria-label="Sections"] {
  margin: 14px 0 0; padding: 8px 0 4px; border-top: 1px solid var(--ink); border-bottom: 1px solid var(--rule);
  display: flex; flex-wrap: wrap; align-items: baseline; row-gap: 2px;
}
.navgroup {
  display: flex; flex-wrap: nowrap; align-items: baseline; column-gap: 10px; min-width: 0;
  padding: 0 14px 0 0; margin: 0 14px 0 0; border-right: 1px solid var(--rule);
}
.navgroup > ul { flex: 1 1 auto; min-width: 0; }
.navgroup:last-child { border-right: 0; margin-right: 0; padding-right: 0; }
.navlabel {
  font-family: var(--sans); font-size: 0.6rem; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-2); white-space: nowrap;
}
nav ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 12px; }
nav a {
  display: inline-block; padding: 3px 0 5px; color: var(--ink); text-decoration: none;
  font-family: var(--sans); font-size: 0.8rem; white-space: nowrap;
}
nav a:hover { color: var(--accent); }
nav a[aria-current="page"] { font-weight: 600; box-shadow: inset 0 -2px 0 var(--accent); }
.navwide { flex: 1 1 30rem; border-right: 0; margin-right: 0; padding-right: 0; }
nav li.navsub { display: flex; flex: 0 0 auto; flex-wrap: nowrap; align-items: baseline; column-gap: 10px; padding-left: 12px; border-left: 1px solid var(--rule); }
nav li.navsub > ul { flex-wrap: nowrap; }
.eyebrow {
  font-family: var(--sans); font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--accent); margin: 0 0 6px;
}
nav.pager {
  display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; max-width: var(--wide);
  margin: 40px 0 0; padding-top: 12px; border-top: 1px solid var(--rule);
  font-family: var(--sans); font-size: 0.85rem;
}
nav.pager a[rel="next"] { margin-left: auto; }

main { padding-top: 34px; padding-bottom: 56px; }
h1 { font-size: 2.35rem; line-height: 1.12; margin: 0 0 14px; letter-spacing: -0.012em; font-weight: 600; max-width: var(--measure); }
h2 {
  font-size: 1.28rem; font-weight: 600; margin: 46px 0 10px; padding-top: 12px;
  border-top: 1px solid var(--rule); max-width: var(--wide); letter-spacing: -0.005em;
}
h3 { font-size: 1.05rem; font-weight: 600; margin: 30px 0 6px; max-width: var(--measure); }
p, li { max-width: var(--measure); }
p { margin: 0 0 1em; }
p.lead { font-size: 1.12rem; color: var(--ink-2); line-height: 1.5; margin-bottom: 26px; }
p.summary { font-size: 1.12rem; line-height: 1.55; margin: 0 0 1.2em; }
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }

/* Figures and tables break out of the text column. */
figure { margin: 26px 0 30px; max-width: var(--wide); }
.figure-wrap { overflow-x: auto; }
figure img { width: 100%; min-width: 660px; height: auto; display: block; background: var(--paper); }
figcaption {
  font-family: var(--sans); font-size: 0.78rem; line-height: 1.5; color: var(--ink-2);
  margin-top: 8px; padding-top: 7px; border-top: 1px solid var(--rule); max-width: 46rem;
}
.table-wrap { overflow-x: auto; margin: 24px 0 8px; max-width: var(--wide); }
table {
  border-collapse: collapse; font-family: var(--sans); font-size: 0.82rem;
  font-variant-numeric: tabular-nums lining-nums; min-width: 460px;
}
caption {
  caption-side: top; text-align: left; font-family: var(--sans); font-size: 0.78rem;
  line-height: 1.5; color: var(--ink-2); padding: 0 0 9px; max-width: 46rem;
}
thead th {
  font-weight: 600; color: var(--ink); text-align: right; vertical-align: bottom;
  padding: 0 14px 6px 0; border-bottom: 1px solid var(--ink);
  border-top: 2px solid var(--ink);
  font-size: 0.74rem; letter-spacing: 0.03em;
}
thead th:first-child { text-align: left; }
tbody th, tbody td { padding: 5px 14px 5px 0; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--rule); }
tbody th { font-weight: 400; text-align: left; }
tbody tr:last-child th, tbody tr:last-child td { border-bottom: 1px solid var(--rule-strong); }
th.wrap, td.wrap { white-space: normal; min-width: 14ch; max-width: 36ch; text-align: left; }
.table-wrap:focus-visible, .figure-wrap:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }

.downloads { font-family: var(--sans); font-size: 0.78rem; color: var(--ink-2); margin: 0 0 30px; max-width: 46rem; }
.note { background: var(--wash); padding: 14px 18px; margin: 22px 0; max-width: var(--measure); }
.note p { margin: 0; }
.limit {
  font-family: var(--sans); font-size: 0.83rem; line-height: 1.55; color: var(--ink-2);
  max-width: 44rem; margin: 26px 0 0; padding-top: 12px; border-top: 1px solid var(--rule);
}
.limit strong { color: var(--ink); }
.conclusion { max-width: var(--measure); margin: 26px 0 0; padding-left: 16px; border-left: 3px solid var(--accent); }
.conclusion p { margin: 0; }

/* Technical detail behind a result: closed by default, a reader opens it when needed. */
details.technical { font-family: var(--sans); font-size: 0.82rem; line-height: 1.5; color: var(--ink-2); max-width: var(--wide); margin: 18px 0 26px; border-top: 1px solid var(--rule); padding-top: 8px; }
details.technical summary { cursor: pointer; color: var(--accent); }
details.technical summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
details.technical p { font-family: var(--sans); font-size: 0.82rem; max-width: 46rem; margin: 8px 0; }

footer {
  border-top: 1px solid var(--rule); margin-top: 20px; padding-top: 18px; padding-bottom: 40px;
  font-family: var(--sans); font-size: 0.78rem; line-height: 1.55; color: var(--ink-2);
}
footer p { max-width: 46rem; }

@media (max-width: 640px) {
  body { font-size: 18px; }
  h1 { font-size: 1.85rem; }
  header, main, footer { padding-left: 16px; padding-right: 16px; }
  figure img { min-width: 0; }
  caption { max-width: calc(100vw - 32px); }
  .navgroup { flex: 1 1 100%; border-right: 0; margin-right: 0; padding-right: 0; }
  .navgroup > .navlabel { flex: 0 0 5.5rem; white-space: normal; }
  nav li.navsub { flex: 1 1 auto; padding-left: 0; border-left: 0; flex-direction: column; align-items: flex-start; }
  nav li.navsub > ul { flex-wrap: wrap; }
  nav li.navsub .navlabel { padding-top: 4px; }
}
@media print {
  nav, .downloads { display: none; }
  body { font-size: 11pt; }
  figure, .figure-wrap, .table-wrap { break-inside: avoid; overflow: visible; }
  figure img { min-width: 0; }
  table { min-width: 0; font-size: 8pt; }
  th, td { white-space: normal; }
  a[href^="http"]::after { content: " (" attr(href) ")"; }
}
"""
