"""Diagnose missed TOP markers: list all lines containing TOP and why rejected."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_text import BODY_H, TOP_H, columns_of, run_bbox  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
KK_DIR = ROOT / "sources/klosterkurier"

for pdf in sorted(KK_DIR.glob("*.pdf")):
    pages = run_bbox(pdf)
    print(f"===== {pdf.stem} =====")
    for pno, page in enumerate(pages, start=1):
        anchors = columns_of(page)
        tops = [l for l in page["lines"] if re.match(r"^TOP[\s\d/-]*$", l["text"].strip()) or re.match(r"^TOP\s*\d+", l["text"])]
        if not tops:
            continue
        accepted = []
        rejected = []
        for l in tops:
            ok_anchor = any(abs(l["x0"] - a) <= 6.0 for a in anchors)
            ok_h = TOP_H[0] <= l["h"] <= TOP_H[1]
            ok_regex = bool(re.match(r"^TOP\s*(\d+)(?:\s*[-/]\s*(\d+))?$", l["text"]))
            if ok_anchor and ok_h and ok_regex:
                accepted.append(l["text"])
            else:
                rejected.append((l["text"], round(l["h"], 1), round(l["x0"], 1), ok_anchor, ok_h, ok_regex))
        if rejected or not anchors:
            print(f"  p{pno} anchors={anchors} accepted={accepted}")
            for t, h, x, a, hh, rx in rejected:
                print(f"    REJECT {t!r} h={h} x0={x} anchor_ok={a} h_ok={hh} re_ok={rx}")
