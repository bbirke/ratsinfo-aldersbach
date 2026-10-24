"""Probe 5: deeper greps of saved HTML, all nuxt bundles, media titles, wayback retries."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import ROOT, fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
P = ROOT / "sources/pages"

# --- 1. broad grep of the 4-2025 post page ----------------------------------------
html = (P / "aldersbach-post-klosterkurier-4-2025.html").read_text(encoding="utf-8", errors="replace")
for pat, label in ((r"[A-Za-z0-9_\-/.]+\.pdf", "pdf-like"),
                   (r"blob\.core\.windows\.net[^\"'<> ]*", "blob"),
                   (r"data-settings=\"[^\"]{0,300}", "elementor-settings"),
                   (r"uploads/[0-9]{4}/[0-9]{2}/[A-Za-z0-9_\-.%]+", "uploads")):
    hits = sorted(set(re.findall(pat, html, re.I)))
    print(f"{label}: {len(hits)}")
    for x in hits[:30]:
        print("   ", x[:200])

# --- 2. all nuxt bundles -----------------------------------------------------------
list_html = (P / "heimat-info-klosterkurier-beitraege.html").read_text(encoding="utf-8", errors="replace")
bundles = sorted(set(re.findall(r"/_nuxt/[A-Za-z0-9._\-]+\.js", list_html)))
print(f"nuxt bundles referenced: {len(bundles)}")
found_api = []
for i, bpath in enumerate(bundles):
    st, h, b = fetch("https://www.heimat-info.de" + bpath)
    if st != 200:
        print(f"  {bpath}: {st}")
        continue
    js = b.decode("utf-8", "replace")
    if "azurewebsites" in js or "beitrag" in js.lower() or "attachment" in js.lower():
        m = re.findall(r'.{80}azurewebsites.{160}', js)
        eps = sorted(set(re.findall(r'[\'"`]((?:/|https://heimatinfo-api)[a-z0-9\-_/.$\{\}]{2,80})[\'"`]', js)))[:40]
        print(f"  {bpath} ({len(js)}B): azure_ctx={len(m)} endpoints={eps[:25]}")
        for x in sorted(set(m))[:4]:
            print("      ", x.replace("\\n", " ")[:300])
        found_api.append(bpath)
    if i > 40:
        break

# --- 3. all media titles from saved JSON -------------------------------------------
titles = []
for p in sorted((ROOT / "sources/aldersbach").glob("wp-media-page*.json")):
    data = json.loads(p.read_text(encoding="utf-8"))
    for mrec in data:
        t = mrec.get("title", {}).get("rendered", "?") if isinstance(mrec.get("title"), dict) else str(mrec.get("title"))
        titles.append((mrec.get("date", "")[:10], t, mrec.get("source_url")))
print(f"media items: {len(titles)}")
for d, t, u in sorted(titles):
    print(f"  {d}  {t[:80]:<80} {u}")

# --- 5. archiv.aldersbach.de (old Joomla site) -------------------------------------
st, h, b = fetch("https://archiv.aldersbach.de/robots.txt")
print("archiv robots:", st, b[:400].decode("utf-8", "replace"))
st, h, b = fetch("https://archiv.aldersbach.de/")
print("archiv home:", st, len(b))
if st == 200:
    save("https://archiv.aldersbach.de/", "pages/archiv-aldersbach-home.html", b, h)
    ahtml = b.decode("utf-8", "replace")
    links = sorted(set(re.findall(r'href="([^"]+)"', ahtml)))
    kk = [u for u in links if "klosterkurier" in u.lower()]
    print("klosterkurier links on archiv home:")
    for u in kk:
        print("   ", u)
    pdfs = [u for u in links if ".pdf" in u.lower()]
    print("pdf links on archiv home:", pdfs[:20])

# --- 6. single heimat-info post page ------------------------------------------------
st, h, b = fetch("https://www.heimat-info.de/beitraege/5445edf4-575f-4a2a-9767-4282ab23c1ef")
print("single post page:", st, len(b))
if st == 200:
    save("https://www.heimat-info.de/beitraege/5445edf4-575f-4a2a-9767-4282ab23c1ef", "pages/heimat-info-post-3-2026.html", b, h)
    phtml = b.decode("utf-8", "replace")
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', phtml, re.S)
    if m:
        raw = m.group(1).replace("&quot;", '"').replace("&#39;", "'").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        arr = json.loads(raw)
        strs = [s for s in arr if isinstance(s, str)]
        blob = sorted(set(re.findall(r"heimatinfo\.blob\.core\.windows\.net/public/[0-9a-f\-]{36}\.\w+", raw)))
        print("  post payload blob urls:", blob)
        print("  post payload strings (files?):", [s for s in strs if ".pdf" in s.lower() or ".png" in s.lower()][:10])
        uuids = sorted(set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", raw)))
        print(f"  post payload uuids: {len(uuids)}", uuids[:12])

# --- 4. wayback retries -------------------------------------------------------------
for label, cdx in (
    ("org-page", "http://web.archive.org/cdx/search/cdx?url=heimat-info.de%2Fgemeinden%2Faldersbach%2Forganisationen%2Faldersbacher-klosterkurier*&output=json&limit=60"),
    ("domain-klosterkurier", "http://web.archive.org/cdx/search/cdx?url=heimat-info.de&matchType=domain&filter=original:.*klosterkurier.*&output=json&limit=60&collapse=urlkey"),
    ("aldersbach-kk", "http://web.archive.org/cdx/search/cdx?url=aldersbach.de&matchType=domain&filter=original:.*klosterkurier.*&output=json&limit=60&collapse=urlkey"),
):
    st, h, b = fetch(cdx)
    print(f"wayback {label}: {st} {len(b)}")
    if st == 200 and len(b) > 4:
        save(cdx, f"raw/wayback-{label}.json", b, h)
        rows = json.loads(b.decode("utf-8"))
        for r in rows[:60]:
            if isinstance(r, list) and len(r) > 4:
                print("   ", r[1], r[2][:60], r[3][:70])
