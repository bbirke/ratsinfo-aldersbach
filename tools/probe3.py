"""Probe 3: 4-2025 post content, gemeinderat page links, heimat-info API, pagination."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def show_links(label: str, html: str):
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
    srcs = re.findall(r'src=["\']([^"\']+)["\']', html)
    urls = sorted(set(hrefs + srcs))
    pdfs = [u for u in urls if ".pdf" in u.lower()]
    print(f"{label}: {len(urls)} links, {len(pdfs)} pdf")
    for u in pdfs:
        print("   PDF:", u)
    return urls


# --- 1. post 49227 (Klosterkurier 4-2025) ----------------------------------------
st, h, b = fetch("https://www.aldersbach.de/wp-json/wp/v2/aktuelles/49227?_fields=id,title,link,date,content")
print("post 49227:", st)
if st == 200:
    save("https://www.aldersbach.de/wp-json/wp/v2/aktuelles/49227?_fields=id,title,link,date,content", "aldersbach/wp-post-49227-klosterkurier-4-2025.json", b, h)
    post = json.loads(b.decode("utf-8"))
    show_links("post 49227", post.get("content", {}).get("rendered", ""))

# --- 2. gemeinderat page content --------------------------------------------------
data = json.loads((Path(__file__).resolve().parents[1] / "sources/aldersbach/wp-page-gemeinderat.json").read_text(encoding="utf-8"))
content = data[0]["content"]["rendered"]
show_links("gemeinderat page", content)
# dump a text-only excerpt to see structure
text = re.sub(r"<[^>]+>", " ", content)
text = re.sub(r"\s+", " ", text)
print("gemeinderat text head:", text[:1500])

# --- 3. heimat-info API backend ---------------------------------------------------
API = "https://heimatinfo-api-platform.azurewebsites.net"
st, h, b = fetch(f"{API}/robots.txt")
print("api robots:", st, b[:300].decode("utf-8", "replace"))
for path in ("/openapi.json", "/swagger/v1/swagger.json", "/api-docs", "/docs", "/"):
    st, h, b = fetch(API + path)
    print(f"api {path}: {st} {len(b)} {b[:160].decode('utf-8', 'replace')!r}")

# --- 4. org page + payload / pagination variants ----------------------------------
ORG = "https://www.heimat-info.de/gemeinden/aldersbach/organisationen/aldersbacher-klosterkurier"
st, h, b = fetch(ORG)
print("org page:", st, len(b))
if st == 200:
    save(ORG, "pages/heimat-info-klosterkurier-org.html", b, h)
    html = b.decode("utf-8", "replace")
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S)
    if m:
        raw = m.group(1).replace("&quot;", '"').replace("&#39;", "'").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        arr = json.loads(raw)
        strs = [e for e in arr if isinstance(e, str)]
        titles = [s for s in strs if re.search(r"Ausgabe|202[4-6]", s)]
        print("org payload strings with Ausgabe/202x:")
        for s in titles[:40]:
            print("   ", s[:120])
    show_links("org page", html)

for variant in ("beitraege?page=2", "beitraege?offset=2", "beitraege/_payload.json"):
    st, h, b = fetch(f"{ORG}/{variant}" if not variant.startswith("beitraege") else
                     "https://www.heimat-info.de/gemeinden/aldersbach/organisationen/aldersbacher-klosterkurier/" + variant)
    print(f"variant {variant}: {st} {len(b)}")
    if st == 200 and len(b) > 2000:
        save(f"{ORG}/{variant}", f"pages/probe-variant-{re.sub(r'[^a-z0-9]+', '-', variant)}.html", b, h)
