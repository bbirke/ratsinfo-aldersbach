"""Dump specific suspect pages to decide continuation rules."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dump_lines import page_lines  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

CASES = [
    ("sources/klosterkurier/klosterkurier-2025-04.pdf", [29, 30]),
    ("sources/klosterkurier/klosterkurier-2025-02.pdf", [14]),
    ("sources/klosterkurier/klosterkurier-2025-01.pdf", [22]),
    ("sources/klosterkurier/klosterkurier-2025-03.pdf", [14]),
    ("sources/klosterkurier/klosterkurier-2025-04.pdf", [31]),
    ("sources/klosterkurier/klosterkurier-2026-02.pdf", [18]),
    ("sources/klosterkurier/klosterkurier-2026-03.pdf", [10]),
]
for pdf, pagenos in CASES:
    for pno in pagenos:
        lines = page_lines(pdf, pno)
        for side, arr in (("L", [l for l in lines if l["x0"] < 300]), ("R", [l for l in lines if l["x0"] >= 300])):
            arr.sort(key=lambda l: (l["y0"], l["x0"]))
            print(f"===== {Path(pdf).name} p{pno} col {side} =====")
            prev_y = None
            for l in arr:
                gap = f"{l['y0'] - prev_y:5.1f}" if prev_y is not None else "    -"
                prev_y = l["y0"]
                print(f"  y={l['y0']:7.1f} Δ{gap} x0={l['x0']:6.1f} h={l['y1']-l['y0']:4.1f} | {l['text'][:80]}")
