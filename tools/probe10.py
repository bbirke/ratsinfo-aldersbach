"""Query Gemeinde Aldersbach org posts; download the two known Klosterkurier PDFs."""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import net  # noqa: E402
from net import fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

API = "https://heimatinfo-api-platform.azurewebsites.net"
EXTRA = {"accept": "application/json", "callertype": "web", "callerversion": "2.15.1", "calleros": ""}


def api_get(url: str, label: str):
    req = urllib.request.Request(url, headers={**EXTRA, "User-Agent": net.UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            st, body, hdrs = r.status, r.read(), dict(r.headers)
    except Exception as e:
        print(f"{label}: FAIL {type(e).__name__} {e}")
        return None
    time.sleep(0.2)
    print(f"{label}: {st} {len(body)} B")
    if st == 200 and body:
        save(url, f"raw/api-{label}.json", body, hdrs)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None
    return None


COMMUNE_ORG = "107975a1-f7ec-41fb-8907-2f5c9cfae3c3"
for page in range(0, 3):
    data = api_get(f"{API}/organizations/{COMMUNE_ORG}/posts?pageIndex={page}&pageSize=50", f"commune-org-posts-{page}")
    if data is None:
        break
    posts = data.get("data") if isinstance(data, dict) else data
    if not isinstance(posts, list) or not posts:
        break
    print(f"page {page}: {len(posts)} posts")
    for p in posts:
        pdfs = [a.get("filename", "") for a in (p.get("attachments") or []) if (a.get("filename", "") or "").lower().endswith(".pdf")]
        print(f"  {p.get('createdOn', '')[:10]}  {p.get('title', '')[:70]:<70} pdf={pdfs}")

# download the two known Klosterkurier PDFs
KK = {
    "klosterkurier-2026-02.pdf": "https://heimatinfo.blob.core.windows.net/public/de86e7a0-1efa-4835-962f-1ff6c26e0b9a.pdf",
    "klosterkurier-2026-03.pdf": "https://heimatinfo.blob.core.windows.net/public/ce5180c3-1219-415c-80b3-15f5d211e247.pdf",
}
for fname, url in KK.items():
    rec = net.already_saved(url)
    if rec:
        print("already saved:", fname)
        continue
    st, h, b = fetch(url)
    print(fname, st, len(b), h.get("Content-Type"))
    if st == 200 and b[:4] == b"%PDF":
        save(url, f"klosterkurier/{fname}", b, h)
    else:
        print("  NOT A PDF, head:", b[:60])
