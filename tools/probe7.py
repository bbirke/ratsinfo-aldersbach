"""Probe 7: CDX full URLs, sitemap, all-bundle API grep, paced wayback retries."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import net  # noqa: E402
from net import ROOT, fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
P = ROOT / "sources/pages"

# 1. full CDX originals
rows = json.loads((ROOT / "sources/raw/wayback-aldersbach-kk.json").read_text(encoding="utf-8"))
print("=== saved CDX originals ===")
for r in rows:
    if isinstance(r, list) and len(r) > 6:
        print(f"{r[1]}  {r[2]}  [{r[3]}] {r[4]}")

# 2. sitemap
for sm in ("https://www.heimat-info.de/sitemap.xml", "https://www.heimat-info.de/sitemap_index.xml"):
    st, h, b = fetch(sm)
    print(f"sitemap {sm}: {st} {len(b)}")
    if st == 200 and len(b) > 100:
        txt = b.decode("utf-8", "replace")
        locs = re.findall(r"<loc>([^<]+)</loc>", txt)
        kk = [u for u in locs if "beitrag" in u or "klosterkurier" in u]
        print(f"  locs: {len(locs)} klosterkurier-ish: {len(kk)}")
        for u in kk[:40]:
            print("   ", u)
        if len(locs) > 0 and len(kk) == 0:
            print("  head:", txt[:400])
        save(sm, f"raw/sitemap-{re.sub(r'[^a-z0-9]+', '-', sm.split('//', 1)[1])}.xml", b, h)

# 3. all bundles: api call paths
list_html = (P / "heimat-info-klosterkurier-beitraege.html").read_text(encoding="utf-8", errors="replace")
bundles = sorted(set(re.findall(r"/_nuxt/[A-Za-z0-9._\-]+\.js", list_html)))
print(f"=== bundle scan: {len(bundles)} ===")
pats = (
    r'apiBase[^;]{0,80}',
    r'["`\'/](contributions|beitraege|attachments|media|documents|organizations)[a-z\-]*["`\'?]',
    r'\$fetch[^;]{0,120}',
)
interesting = {}
for i, bpath in enumerate(bundles):
    st, h, b = fetch("https://www.heimat-info.de" + bpath)
    if st != 200:
        continue
    js = b.decode("utf-8", "replace")
    marks = []
    if "contributions" in js or "attachments" in js:
        for m in re.finditer(r'.{60}(?:contributions|attachments).{100}', js):
            marks.append(m.group(0).replace("\n", " "))
    if marks:
        interesting[bpath] = sorted(set(marks))[:8]
        print(f"HIT {bpath} ({len(js)}B)")
        for x in interesting[bpath]:
            print("     ", x[:260])
    if (i % 25) == 0:
        print(f"  ...scanned {i+1}/{len(bundles)}")
print(f"bundles with hits: {len(interesting)}")

# 4. paced wayback retries
time.sleep(5)
for label, cdx in (
    ("kk-prefix", "http://web.archive.org/cdx/search/cdx?url=heimat-info.de%2Fgemeinden%2Faldersbach%2Forganisationen%2Faldersbacher-klosterkurier*&output=json&limit=100"),
):
    st, h, b = fetch(cdx)
    print(f"wayback {label}: {st} {len(b)}")
    if st == 200 and len(b) > 4:
        save(cdx, f"raw/wayback-{label}.json", b, h)
        rows = json.loads(b.decode("utf-8"))
        for r in rows:
            if isinstance(r, list) and len(r) > 6:
                print("   ", r[1], r[2][:110], r[3], r[4])
