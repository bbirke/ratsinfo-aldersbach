"""Phase 2 recon: Landkreis Passau Kreistag SessionNet (check only - no crawling).

- robots.txt
- calendar page si0040.asp (one request) to see structure and count meetings
- OParl availability (standard endpoints, a few GET probes max)
Then STOP - no further crawling without the user's decision.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://buergerinfo.landkreis-passau.de"

st, h, b = fetch(f"{BASE}/robots.txt")
print("robots.txt:", st)
print(b.decode("utf-8", "replace")[:800] if b else "(empty)")
if st == 200:
    save(f"{BASE}/robots.txt", "landkreis/robots.txt", b, h)

# main calendar page (si0040.asp = Sitzungskalender)
st, h, b = fetch(f"{BASE}/si0040.asp")
print("\nsi0040.asp:", st, len(b))
if st == 200 and b:
    save(f"{BASE}/si0040.asp", "landkreis/si0040.html", b, h)
    html = b.decode("utf-8", "replace")
    # SessionNet calendars list meetings with links si0112.asp?...
    meetings = re.findall(r"si0112\.asp[^\"'>]*", html)
    print("meeting links on default calendar view:", len(meetings), meetings[:5])
    dates = re.findall(r"\d{2}\.\d{2}\.\d{4}", html)
    print("date-like strings:", len(dates), dates[:10])
    # year selector?
    years = re.findall(r"(20\d\d)", html)
    print("years mentioned:", sorted(set(years)))

# OParl probes (standard paths, few requests only)
for path in ("/oparl", "/oparl/v1.1", "/api/oparl/v1.1", "/oparl/system"):
    st, h, b = fetch(BASE + path)
    head = b[:200].decode("utf-8", "replace") if b else ""
    print(f"oparl probe {path}: {st} {head[:120]!r}")
