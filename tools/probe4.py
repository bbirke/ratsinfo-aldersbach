"""Probe 4: post page HTML, JS bundle API endpoints, Wayback CDX snapshots."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# --- a. public post page for Klosterkurier 4-2025 ---------------------------------
POST_URL = "https://www.aldersbach.de/aktuelles/aldersbacher-klosterkurier-offizielles-informationsblatt-der-gemeinde-aldersbach-ausgabe-4-2025/"
st, h, b = fetch(POST_URL)
print("post page:", st, len(b))
if st == 200:
    save(POST_URL, "pages/aldersbach-post-klosterkurier-4-2025.html", b, h)
    html = b.decode("utf-8", "replace")
    urls = sorted(set(re.findall(r'https?://[^\s"\'<>]+', html)))
    pdfs = [u for u in urls if ".pdf" in u.lower() or "blob" in u.lower()]
    print("pdf/blob urls on post page:")
    for u in pdfs:
        print("   ", u)
    # also relative pdf links
    rel = sorted(set(re.findall(r'href="([^"]+\.pdf[^"]*)"', html)))
    for u in rel:
        print("   REL:", u)

# --- b. JS bundles: find API endpoints --------------------------------------------
list_html = (Path(__file__).resolve().parents[1] / "sources/pages/heimat-info-klosterkurier-beitraege.html").read_text(encoding="utf-8", errors="replace")
scripts = sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', list_html)))
print(f"script tags: {len(scripts)}")
for s in scripts:
    print("   ", s[:160])

checked = 0
for s in scripts:
    if "/_nuxt/" not in s:
        continue
    url = "https://www.heimat-info.de" + s if s.startswith("/") else s
    st, h, b = fetch(url)
    checked += 1
    if st != 200:
        continue
    js = b.decode("utf-8", "replace")
    hits = set()
    if "azurewebsites" in js:
        for m in re.finditer(r'.{120}azurewebsites.{240}', js):
            hits.add(m.group(0))
        print(f"--- {s} ({len(js)} bytes) azurewebsites context:")
        for x in sorted(hits)[:6]:
            print("   ", x.replace("\n", " ")[:380])
    endpoints = sorted(set(re.findall(r'"/(?:beitrag|organization|commune|attachment|media|file)[a-z]*[^"]{0,60}"', js, re.I)))[:30]
    if endpoints:
        print(f"--- {s}: endpoint-ish strings: {endpoints[:20]}")
    if checked >= 8:
        break

# --- c. Wayback CDX ---------------------------------------------------------------
CDX = (
    "http://web.archive.org/cdx/search/cdx?"
    "url=heimat-info.de/gemeinden/aldersbach/organisationen/aldersbacher-klosterkurier/beitraege"
    "&output=json&from=2025&to=2027&filter=statuscode:200&collapse=timestamp:6&limit=50"
)
st, h, b = fetch(CDX)
print("wayback cdx:", st)
if st == 200:
    save(CDX, "raw/wayback-cdx-beitraege.json", b, h)
    rows = json.loads(b.decode("utf-8"))
    for r in rows[:1]:
        print("  header:", r)
    for r in rows[1:]:
        print(f"  {r[1]} {r[3]} {r[4]}")
