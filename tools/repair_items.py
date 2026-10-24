"""Repair pass: re-ask the model for items whose quote/facts fail literal checks.

Only quote and fact fields may change; subject/decision/topic stay unless the
model flagrantly failed. Results overwrite data/items.jsonl in place.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")
from verify import norm, squash, top_key  # noqa: E402
from extract_items import MODEL, MODEL_URL, parse_lenient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "data/items.jsonl"
EXTRACTED = ROOT / "data/extracted"

REPAIR_PROMPT = """You previously analysed a German agenda item of the municipal council of Aldersbach. Your JSON had literal-text errors:

{problems}

Rules you must now follow strictly:
- "quote" must be ONE contiguous German sentence copied character-for-character from the source text below (apart from joining line-break hyphenation, e.g. "Gemein-derat" -> "Gemeinderat"). Do NOT use ellipses ("...") and do NOT paraphrase. If no sentence states a decision, return the sentence that comes closest.
- "facts.vote" must either be null or a SHORT German phrase that appears VERBATIM and CONTIGUOUSLY in the source text (e.g. "stimmte zu", "wurde zugestimmt", "beschloss", "billigte", "Kenntnisnahme"). No ellipses, no reordering, no invented words.
- every "facts.amounts[].value" and every "facts.places[]" entry must appear verbatim and contiguously in the source text; otherwise remove it.
- "facts.meeting_date", "facts.body", "facts.top" must appear in the source text (the top label without the word "TOP", e.g. "06").
- Keep "subject", "decision" and "topic" unchanged unless they contradict the source text.

Return ONLY the corrected JSON object with keys: subject, decision, topic, facts (meeting_date, body, top, amounts, vote, places), quote."""


def item_problems(it: dict, page_lines: dict) -> list[str]:
    problems = []
    disp = norm(it["source_text_display"])
    raw_join = norm(" ".join(it["source_lines"]))
    # quote
    q = norm(it.get("quote", ""))
    variants = [disp, raw_join, squash(disp), squash(raw_join)]
    if not q or not any(q in v or squash(q) in v for v in variants):
        problems.append(f'The quote {q[:160]!r} does not appear literally in the source text.')
    facts = it.get("facts", {})
    md = facts.get("meeting_date")
    hdr_ok = any(
        f"vom {md}" in " ".join(ls)
        for ls in page_lines.get(it["issue"], {}).values()
    )
    if md and not hdr_ok:
        problems.append(f"meeting_date {md!r} not found in the document")
    top = facts.get("top")
    if top:
        tk = top_key(str(top))
        # non-circular: compare against real printed TOP lines of the item's pages
        page_tops = [
            p
            for pno in it["pages"]
            for p in page_lines.get(it["issue"], {}).get(pno, [])
            if re.match(r"^TOP\b", p, re.I)
        ]
        if not any(top_key(p) == tk for p in page_tops):
            problems.append(f"top {top!r} does not match a printed TOP label on the item's pages")
    for a in facts.get("amounts", []):
        v = norm(str(a.get("value", "")))
        if v and v not in disp and v not in raw_join and squash(v) not in squash(disp) and squash(v) not in squash(raw_join):
            problems.append(f'The amount {v!r} does not appear verbatim in the source text.')
    vote = facts.get("vote")
    if vote:
        v = norm(str(vote))
        if v not in disp and v not in raw_join and squash(v) not in squash(disp) and squash(v) not in squash(raw_join):
            problems.append(f'The vote phrase {v!r} does not appear verbatim and contiguously in the source text.')
    for pl in facts.get("places", []):
        p = norm(str(pl))
        if p and p not in disp and p not in raw_join:
            problems.append(f'The place {p!r} does not appear verbatim in the source text.')
    return problems


def call_repair(it: dict) -> dict:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": REPAIR_PROMPT.format(problems="\n".join(f"- {p}" for p in it["_problems"]))},
            {"role": "user", "content": "Previous answer (JSON):\n" + json.dumps({
                "subject": it["subject"], "decision": it["decision"], "topic": it["topic"],
                "facts": it["facts"], "quote": it["quote"],
            }, ensure_ascii=False)},
            {"role": "user", "content": "Source text (verbatim German):\n" + it["source_text_display"]},
        ],
        "temperature": 0,
        "max_tokens": 1600,
        "reasoning_effort": "low",
    }
    req = urllib.request.Request(MODEL_URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read().decode("utf-8"))
    content = out["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
    return parse_lenient(content)


def main():
    items = [json.loads(l) for l in ITEMS.read_text(encoding="utf-8").splitlines() if l.strip()]
    page_lines = {}
    for f in EXTRACTED.glob("*.pages.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        page_lines[f.stem.replace(".pages", "")] = {int(p): ls for p, ls in d.items()}

    for round_no in (1, 2):
        todo = []
        for it in items:
            probs = item_problems(it, page_lines)
            it["_problems"] = probs
            if probs:
                todo.append(it)
        print(f"round {round_no}: {len(todo)} items to repair")
        if not todo:
            break
        fixed = {}

        def work(it):
            try:
                data = call_repair(it)
                return it["id"], data
            except Exception as e:
                return it["id"], {"__error__": str(e)}

        with ThreadPoolExecutor(max_workers=8) as pool:
            for fut in as_completed([pool.submit(work, it) for it in todo]):
                iid, data = fut.result()
                if "__error__" not in data:
                    fixed[iid] = data
        n_fixed = 0
        for it in items:
            if it["id"] in fixed:
                data = fixed[it["id"]]
                facts = data.get("facts", {})
                if data.get("quote"):
                    it["quote"] = str(data["quote"]).strip()
                if facts:
                    # only overwrite keys the repair actually returned, so a
                    # partial response cannot wipe previously verified data
                    if "meeting_date" in facts:
                        it["facts"]["meeting_date"] = facts.get("meeting_date")
                    if "body" in facts:
                        it["facts"]["body"] = facts.get("body")
                    if "top" in facts:
                        it["facts"]["top"] = facts.get("top")
                    if "amounts" in facts:
                        it["facts"]["amounts"] = facts.get("amounts") or []
                    if "vote" in facts:
                        it["facts"]["vote"] = facts.get("vote")
                    if "places" in facts:
                        it["facts"]["places"] = facts.get("places") or []
                n_fixed += 1
        print(f"  repaired {n_fixed} items")
        time.sleep(1)

    for it in items:
        it.pop("_problems", None)
    with ITEMS.open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    print("items.jsonl updated")


if __name__ == "__main__":
    main()
