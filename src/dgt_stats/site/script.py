"""The one script the site runs, and only to make reading easier; every page works without it.

It opens and closes the section menus and the small-screen menu, marks the section of a long page
that is being read in its contents rail, gives a chart or table a keyboard stop and a note about
scrolling sideways only when it overflows its column, and opens the technical details before a
page is printed. The pages set ``class="js"`` on ``<html>`` from a one-line inline script, so that
without scripting the navigation is simply shown open.
"""

from __future__ import annotations

# The inline line in each page's head: it runs before the page is drawn, so the small-screen menu
# never flashes open.
JS_FLAG = "<script>document.documentElement.classList.add('js')</script>"

SCRIPT = r"""
(function () {
  "use strict";

  // Section menus: a button opens its list; Escape, a click elsewhere or leaving the menu closes it.
  var groups = Array.prototype.slice.call(document.querySelectorAll(".nav-group"));
  function close(group, focus) {
    var trigger = group.querySelector(".nav-trigger");
    if (!trigger) return;
    group.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
    if (focus) trigger.focus();
  }
  groups.forEach(function (group) {
    var trigger = group.querySelector(".nav-trigger");
    if (!trigger) return;
    trigger.addEventListener("click", function () {
      var open = !group.classList.contains("is-open");
      groups.forEach(function (other) { if (other !== group) close(other, false); });
      group.classList.toggle("is-open", open);
      trigger.setAttribute("aria-expanded", open ? "true" : "false");
    });
    group.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && group.classList.contains("is-open")) close(group, true);
    });
    group.addEventListener("focusout", function (event) {
      if (!group.contains(event.relatedTarget)) close(group, false);
    });
  });
  document.addEventListener("click", function (event) {
    groups.forEach(function (group) { if (!group.contains(event.target)) close(group, false); });
  });

  // The small-screen menu button.
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  if (toggle && nav) {
    toggle.hidden = false;
    toggle.addEventListener("click", function () {
      var open = !nav.classList.contains("is-open");
      nav.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // The contents rail marks the section being read: the last heading above the top third of the
  // window, or the last section once the page is scrolled to its end.
  var links = Array.prototype.slice.call(document.querySelectorAll(".toc-rail a[href^='#']"));
  if (links.length) {
    var headings = links.map(function (link) {
      return document.getElementById(link.getAttribute("href").slice(1));
    });
    var pending = false;
    var mark = function () {
      pending = false;
      var current = -1;
      headings.forEach(function (heading, index) {
        if (heading && heading.getBoundingClientRect().top < window.innerHeight * 0.3) current = index;
      });
      var root = document.documentElement;
      if (window.innerHeight + window.pageYOffset >= root.scrollHeight - 2) current = headings.length - 1;
      links.forEach(function (link, index) {
        if (index === current) link.setAttribute("aria-current", "true");
        else link.removeAttribute("aria-current");
      });
    };
    var schedule = function () {
      if (!pending) { pending = true; window.requestAnimationFrame(mark); }
    };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    mark();
  }

  // A chart or table that fits its column needs no keyboard stop of its own and no note about
  // scrolling sideways; one that does not fit gets both.
  var regions = Array.prototype.slice.call(document.querySelectorAll(".figure-media, .table-wrap"));
  function tabStops() {
    regions.forEach(function (region) {
      var overflows = region.scrollWidth > region.clientWidth + 1;
      if (overflows) region.setAttribute("tabindex", "0");
      else region.removeAttribute("tabindex");
      var note = region.previousElementSibling;
      if (note && /\b(figure|table)-tools\b/.test(note.className)) note.hidden = !overflows;
    });
  }
  tabStops();
  window.addEventListener("resize", tabStops);

  // Print the technical details open, then restore them.
  var closed = [];
  window.addEventListener("beforeprint", function () {
    closed = Array.prototype.slice.call(document.querySelectorAll("details:not([open])"));
    closed.forEach(function (details) { details.open = true; });
  });
  window.addEventListener("afterprint", function () {
    closed.forEach(function (details) { details.open = false; });
    closed = [];
  });
})();
"""
