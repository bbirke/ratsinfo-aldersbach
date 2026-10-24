"""Extract per-agenda-item (TOP) blocks from Klosterkurier PDFs.

Strategy: pdftotext -bbox-layout gives geometric lines. Body text lines sit in
one or two columns with a consistent x0 and line height (~15.6pt in 2026);
TOP markers are short lines at the column x0 with height ~13.8. Ads have
different x0/height and are filtered geometrically. Each TOP marker starts an
item; subsequent body lines of the same column (y-ordered, contiguous pitch)
belong to it until the next TOP marker or a layout break.

Output: data/extracted/<issue>.blocks.json with items incl. raw lines, full
line boxes and per-page bounding boxes for the highlight step.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
KK_DIR = ROOT / "sources/klosterkurier"
OUT_DIR = ROOT / "data/extracted"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADER_RE = re.compile(r"^Infos aus der .*(?:Gemeinderat|Sitzung).*", re.I)
TOP_RE = re.compile(r"^TOP\s*(\d+)\s*(?:[-–/]\s*(\d+)|(?:und|bis)\s+(\d+))?$", re.I)
BODY_H = (14.2, 17.2)
TOP_H = (12.5, 15.0)


def run_bbox(pdf: Path) -> list[dict]:
    """Return per-page line dicts for the whole PDF."""
    out = ROOT / f"tmp/bbox-{pdf.stem}.xml"
    subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), str(out)],
        check=True, capture_output=True,
    )
    xml = out.read_text(encoding="utf-8", errors="replace")
    pages = []
    for pm in re.finditer(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', xml, re.S):
        w, h, body = float(pm.group(1)), float(pm.group(2)), pm.group(3)
        lines = []
        for m in re.finditer(
            r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>', body, re.S
        ):
            x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
            words = [w.group(1) for w in re.finditer(r"<word[^>]*>([^<]*)</word>", m.group(5))]
            text = " ".join(words).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'")
            lines.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "h": y1 - y0, "w": x1 - x0, "text": text})
        pages.append({"width": w, "height": h, "lines": lines})
    return pages


def columns_of(page: dict) -> list[float]:
    """Find column x0 anchors: mode of x0 among body-height lines."""
    from collections import Counter

    cands = [round(l["x0"], 1) for l in page["lines"] if BODY_H[0] <= l["h"] <= BODY_H[1]]
    if not cands:
        cands = [round(l["x0"], 1) for l in page["lines"] if TOP_H[0] <= l["h"] <= BODY_H[1]]
    counts = Counter(cands)
    anchors = []
    for x0, n in counts.most_common():
        if n < 6:
            continue
        if any(abs(x0 - a) <= 12 for a in anchors):
            continue
        anchors.append(x0)
    return sorted(anchors)


def extract_issue(pdf: Path) -> dict:
    pages = run_bbox(pdf)
    issue = pdf.stem
    meeting = None
    items = []
    warnings = []

    # pre-scan: meeting header of each page (top banner, any x position)
    page_meeting = []
    for page in pages:
        date = None
        for l in page["lines"]:
            if l["h"] > 19:
                m = HEADER_RE.match(l["text"])
                if m:
                    d = re.search(r"(\d{2}\.\d{2}\.\d{4})", l["text"])
                    if d:
                        date = d.group(1)
                        break
        page_meeting.append(date)
    meeting_pages: dict[str, set[int]] = {}
    for pno, d in enumerate(page_meeting, start=1):
        if d:
            meeting_pages.setdefault(d, set()).add(pno)
    # a meeting also owns contiguous header-less pages that carry TOP markers
    # belonging to it (e.g. issue 1-2026 page 9 continues the 28.01.2026 item)
    for date, pset in list(meeting_pages.items()):
        last_hdr = max(pset)
        next_hdr = min(
            (p for p, dd in enumerate(page_meeting, start=1) if dd and p > last_hdr),
            default=len(page_meeting) + 1,
        )
        p = last_hdr + 1
        while p < next_hdr and page_meeting[p - 1] is None:
            has_top = any(
                TOP_RE.match(l["text"]) and TOP_H[0] <= l["h"] <= TOP_H[1]
                for l in pages[p - 1]["lines"]
            )
            if not has_top:
                break
            pset.add(p)
            p += 1

    for pno, page in enumerate(pages, start=1):
        if page_meeting[pno - 1]:
            meeting = page_meeting[pno - 1]
        anchors = columns_of(page)
        if not anchors:
            continue
        col_lines = []
        for a in anchors:
            col = [l for l in page["lines"] if abs(l["x0"] - a) <= 15.0 and l["h"] <= 60.0]
            col.sort(key=lambda l: (l["y0"], l["x0"]))
            col_lines.append((a, col))
        # reading order: leftmost column first
        col_lines.sort(key=lambda t: t[0])

        allowed = meeting_pages.get(meeting, set())
        for anchor, col in col_lines:
            last_y = None
            last_x = None
            for l in col:
                tm = TOP_RE.match(l["text"])
                if tm and TOP_H[0] <= l["h"] <= TOP_H[1] and abs(l["x0"] - anchor) <= 6:
                    end = tm.group(2) or tm.group(3)
                    top_num = tm.group(1) + (f"-{end}" if end else "")
                    items.append({
                        "issue": issue,
                        "page_start": pno,
                        "meeting_date": meeting,
                        "top": top_num,
                        "lines": [],
                        "line_refs": [],
                    })
                    last_y, last_x = l["y1"], l["x0"]
                    continue
                if items and items[-1]["meeting_date"] == meeting and BODY_H[0] <= l["h"] <= BODY_H[1]:
                    cur = items[-1]
                    # skip page headers/footers masquerading as body
                    if re.match(r"^KLOSTERKURIER", l["text"]) or re.match(r"^[\d\s]+$", l["text"]):
                        continue
                    if not re.search(r"[A-Za-zÄÖÜäöüß]", l["text"]):
                        continue
                    # only attach text from the meeting's own pages (avoid
                    # unrelated articles elsewhere in the magazine)
                    if pno not in allowed:
                        continue
                    # tight x-tolerance while the text flows (line pitch),
                    # loose for indented list lines, tight after a break
                    gap = l["y0"] - last_y if last_y is not None else None
                    tol = 12.0 if (gap is not None and -4.0 <= gap <= 20.0) else 6.0
                    if abs(l["x0"] - anchor) > tol:
                        continue
                    cur["lines"].append(l["text"])
                    cur["line_refs"].append(
                        {"page": pno, "y0": l["y0"], "x0": l["x0"], "x1": l["x1"], "y1": l["y1"]})
                    last_y, last_x = l["y1"], l["x0"]

    # drop items without text and items without meeting
    items = [it for it in items if it["lines"] and it["meeting_date"]]
    for it in items:
        it["pages"] = sorted({r["page"] for r in it["line_refs"]} | {it["page_start"]})
        # per-page union of the item's line boxes (+ ~4pt padding) so the
        # highlight step can draw one rectangle per page the item's text spans
        # (items may run over a page break and into a second column)
        by_page: dict[int, list[dict]] = {}
        for r in it["line_refs"]:
            by_page.setdefault(r["page"], []).append(r)
        it["bboxes"] = [
            {
                "page": pno,
                "x0": round(max(0.0, min(r["x0"] for r in refs) - 4.0), 2),
                "y0": round(max(0.0, min(r["y0"] for r in refs) - 4.0), 2),
                "x1": round(min(pages[pno - 1]["width"], max(r["x1"] for r in refs) + 4.0), 2),
                "y1": round(min(pages[pno - 1]["height"], max(r["y1"] for r in refs) + 4.0), 2),
            }
            for pno, refs in sorted(by_page.items())
        ]
        last = it["lines"][-1].rstrip()
        it["open_end"] = not re.search(r"[.;:!?\u00bb\u201c\u201d)]\s*$", last)
    return {"issue": issue, "items": items, "warnings": warnings}


def main():
    pdfs = sorted(KK_DIR.glob("*.pdf"))
    print(f"{len(pdfs)} issue PDFs")
    for pdf in pdfs:
        pages = run_bbox(pdf)
        # dump raw page lines for the verifier
        dump = {str(i): [l["text"] for l in p["lines"]] for i, p in enumerate(pages, start=1)}
        (OUT_DIR / f"{pdf.stem}.pages.json").write_text(
            json.dumps(dump, ensure_ascii=False), encoding="utf-8")
        res = extract_issue(pdf)
        out = OUT_DIR / f"{pdf.stem}.blocks.json"
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        dates = {}
        for it in res["items"]:
            dates.setdefault(it["meeting_date"], []).append(it["top"])
        print(f"{pdf.name}: {len(res['items'])} items; meetings:")
        for d, tops in dates.items():
            print(f"   {d}: {', '.join(tops)}")
        for w in res["warnings"][:10]:
            print(f"   WARN {w}")


if __name__ == "__main__":
    main()
