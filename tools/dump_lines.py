"""Dump per-page line geometry (bbox-layout) for inspection."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PDF = "sources/klosterkurier/klosterkurier-2026-03.pdf"


def page_lines(pdf: str, page: int) -> list[dict]:
    out = Path(f"tmp/bbox-p{page}.xml")
    subprocess.run(["pdftotext", "-bbox-layout", "-f", str(page), "-l", str(page), pdf, str(out)], check=True, capture_output=True)
    xml = out.read_text(encoding="utf-8", errors="replace")
    lines = []
    for m in re.finditer(r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>', xml, re.S):
        x0, y0, x1, y1, inner = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), m.group(5)
        words = [w.group(1) for w in re.finditer(r"<word[^>]*>([^<]*)</word>", inner)]
        lines.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "text": " ".join(words)})
    return lines


for page in (5, 6):
    lines = page_lines(PDF, page)
    left = sorted([l for l in lines if l["x0"] < 300], key=lambda l: (l["y0"], l["x0"]))
    right = sorted([l for l in lines if l["x0"] >= 300], key=lambda l: (l["y0"], l["x0"]))
    print(f"===== PAGE {page} =====")
    for side, arr in (("L", left), ("R", right)):
        print(f"--- column {side}: {len(arr)} lines")
        for l in arr:
            w = l["x1"] - l["x0"]
            h = l["y1"] - l["y0"]
            print(f"  {side} y={l['y0']:7.1f} x0={l['x0']:6.1f} w={w:6.1f} h={h:4.1f} | {l['text'][:78]}")
