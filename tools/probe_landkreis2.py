"""Count Kreistag/agenda meetings for the last 12 months from month calendar views.
Check-only phase 2: month listing pages only, no meeting detail pages."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://buergerinfo.landkreis-passau.de"
months = [
    (2025, 10), (2025, 11), (2025, 12),
    (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5), (2026, 6),
    (2026, 7), (2026, 8), (2026, 9), (2026, 10),
]
total = 0
per_month = []
all_meetings = set()
for y, m in months:
    url = f"{BASE}/si0040.asp?__cjahr={y}&__cmonat={m}&__canz=1&__cselect=0"
    st, h, b = fetch(url)
    if st != 200 or not b:
        print(f"{y}-{m:02d}: {st}")
        per_month.append((f"{y}-{m:02d}", None))
        continue
    save(url, f"landkreis/calendar-{y}-{m:02d}.html", b, h)
    html = b.decode("utf-8", "replace")
    # meeting rows link to si0112.asp (Sitzung) or similar; count distinct links
    links = set(re.findall(r"si0112\.asp\?[^\s\"'>]+", html))
    # also count explicit meeting titles in the day cells
    titles = re.findall(r"<a[^>]+href=\"si0112\.asp[^\"]*\"[^>]*>([^<]{5,120})</a>", html)
    per_month.append((f"{y}-{m:02d}", len(links)))
    all_meetings |= {l.split("&sid")[0] for l in links}
    print(f"{y}-{m:02d}: {len(links):>2} meeting links; titles sample: {[t.strip()[:40] for t in titles[:3]]}")

print("\nSUMMARY per month:", per_month)
print("unique meeting links over 13 months:", len(all_meetings))
