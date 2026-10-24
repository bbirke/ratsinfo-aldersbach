"""Recompute source_text_display in data/items.jsonl with an improved joiner."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/items.jsonl"

NO_DEHYPHEN = {"bzw", "u", "z", "d", "i", "s", "ggf", "evtl", "ua", "usw"}


def join_lines(lines: list[str]) -> str:
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not out:
            out = ln
            continue
        if out.endswith("\u00ad") and ln and ln[0].islower():
            out = out[:-1] + ln
        elif out.endswith("-"):
            m = re.match(r"^([a-zäöüß]+)", ln)
            token = m.group(1) if m else ""
            if token and token.rstrip(".") in NO_DEHYPHEN:
                out = out + " " + ln
            elif ln and ln[0].islower():
                out = out[:-1] + ln
            else:
                out = out + " " + ln
        else:
            out = out + " " + ln
    return out.replace("\u00ad", "")


items = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
for it in items:
    it["source_text_display"] = join_lines(it["source_lines"])
with OUT.open("w", encoding="utf-8") as fh:
    for it in items:
        fh.write(json.dumps(it, ensure_ascii=False) + "\n")
print(f"rejoined display text for {len(items)} items")
