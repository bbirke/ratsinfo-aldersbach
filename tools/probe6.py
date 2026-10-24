"""Probe 6: archiv.aldersbach.de (Joomla), single heimat-info post, wayback, bundle grep."""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import net  # noqa: E402
from net import ROOT, fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
P = ROOT / "sources/pages"


def raw_get(url: str, timeout: int = 60) -> tuple[int, dict, bytes]:
    """GET without following redirects, single attempt (for redirect inspection)."""
    req = urllib.request.Request(url, headers={"User-Agent": net.UA})
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), b""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def section(label):
    def deco(fn):
        def run():
            try:
                print(f"--- {label}")
                fn()
            except Exception as e:
                print(f"!!! {label} failed: {type(e).__name__}: {e}")
        return run
    return deco


@section("archiv home (no redirect)")
def s1():
    st, h, b = raw_get("https://archiv.aldersbach.de/")
    print("status:", st, "location:", h.get("Location"), "len:", len(b))
    if st in (200, 301, 302):
        save("https://archiv.aldersbach.de/", "pages/archiv-aldersbach-home-noredir.html", b, h) if st == 200 and b else None


@section("archiv home (follow redirects, retry x2)")
def s2():
    st, h, b = fetch("https://archiv.aldersbach.de/")
    print("status:", st, "len:", len(b))
    if st == 200 and b:
        save("https://archiv.aldersbach.de/", "pages/archiv-aldersbach-home.html", b, h)
        ahtml = b.decode("utf-8", "replace")
        links = sorted(set(re.findall(r'href="([^"]+)"', ahtml)))
        kk = [u for u in links if "klosterkurier" in u.lower()]
        print("klosterkurier links:", kk[:20])
        print("pdf links:", [u for u in links if ".pdf" in u.lower()][:20])
        # article list links
        arts = sorted(set(re.findall(r'href="([^"]*(?:aktuelles|nachrichten|index\.php)[^"]*)"', ahtml, re.I)))
        print("article-ish links:", arts[:30])


@section("heimat-info single post page")
def s3():
    st, h, b = fetch("https://www.heimat-info.de/beitraege/5445edf4-575f-4a2a-9767-4282ab23c1ef")
    print("status:", st, "len:", len(b))
    if st == 200:
        save("https://www.heimat-info.de/beitraege/5445edf4-575f-4a2a-9767-4282ab23c1ef", "pages/heimat-info-post-3-2026.html", b, h)
        phtml = b.decode("utf-8", "replace")
        m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', phtml, re.S)
        if m:
            raw = m.group(1).replace("&quot;", '"').replace("&#39;", "'").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            blob = sorted(set(re.findall(r"heimatinfo\.blob\.core\.windows\.net/public/[0-9a-f\-]{36}\.\w+", raw)))
            print("  payload blob urls:", blob)
            uuids = sorted(set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", raw)))
            print(f"  payload uuids: {len(uuids)}", uuids[:15])
            strs = [s for s in json.loads(raw) if isinstance(s, str)]
            print("  strings w/ pdf:", [s for s in strs if "pdf" in s.lower()][:10])


@section("wayback cdx")
def s4():
    for label, cdx in (
        ("kk-prefix", "http://web.archive.org/cdx/search/cdx?url=heimat-info.de%2Fgemeinden%2Faldersbach%2Forganisationen%2Faldersbacher-klosterkurier*&output=json&limit=100"),
        ("blob-pdfs", "http://web.archive.org/cdx/search/cdx?url=heimatinfo.blob.core.windows.net%2Fpublic%2F*&output=json&limit=200&filter=original:.*pdf&collapse=urlkey"),
        ("aldersbach-kk", "http://web.archive.org/cdx/search/cdx?url=aldersbach.de&matchType=domain&filter=original:.*[Kk]losterkurier.*&output=json&limit=100&collapse=urlkey"),
    ):
        st, h, b = fetch(cdx)
        print(f"{label}: {st} {len(b)}")
        if st == 200 and len(b) > 4:
            save(cdx, f"raw/wayback-{label}.json", b, h)
            rows = json.loads(b.decode("utf-8"))
            for r in rows[:80]:
                if isinstance(r, list) and len(r) > 4:
                    print("   ", r[1], r[3][:60], r[4][:90])


@section("bundle grep for api")
def s5():
    list_html = (P / "heimat-info-klosterkurier-beitraege.html").read_text(encoding="utf-8", errors="replace")
    bundles = sorted(set(re.findall(r"/_nuxt/[A-Za-z0-9._\-]+\.js", list_html)))
    print(f"bundles: {len(bundles)}")
    hits = 0
    for i, bpath in enumerate(bundles):
        st, h, b = fetch("https://www.heimat-info.de" + bpath)
        if st != 200:
            continue
        js = b.decode("utf-8", "replace")
        if "azurewebsites" in js or "api-platform" in js:
            hits += 1
            ctx = re.findall(r'.{100}(?:azurewebsites|api-platform).{200}', js)
            print(f"  HIT {bpath} ({len(js)}B):")
            for x in sorted(set(ctx))[:5]:
                print("     ", x.replace("\n", " ")[:340])
        if hits >= 3 or i > 120:
            break


for fn in (s1, s2, s3, s4, s5):
    fn()
print("probe6 done")
