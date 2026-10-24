"""Purge mis-resolved / to-be-retried entries from data/geocoded.json."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/geocoded.json"
purge = [
    "Vilshofen", "Hirschbach", "Pirach", "Roßbach", "Häusling", "Unterfeld",
    "Wettmannstätten", "Waldstadion", "Kläranlage", "Friedhof St. Peter",
    "Aldersbach-Kollberg", "Bahnhofsstraße", "GE Linda", "Lindahof III",
    "WA am Zeitlarner Berg II", "Industrie- und Gewerbegebiet Esterndorf",
    "SO Solarpark Dorf II", "„Waldschule“",
]
g = json.loads(P.read_text(encoding="utf-8"))
for name in purge:
    if name in g:
        del g[name]
        print("purged:", name)
P.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(g)} entries remain")
