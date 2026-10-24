"""Re-run CDX with saving; fetch Wayback snapshots of 1-2026 and 4-2025 posts."""
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


def cdx(params: str, label: str, show_pdf: bool = False):
    st, h, b = fetch(f"{CDX}?{params}")
    print(f"{label}: {st} {len(b)}")
    if st == 200 and len(b) > 4:
        save(f"{CDX}?{params}", f"raw/wayback-{label}.json", b, h)
        rows = json.loads(b.decode("utf-8"))
        print(f"  rows: {len(rows) - 1}")
        if show_pdf:
            for r in rows[1:]:
                if ".pdf" in r[2].lower() or (len(r) > 3 and r[3] == "application/pdf"):
                    print(f"  {r[1]} {r[2]}")
        return rows
    time.sleep(6)
    return None


rows = cdx("url=archiv.aldersbach.de&matchType=domain&output=json&limit=2000&collapse=urlkey", "archiv-domain", show_pdf=True)
time.sleep(4)
rows2 = cdx("url=aldersbach.de&matchType=domain&output=json&limit=1000&collapse=urlkey&filter=mimetype:application/pdf", "aldersbach-domain-pdf", show_pdf=True)

# snapshots of the 1-2026 post and 4-2025 post on the new site
SNAPS = {
    "wayback-aldersbach-post-1-2026.html": "http://web.archive.org/web/20260318133859/https://aldersbach.de/aktuelles/hier-steht-ihnen-das-aktuelle-informationsblatt-ausgabe-01-2026-zum-download-bereit/",
    "wayback-aldersbach-post-4-2025.html": "http://web.archive.org/web/20260130125417/https://aldersbach.de/aktuelles/aldersbacher-klosterkurier-offizielles-informationsblatt-der-gemeinde-aldersbach-ausgabe-4-2025/",
}
for fname, url in SNAPS.items():
    time.sleep(4)
    st, h, b = fetch(url)
    print(f"snapshot {fname}: {st} {len(b)}")
    if st == 200 and len(b) > 1000:
        save(url, f"pages/{fname}", b, h)
        html = b.decode("utf-8", "replace")
        pdfs = sorted(set(re.findall(r'https?://[^\s"\'<>]+?\.pdf[^\s"\'<>]*', html)))
        rel = sorted(set(re.findall(r'href="([^"]+\.pdf[^"]*)"', html)))
        wp = sorted(set(re.findall(r'wp-content/uploads/[^"\'<> ]+?\.pdf', html)))
        print("  abs pdfs:", pdfs[:10])
        print("  rel pdfs:", rel[:10])
        print("  wp uploads pdfs:", wp[:10])
