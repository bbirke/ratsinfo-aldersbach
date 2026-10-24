/* Ratsinfo-Archiv Aldersbach - map component.
 * Hand-edited source: tools/site/map.js (copied to archive/assets/ by the build).
 *
 * Every element with [data-map] becomes a Leaflet map once it scrolls into view:
 *   data-map="all"    all pins, clustered, filterable via <select id="map-topic">
 *   data-map="items"  only the pins of the item ids in data-items (JSON array)
 * Leaflet + markercluster are vendored (vendor/) and loaded on first use only.
 * Tiles: first reachable provider of basemap.de -> OSM-DE -> CARTO -> OSM.org.
 * Data: window.ARCHIVE_GEO from data/map-data.js (tools/build_archive.py). */
(function () {
  "use strict";

  var ROOT = document.documentElement.getAttribute("data-root") || "";
  var PROVIDERS = [
    { tiles: "https://sgx.geodatenzentrum.de/wmts_basemapde/tile/1.0.0/de_basemapde_web_raster_farbe/default/GLOBAL_WEBMERCATOR/{z}/{y}/{x}.png",
      attr: 'Hintergrund &copy; GeoBasis-DE / BKG (<a href="https://www.basemap.de">basemap.de</a>) | Flurst&uuml;cke &copy; BayernAtlas (ALKIS)' },
    { tiles: "https://tile.openstreetmap.de/{z}/{x}/{y}.png",
      attr: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende | Flurst&uuml;cke &copy; BayernAtlas (ALKIS)' },
    { tiles: "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      attr: '&copy; OpenStreetMap contributors &copy; CARTO | Flurst&uuml;cke &copy; BayernAtlas (ALKIS)' },
    { tiles: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      attr: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Flurst&uuml;cke &copy; BayernAtlas (ALKIS)' }
  ];
  var CENTER = [48.587, 13.09];
  var leafletP = null, clusterP = null, providerP = null;

  function esc(s) {
    s = (s === undefined || s === null) ? "" : String(s);
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function items() { return (window.ARCHIVE_GEO && window.ARCHIVE_GEO.items) || []; }

  // resolves once the stylesheet has applied: Leaflet measures the container on creation
  function loadCss(href) {
    return new Promise(function (resolve) {
      var l = document.createElement("link"); l.rel = "stylesheet"; l.href = ROOT + href;
      l.onload = resolve; l.onerror = resolve;
      document.head.appendChild(l);
    });
  }
  function loadJs(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script"); s.src = ROOT + src; s.onload = resolve; s.onerror = reject;
      document.head.appendChild(s);
    });
  }
  function loadLeaflet() {
    if (!leafletP) {
      leafletP = Promise.all([loadCss("vendor/leaflet/leaflet.css"), loadJs("vendor/leaflet/leaflet.js")]);
      leafletP.catch(function () { leafletP = null; });
    }
    return leafletP;
  }
  function loadCluster() {
    if (!clusterP) {
      clusterP = Promise.all([
        loadCss("vendor/markercluster/MarkerCluster.css"),
        loadCss("vendor/markercluster/MarkerCluster.Default.css"),
        loadLeaflet().then(function () { return loadJs("vendor/markercluster/leaflet.markercluster.js"); })
      ]);
      clusterP.catch(function () { clusterP = null; });
    }
    return clusterP;
  }

  function probe(url) {
    return new Promise(function (resolve) {
      var img = new Image(), done = false;
      var t = setTimeout(function () { if (!done) { done = true; resolve(false); } }, 5000);
      img.onload = function () { if (!done) { done = true; clearTimeout(t); resolve(true); } };
      img.onerror = function () { if (!done) { done = true; clearTimeout(t); resolve(false); } };
      img.src = url;
    });
  }
  function pickProvider() {
    if (providerP) return providerP;
    var i = 0;
    function next() {
      if (i >= PROVIDERS.length) return Promise.resolve(null);
      var p = PROVIDERS[i++];
      return probe(p.tiles.replace("{z}", "12").replace("{y}", "1413").replace("{x}", "2199"))
        .then(function (ok) { return ok ? p : next(); });
    }
    providerP = next();
    return providerP;
  }

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }
  function pinColor(pin) {
    if (!pin.local) return cssVar("--pin-ext", "#8a8f98");
    return pin.approx ? cssVar("--pin-approx", "#c47a12") : cssVar("--pin-exact", "#1d5c63");
  }

  function makeMap(el, provider) {
    var map = L.map(el, { scrollWheelZoom: false, zoomControl: true });
    L.Icon.Default.imagePath = ROOT + "vendor/leaflet/images/";
    L.tileLayer(provider.tiles, { maxZoom: 19, attribution: provider.attr }).addTo(map);
    // wheel zoom only after the user has engaged with the map (no scroll traps)
    map.once("focus click", function () { map.scrollWheelZoom.enable(); });
    return map;
  }

  function marker(item, pin) {
    var c = pinColor(pin);
    var m = L.circleMarker([pin.lat, pin.lon], {
      color: c, weight: 2, fillColor: c, fillOpacity: 0.4, radius: pin.local ? (pin.approx ? 7 : 8) : 6
    });
    m.bindPopup(
      "<div class='bamap-popup'><b>" + esc(pin.name) + (pin.approx ? " *" : "") + "</b>" +
      "<span class='k'>" + esc(item.d) + " &middot; TOP " + esc(item.t) + "</span><br>" +
      esc(item.s).slice(0, 170) + "<br>" +
      "<a href='" + esc(ROOT + item.p) + "'>Open decision</a> &middot; " +
      "<a href='" + esc(ROOT + item.pg) + "'>Source PDF</a></div>", { maxWidth: 300 });
    return m;
  }

  function fail(host) {
    host.innerHTML = "<div class='bamap-note'><p>The map could not be loaded (offline, or the tile services are blocked). " +
      "The place links on each decision still open OpenStreetMap.</p></div>";
  }

  function mountAll(host) {
    var sel = document.getElementById("map-topic");
    var cluster = null;
    function fill() {
      var topic = sel ? sel.value : "";
      cluster.clearLayers();
      items().forEach(function (it) {
        if (topic && it.tp !== topic) return;
        (it.geo || []).forEach(function (pin) { cluster.addLayer(marker(it, pin)); });
      });
    }
    loadCluster().then(pickProvider).then(function (provider) {
      if (!provider) throw new Error("no tiles");
      host.innerHTML = "";
      var map = makeMap(host, provider);
      map.setView(CENTER, 12);
      cluster = L.markerClusterGroup({ maxClusterRadius: 38, showCoverageOnHover: false });
      fill();
      map.addLayer(cluster);
      if (sel) sel.addEventListener("change", fill);
    }).catch(function () { fail(host); });
  }

  function mountItems(host) {
    var ids;
    try { ids = JSON.parse(host.getAttribute("data-items") || "[]"); } catch (e) { ids = []; }
    var wanted = items().filter(function (it) { return ids.indexOf(it.id) !== -1; });
    if (!wanted.length) { host.hidden = true; return; }
    loadLeaflet().then(pickProvider).then(function (provider) {
      if (!provider) throw new Error("no tiles");
      host.innerHTML = "";
      var map = makeMap(host, provider);
      var pts = [];
      wanted.forEach(function (it) {
        (it.geo || []).forEach(function (pin) {
          if (host.hasAttribute("data-local-only") && !pin.local && wanted.length > 1) return;
          marker(it, pin).addTo(map);
          pts.push([pin.lat, pin.lon]);
        });
      });
      if (pts.length === 1) map.setView(pts[0], 16);
      else map.fitBounds(L.latLngBounds(pts), { padding: [28, 28], maxZoom: 16 });
    }).catch(function () { fail(host); });
  }

  function mount(host) {
    if (host._mounted) return;
    host._mounted = true;
    if (host.getAttribute("data-map") === "all") mountAll(host); else mountItems(host);
  }

  function boot() {
    if (!window.ARCHIVE_GEO) return;
    var hosts = Array.prototype.slice.call(document.querySelectorAll("[data-map]"));
    if (!hosts.length) return;
    // fill the topic filter of the overview map
    var sel = document.getElementById("map-topic");
    if (sel) {
      var topics = {};
      items().forEach(function (it) { topics[it.tp] = 1; });
      Object.keys(topics).sort().forEach(function (t) { sel.add(new Option(t, t)); });
    }
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting) { io.unobserve(e.target); mount(e.target); } });
      }, { rootMargin: "250px" });
      hosts.forEach(function (h) { io.observe(h); });
    } else {
      hosts.forEach(mount);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
