/* Ratsinfo-Archiv Aldersbach - site behaviour (progressive enhancement only).
 * Hand-edited source: tools/site/app.js (copied to archive/assets/ by the build).
 *
 *  - theme toggle (light / dark / system), remembered per browser
 *  - header omnibox on every page: lazy-loads data/search-index.js on first use,
 *    shows the best matches in a dropdown (arrow keys, Enter, Escape; "/" focuses)
 *  - search.html: full results with facets, state mirrored into the URL
 *  - documents.html: instant filter
 *  - decision pages: "copy citation" button; details are opened for printing
 *
 * <html data-root="../"> tells the script how to reach the site root from the
 * current page, so everything works from file:// and from any sub-path
 * (e.g. GitHub Pages project sites). */
(function () {
  "use strict";

  var ROOT = document.documentElement.getAttribute("data-root") || "";
  var INDEX = null;       // window.ARCHIVE_INDEX once loaded
  var indexPromise = null;

  function $(sel, el) { return (el || document).querySelector(sel); }
  function $all(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(s) {
    s = (s === undefined || s === null) ? "" : String(s);
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function store(key, val) {
    try {
      if (val === undefined) return window.localStorage.getItem(key);
      if (val === null) window.localStorage.removeItem(key); else window.localStorage.setItem(key, val);
    } catch (e) { /* storage unavailable: fine */ }
    return null;
  }

  /* ---------- theme ---------- */
  function initTheme() {
    var btn = $(".theme-btn");
    if (!btn) return;
    function label() {
      var t = document.documentElement.getAttribute("data-theme") || "system";
      btn.setAttribute("aria-label", "Colour theme: " + t + " (click to change)");
      btn.title = "Theme: " + t;
      btn.setAttribute("data-mode", t);
    }
    btn.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme");
      var next = cur === "light" ? "dark" : cur === "dark" ? null : "light";
      if (next) document.documentElement.setAttribute("data-theme", next);
      else document.documentElement.removeAttribute("data-theme");
      store("ba-theme", next);
      label();
    });
    label();
  }

  /* ---------- search core ---------- */

  /* Fold German spelling variants so "strasse" finds "Straße" and "Bauantraege"
   * finds "Bauanträge". Returns the folded string plus, per folded char, the
   * [start, end) range in the original string (needed to highlight matches). */
  function fold(str) {
    var s = String(str || "");
    var out = "", map = [];
    for (var i = 0; i < s.length; i++) {
      var c = s.charAt(i).toLowerCase();
      if (c === "ß") { out += "ss"; map.push([i, i + 1], [i, i + 1]); continue; }
      var base = c.normalize ? c.normalize("NFD").charAt(0) : c;
      var nx = s.charAt(i + 1).toLowerCase();
      if ((base === "a" || base === "o" || base === "u") && base === c && nx === "e") {
        out += base; map.push([i, i + 2]); i++; continue;
      }
      out += base; map.push([i, i + 1]);
    }
    return { s: out, map: map };
  }
  function foldS(str) { return fold(str).s; }

  function loadIndex() {
    if (INDEX) return Promise.resolve(INDEX);
    if (indexPromise) return indexPromise;
    indexPromise = new Promise(function (resolve, reject) {
      if (window.ARCHIVE_INDEX) { resolve(window.ARCHIVE_INDEX); return; }
      var s = document.createElement("script");
      s.src = ROOT + "data/search-index.js";
      s.onload = function () { window.ARCHIVE_INDEX ? resolve(window.ARCHIVE_INDEX) : reject(new Error("empty index")); };
      s.onerror = reject;
      document.head.appendChild(s);
    }).then(function (idx) {
      idx.items.forEach(function (it) {
        it._s = foldS(it.s);
        it._x = foldS(it.x);
        it._l = foldS(it.l);
        it._h = foldS(it.tx + " " + it.d + " top " + it.t + " " + it.tp);
      });
      INDEX = idx;
      return idx;
    });
    indexPromise.catch(function () { indexPromise = null; });
    return indexPromise;
  }

  function terms(q) {
    return foldS(q).split(/\s+/).filter(function (t) { return t.length > 0; });
  }

  function score(it, ts) {
    var sc = 0;
    for (var i = 0; i < ts.length; i++) {
      var t = ts[i], hit = 0;
      if (it._s.indexOf(t) !== -1) hit += 6;
      if (it._x.indexOf(t) !== -1) hit += 3;
      if (it._l.indexOf(t) !== -1) hit += 4;
      if (it._h.indexOf(t) !== -1) hit += 1;
      if (!hit) return 0;
      sc += hit;
    }
    return sc;
  }

  function query(idx, q, f) {
    var ts = terms(q);
    var res = [];
    idx.items.forEach(function (it) {
      if (f && f.topic && it.tp !== f.topic) return;
      if (f && f.year && it.y !== f.year) return;
      if (f && f.kind && it.k !== f.kind) return;
      var sc = ts.length ? score(it, ts) : 1;
      if (sc > 0) res.push({ it: it, sc: sc });
    });
    return { terms: ts, hits: res };
  }

  function highlight(text, ts) {
    if (!ts.length) return esc(text);
    var f = fold(text), ranges = [];
    ts.forEach(function (t) {
      if (t.length < 2) return;
      var p = 0, at;
      while ((at = f.s.indexOf(t, p)) !== -1) {
        ranges.push([f.map[at][0], f.map[at + t.length - 1][1]]);
        p = at + t.length;
      }
    });
    if (!ranges.length) return esc(text);
    ranges.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [ranges[0]];
    for (var i = 1; i < ranges.length; i++) {
      var last = merged[merged.length - 1];
      if (ranges[i][0] <= last[1]) last[1] = Math.max(last[1], ranges[i][1]); else merged.push(ranges[i]);
    }
    var out = "", pos = 0;
    merged.forEach(function (r) {
      out += esc(text.slice(pos, r[0])) + "<mark>" + esc(text.slice(r[0], r[1])) + "</mark>";
      pos = r[1];
    });
    return out + esc(text.slice(pos));
  }

  function snippet(text, ts, width) {
    width = width || 200;
    if (!ts.length) return "";
    var f = fold(text), first = -1;
    ts.forEach(function (t) {
      var p = f.s.indexOf(t);
      if (p !== -1 && (first === -1 || p < first)) first = p;
    });
    if (first === -1) return "";
    var o = f.map[first][0];
    var start = Math.max(0, o - Math.round(width * 0.35));
    if (start > 0) { var sp = text.indexOf(" ", start); if (sp !== -1 && sp < o) start = sp + 1; }
    var part = text.substr(start, width);
    return (start > 0 ? "... " : "") + highlight(part, ts) + (start + width < text.length ? " ..." : "");
  }

  function badge(idx, k) {
    var kd = idx.kinds[k] || [k, "", "none"];
    return "<span class='badge tone-" + esc(kd[2]) + "' title='" + esc(kd[1]) + "'>" + esc(kd[0]) + "</span>";
  }

  function searchUrl(q) {
    return ROOT + "search.html" + (q ? "?q=" + encodeURIComponent(q) : "");
  }

  /* ---------- omnibox dropdown (every page) ---------- */
  function initOmni(form) {
    var input = $("input", form);
    var pop = $(".omni-pop", form);
    if (!input || !pop) return;
    var active = -1, opts = [], timer = null;

    function close() { pop.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; }
    function setActive(i) {
      opts.forEach(function (o, j) { o.setAttribute("aria-selected", j === i ? "true" : "false"); });
      active = i;
      if (opts[i]) { opts[i].scrollIntoView({ block: "nearest" }); input.setAttribute("aria-activedescendant", opts[i].id); }
      else input.removeAttribute("aria-activedescendant");
    }
    function render() {
      var q = input.value.trim();
      if (!q) { close(); return; }
      loadIndex().then(function (idx) {
        if (input.value.trim() !== q) return;
        var r = query(idx, q);
        r.hits.sort(function (a, b) { return b.sc - a.sc || (b.it.o - a.it.o); });
        var top = r.hits.slice(0, 7);
        var html = top.map(function (h, i) {
          var it = h.it;
          return "<a class='omni-opt' role='option' id='omni-o" + i + "' href='" + esc(ROOT + it.p) + "'>" +
            "<span class='l1'>" + badge(idx, it.k) + "<span>" + esc(it.d) + "</span><span class='top-no'>TOP " + esc(it.t) + "</span></span>" +
            "<span class='l2'>" + highlight(it.s, r.terms) + "</span></a>";
        }).join("");
        if (!top.length) html = "<div class='omni-empty'>No decisions match \"" + esc(q) + "\".</div>";
        html += "<a class='omni-foot' href='" + esc(searchUrl(q)) + "'>" +
          (r.hits.length > top.length ? "Show all " + r.hits.length + " results" : "Open full search") + " &rarr;</a>";
        pop.innerHTML = html;
        opts = $all(".omni-opt", pop);
        pop.hidden = false;
        input.setAttribute("aria-expanded", "true");
        setActive(-1);
      }).catch(function () {
        pop.innerHTML = "<div class='omni-empty'>Search index could not be loaded.</div>";
        pop.hidden = false;
      });
    }

    input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(render, 80); });
    input.addEventListener("focus", function () { loadIndex(); if (input.value.trim()) render(); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" && !pop.hidden) { e.preventDefault(); setActive(Math.min(active + 1, opts.length - 1)); }
      else if (e.key === "ArrowUp" && !pop.hidden) { e.preventDefault(); setActive(Math.max(active - 1, -1)); }
      else if (e.key === "Escape") { close(); }
      else if (e.key === "Enter" && active >= 0 && opts[active]) { e.preventDefault(); location.href = opts[active].href; }
    });
    form.addEventListener("submit", function (e) {
      if (form.hasAttribute("data-local")) return; // search page handles it
      e.preventDefault();
      location.href = searchUrl(input.value.trim());
    });
    document.addEventListener("click", function (e) { if (!form.contains(e.target)) close(); });
  }

  /* ---------- search page ---------- */
  function initSearchPage() {
    var page = $("#search-page");
    if (!page) return;
    var input = $("#sq"), out = $("#results"), count = $("#count");
    var sel = { topic: $("#f-topic"), year: $("#f-year"), kind: $("#f-kind"), sort: $("#f-sort") };
    var params = new URLSearchParams(location.search);
    input.value = params.get("q") || "";

    loadIndex().then(function (idx) {
      var topics = {}, years = {};
      idx.items.forEach(function (it) { topics[it.tp] = 1; years[it.y] = 1; });
      Object.keys(topics).sort().forEach(function (t) { sel.topic.add(new Option(t, t)); });
      Object.keys(years).sort().reverse().forEach(function (y) { sel.year.add(new Option(y, y)); });
      idx.kindOrder.forEach(function (k) { if (idx.kinds[k]) sel.kind.add(new Option(idx.kinds[k][0] + " (" + idx.kinds[k][1] + ")", k)); });
      ["topic", "year", "kind", "sort"].forEach(function (k) { var v = params.get(k); if (v) sel[k].value = v; });
      run();
      input.addEventListener("input", debounce(run, 120));
      ["topic", "year", "kind", "sort"].forEach(function (k) { sel[k].addEventListener("change", run); });
      page.querySelector("form").addEventListener("submit", function (e) { e.preventDefault(); run(); });

      function run() {
        var q = input.value.trim();
        var f = { topic: sel.topic.value, year: sel.year.value, kind: sel.kind.value };
        var p = new URLSearchParams();
        if (q) p.set("q", q);
        Object.keys(f).forEach(function (k) { if (f[k]) p.set(k, f[k]); });
        if (sel.sort.value !== "date") p.set("sort", sel.sort.value);
        history.replaceState(null, "", location.pathname + (p.toString() ? "?" + p : ""));
        var r = query(idx, q, f);
        var byRel = sel.sort.value === "relevance" && r.terms.length;
        r.hits.sort(byRel ? function (a, b) { return b.sc - a.sc || b.it.o - a.it.o; }
                          : function (a, b) { return b.it.o - a.it.o; });
        count.textContent = r.hits.length + (r.hits.length === 1 ? " item" : " items") +
          (q || f.topic || f.year || f.kind ? " found" : " in the archive");
        if (!r.hits.length) {
          out.innerHTML = "<div class='card'><p>Nothing found. Try fewer words, a place name (e.g. <em>Walchsing</em>), " +
            "a parcel number (<em>447/7</em>) or a date (<em>30.07.2025</em>).</p></div>";
          return;
        }
        var html = [], lastGroup = null, open = false;
        r.hits.slice(0, 400).forEach(function (h) {
          var it = h.it;
          var group = byRel ? null : it.d;
          if (!byRel && group !== lastGroup) {
            if (open) html.push("</ol>");
            html.push("<div class='group-h'><h3>Council meeting " + esc(it.d) + "</h3><a href='" + esc(ROOT + it.m) + "'>Meeting page</a></div><ol class='list'>");
            lastGroup = group; open = true;
          } else if (byRel && !open) { html.push("<ol class='list'>"); open = true; }
          var sn = snippet(it.tx, r.terms);
          html.push("<li><a class='row-link' href='" + esc(ROOT + it.p) + "'>" +
            "<span class='date'>" + esc(it.d) + "</span><span class='top-no'>TOP " + esc(it.t) + "</span>" +
            "<span class='subj'>" + highlight(it.s, r.terms) + "</span>" + badge(idx, it.k) +
            (sn ? "<span class='snip' lang='de'>" + sn + "</span>" : "") + "</a></li>");
        });
        if (open) html.push("</ol>");
        out.innerHTML = html.join("");
      }
    }).catch(function () {
      count.textContent = "The search index could not be loaded. Browse via Meetings or Topics, or use All items.";
    });
  }

  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }

  /* ---------- documents filter ---------- */
  function initDocFilter() {
    var input = $("#doc-filter");
    if (!input) return;
    var rows = $all("[data-doc]");
    var groups = $all("[data-doc-group]");
    var count = $("#doc-count");
    rows.forEach(function (r) { r._t = foldS(r.getAttribute("data-doc")); });
    input.addEventListener("input", function () {
      var ts = terms(input.value), n = 0;
      rows.forEach(function (r) {
        var ok = ts.every(function (t) { return r._t.indexOf(t) !== -1; });
        r.hidden = !ok; if (ok) n++;
      });
      groups.forEach(function (g) { g.hidden = !$all("[data-doc]:not([hidden])", g).length; });
      if (count) count.textContent = n + " of " + rows.length + " documents";
    });
  }

  /* ---------- citation copy ---------- */
  function initCite() {
    $all("[data-cite]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var text = btn.getAttribute("data-cite") + " " + location.href.split("#")[0];
        var done = function () {
          var old = btn.textContent; btn.textContent = "Copied"; setTimeout(function () { btn.textContent = old; }, 1600);
        };
        if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, fallback);
        else fallback();
        function fallback() {
          var ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
          try { document.execCommand("copy"); done(); } catch (e) { window.prompt("Copy this citation:", text); }
          ta.remove();
        }
      });
    });
  }

  /* ---------- keyboard + print ---------- */
  function initKeys() {
    document.addEventListener("keydown", function (e) {
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
      var a = document.activeElement;
      if (a && (/INPUT|TEXTAREA|SELECT/.test(a.tagName) || a.isContentEditable)) return;
      var target = $("#sq") || $("#hq") || $("#gq");
      if (target) { e.preventDefault(); target.focus(); target.select(); }
    });
    window.addEventListener("beforeprint", function () {
      $all("details.src:not([open])").forEach(function (d) { d.setAttribute("open", ""); d.setAttribute("data-print-open", ""); });
    });
    window.addEventListener("afterprint", function () {
      $all("details[data-print-open]").forEach(function (d) { d.removeAttribute("open"); d.removeAttribute("data-print-open"); });
    });
  }

  function boot() {
    initTheme();
    $all("form.omni").forEach(initOmni);
    initSearchPage();
    initDocFilter();
    initCite();
    initKeys();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
