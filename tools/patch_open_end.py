"""Propagate open_end flags from blocks files into data/items.jsonl."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/items.jsonl"

flags = {}
for f in (ROOT / "data/extracted").glob("*.blocks.json"):
    d = json.loads(f.read_text(encoding="utf-8"))
    for b in d["items"]:
        flags[(b["issue"], b["meeting_date"], b["top"])] = bool(b.get("open_end"))

items = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
n = 0
for it in items:
    key = (it["issue"], it["meeting_date"], it["top"])
    it["open_end"] = flags.get(key, False)
    if it["open_end"]:
        n += 1
with OUT.open("w", encoding="utf-8") as fh:
    for it in items:
        fh.write(json.dumps(it, ensure_ascii=False) + "\n")
print(f"propagated open_end flags; {n} items flagged")
