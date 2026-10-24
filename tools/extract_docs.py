"""Extract plain text for every collected council document PDF."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources/aldersbach"
OUT = ROOT / "data/doctext"
OUT.mkdir(parents=True, exist_ok=True)

manifest = [json.loads(l) for l in (ROOT / "sources/manifest.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

docs = []
for m in manifest:
    f = ROOT / m["file"]
    if not f.exists() or f.suffix.lower() != ".pdf":
        continue
    rel = Path(m["file"])
    if rel.parts[1] != "aldersbach":  # only council documents, not the magazine
        continue
    txt_path = OUT / (f.stem + ".txt")
    if not txt_path.exists():
        subprocess.run(["pdftotext", "-layout", str(f), str(txt_path)], check=True, capture_output=True)
    text = txt_path.read_text(encoding="utf-8", errors="replace")
    npages = text.count("\f") + 1 if text else 0
    docs.append({
        "id": f.stem,
        "file": m["file"],
        "url": m["url"],
        "retrieved_via": m.get("retrieved_via"),
        "sha256": m["sha256"],
        "bytes": m["bytes"],
        "text_file": str(txt_path.relative_to(ROOT)).replace("\\", "/"),
        "chars": len(text),
        "pages_est": npages,
        "first_line": text.strip().splitlines()[0][:120] if text.strip() else "",
    })

(out := ROOT / "data/documents.json").write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(docs)} documents -> {out}")
for d in docs:
    print(f"  {d['id']:<55} {d['pages_est']:>3}p {d['chars']:>7}c  {d['first_line'][:60]}")
