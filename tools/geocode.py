"""Geocode the unique place strings of the archive via Nominatim (OpenStreetMap).

Politeness: >= 1.5 s between requests, identifying User-Agent, one-time lookups
cached in data/geocache.json so re-runs never re-query.

Resolution strategy per place string:
1. curated alias -> explicit query plan (Baugebiete/plan names/facilities)
2. generic: "<name>, Aldersbach" inside a bounding box around the municipality
3. fallback: "<name>" unbounded (neighbouring towns, firm seats)

Output: data/geocoded.json mapping raw name -> record or None.
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
UA = "ratsinfo-aldersbach-archive/0.1 (citizen archive of council decisions; contact: local operator)"
VIEWBOX = "13.00,48.63,13.20,48.52"  # left,top,right,bottom around Gemeinde Aldersbach
BA_BACKEND = "https://services.atlas.bayern.de"
R_MERC = 6378137.0


def mercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """EPSG:3857 -> WGS84 lon/lat."""
    lon = math.degrees(x / R_MERC)
    lat = math.degrees(2 * math.atan(math.exp(y / R_MERC)) - math.pi / 2)
    return lon, lat


def ba_cp(searchtext: str) -> list[dict]:
    """BayernAtlas cadastral parcel search; returns raw hits."""
    url = f"{BA_BACKEND}/search/type/cp/searchText/" + urllib.parse.quote(searchtext)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def ba_loc(term: str) -> list[dict]:
    """BayernAtlas location search (POST); returns raw hits."""
    url = f"{BA_BACKEND}/search/type/location/searchText"
    req = urllib.request.Request(
        url,
        data=json.dumps({"term": term}).encode("utf-8"),
        headers={"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def resolve_ba_cp(searchtext: str) -> dict | None:
    try:
        hits = ba_cp(searchtext)
    except Exception as e:
        print(f"  ba_cp failed for {searchtext!r}: {e}")
        return None
    time.sleep(1.2)
    if not hits:
        return None
    import re

    wanted = searchtext.split()
    gem, num = wanted[0], " ".join(wanted[1:]).replace(" ", "/") if len(wanted) > 1 else ""
    best = None
    for h in hits:
        label = h.get("attrs", {}).get("label", "")
        m = re.match(r"^([^(]+)\s*\((\d+)\),\s*(\d+(?:\s*/\s*\d+)?)\s+-", label)
        if m and (num.replace(" ", "") in m.group(3).replace(" ", "")):
            best = h
            break
    hit = best or hits[0]
    a = hit.get("attrs", {})
    x, y = a.get("coordinate") or (None, None)
    if x is None:
        return None
    lon, lat = mercator_to_wgs84(x, y)
    return {"display": a.get("label", ""), "lat": lat, "lon": lon,
            "class": "landparcel", "type": "Flurstück (BayernAtlas/ALKIS)"}


def resolve_ba_loc(term: str, expect_local: bool = True) -> dict | None:
    try:
        hits = ba_loc(term)
    except Exception as e:
        print(f"  ba_loc failed for {term!r}: {e}")
        return None
    time.sleep(1.2)
    if not hits:
        return None
    a = hits[0].get("attrs", {})
    label = a.get("label", "")
    coord = a.get("coordinate")
    if not coord:
        return None
    lon, lat = mercator_to_wgs84(*coord)
    return {"display": label.replace("<b>", "").replace("</b>", ""),
            "lat": lat, "lon": lon,
            "class": "location", "type": "Adresse/Flur (BayernAtlas)"}


def q(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def nominatim(query: str, bounded: bool, cc: str | None = "de") -> dict | None:
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": "1",
        "accept-language": "de",
    }
    if cc:
        params["countrycodes"] = cc
    if bounded:
        params["viewbox"] = VIEWBOX
        params["bounded"] = "1"
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    hits = q(url)
    time.sleep(1.5)
    if not hits:
        return None
    h = hits[0]
    return {
        "display": h.get("display_name"),
        "lat": float(h["lat"]),
        "lon": float(h["lon"]),
        "class": h.get("class"),
        "type": h.get("type"),
    }


# curated aliases: raw place string -> list of attempts
# attempt = {query, bounded, local, precision, cc?}; local=True marks the result
# as inside Gemeinde Aldersbach regardless of display; cc=None disables the
# country filter; empty list = "not a location, drop entirely".
A: dict[str, list] = {
    "Passau": [{"query": "Passau", "bounded": False, "local": False, "precision": "exact"}],
    "Aldersbach": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "exact"}],
    "Schwaig X": [{"query": "Abt-Zanker-Straße, Aldersbach", "bounded": True, "local": True, "precision": "approximate — Baugebiet, Erschließung über Abt-Zanker-Straße"}],
    "Abt-Zanker-Straße": [{"query": "Abt-Zanker-Straße, Aldersbach", "bounded": True, "local": True, "precision": "exact"}],
    "Ortskern Aldersbach": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Ortskern (village centre)"}],
    "Umspannwerk": [{"ba_cp": "Pörndorf 507", "local": True, "precision": "approximate — Flurstück 507, Gemarkung Pörndorf (Plan ist eine Teilfläche)"}],
    "SO Energie – Batteriespeicheranlage am Umspannwerk": [{"ba_cp": "Pörndorf 507", "local": True, "precision": "approximate — Flurstück 507, Gemarkung Pörndorf (Plan ist eine Teilfläche)"}],
    "SO Golf": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Gemeindegebiet"}],
    "Uttigkofen-Eggerting": [{"ba_cp": "Haidenburg 1250", "local": True, "precision": "exact — Flurstück 1250, Gemarkung Haidenburg"}],
    "GE Uttigkofen-Eggerting": [{"ba_cp": "Haidenburg 1250", "local": True, "precision": "exact — Flurstück 1250, Gemarkung Haidenburg"}],
    "Gewerbegebiet Uttigkofen": [{"ba_cp": "Haidenburg 1250", "local": True, "precision": "exact — Flurstück 1250, Gemarkung Haidenburg"}],
    "Uttigkofen-Haidenburg": [{"query": "Haidenburg, Aldersbach", "bounded": True, "local": True, "precision": "approximate"}],
    "Gemarkung Haidenburg": [{"query": "Haidenburg, Aldersbach", "bounded": True, "local": True, "precision": "exact"}],
    "Haidenburg/ Häusling": [{"ba_cp": "Haidenburg 23 17", "local": True, "precision": "approximate — B-Plan umfasst die Flurstücke 23/17, 23/7 und 25/1"}],
    "Häusling": [{"query": "Haidenburg, Aldersbach", "bounded": True, "local": True, "precision": "approximate — Ortsteil Häusling (bei Haidenburg)"}],
    "Aldersbach Nord": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Gewerbegebiet im Norden des Gemeindegebiets"}],
    "Aldersbach-Nord": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Gewerbegebiet im Norden des Gemeindegebiets"}],
    "Kloster Aldersbach": [{"query": "Kloster Aldersbach", "bounded": False, "local": True, "precision": "exact"}],
    "Kloster": [{"query": "Kloster Aldersbach", "bounded": False, "local": True, "precision": "approximate"}],
    "Klostergarten": [{"query": "Kloster Aldersbach", "bounded": False, "local": True, "precision": "approximate"}],
    "Biergarten": [{"query": "Kloster Aldersbach", "bounded": False, "local": True, "precision": "approximate — Biergarten am Klosterareal"}],
    "Waschhaus": [{"query": "Kloster Aldersbach", "bounded": False, "local": True, "precision": "approximate — ehemaliges Waschhaus im Klosterareal"}],
    "Brauereiparkplatz": [{"query": "Brauerei Aldersbach", "bounded": False, "local": True, "precision": "approximate"},
                          {"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Brauereiparkplatz"}],
    "Kläranlage": [{"query": "Kläranlage Aldersbach", "bounded": True, "local": True, "precision": "exact"},
                   {"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Kläranlage im Gemeindegebiet"}],
    "Grundschule Aldersbach": [{"query": "Grundschule Aldersbach", "bounded": True, "local": True, "precision": "exact"}],
    "Friedhof St. Peter": [{"query": "Friedhof Aldersbach", "bounded": True, "local": True, "precision": "approximate — Friedhof St. Peter"},
                           {"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Friedhof St. Peter"}],
    "Waldstadion": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Waldstadion (FC Aldersbach)"}],
    "Turnhalle": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Turnhalle in Aldersbach"}],
    "Volksfestplatz": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Volksfestplatz in Aldersbach"}],
    "Verkehrsübungsplatz": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate"}],
    "Waldspielplatz": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Waldspielplatz"}],
    "Spielplatzes am Hang": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Spielplatz am Hang (Zisterzienserstraße)"}],
    "Dorfanger": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Ortsmitte/Dorfanger"}],
    "Waldschulsiedlung": [{"query": "Robert-Daiser-Straße, Aldersbach", "bounded": True, "local": True, "precision": "approximate — Waldschulsiedlung"}],
    "St. Peter": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Ortsbereich „St. Peter“"}],
    "Sankt Peter": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Ortsbereich „St. Peter“"}],
    "„St. Peter“": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Ortsbereich „St. Peter“"}],
    "Waldschule": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Ortsbereich „Waldschule“"}],
    "„Waldschule“": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Ortsbereich „Waldschule“"}],
    "„Schwaig“": [{"query": "Schwaig, Aldersbach", "bounded": True, "local": True, "precision": "approximate — Ortsbereich „Schwaig“"}],
    "Apostelbrücke": [{"query": "Walchsing, Aldersbach", "bounded": True, "local": True, "precision": "approximate — Apostelbrücke in Walchsing"}],
    "Rindellohbachbrücke": [{"query": "Kriestorf, Aldersbach", "bounded": True, "local": True, "precision": "approximate — Rindellohbachbrücke in Kriestorf"}],
    "Drucksteigerungspumpwerk Wifling": [{"query": "Wifling, Aldersbach", "bounded": True, "local": True, "precision": "approximate"}],
    "Aldersbach-Kollberg": [{"query": "Kollberg, Aldersbach", "bounded": True, "local": True, "precision": "exact"},
                            {"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Ortsteil Kollberg"}],
    "SO Photovoltaikpark Wetzstein": [{"query": "Wetzstein, Aldersbach", "bounded": True, "local": True, "precision": "approximate"}],
    "So Photovoltaikpark Edelsbrunn": [{"ba_cp": "Aldersbach 611", "local": True, "precision": "exact — Flurstück 611, Gemarkung Aldersbach"}],
    "SO Photovoltaikpark Edelsbrunn": [{"ba_cp": "Aldersbach 611", "local": True, "precision": "exact — Flurstück 611, Gemarkung Aldersbach"}],
    "GE Linda": [{"query": "Linda, Vilshofen an der Donau", "bounded": False, "local": False, "precision": "approximate — GE „Linda“ der Stadt Vilshofen"},
                 {"query": "Vilshofen an der Donau", "bounded": False, "local": False, "precision": "approximate — GE „Linda“ der Stadt Vilshofen"}],
    "Lindahof III": [{"query": "Linda, Vilshofen an der Donau", "bounded": False, "local": False, "precision": "approximate — Lindahof-Pläne der Stadt Vilshofen"},
                     {"query": "Vilshofen an der Donau", "bounded": False, "local": False, "precision": "approximate — Lindahof-Pläne der Stadt Vilshofen"}],
    "Deponie Hiendlöd": [{"query": "Hiendlöd, Aldersbach", "bounded": True, "local": True, "precision": "exact"}],
    "St 2083": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Staatsstraße 2083 im Gemeindegebiet"}],
    "ST 2108": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Staatsstraße 2108 im Gemeindegebiet"}],
    "Vivilo-/ Urbanstraße": [{"query": "Urbanstraße, Aldersbach", "bounded": True, "local": True, "precision": "approximate — Kreuzungsbereich Vivilo-/Urbanstraße"}],
    "Kreuzungsbereich der Ortsstraßen": [{"query": "Aldersbach", "bounded": False, "local": True, "precision": "approximate — Kreuzungsbereich der Ortsstraßen"}],
    "Hauptplatz": [{"query": "Pörndorf, Aldersbach", "bounded": True, "local": True, "precision": "approximate — Hauptplatz Pörndorf"}],
    "Bahnhofsstraße": [{"ba_cp": "Aldersbach 447 7", "local": True, "precision": "exact — Flurstück 447/7, Gemarkung Aldersbach (freie Fläche)"}],
    "Unterfeld": [{"query": "Vilshofen an der Donau", "bounded": False, "local": False, "precision": "approximate — B-Plan „Unterfeld“ der Stadt Vilshofen"}],
    "WA am Zeitlarner Berg II": [{"query": "Zeitlarner Berg", "bounded": False, "local": False, "precision": "approximate — B-Plan der Stadt Vilshofen"}],
    "Industrie- und Gewerbegebiet Esterndorf": [{"query": "Esterndorf, Landkreis Passau", "bounded": False, "local": False, "precision": "approximate — GE Esterndorf (Gemeinde Roßbach)"}],
    "SO Solarpark Dorf II": [{"query": "Vilshofen an der Donau", "bounded": False, "local": False, "precision": "approximate — B-Plan „SO Solarpark Dorf II“ der Stadt Vilshofen"}],
    "Vilshofen": [{"query": "Vilshofen an der Donau", "bounded": False, "local": False, "precision": "exact"}],
    "Hirschbach": [{"query": "Hirschbach, Landkreis Passau", "bounded": False, "local": False, "precision": "exact"}],
    "Pirach": [{"query": "Pirach, Vilshofen an der Donau", "bounded": False, "local": False, "precision": "exact"}],
    "Roßbach": [{"query": "Roßbach, Landkreis Passau", "bounded": False, "local": False, "precision": "exact"}],
    "Wettmannstätten": [{"query": "Wettmannstätten", "bounded": False, "local": False, "precision": "exact", "cc": None}],
    "Bebauungsplanes Alter Sportplatz": [],
    "Deckblatt Nr. 35": [],
    "ILE Klosterwinkel": [],
    "Passauer Land": [],
    "Emmersdorfer Straße": [{"ba_loc": "Emmersdorfer Straße", "local": True, "precision": "exact — Emmersdorfer Straße, Gemarkung Haidenburg"}],
    "Seier": [{"ba_loc": "Seier Aldersbach", "local": True, "precision": "exact"}],
    "Anwesen Vogler": [{"ba_loc": "Anwesen Vogler Aldersbach", "local": True, "precision": "approximate — Anwesen Vogler"}],
    "Kramersepp": [{"ba_loc": "Kramersepp Aldersbach", "local": True, "precision": "exact — Gemeindeverbindungsstraße Kramersepp"}],
    "Schöfbachstraße": [{"ba_loc": "Schöfbachstraße Aldersbach", "local": True, "precision": "exact"}],
    "Schartnergasse": [{"ba_loc": "Schartnergasse Aldersbach", "local": True, "precision": "exact"}],
    "Landkreis Passau": [],
}


def norm(s: str) -> str:
    return s.replace("„", "").replace("“", "").replace("‘", "").replace("’", "").strip()


def plan_for(name: str) -> list[dict]:
    """Return a list of attempts: {query, bounded, local, precision, cc}."""
    name_n = norm(name)
    if name_n in A:
        return [dict(a) for a in A[name_n]]
    # generic: first inside the municipality, then anywhere
    return [
        {"query": f"{name_n}, Aldersbach", "bounded": True, "local": True, "precision": "exact"},
        {"query": name_n, "bounded": False, "local": False, "precision": "exact"},
    ]


def main():
    cache_path = ROOT / "data/geocache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    places = json.loads((ROOT / "data/places_unique.json").read_text(encoding="utf-8"))
    names = [p["name"] for p in places]
    out_path = ROOT / "data/geocoded.json"
    out = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}

    for i, name in enumerate(names):
        if name in out:
            continue
        result = None
        for att in plan_for(name):
            if "ba_cp" in att:
                cq = f"ba:cp:{att['ba_cp']}"
                if cq not in cache:
                    try:
                        cache[cq] = resolve_ba_cp(att["ba_cp"])
                    except Exception as e:
                        print(f"  ba_cp request failed for {cq!r}: {e}")
                        cache[cq] = None
                hit = cache.get(cq)
            elif "ba_loc" in att:
                cq = f"ba:loc:{att['ba_loc']}"
                if cq not in cache:
                    try:
                        cache[cq] = resolve_ba_loc(att["ba_loc"])
                    except Exception as e:
                        print(f"  ba_loc request failed for {cq!r}: {e}")
                        cache[cq] = None
                hit = cache.get(cq)
            else:
                cc = att.get("cc", "de")
                cq = f"{att['query']}|bounded={att['bounded']}" + (f"|cc={cc}" if cc != "de" else "")
                if cq not in cache:
                    try:
                        cache[cq] = nominatim(att["query"], att["bounded"], att.get("cc", "de"))
                    except Exception as e:
                        print(f"  request failed for {cq!r}: {e}")
                        cache[cq] = None
                hit = cache.get(cq)
                # bounded attempts must land inside the Aldersbach viewbox, else
                # reject the hit (guards against fuzzy matches far away)
                if hit and att["bounded"] and not (13.00 <= hit["lon"] <= 13.20 and 48.52 <= hit["lat"] <= 48.63):
                    hit = None
            if hit:
                local = att["local"] or ("Aldersbach" in (hit.get("display") or ""))
                result = {
                    "display": hit["display"],
                    "lat": hit["lat"],
                    "lon": hit["lon"],
                    "class": hit["class"],
                    "type": hit["type"],
                    "in_aldersbach": local,
                    "precision": att.get("precision") or "exact",
                    "query": att.get("ba_cp") or att.get("ba_loc") or att.get("query"),
                }
                break
        out[name] = result
        status = "OK " if result else "-- "
        extra = f" -> {result['display'][:60]} [{result['type']}]" if result else " unresolved"
        print(f"{status}{i + 1:>3}/{len(names)}  {name[:45]:<45}{extra}")
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    n_ok = sum(1 for v in out.values() if v)
    print(f"\ngeocoded {n_ok}/{len(out)} place strings -> {out_path}")


if __name__ == "__main__":
    main()
