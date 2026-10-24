"""Build data/items.jsonl from extracted TOP blocks using the local model.

For each agenda item the model produces English subject/decision, topic tag,
language-neutral facts and one verbatim German quote - derived ONLY from the
verbatim German source_text. Everything is stored so the verifier can check
quotes and facts against the extracted page text.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BLOCKS = ROOT / "data/extracted"
OUT = ROOT / "data/items.jsonl"
MANUAL = ROOT / "data/manual_review.jsonl"

MODEL_URL = "http://192.168.178.10:8015/v1/chat/completions"
MODEL = "GLM-5.3-Flash-NVFP4-NVIDIA-TP4"
MAX_PARALLEL = 8

TOPICS = [
    "Bauleitplanung", "Bauanträge", "Finanzen", "Kindergarten/Schule",
    "Straßen/Verkehr", "Wasser/Abwasser", "Energie", "Vereine/Kultur",
    "Personal", "Sonstiges",
]

SYSTEM = """You build a public archive of municipal council decisions of Aldersbach (Landkreis Passau, Bavaria). You receive the verbatim German text of one agenda item (TOP) from the official municipal newsletter "Aldersbacher Klosterkurier", including the section header line, the TOP marker and the article paragraphs.

Tasks:
1. subject: English, 1-2 sentences, WHAT the item is about. Keep German proper nouns (place names, street names, Baugebiete, plan names like "Bebauungsplan Schwaig X", "SO Energie") exactly as written. A short English gloss in parentheses is allowed on first use of a German technical term.
2. decision: English, 1-2 sentences, WHAT the council decided or took note of, derived ONLY from the source text. Preserve the exact German decision verb in quotation marks right after the English verb, e.g. approved ("beschloss"), approved ("billigte"), approved ("stimmte zu"), took note ("Kenntnisnahme"), consented ("zustimmen"/"zugestimmt"), favoured ("befürwortet"), granted consent ("Einvernehmen erteilt"). If the text states no decision, say so explicitly.
3. topic: exactly one of: Bauleitplanung, Bauanträge, Finanzen, Kindergarten/Schule, Straßen/Verkehr, Wasser/Abwasser, Energie, Vereine/Kultur, Personal, Sonstiges.
4. facts, taken from source_text ONLY (never invent):
   - meeting_date: DD.MM.YYYY of the meeting (from the header line)
   - body: the council body named in the text, normally "Gemeinderat"
   - top: the TOP label exactly as printed (e.g. "TOP 03", "TOP 10-11")
   - amounts: every EUR amount that appears in the text, as list of {"value": "10.000, -", "context": short German fragment around it}; [] if none. Copy digits exactly as printed.
   - vote: the German decision phrase from the text (e.g. "beschloss", "stimmte zu", "wurde zugestimmt", "Kenntnisnahme", "gebilligt", "befürwortet", "erteilte das Einvernehmen"), or null if the text states none.
   - places: German place/street/Baugebiet/Ortsteil names mentioned (e.g. "Schwaig X", "Abt-Zanker-Straße", "Walchsing"); [] if none.
5. quote: ONE verbatim German sentence from the source text that best carries the decision. Copy it character-for-character EXCEPT that words hyphen-split across line breaks in the source are joined into their complete form (a line ending "Gemein-" followed by "derat" becomes "Gemeinderat"); keep every other character exactly as printed, including German punctuation, typographic quotes („ “), amounts and abbreviations.

JSON rules: return a single valid JSON object. Keep the German typographic quotation marks exactly as they appear in the source („ ... " and ‚ ... ') - they are safe inside JSON strings and must NOT be converted to ASCII double quotes. If you ever need an ASCII double quote inside a string value, escape it as \". Never use ASCII double quotes for German quotations.

Return ONLY a JSON object with keys: subject, decision, topic, facts (object with meeting_date, body, top, amounts, vote, places), quote. No markdown, no commentary."""

_lock = threading.Lock()


def join_lines(lines: list[str]) -> str:
    """Join wrapped magazine lines into flowing paragraphs, de-hyphenating."""
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not out:
            out = ln
            continue
        if out.endswith("-") and ln and ln[0].islower():
            out = out[:-1] + ln
        else:
            out = out + " " + ln
    return out


def build_record(block: dict, issue_pdf: dict) -> dict:
    header = f"Infos aus der Gemeinderatssitzung vom {block['meeting_date']}"
    src_lines = [header, f"TOP {block['top']}"] + list(block["lines"])
    pages = block["pages"]
    issue_file = issue_pdf["file"]
    pdf_url = issue_pdf["url"]
    return {
        "id": f"{issue_file}#{block['meeting_date']}#TOP{block['top']}",
        "issue": block["issue"],
        "issue_file": issue_file,
        "issue_url": pdf_url,
        "meeting_date": block["meeting_date"],
        "top": block["top"],
        "pages": pages,
        "page_start": block["page_start"],
        "source_lines": src_lines,
        "source_text": "\n".join(src_lines),
        "source_text_display": join_lines(src_lines),
        "open_end": bool(block.get("open_end")),
    }


def parse_lenient(s: str):
    """json.loads, then repair LLM-typical unescaped quotes inside strings."""
    try:
        return json.loads(s)
    except Exception:
        pass
    out: list[str] = []
    in_str = False
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if not in_str:
            if c == '"':
                in_str = True
            out.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(s[i:i + 2])
            i += 2
            continue
        if c == '"':
            # structural if preceded by a JSON punctuation start or followed
            # by a JSON punctuation continuation
            j = i + 1
            while j < n and s[j] in " \t\r\n":
                j += 1
            nxt = s[j] if j < n else ""
            prev_sig = ""
            for ch in reversed(out):
                if ch not in " \t\r\n":
                    prev_sig = ch
                    break
            if prev_sig in ':,{[' or nxt in ':,}]':
                in_str = False
                out.append(c)
            else:
                out.append('\\"')
            i += 1
            continue
        out.append(c)
        i += 1
    return json.loads("".join(out))


def call_model(rec: dict, attempt: int = 1, repair: str | None = None) -> dict:
    user_content = rec["source_text_display"]
    if repair:
        user_content = (
            f"{rec['source_text_display']}\n\n"
            f"Your previous answer was not valid JSON: {repair}\n"
            "Return again ONLY a single valid JSON object with the same keys. "
            'Escape any ASCII double quote inside string values as \\" and keep '
            "German typographic quotes („ “) unchanged."
        )
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0,
        "max_tokens": 1600,
        "reasoning_effort": "low",
    }
    req = urllib.request.Request(
        MODEL_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read().decode("utf-8"))
    content = out["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
    try:
        data = parse_lenient(content)
    except Exception as e:
        raise ValueError(f"invalid JSON from model: {e}; raw head: {content[:200]!r}") from e
    return data


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def process(rec: dict, issue_pdf: dict) -> dict:
    last_err = None
    repair = None
    for attempt in (1, 2, 3):
        try:
            data = call_model(rec, attempt=attempt, repair=repair)
            facts = data.get("facts", {})
            item = {
                "id": rec["id"],
                "issue": rec["issue"],
                "issue_file": rec["issue_file"],
                "issue_url": rec["issue_url"],
                "meeting_date": rec["meeting_date"],
                "top": rec["top"],
                "pages": rec["pages"],
                "page_start": rec["page_start"],
                "source_lines": rec["source_lines"],
                "source_text": rec["source_text"],
                "source_text_display": rec["source_text_display"],
                "subject": str(data.get("subject", "")).strip(),
                "decision": str(data.get("decision", "")).strip(),
                "topic": str(data.get("topic", "")).strip(),
                "facts": {
                    "meeting_date": facts.get("meeting_date"),
                    "body": facts.get("body"),
                    "top": facts.get("top"),
                    "amounts": facts.get("amounts") or [],
                    "vote": facts.get("vote"),
                    "places": facts.get("places") or [],
                },
                "quote": str(data.get("quote", "")).strip(),
                "open_end": bool(rec.get("open_end")),
            }
            return item
        except Exception as e:
            last_err = e
            repair = str(e)
            time.sleep(2 * attempt)
    with _lock:
        with MANUAL.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": rec["id"], "error": str(last_err), "source_text": rec["source_text"]}, ensure_ascii=False) + "\n")
    print(f"FAILED {rec['id']}: {last_err}")
    return None


def main():
    # issue pdf manifest lookup
    manifest = [json.loads(l) for l in (ROOT / "sources/manifest.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    issue_pdfs = {}
    for m in manifest:
        fname = Path(m["file"]).name
        if fname.startswith("klosterkurier-"):
            issue_pdfs[fname.replace(".pdf", "")] = m

    blocks_all = []
    for f in sorted(BLOCKS.glob("*.blocks.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for b in d["items"]:
            blocks_all.append(b)

    # dedupe (issue, meeting, top)
    seen = set()
    recs = []
    for b in blocks_all:
        key = (b["issue"], b["meeting_date"], b["top"])
        if key in seen:
            print(f"DUPLICATE skipped: {key}")
            continue
        seen.add(key)
        issue_pdf = issue_pdfs.get(b["issue"], {})
        recs.append(build_record(b, issue_pdf))

    done_ids = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    done_ids.add(json.loads(line)["id"])
                except Exception:
                    pass
    todo = [r for r in recs if r["id"] not in done_ids]
    print(f"{len(recs)} items total, {len(todo)} to process (model: {MODEL}, parallel {MAX_PARALLEL})")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        futs = {pool.submit(process, r, None): r for r in todo}
        n = 0
        for fut in as_completed(futs):
            item = fut.result()
            n += 1
            if item:
                results.append(item)
            if n % 20 == 0:
                print(f"  ... {n}/{len(todo)}")

    # order results by (meeting date, top) for stable file
    def datekey(d: str):
        dd, mm, yy = d.split(".")
        return (yy, mm, dd)

    def topkey(t: str):
        m = re.match(r"(\d+)(?:-(\d+))?", t)
        a = int(m.group(1))
        b = int(m.group(2) or m.group(1))
        return (a, b)

    results.sort(key=lambda it: (datekey(it["meeting_date"]), topkey(it["top"]), it["issue"]))
    with OUT.open("a", encoding="utf-8") as fh:
        for it in results:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"wrote {len(results)} items -> {OUT}")
    if MANUAL.exists():
        print(f"manual review needed: see {MANUAL}")


if __name__ == "__main__":
    main()
