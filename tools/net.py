"""Polite HTTP helpers for the Aldersbach ratsinfo archive.

Rules implemented here:
- at least MIN_INTERVAL seconds between requests to the same host
- identify with a User-Agent containing a contact
- only public pages, no logins, no form submissions
- every saved artifact is recorded in sources/manifest.jsonl with
  url, fetched_at (UTC), http last-modified/etag, sha256, size
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources"
RAW = SOURCES / "raw"
MANIFEST = SOURCES / "manifest.jsonl"

UA = "ratsinfo-aldersbach-archive/0.1 (citizen information archive; contact: local operator of this machine)"
MIN_INTERVAL = 1.1  # seconds between requests to the same host

_last_hit: dict[str, float] = {}


def _throttle(host: str) -> None:
    now = time.monotonic()
    wait = _last_hit.get(host, 0.0) + MIN_INTERVAL - now
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def fetch(url: str, timeout: int = 90, tries: int = 3) -> tuple[int, dict, bytes]:
    """GET a URL politely. Returns (status, headers, body). Retries on 5xx/429."""
    host = urllib.parse.urlsplit(url).netloc
    last_err: Exception | None = None
    for attempt in range(tries):
        _throttle(host)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(2.0 * (attempt + 1))
                last_err = e
                continue
            return e.code, dict(e.headers or {}), b""
        except Exception as e:  # network hiccup
            last_err = e
            if attempt < tries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"fetch failed after {tries} tries: {url}: {last_err}")


def slugify(name: str, maxlen: int = 80) -> str:
    s = name.lower()
    s = re.sub(r"[äöüß]", lambda m: {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}[m.group(0)], s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maxlen] or "unnamed"


def save(url: str, relpath: str, body: bytes, headers: dict, extra: dict | None = None) -> dict:
    """Save an artifact under sources/<relpath> and append a manifest record."""
    path = SOURCES / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size == len(body):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        digest = hashlib.sha256(body).hexdigest()
        path.write_bytes(body)
    rec = {
        "url": url,
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "http_last_modified": headers.get("Last-Modified"),
        "http_etag": headers.get("ETag"),
        "content_type": headers.get("Content-Type"),
        "bytes": len(body),
        "sha256": digest,
    }
    if extra:
        rec.update(extra)
    with MANIFEST.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"saved {len(body):>9} B  {relpath}  <- {url}")
    return rec


def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        return []
    return [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]


def already_saved(url: str) -> dict | None:
    for rec in load_manifest():
        if rec["url"] == url:
            return rec
    return None
