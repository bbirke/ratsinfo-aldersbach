"""Parse the Nuxt devalue payload embedded in the Klosterkurier issue list page."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")

html = (ROOT / "sources/pages/heimat-info-klosterkurier-beitraege.html").read_text(encoding="utf-8", errors="replace")
m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S)
assert m, "payload not found"
payload_raw = m.group(1)
# Nuxt escapes the payload inside a script tag; reverse the common escapes.
payload_raw = payload_raw.replace('&quot;', '"').replace('&#39;', "'").replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
arr = json.loads(payload_raw)
print("payload entries:", len(arr))

def entry(i):
    if isinstance(i, int) and 0 <= i < len(arr):
        return arr[i]
    return None

# print type census
from collections import Counter
c = Counter(type(e).__name__ for e in arr)
print(c)

# print first entries to understand format
for i in range(0, 8):
    print(i, repr(arr[i])[:220])

# find all strings, print those mentioning Klosterkurier / years
strings = [(i, e) for i, e in enumerate(arr) if isinstance(e, str)]
print("string entries:", len(strings))
for i, s in strings:
    if re.search(r"klosterkurier|20(2[4-9])", s, re.I):
        print(f"  [{i}] {s[:160]}")
