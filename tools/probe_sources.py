"""Probe both source sites and save raw responses into sources/."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import RAW, ROOT, fetch, save  # noqa: E402

# --- 1. robots.txt of heimat-info.de -------------------------------------------------
st, h, b = fetch("https://www.heimat-info.de/robots.txt")
print("robots heimat-info:", st, b[:600].decode("utf-8", "replace"))

# --- 2. Klosterkurier issue list page ------------------------------------------------
LIST_URL = (
    "https://www.heimat-info.de/gemeinden/aldersbach/organisationen/"
    "aldersbacher-klosterkurier/beitraege"
)
st, h, b = fetch(LIST_URL)
print("liste:", st, len(b), "bytes")
html = b.decode("utf-8", "replace")
save(LIST_URL, "pages/heimat-info-klosterkurier-beitraege.html", b, h)

blob_pdfs = sorted(set(re.findall(r"https://heimatinfo\.blob\.core\.windows\.net/public/[0-9a-f\-]{36}\.pdf", html)))
print(f"blob PDF urls in page: {len(blob_pdfs)}")
for u in blob_pdfs:
    print("  ", u)

# embedded payload scripts (Nuxt)
payloads = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S)
print(f"application/json script blocks: {len(payloads)}")
for i, p in enumerate(payloads):
    print(f"--- payload {i} len={len(p)} head: {p[:200]!r}")
nuxt = re.findall(r"window\.__NUXT__\s*=\s*", html)
print("window.__NUXT__ markers:", len(nuxt))

# any other blob references (non-pdf)?
other = sorted(set(re.findall(r"heimatinfo\.blob\.core\.windows\.net/public/[0-9a-f\-]{36}", html)))
print(f"distinct blob ids: {len(other)}")

# --- 3. aldersbach.de REST API -------------------------------------------------------
def get_json(url: str):
    st, h, b = fetch(url)
    try:
        return st, h, json.loads(b.decode("utf-8"))
    except Exception:
        return st, h, b

MEDIA = "https://www.aldersbach.de/wp-json/wp/v2/media?mime_type=application/pdf&per_page=100&_fields=id,title,source_url,date,caption&page={page}"
all_media = []
for page in (1, 2):
    st, h, data = get_json(MEDIA.format(page=page))
    print(f"media page {page}: status={st} total={h.get('x-wp-total')} pages={h.get('x-wp-totalpages')}")
    if isinstance(data, list):
        all_media.extend(data)
        save(MEDIA.format(page=page), f"aldersbach/wp-media-page{page}.json", json.dumps(data, ensure_ascii=False).encode(), h)
print(f"media total collected: {len(all_media)}")
for m in all_media:
    title = m.get("title", {}).get("rendered", "?") if isinstance(m.get("title"), dict) else str(m.get("title"))
    print(f"  [{m.get('id')}] {m.get('date', '')[:10]} {title[:90]}  {m.get('source_url')}")

POSTS = "https://www.aldersbach.de/wp-json/wp/v2/aktuelles?per_page=100&_fields=id,title,link,date,modified,excerpt"
st, h, posts = get_json(POSTS)
print(f"aktuelles: status={st} total={h.get('x-wp-total')}")
if isinstance(posts, list):
    save(POSTS, "aldersbach/wp-aktuelles.json", json.dumps(posts, ensure_ascii=False).encode(), h)
    for p in posts:
        title = p.get("title", {}).get("rendered", "?") if isinstance(p.get("title"), dict) else str(p.get("title"))
        print(f"  [{p.get('id')}] {p.get('date', '')[:10]} {title[:100]}  {p.get('link')}")

st, h, pages = get_json("https://www.aldersbach.de/wp-json/wp/v2/pages?slug=gemeinderat&_fields=id,title,link,content")
print(f"page gemeinderat: status={st} n={len(pages) if isinstance(pages, list) else '?'}")
if isinstance(pages, list) and pages:
    save("https://www.aldersbach.de/wp-json/wp/v2/pages?slug=gemeinderat", "aldersbach/wp-page-gemeinderat.json", json.dumps(pages, ensure_ascii=False).encode(), h)
