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

  // Light and dark: the system's theme until the reader picks one, which this browser keeps. Picking
  // the system's own theme forgets the choice, so the site follows the system again.
  var themeButton = document.querySelector(".theme-toggle");
  if (themeButton) {
    var root = document.documentElement;
    var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    var systemDark = function () { return Boolean(media && media.matches); };
    var isDark = function () {
      var chosen = root.getAttribute("data-theme");
      return chosen ? chosen === "dark" : systemDark();
    };
    var show = function () {
      themeButton.setAttribute("aria-pressed", isDark() ? "true" : "false");
      tabStops();
    };
    // Read the kept choice again when a page comes back from the history cache or another tab
    // changes it.
    var sync = function () {
      var kept = null;
      try { kept = window.localStorage.getItem("theme"); } catch (error) { kept = null; }
      if (kept === "dark" || kept === "light") root.setAttribute("data-theme", kept);
      else root.removeAttribute("data-theme");
      show();
    };
    themeButton.hidden = false;
    show();
    themeButton.addEventListener("click", function () {
      var dark = !isDark();
      try {
        if (dark === systemDark()) window.localStorage.removeItem("theme");
        else window.localStorage.setItem("theme", dark ? "dark" : "light");
      } catch (error) { /* the choice lasts for this page only */ }
      if (dark === systemDark()) root.removeAttribute("data-theme");
      else root.setAttribute("data-theme", dark ? "dark" : "light");
      show();
    });
    window.addEventListener("pageshow", function (event) { if (event.persisted) sync(); });
    window.addEventListener("storage", function (event) {
      if (event.key === "theme" || event.key === null) sync();
    });
    if (media && media.addEventListener) media.addEventListener("change", show);
    else if (media && media.addListener) media.addListener(show);
  }

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
