"""Probe deeper: blob listing, Nuxt API hints, aldersbach.de posts."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import ROOT, fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# --- 1. Azure blob container listing ---------------------------------------------
st, h, b = fetch("https://heimatinfo.blob.core.windows.net/public?restype=container&comp=list")
print("blob list:", st, len(b))
if st == 200:
    save("https://heimatinfo.blob.core.windows.net/public?restype=container&comp=list", "raw/azure-blob-list.xml", b, h)
    txt = b.decode("utf-8", "replace")
    names = re.findall(r"<Name>([^<]+)</Name>", txt)
    print("blobs:", len(names))
    # print with size/type from the XML
    for m in re.finditer(r"<Blob>(.*?)</Blob>", txt, re.S):
        blob = m.group(1)
        name = re.search(r"<Name>([^<]+)</Name>", blob).group(1)
        props = re.search(r"<Properties>(.*?)</Properties>", blob, re.S)
        ct = re.search(r"<Content-Type>([^<]+)</Content-Type>", blob)
        sz = re.search(r"<Content-Length>(\d+)</Content-Length>", blob)
        lm = re.search(r"<Last-Modified>([^<]+)</Last-Modified>", blob)
        print(f"  {name}  {ct.group(1) if ct else '?':<24} {int(sz.group(1)) if sz else 0:>9}  {lm.group(1) if lm else '?'}")
    nxt = re.search(r"<NextMarker>([^<]*)</NextMarker>", txt)
    print("NextMarker:", nxt.group(1) if nxt else "(none)")

# --- 2. API hints in saved HTML ---------------------------------------------------
html = (ROOT / "sources/pages/heimat-info-klosterkurier-beitraege.html").read_text(encoding="utf-8", errors="replace")
for pat in (r"https?://[a-z0-9.-]*api[a-z0-9.-]*\.[a-z]{2,}[^\"'\\ ]*", r"/api/[a-z0-9_\-/]+", r"supabase|strapi|directus|contentful|sanity|payload"):
    hits = sorted(set(re.findall(pat, html, re.I)))[:20]
    print(f"pattern {pat[:40]!r}: {hits}")

# payload links (/_payload.json etc.)
print("payload links:", sorted(set(re.findall(r"/_payload[^\"']*|/_nitro[^\"']*", html)))[:10])

# --- 3. aldersbach.de posts -------------------------------------------------------
st, h, b = fetch("https://www.aldersbach.de/wp-json/wp/v2/aktuelles?per_page=100&_fields=id,title,link,date,modified")
print("aktuelles:", st)
if st == 200:
    save("https://www.aldersbach.de/wp-json/wp/v2/aktuelles?per_page=100&_fields=id,title,link,date,modified", "aldersbach/wp-aktuelles.json", b, h)
    posts = json.loads(b.decode("utf-8"))
    for p in posts:
        t = p.get("title", {}).get("rendered", "?")
        print(f"  [{p['id']}] {p['date'][:10]} {t[:100]}  {p['link']}")

st, h, b = fetch("https://www.aldersbach.de/wp-json/wp/v2/pages?slug=gemeinderat&_fields=id,title,link,content")
print("page gemeinderat:", st)
if st == 200:
    save("https://www.aldersbach.de/wp-json/wp/v2/pages?slug=gemeinderat&_fields=id,title,link,content", "aldersbach/wp-page-gemeinderat.json", b, h)
    pages = json.loads(b.decode("utf-8"))
    if pages:
        content = pages[0].get("content", {}).get("rendered", "")
        print("  gemeinderat page content length:", len(content))
        pdfs = sorted(set(re.findall(r"https://www\.aldersbach\.de/wp-content/uploads/[^\s\"'<>]+?\.pdf", content)))
        print("  pdf links on page:", len(pdfs))
        for u in pdfs:
            print("   ", u)
