"""Test per-page extraction: locate meeting pages, inspect -bbox-layout XML."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PDF = "sources/klosterkurier/klosterkurier-2026-03.pdf"
txt = Path("tmp/kk3-default.txt").read_text(encoding="utf-8", errors="replace")
pages = txt.split("\f")
print("pages:", len(pages))
hits = {}
for i, p in enumerate(pages, start=1):
    for m in re.finditer(r"Gemeinderatssitzung vom (\d{2}\.\d{2}\.\d{4})", p):
        hits.setdefault(m.group(1), []).append(i)
print("meeting -> pdf pages:", hits)

# inspect bbox-layout of the first meeting page
first = min(hits["24.06.2026"])
out = Path(f"tmp/kk3-p{first}.xml")
subprocess.run(["pdftotext", "-bbox-layout", "-f", str(first), "-l", str(first), PDF, str(out)], check=True, capture_output=True)
xml = out.read_text(encoding="utf-8", errors="replace")
print(f"bbox xml len: {len(xml)}")
print(xml[:3000])
