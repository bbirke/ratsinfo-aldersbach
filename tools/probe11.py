"""Wayback CDX for old aldersbach.de (Joomla) + archiv host; donaudruck page."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import net  # noqa: E402
from net import fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

CDX = "http://web.archive.org/cdx/search/cdx"


def cdx(params: str, label: str):
    st, h, b = fetch(f"{CDX}?{params}")
    print(f"{label}: {st} {len(b)}")
    if st == 200 and len(b) > 4:
        rows = json.loads(b.decode("utf-8"))
        print(f"  rows: {len(rows) - 1}")
        return rows
    time.sleep(4)
    return None


# 1. old Joomla site: index.php paths (any year)
rows = cdx("url=aldersbach.de%2Findex.php*&output=json&limit=2000&collapse=urlkey&filter=statuscode:200", "aldersbach.de/index.php*")
if rows:
    for r in rows[1:]:
        print(f"  {r[1]} {r[2][:110]} [{r[3]}]")

# 2. all aldersbach.de html snapshots mentioning kurier in path
rows = cdx("url=aldersbach.de&matchType=domain&output=json&limit=3000&collapse=urlkey&filter=statuscode:200&filter=mimetype:text/html", "aldersbach.de domain html")
if rows:
    kk = [r for r in rows[1:] if re.search(r"kurier|kirch|aktuell", r[2], re.I)]
    print(f"  html urls: {len(rows) - 1}, kurier/aktuell-ish: {len(kk)}")
    for r in kk[:60]:
        print(f"  {r[1]} {r[2][:120]}")

# 3. pdf snapshots on aldersbach.de
rows = cdx("url=aldersbach.de&matchType=domain&output=json&limit=1000&collapse=urlkey&filter=mimetype:application/pdf", "aldersbach.de domain pdf")
if rows:
    print(f"  pdf urls: {len(rows) - 1}")
    for r in rows[1:]:
        print(f"  {r[1]} {r[2][:120]}")

# 4. archiv host
rows = cdx("url=archiv.aldersbach.de&matchType=domain&output=json&limit=1000&collapse=urlkey", "archiv.aldersbach.de domain")
if rows:
    print(f"  urls: {len(rows) - 1}")
    for r in rows[1:40]:
        print(f"  {r[1]} {r[2][:120]} [{r[3]}]")

# 5. donaudruck page
st, h, b = fetch("https://donaudruck.de/klosterkurier-aldersbach")
print("donaudruck:", st, len(b))
if st == 200:
    save("https://donaudruck.de/klosterkurier-aldersbach", "pages/donaudruck-klosterkurier.html", b, h)
    html = b.decode("utf-8", "replace")
    print("  pdfs:", sorted(set(re.findall(r'href="([^"]+\.pdf[^"]*)"', html)))[:10])
