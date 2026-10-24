"""Attach resolved locations to each item in data/items.jsonl.

Locations come from the item's own verified facts.places strings:
- resolved via data/geocoded.json (Nominatim/OSM, cached) -> with coordinates
- unresolved but genuinely local -> kept as plain-text entries (resolved=False)
- names that are not locations at all (plan sheet numbers, regions) are dropped
  (curated empty alias list in geocode.py)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")
from geocode import norm, plan_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/items.jsonl"

geo = json.loads((ROOT / "data/geocoded.json").read_text(encoding="utf-8"))
items = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]

n_items = 0
n_resolved = 0
n_text = 0
dropped = set()
for it in items:
    locs = []
    seen = set()
    for p in it.get("facts", {}).get("places", []):
        name = str(p).strip()
        if not name or name in seen:
            continue
        if not plan_for(name):  # curated "not a location"
            dropped.add(name)
            continue
        seen.add(name)
        g = geo.get(name)
        if g:
            locs.append({
                "name": name, "resolved": True,
                "display": g["display"], "lat": g["lat"], "lon": g["lon"],
                "type": g["type"], "in_aldersbach": g["in_aldersbach"],
                "precision": g.get("precision", "exact"),
            })
            n_resolved += 1
        else:
            # unresolved: keep as text. Default locality follows the first
            # attempt's flag (local-first plan -> in Aldersbach; curated
            # external aliases -> external).
            attempts = plan_for(name)
            local_default = attempts[0].get("local", True) if attempts else True
            locs.append({"name": name, "resolved": False, "in_aldersbach": local_default,
                         "precision": "unresolved"})
            n_text += 1
    locs.sort(key=lambda l: (not l.get("in_aldersbach", True), l["name"].lower()))
    it["locations"] = locs
    if locs:
        n_items += 1

with OUT.open("w", encoding="utf-8") as fh:
    for it in items:
        fh.write(json.dumps(it, ensure_ascii=False) + "\n")

print(f"items with >=1 location: {n_items}/{len(items)}; resolved entries: {n_resolved}; text-only entries: {n_text}")
print(f"dropped as non-locations: {sorted(dropped)}")
