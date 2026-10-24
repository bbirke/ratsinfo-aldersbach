"""Verify every item in data/items.jsonl against the extracted page text.

Checks:
1. every source_line appears verbatim among the extracted lines of its pages
2. quote (whitespace-normalized) is a substring of source_text_display
3. facts (meeting_date, top, amounts, vote, places) appear literally in
   source_text_display (whitespace-normalized)
4. topic is one of the allowed tags; subject/decision non-empty

Writes data/verification_report.json and prints a summary.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "data/items.jsonl"
EXTRACTED = ROOT / "data/extracted"
TOPICS = {
    "Bauleitplanung", "Bauanträge", "Finanzen", "Kindergarten/Schule",
    "Straßen/Verkehr", "Wasser/Abwasser", "Energie", "Vereine/Kultur",
    "Personal", "Sonstiges",
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\u00ad", "")).strip()


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s.replace("\u00ad", ""))


def top_key(s: str) -> str:
    """Normalize a TOP label: 'TOP 04 - 05', 'TOP 04 und 05', 'TOP04-05' -> '04-05'."""
    t = s.strip().upper().replace("TOP", "").strip()
    t = re.sub(r"[\s\-–/]+(?:UND|BIS)?[\s\-–/]*", "-", t)
    return t.strip("-")


def main() -> None:
    items = [json.loads(l) for l in ITEMS.read_text(encoding="utf-8").splitlines() if l.strip()]
    # page lines per issue
    page_lines: dict[str, dict[int, list[str]]] = {}
    for f in EXTRACTED.glob("*.pages.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        issue = f.stem.replace(".pages", "")
        page_lines[issue] = {int(p): ls for p, ls in d.items()}

    report = {"items": len(items), "line_fail": [], "quote_fail": [], "fact_fail": [],
              "topic_fail": [], "empty_field": [], "open_end": []}
    line_ok = quote_ok = fact_ok = 0

    for it in items:
        issue = it["issue"]
        ok = True
        # 1. lines verbatim (TOP markers compared label-normalized; meeting
        # header lines are checked across the whole issue: continuation pages
        # carry no header)
        missing = []
        for ln in it["source_lines"]:
            if re.match(r"^TOP\b", ln, re.I):
                want = top_key(ln)
                found = any(top_key(p) == want for p in page_lines[issue].get(it["page_start"], []) + page_lines[issue].get(it["pages"][-1], []) if re.match(r"^TOP\b", p, re.I))
            elif re.match(r"^Infos aus der", ln, re.I):
                found = any(ln in " ".join(ls) for ls in page_lines[issue].values())
            else:
                found = any(ln in page_lines[issue].get(p, []) for p in it["pages"])
            if not found:
                missing.append(ln)
        if missing:
            ok = False
            report["line_fail"].append({"id": it["id"], "missing": missing[:5]})
        # 2. quote: accept match against de-hyphenated display OR raw space-join
        raw_join = norm(" ".join(it["source_lines"]))
        q = norm(it.get("quote", ""))
        disp = norm(it["source_text_display"])
        variants = [disp, raw_join, squash(disp), squash(raw_join)]
        if not q or not any(q in v or squash(q) in v for v in variants):
            ok = False
            report["quote_fail"].append({"id": it["id"], "quote": q[:120]})
        else:
            quote_ok += 1
        # 3. facts - non-circular: meeting_date/top validated against the real
        # extracted page lines (*.pages.json), not the synthesized header/label
        facts = it.get("facts", {})
        problems = []
        md = facts.get("meeting_date")
        if md:
            hdr_ok = any(
                f"vom {md}" in ln
                for lines in page_lines.get(issue, {}).values()
                for ln in lines
            )
            if not hdr_ok:
                problems.append(f"meeting_date {md!r} not found in the document headers")
        top = facts.get("top")
        if top:
            tk = top_key(str(top))
            top_ok = any(
                top_key(p) == tk
                for pno in it["pages"]
                for p in page_lines.get(issue, {}).get(pno, [])
                if re.match(r"^TOP\b", p, re.I)
            )
            if not top_ok:
                problems.append(f"top {top!r} does not match a printed TOP label on the item's pages")
        for a in facts.get("amounts", []):
            v = norm(str(a.get("value", "")))
            if v and v not in disp and v not in raw_join and squash(v) not in squash(disp):
                problems.append(f"amount {v!r}")
        vote = facts.get("vote")
        if vote:
            v = norm(str(vote))
            if v not in disp and v not in raw_join and squash(v) not in squash(disp) and squash(v) not in squash(raw_join):
                problems.append(f"vote {v!r}")
        for pl in facts.get("places", []):
            p = norm(str(pl))
            if p and p not in disp and p not in raw_join:
                problems.append(f"place {p!r}")
        if problems:
            ok = False
            report["fact_fail"].append({"id": it["id"], "problems": problems})
        else:
            fact_ok += 1
        # 4. topic + fields
        if it.get("topic") not in TOPICS:
            ok = False
            report["topic_fail"].append({"id": it["id"], "topic": it.get("topic")})
        if not it.get("subject") or not it.get("decision"):
            ok = False
            report["empty_field"].append({"id": it["id"]})
        if it.get("open_end"):
            report["open_end"].append(it["id"])
        if ok:
            line_ok += 1

    n = len(items)
    summary = {
        "items": n,
        "all_lines_verbatim": sum(1 for it in items if not any(r["id"] == it["id"] for r in report["line_fail"])),
        "quotes_ok": quote_ok,
        "facts_ok": fact_ok,
        "topics_ok": n - len(report["topic_fail"]),
        "fully_ok": line_ok,
        "open_end": len(report["open_end"]),
    }
    report["summary"] = summary
    (ROOT / "data/verification_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    for key in ("line_fail", "quote_fail", "fact_fail", "topic_fail", "empty_field"):
        if report[key]:
            print(f"\n--- {key} ({len(report[key])})")
            for r in report[key][:15]:
                print("  ", json.dumps(r, ensure_ascii=False)[:300])


if __name__ == "__main__":
    main()
