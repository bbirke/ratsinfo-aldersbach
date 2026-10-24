"""Query the heimat-info API for all Klosterkurier posts and attachments."""
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
ORG = "c6e08731-9297-4ca4-943a-02beed3f4bb6"
EXTRA = {"accept": "application/json", "callertype": "web", "callerversion": "2.15.1", "calleros": ""}


def api_get(path: str, label: str):
    url = API + path
    req = urllib.request.Request(url, headers={**EXTRA, "User-Agent": net.UA})
    host = "heimatinfo-api-platform.azurewebsites.net"
    now = time.monotonic()
    wait = net._last_hit.get(host, 0.0) + net.MIN_INTERVAL - now
    if wait > 0:
        time.sleep(wait)
    net._last_hit[host] = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            st, body = r.status, r.read()
            hdrs = dict(r.headers)
    except Exception as e:
        print(f"{label}: FAIL {type(e).__name__} {e}")
        return None
    print(f"{label}: {st} {len(body)} B total={hdrs.get('X-PagedRequestResponse-TotalRows')}")
    if st == 200 and body:
        save(url, f"raw/api-{label}.json", body, hdrs)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None
    return None


data = api_get(f"/organizations/{ORG}/posts?pageIndex=0&pageSize=100", "posts-100")
if data is not None:
    posts = data.get("data") if isinstance(data, dict) else data
    print(f"posts returned: {len(posts) if isinstance(posts, list) else '?'}")
    if isinstance(posts, list):
        for p in posts:
            att = [a.get("filename", "") for a in (p.get("attachments") or []) if (a.get("filename", "") or "").lower().endswith(".pdf")]
            print(f"  {p.get('createdOn', '')[:10]}  {p.get('title', '')[:60]:<60} status={p.get('status')} pdf={att}")

org = api_get(f"/organizations/{ORG}", "org-detail")
if org is not None and isinstance(org, dict):
    d = org.get("data") or org
    print("org name:", d.get("name"), "id:", d.get("id"), "status:", d.get("status"))

atts = api_get(f"/organizations/{ORG}/attachments?pageIndex=0&pageSize=100", "attachments-100")
if atts is not None:
    rows = atts.get("data") if isinstance(atts, dict) else atts
    print(f"attachments returned: {len(rows) if isinstance(rows, list) else '?'}")
    if isinstance(rows, list):
        for a in rows:
            print(f"  {a.get('filename', '')[:70]:<70} type={a.get('type')} {a.get('url', '')[:80]}")
