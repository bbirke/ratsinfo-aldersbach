"""Decode XML entities (&apos; etc.) inside data/items.jsonl (poppler artifact)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/items.jsonl"

DECODINGS = [("&apos;", "'"), ("&quot;", '"'), ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")]


def dec(s: str) -> str:
    for a, b in DECODINGS:
        s = s.replace(a, b)
    return s


def deep(x):
    if isinstance(x, str):
        return dec(x)
    if isinstance(x, list):
        return [deep(v) for v in x]
    if isinstance(x, dict):
        return {k: deep(v) for k, v in x.items()}
    return x


items = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
items = [deep(it) for it in items]
with OUT.open("w", encoding="utf-8") as fh:
    for it in items:
        fh.write(json.dumps(it, ensure_ascii=False) + "\n")
print(f"decoded entities in {len(items)} items")
