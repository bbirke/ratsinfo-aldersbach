"""Create highlighted copies of the Klosterkurier issue PDFs.

For every agenda item (TOP) in data/extracted/<issue>.blocks.json draw a
translucent yellow rectangle over the item's passage (one rectangle per page
the item's text spans, computed by extract_text.py as item["bboxes"]) plus a
small "TOP <nn>" label chip just above the box. One highlighted copy per issue
is written to sources/highlights/<issue>.pdf; the originals in
sources/klosterkurier/ stay untouched.

PyMuPDF is vendored into <ROOT>/pylibs (pip install --target=pylibs pymupdf);
nothing is installed into the global environment.

Deterministic and idempotent: always rendered from the original PDF, output
overwritten on each run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pylibs"))

import fitz  # noqa: E402  (PyMuPDF, vendored in pylibs/)

KK_DIR = ROOT / "sources/klosterkurier"
BLOCKS_DIR = ROOT / "data/extracted"
OUT_DIR = ROOT / "sources/highlights"

FILL = (1, 0.92, 0.25)        # yellow
BORDER = (0.85, 0.45, 0.0)    # orange
FILL_OPACITY = 0.35
BORDER_OPACITY = 0.9
BORDER_WIDTH = 0.7
LABEL_FONT = "hebo"           # Helvetica-Bold (base-14)
LABEL_SIZE = 6.5
LABEL_TEXT_COLOR = (0.25, 0.08, 0.0)   # dark brown
LABEL_CHIP_FILL = (1, 0.92, 0.25)
LABEL_CHIP_BORDER = (0.85, 0.45, 0.0)
LABEL_PAD_X = 2.0
LABEL_PAD_Y = 1.2
LABEL_GAP = 1.5               # gap between chip and box top

# fixed metadata timestamps so repeated runs produce byte-identical output
FIXED_DATE = "D:20260101000000Z"
META_KEYS = ("format", "title", "author", "subject", "keywords",
             "creator", "producer", "creationDate", "modDate")


def highlight_issue(pdf_path: Path, blocks: dict) -> int:
    """Draw highlights into a fresh copy of pdf_path; return item count."""
    doc = fitz.open(pdf_path)
    # page no -> [(bbox, top), ...] in document order
    per_page: dict[int, list[tuple[dict, str]]] = {}
    for it in blocks["items"]:
        for bb in it["bboxes"]:
            per_page.setdefault(bb["page"], []).append((bb, it["top"]))

    for pno in sorted(per_page):
        page = doc[pno - 1]
        pw = page.rect.width
        marks = per_page[pno]
        # rectangles first, labels afterwards so chips sit on top of fills
        for bb, _top in marks:
            rect = fitz.Rect(bb["x0"], bb["y0"], bb["x1"], bb["y1"])
            page.draw_rect(
                rect,
                color=BORDER, fill=FILL, width=BORDER_WIDTH,
                fill_opacity=FILL_OPACITY, stroke_opacity=BORDER_OPACITY,
            )
        for bb, top in marks:
            label = f"TOP {top}"
            lw = fitz.get_text_length(label, fontname=LABEL_FONT, fontsize=LABEL_SIZE)
            chip_h = LABEL_SIZE + 2 * LABEL_PAD_Y
            chip_y1 = bb["y0"] - LABEL_GAP
            chip_y0 = chip_y1 - chip_h
            if chip_y0 < 0:
                continue  # no room above the box
            chip_w = lw + 2 * LABEL_PAD_X
            chip_x0 = min(bb["x0"], max(0.0, pw - chip_w - 1.0))
            chip = fitz.Rect(chip_x0, chip_y0, chip_x0 + chip_w, chip_y1)
            page.draw_rect(
                chip,
                color=LABEL_CHIP_BORDER, fill=LABEL_CHIP_FILL, width=0.5,
                fill_opacity=0.9, stroke_opacity=0.9,
            )
            # baseline: centre the text vertically inside the chip
            baseline = chip_y1 - LABEL_PAD_Y - LABEL_SIZE * 0.12
            page.insert_text(
                (chip_x0 + LABEL_PAD_X, baseline),
                label,
                fontname=LABEL_FONT, fontsize=LABEL_SIZE,
                color=LABEL_TEXT_COLOR,
            )

    old_meta = doc.metadata or {}
    fixed_meta = {k: old_meta.get(k) for k in META_KEYS}
    fixed_meta["creationDate"] = FIXED_DATE
    fixed_meta["modDate"] = FIXED_DATE
    doc.set_metadata(fixed_meta)

    out_path = OUT_DIR / pdf_path.name
    # no_new_id: keep the source document's /ID instead of generating a fresh
    # random one per save -> repeated runs produce byte-identical output
    doc.save(out_path, garbage=3, deflate=True, no_new_id=True)
    doc.close()
    return len(blocks["items"])


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(KK_DIR.glob("*.pdf"))
    print(f"{len(pdfs)} issue PDFs")
    total = 0
    for pdf in pdfs:
        blocks_path = BLOCKS_DIR / f"{pdf.stem}.blocks.json"
        if not blocks_path.exists():
            print(f"{pdf.name}: no blocks.json, skipped")
            continue
        blocks = json.loads(blocks_path.read_text(encoding="utf-8"))
        n = highlight_issue(pdf, blocks)
        total += n
        out = OUT_DIR / pdf.name
        size_kb = out.stat().st_size / 1024
        orig_kb = pdf.stat().st_size / 1024
        print(f"{pdf.name}: {n} items highlighted -> {out.relative_to(ROOT)} "
              f"({size_kb:.0f} kB, original {orig_kb:.0f} kB)")
    print(f"total items highlighted: {total}")


if __name__ == "__main__":
    main()
