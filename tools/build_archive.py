"""Build the static archive under archive/ from data/items.jsonl + documents.

The output folder is self-contained (pages, assets, search/map data and copies
of every linked PDF) so it can be opened from file:// or published unchanged,
e.g. as a GitHub Pages site. All links are relative.

Hand-edited static sources live in tools/site/ (style.css, app.js, map.js) and
are copied to archive/assets/. archive/vendor/ (Leaflet) is maintained by
tools/vendor_leaflet.py and left untouched.

    python tools/build_archive.py            # build, copying PDFs (skips unchanged)
    python tools/build_archive.py --no-pdfs  # build pages only, keep files/ as is
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date as Date, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive"
SITE_SRC = ROOT / "tools/site"
ITEMS = ROOT / "data/items.jsonl"
DOCS = ROOT / "data/documents.json"
HIGHLIGHTS = ROOT / "sources/highlights"

# generated trees that are wiped before every build (never hand-edit these)
GENERATED_DIRS = ["decisions", "meetings", "topics", "verlaeufe", "assets", "data"]
# outputs of the previous site layout, removed if still present
LEGACY_FILES = ["style.css", "search.js", "map.js", "search-data.js", "map-data.js"]

TOPIC_ORDER = [
    "Bauleitplanung", "Bauanträge", "Finanzen", "Kindergarten/Schule",
    "Straßen/Verkehr", "Wasser/Abwasser", "Energie", "Vereine/Kultur",
    "Personal", "Sonstiges",
]
TOPIC_EN = {
    "Bauleitplanung": "Land-use and development plans",
    "Bauanträge": "Building applications",
    "Finanzen": "Budget, fees and finance",
    "Kindergarten/Schule": "Childcare and schools",
    "Straßen/Verkehr": "Roads and traffic",
    "Wasser/Abwasser": "Water and sewage",
    "Energie": "Energy",
    "Vereine/Kultur": "Clubs, culture and events",
    "Personal": "Staff",
    "Sonstiges": "Other matters",
}

ISSUE_LABELS = {
    "klosterkurier-2025-01": "Klosterkurier 1/2025 (March 2025)",
    "klosterkurier-2025-02": "Klosterkurier 2/2025 (June 2025)",
    "klosterkurier-2025-03": "Klosterkurier 3/2025 (September 2025)",
    "klosterkurier-2025-04": "Klosterkurier 4/2025 (December 2025)",
    "klosterkurier-2026-01": "Klosterkurier 1/2026 (March 2026)",
    "klosterkurier-2026-02": "Klosterkurier 2/2026 (June 2026)",
    "klosterkurier-2026-03": "Klosterkurier 3/2026 (September 2026)",
}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


# ---- small helpers -------------------------------------------------------------
def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def ui(s) -> str:
    """Escape an English summary for display; normalise long dashes to a hyphen."""
    return esc(re.sub("\\s*[\\u2013\\u2014]\\s*", " - ", str(s)))


def date_key(d: str):
    dd, mm, yy = d.split(".")
    return (int(yy), int(mm), int(dd))


def top_key(t: str):
    m = re.match(r"(\d+)(?:-(\d+))?", t or "")
    a = int(m.group(1)) if m else 999
    b = int(m.group(2)) if m and m.group(2) else a
    return (a, b)


def long_date(d: str) -> str:
    y, m, dd = date_key(d)
    return f"{WEEKDAYS[Date(y, m, dd).weekday()]}, {dd} {MONTHS[m - 1]} {y}"


def meeting_file(d: str) -> str:
    return f"{d.replace('.', '-')}.html"


def anchor_of(it: dict) -> str:
    return "item-" + it["id"].replace("#", "-").replace("/", "-")


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def topic_slug(t: str) -> str:
    return {"Bauleitplanung": "bauleitplanung", "Bauanträge": "bauantraege",
            "Finanzen": "finanzen", "Kindergarten/Schule": "kindergarten-schule",
            "Straßen/Verkehr": "strassen-verkehr", "Wasser/Abwasser": "wasser-abwasser",
            "Energie": "energie", "Vereine/Kultur": "vereine-kultur",
            "Personal": "personal", "Sonstiges": "sonstiges"}[t]


def load():
    items = [json.loads(l) for l in ITEMS.read_text(encoding="utf-8").splitlines() if l.strip()]
    docs = json.loads(DOCS.read_text(encoding="utf-8"))
    for it in items:
        it["_dk"] = date_key(it["meeting_date"])
        it["_tk"] = top_key(it["top"])
    items.sort(key=lambda it: (it["_dk"], it["_tk"], it["issue"]))
    return items, docs


# ---- decision kinds (derived honestly from the verified vote phrase) ----------
KIND_ORDER = [
    ("ablehnung", r"ablehn|abgelehnt|\blehn(te|en|t)\b"),
    ("billigung", r"billig"),
    ("einvernehmen", r"einvernehmen"),
    ("zustimmung", r"stimmte|zugestimmt|stimmt|zustimmung|genehmigt|gewähr|bewillig|zustimmen|akzeptiert|vollinhaltlich"),
    ("befürwortung", r"befürwort"),
    ("bestätigung", r"bestätig"),
    ("vertagung", r"vertag"),
    ("vergabe", r"vergab|vergabe|vergeben|auftragsvergabe"),
    ("beschluss", r"beschloss|beschließt|beschluss|entschied|festgestellt|freigegeben|bestellt|entlastung|beauftragt|ermächtigt|fasste|stellte [\wäöüß ,]{0,60}fest|zum entschluss"),
    ("kenntnisnahme", r"kenntnis"),
]
# key -> (German label, English gloss, visual tone)
KINDS = {
    "beschluss": ("Beschluss", "decision", "decide"),
    "vergabe": ("Vergabe", "contract award", "decide"),
    "zustimmung": ("Zustimmung", "consent / approval", "approve"),
    "billigung": ("Billigung", "assent", "approve"),
    "einvernehmen": ("Einvernehmen", "statutory consent", "approve"),
    "befürwortung": ("Befürwortung", "endorsement", "approve"),
    "bestätigung": ("Bestätigung", "confirmation", "approve"),
    "ablehnung": ("Ablehnung", "rejection", "reject"),
    "vertagung": ("Vertagung", "deferred", "defer"),
    "kenntnisnahme": ("Kenntnisnahme", "taken note, no decision", "note"),
    "keineangabe": ("Kein Beschluss genannt", "no decision stated", "none"),
}
KIND_DISPLAY_ORDER = list(KINDS.keys())


def kind_anchor(k: str) -> str:
    return "k-" + k.replace("ü", "ue").replace("ä", "ae").replace("ö", "oe")


def decision_kind(it: dict) -> str:
    v = str(it.get("facts", {}).get("vote") or "").lower()
    if v.strip():
        for key, pat in KIND_ORDER:
            if re.search(pat, v):
                return key
    # no vote phrase (or an unmatched one): use the verified decision text
    d = str(it.get("decision", "")).lower()
    if re.search(r"reject", d):
        return "ablehnung"
    if re.search(r"took note|kenntnis|no [\w\s]{0,30}decision|informational|announced", d):
        return "kenntnisnahme"
    if re.search(r"\bawarded\b|contract award", d):
        return "vergabe"
    if re.search(r"\bdecided\b", d):
        return "beschluss"
    if re.search(r"approved|consented|granted", d):
        return "zustimmung"
    if re.search(r"favoured", d):
        return "befürwortung"
    if re.search(r"confirmed", d):
        return "bestätigung"
    if re.search(r"postpon|adjourn", d):
        return "vertagung"
    if re.search(r"prioritis|prioritiz|set new|ermächtigt", d):
        return "beschluss"
    return "keineangabe"


def decision_slug(it: dict) -> str:
    return f"{it['meeting_date'].replace('.', '-')}-top{str(it['top']).lower()}"


def decision_path(it: dict, root: str = "") -> str:
    return f"{root}decisions/{decision_slug(it)}.html"


# ---- source files (copied into archive/files/ so the site is self-contained) ----
def issue_pdf(it: dict, root: str, highlighted: bool = False) -> str:
    name = it["issue_file"].split("/")[-1]
    sub = "highlights" if highlighted else "klosterkurier"
    return f"{root}files/{sub}/{name}#page={it['page_start']}"


def has_highlight(it: dict) -> bool:
    return (HIGHLIGHTS / it["issue_file"].split("/")[-1]).exists()


def doc_href(d: dict, root: str) -> str:
    return f"{root}files/documents/{d['file'].split('/')[-1]}"


def copy_pdfs(items: list, docs: list) -> tuple[int, int]:
    """Mirror every PDF the site links to into archive/files/. Returns (copied, total)."""
    jobs = []
    for name in sorted({it["issue_file"].split("/")[-1] for it in items}):
        jobs.append((ROOT / "sources/klosterkurier" / name, ARCHIVE / "files/klosterkurier" / name))
        if (HIGHLIGHTS / name).exists():
            jobs.append((HIGHLIGHTS / name, ARCHIVE / "files/highlights" / name))
    for d in docs:
        jobs.append((ROOT / d["file"], ARCHIVE / "files/documents" / d["file"].split("/")[-1]))
    copied = 0
    for src, dst in jobs:
        if not src.exists():
            print(f"WARNING: missing source file {src.relative_to(ROOT)}")
            continue
        if dst.exists() and dst.stat().st_size == src.stat().st_size and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied, len(jobs)


# ---- icons (inline SVG, stroke = currentColor) ----------------------------------
_ICONS = {
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "theme": '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "marker": '<path d="m9 11-6 6v3h9l3-3"/><path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "print": '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M6 14h12v7H6z"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
}


def icon(name: str, cls: str = "icon") -> str:
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_ICONS[name]}</svg>')


# ---- layout ------------------------------------------------------------------------
NAV = [("meetings/index.html", "Meetings"), ("topics/index.html", "Topics"),
       ("verlaeufe/index.html", "Dossiers"), ("decisions/index.html", "Decisions"),
       ("documents.html", "Documents"), ("map.html", "Map"), ("about.html", "About")]
SITE_NAME = "Ratsinfo-Archiv Aldersbach"
CUR = ' aria-current="page"'
STAMP = datetime.now().strftime("%d.%m.%Y")


def omni_form(root: str, field_id: str = "gq", big: bool = False, value: str = "") -> str:
    ph = ("Search decisions, places, parcels, dates..." if big else "Search the archive")
    kbd = "" if big else "<kbd>/</kbd>"
    return (f'<form class="omni" role="search" action="{root}search.html" method="get">'
            f'<label class="omni-field">{icon("search")}<span class="sr-only">Search the archive</span>'
            f'<input id="{field_id}" name="q" type="search" autocomplete="off" spellcheck="false" placeholder="{ph}" '
            f'value="{esc(value)}" role="combobox" aria-expanded="false" aria-controls="{field_id}-pop" aria-autocomplete="list">'
            f'{kbd}</label>'
            + (f'<button class="btn primary" type="submit">Search</button>' if big else "")
            + f'<div class="omni-pop" id="{field_id}-pop" role="listbox" hidden></div></form>')


def render_header(root: str, active: str) -> str:
    links = "".join(
        f'<a href="{root}{p}"{CUR if p == active else ""}>{t}</a>' for p, t in NAV)
    return (f'<a class="skip" href="#main">Skip to content</a>'
            f'<header class="site-header"><div class="wrap bar">'
            f'<a class="brand" href="{root}index.html" aria-label="{SITE_NAME}, home">'
            f'<img class="brand-mark" src="{root}assets/wappen-aldersbach.svg" alt="" width="30" height="33">'
            f'<span class="brand-text"><strong>Ratsinfo-Archiv</strong><span>Gemeinderat Aldersbach</span></span></a>'
            f'<nav class="mainnav" aria-label="Main">{links}</nav>'
            f'{omni_form(root)}'
            f'<button class="icon-btn theme-btn" type="button" aria-label="Colour theme">{icon("theme", "")}</button>'
            f'</div></header>')


def render_footer(root: str, cov: dict) -> str:
    return f"""<footer class="site-footer"><div class="wrap cols">
<div><h2>{SITE_NAME}</h2>
<p>An independent citizen archive of the decisions of the Gemeinderat Aldersbach (Landkreis Passau),
reconstructed from the municipal newsletter "Aldersbacher Klosterkurier" and documents from aldersbach.de.
Not an official publication. English summaries; German source text always verbatim.</p>
<p>{cov['items']} agenda items from {cov['meetings']} meetings, {cov['first']} to {cov['last']} &middot; built {STAMP}</p></div>
<div><h2>Browse</h2><ul>
<li><a href="{root}meetings/index.html">Meetings</a></li><li><a href="{root}topics/index.html">Topics</a></li>
<li><a href="{root}verlaeufe/index.html">Dossiers</a></li><li><a href="{root}decisions/index.html">All decisions</a></li>
<li><a href="{root}documents.html">Documents</a></li></ul></div>
<div><h2>Reference</h2><ul>
<li><a href="{root}search.html">Search</a></li><li><a href="{root}glossary.html">Glossary</a></li>
<li><a href="{root}about.html">About &amp; methodology</a></li>
<li><a href="{root}all-items.html">Everything on one page</a></li></ul></div>
</div></footer>"""


def render_crumbs(root: str, parts: list) -> str:
    bits = [f'<li><a href="{root}index.html">Home</a></li>']
    for i, (href, label) in enumerate(parts):
        if href and i < len(parts) - 1:
            bits.append(f'<li><a href="{root}{href}">{esc(label)}</a></li>')
        else:
            bits.append(f'<li aria-current="page">{esc(label)}</li>')
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(bits)}</ol></nav>'


COV: dict = {}


def page(path: str, title: str, body: str, *, active: str = "", desc: str = "",
         crumbs: list | None = None, maps: bool = False, home: bool = False) -> None:
    """Write one page. `path` is relative to archive/; links are made relative to it."""
    root = "../" * path.count("/")
    full_title = SITE_NAME if home else f"{title} - {SITE_NAME}"
    desc = desc or "Searchable citizen archive of the decisions of the municipal council of Aldersbach."
    scripts = f'<script src="{root}assets/app.js" defer></script>'
    if maps:
        scripts += f'<script src="{root}data/map-data.js" defer></script><script src="{root}assets/map.js" defer></script>'
    html = f"""<!doctype html>
<html lang="en" data-root="{root}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{ui(full_title)}</title>
<meta name="description" content="{ui(desc)}">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="{root}assets/wappen-aldersbach.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}assets/style.css">
<script>try{{var t=localStorage.getItem("ba-theme");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
{scripts}
</head>
<body>
{render_header(root, active)}
<main id="main" class="wrap">
{render_crumbs(root, crumbs) if crumbs else ""}
{body}
</main>
{render_footer(root, COV)}
</body>
</html>
"""
    out = ARCHIVE / path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


# ---- shared fragments --------------------------------------------------------------
def badge(kind: str, root: str | None = None) -> str:
    label, en, tone = KINDS[kind]
    if root is None:
        return f'<span class="badge tone-{tone}" title="{esc(en)}">{esc(label)}</span>'
    return (f'<a class="badge tone-{tone}" href="{root}glossary.html#{kind_anchor(kind)}" '
            f'title="{esc(en)} (glossary)">{esc(label)}</a>')


def topic_chip(topic: str, root: str, n: int | None = None) -> str:
    cnt = f' <span class="n">{n}</span>' if n is not None else ""
    return f'<a class="chip" href="{root}topics/{topic_slug(topic)}.html">{esc(topic)}{cnt}</a>'


def amounts_of(it: dict) -> str:
    return ", ".join(
        (lambda v: v if v.strip().endswith("€") else f"{v} €")(str(a.get("value", "")).strip())
        for a in it["facts"].get("amounts", []))


def place_chips(locs: list) -> str:
    out = []
    for l in locs:
        local = l.get("in_aldersbach", True)
        if l.get("resolved"):
            approx = not str(l.get("precision", "exact")).startswith("exact")
            osm = f"https://www.openstreetmap.org/?mlat={l['lat']}&amp;mlon={l['lon']}#map=17/{l['lat']}/{l['lon']}"
            tip = ("Flurstück (BayernAtlas/ALKIS)" if "Flurstück" in str(l.get("type", ""))
                   else str(l.get("display", "")))
            tip += " - approximate position" if approx else ""
            cls = "place" + (" approx" if approx else "") + ("" if local else " ext")
            out.append(f'<a class="{cls}" href="{osm}" title="{esc(tip)}"><span class="dot"></span>'
                       f'{esc(l["name"])}{" *" if approx else ""}</a>')
        else:
            out.append(f'<span class="place nogeo" title="not found in OpenStreetMap">{esc(l["name"])}</span>')
    return f'<div class="places">{"".join(out)}</div>' if out else ""


def row_link(it: dict, root: str, snippet: str = "") -> str:
    sn = f'<span class="snip">{snippet}</span>' if snippet else ""
    return (f'<li><a class="row-link" href="{decision_path(it, root)}">'
            f'<span class="date">{esc(it["meeting_date"])}</span>'
            f'<span class="top-no">TOP {esc(it["top"])}</span>'
            f'<span class="subj">{ui(it["subject"])}</span>{badge(it["_kind"])}{sn}</a></li>')


def entry(it: dict, root: str, show_date: bool = False) -> str:
    """Agenda entry: full summary, facts, places, links and the verbatim German text."""
    vote = it["facts"].get("vote")
    amounts = amounts_of(it)
    facts = []
    if vote:
        facts.append(f'Vote as printed: <em lang="de">{esc(vote)}</em>')
    if amounts:
        facts.append(f"Amounts: {esc(amounts)}")
    facts_html = f'<p class="facts">{" &middot; ".join(facts)}</p>' if facts else ""
    hl = (f'<a href="{issue_pdf(it, root, True)}">Highlighted PDF, p. {it["page_start"]}</a>'
          if has_highlight(it) else "")
    when = f'<small>{esc(it["meeting_date"])}</small>' if show_date else ""
    return f"""<li class="entry" id="{esc(anchor_of(it))}">
<div class="gutter">TOP {esc(it['top'])}{when}</div>
<div>
<div class="head">{badge(it['_kind'], root)}{topic_chip(it['topic'], root)}</div>
<h3><a href="{decision_path(it, root)}">{ui(it['subject'])}</a></h3>
<p class="decision">{ui(it['decision'])}</p>
{facts_html}{place_chips(it.get('locations', []))}
<p class="links"><a href="{decision_path(it, root)}">Decision page</a>{hl}<a href="{issue_pdf(it, root)}">Original PDF</a></p>
<details class="src"><summary>Originaltext (German, verbatim)</summary><div class="verbatim" lang="de">{esc(it['source_text'])}</div></details>
</div></li>"""


# ---- dossiers (Verläufe) --------------------------------------------------------
TIMELINES = [
    {
        "slug": "bplan-schwaig-x",
        "status": "open",
        "status_note": "2. öffentliche Auslegung läuft (Bekanntmachung vom 20.10.2026); Wasserrechtsverfahren wird vorbereitet",
        "title": 'Bebauungsplan "Schwaig X" (new residential area)',
        "intro": ("From the Aufstellungsbeschluss (resolution to draw up the plan, 20.04.2022) via preliminary draft, "
                  "first public Auslegung (2025), Abwägung (weighing of objections) to the second Auslegung and the "
                  "Satzung (statute) in autumn 2026. Traffic study and noise report accompany the process."),
        "keywords": r"Schwaig\s?X|Abt-Zanker|Verkehrsuntersuchung",
        "docs": [
            ("bplan-schwaig-x-bekanntmachung-aufstellung-2024", "2024-11", "Public notice: Aufstellungsbeschluss"),
            ("bplan-schwaig-x-vorentwurf", "2024/2025", "Preliminary draft (Vorentwurf)"),
            ("bplan-schwaig-x-begruendung-2024", "2024-11", "Begründung (rationale), 1st version"),
            ("bplan-schwaig-x-starkregen-ergebnis", "2024-12", "Heavy-rain analysis, results"),
            ("bplan-schwaig-x-beschluss-1-auslegung-bplan", "2025-04", "Council resolution: 1. Auslegung (B-Plan)"),
            ("bplan-schwaig-x-beschluss-1-auslegung-fplan", "2025-04", "Council resolution: 1. Auslegung (F-Plan)"),
            ("bplan-schwaig-x-bekanntmachung-1-auslegung", "2025-04", "Public notice: 1. Auslegung"),
            ("bplan-schwaig-x-schallbericht-2025", "2025/2026", "Noise report (Schalltechnischer Bericht)"),
            ("bplan-schwaig-x-geotechnik-2022", "2022-11-24", "Geotechnical report"),
            ("bplan-schwaig-x-geotechnik-2026", "2026-09-01", "Geotechnical report (update)"),
            ("bplan-schwaig-x-umweltbericht", "2026-10", "Umweltbericht (environmental report)"),
            ("bplan-schwaig-x-beschluss-abwaegung", "2026-10", "Council resolution: Abwägung"),
            ("bplan-schwaig-x-beschluss-2-auslegung", "2026-10", "Council resolution: 2. Auslegung"),
            ("bplan-schwaig-x-bekanntmachung-2-auslegung", "2026-10", "Public notice: 2. Auslegung"),
            ("bplan-schwaig-x-satzung", "2026-10", "Satzung (statute, final plan)"),
            ("bplan-schwaig-x-lageplan", "2026-10", "Site plan (Lageplan)"),
            ("bplan-schwaig-x-verkehrsuntersuchung", "2026-10", "Traffic study (Verkehrsuntersuchung)"),
            ("bplan-schwaig-x-umweltinfos-aushang", "2026-09", "Public notice: environmental information"),
        ],
    },
    {
        "slug": "so-energie-batteriespeicheranlage",
        "status": "open",
        "status_note": "Aufstellungsbeschluss gefasst (11.12.2025); öffentliche Auslegung und Festsetzung stehen aus",
        "title": 'Vorhabenbezogener Bebauungsplan "SO Energie - Batteriespeicheranlage am Umspannwerk"',
        "intro": ("Grid-scale battery storage near the Pörndorf substation: Gestattungsvertrag (grid connection consent), "
                  "Aufstellungsbeschluss with parallel F-Plan change (Deckblatt Nr. 40), early public participation."),
        "keywords": r"SO\s?Energie|Batteriespeicher|Umspannwerk",
        "docs": [
            ("so-energie-batteriespeicher-bekanntmachung", "2025-10", "Public notice: Aufstellungsbeschluss"),
            ("so-energie-batteriespeicher-satzung", "2025-10", "Draft plan (Satzung/plan document)"),
        ],
    },
    {
        "slug": "ge-uttigkofen-eggerting",
        "status": "open",
        "status_note": "Aufstellung beschlossen (12.11.2025); öffentliche Auslegung steht aus",
        "title": 'Gewerbegebiet "Uttigkofen-Eggerting" (B-Plan GE)',
        "intro": ("Industrial/commercial area development between Uttigkofen and Eggerting (Flur-Nr. 1250, Gemarkung "
                  "Haidenburg): Vorentwurf January 2025, Abwägung and Prüfung in November 2025."),
        "keywords": r"Uttigkofen-Eggerting|GE\s+Uttigkofen|Gewerbegebiet\s+Uttigkofen",
        "docs": [
            ("bbp-uttigkofen-eggerting-vorentwurf", "2025-01-29", "Vorentwurf (preliminary draft)"),
            ("bbp-uttigkofen-eggerting-begruendung", "2025-02-10", "Begründung, Vorabzug"),
        ],
    },
    {
        "slug": "ratsinfo-heimat-info",
        "status": "open",
        "status_note": "Session.Net beschlossen (29.07.2026); Ratsinformationssystem noch nicht online",
        "title": "From Klosterkurier to a council information system (Heimat-Info / Session.Net)",
        "intro": ("Aldersbach had no council information system (Ratsinformationssystem). In June 2026 the council "
                  "introduced the Heimat-Info citizen app; on 29.07.2026 it decided to buy the AKDB add-on "
                  '"Session.Net". Once it goes online, this archive can switch to official minutes.'),
        "keywords": r"Heimat-Info|Session\.?\s?Net|AKDB|Ratsinformationssystem|Cosmema",
        "docs": [],
    },
    {
        "slug": "ortskern-staedtebaufoerderung",
        "status": "open",
        "status_note": "2. Bauabschnitt: Vorentwurf gebilligt (29.07.2026), Förderantrag bei der Regierung von Niederbayern läuft",
        "title": "Städtebauförderung Ortskern Aldersbach (urban development around Zisterzienserstraße)",
        "intro": ("Urban-renewal programme in the town centre: parking Brauerei (1st construction phase), then planning "
                  "of the 2nd phase along Zisterzienserstraße."),
        "keywords": r"Städtebauförde|Zisterzienserstra|Ortskern\s+Aldersbach|Brauerei mit Umfeld",
        "docs": [
            ("bek-aufstellungsbeschluss-2025", "2025-07", "Public notice: Aufstellungsbeschluss (Ortskern)"),
        ],
    },
    {
        "slug": "wasser-abwasser",
        "status": "open",
        "status_note": "laufendes Aufgabengebiet: Pumpstationen, Gebührenmodelle, Kläranlage-Vereinbarung mit Aidenbach",
        "title": "Water, sewage and the new split sewage fee (getrennte Abwassergebühr)",
        "intro": ("Pump stations, sewage treatment plant agreement with Markt Aidenbach, and the introduction of the "
                  "split sewage fee (GAG) including the informational brochure."),
        "keywords": r"Kläranlage|Abwasser|Wasserversorgung|Wasserabgabe|Pumpstation|Entwässerung",
        "docs": [
            ("wasserabgabesatzung", "2026-04", "Wasserabgabesatzung (water fee statute)"),
            ("entwaesserungssatzung", "2026-04", "Entwässerungssatzung (sewage statute)"),
            ("beitrags-gebuehrensatzung", "2026-04", "Beitrags- und Gebührensatzung"),
            ("beitrags-gebuehrensatzung-entwaesserung-4", "2026-04", "Beitrags- und Gebührensatzung zur Entwässerungssatzung"),
            ("gag-broschuere", "2025-12", "Brochure: getrennte Abwassergebühr (GAG)"),
        ],
    },
    {
        "slug": "glasfaser-breitband",
        "status": "open",
        "status_note": "Förderantrag nach Gigabit-Richtlinie gestellt; Auswahlverfahren des Netzbetreibers ausstehend",
        "title": "Glasfaser / Breitband (fibre-optic broadband expansion)",
        "intro": ("Fibre-optic rollout thread: a market exploration (15.04. to 13.06.2025) found no provider willing to "
                  "build commercially, so the council had a federal Gigabit-Richtlinie funding application submitted "
                  "and, conditional on approval, decided on a selection procedure for a network operator (30.07.2025). "
                  "Several 2025 street-rehabilitation works were deferred where broadband ducts will be laid first "
                  '(10.09.2025). In Walchsing, the 2022 Leonet network switches operator to "Unsere Grüne Glasfaser" '
                  "(UGG) with a last free house connection until 30.06.2026 (21.05.2026). Open thread: the outcome of "
                  "the funding application and operator selection had not been reported by 02.09.2026; the next update "
                  "is expected in issue 4/2026 (10 December 2026)."),
        "keywords": r"Glasfaser|Breitband|Gigabit|Leonet",
        "docs": [],
    },
]

# ---- documents library -------------------------------------------------------------
DOC_TITLES = {
    "geschaeftsordnung-2026-2032": "Geschäftsordnung des Gemeinderats 2026-2032 (rules of procedure)",
    "gemeinderat-mitglieder-2026-04": "Members of the municipal council (April 2026)",
    "buergermeister-2026-04": "Mayor and deputy mayors (April 2026)",
    "ausschuesse-2026-32": "Committees 2026-2032: members and deputies",
    "gemeinderat-fraktionen-2026-32": "Council groups (Fraktionen) 2026-2032",
    "mitglieder-bau-umweltausschuss": "Members: Bau- und Umweltausschuss",
    "mitglieder-haupt-finanzausschuss": "Members: Haupt- und Finanzausschuss",
    "mitglieder-kindergartenausschuss": "Members: Kindergartenausschuss",
    "mitglieder-rechnungspruefungsausschuss": "Members: Rechnungsprüfungsausschuss",
    "mitglieder-schulverbandsversammlung-aldersbach": "Members: Schulverbandsversammlung Aldersbach",
    "mitglieder-sport-kulturausschuss": "Members: Sport- und Kulturausschuss",
    "jugendbeauftragte": "Jugendbeauftragte (youth representatives)",
    "schulverbandsversammlung-aidenbach": "Members: Schulverbandsversammlung Aidenbach",
    "realsteuerhebesatzung": "Realsteuerhebesatzung (local tax rates)",
    "stellplatzsatzung": "Stellplatzsatzung (parking spaces statute)",
    "hundesteuersatzung": "Hundesteuersatzung (dog tax statute)",
    "reinigungs-sicherungsverordnung": "Reinigungs- und Sicherungsverordnung (street cleaning and winter service)",
    "aufhebung-verordnung-verbrennen-abfaelle": "Aufhebung der Verordnung über das Verbrennen von Abfällen (repeal)",
    "bekanntmachung-pv-freiflaechen": "Public notice: PV-Freiflächen (ground-mounted solar)",
    "vergabekriterien-2025-12-11": "Vergabekriterien (allocation criteria), 11.12.2025",
    "bplan-schwaig-x-begruendung": "Begründung (rationale), current version",
    "bplan-schwaig-x-starkregenanalyse": "Heavy-rain analysis (Starkregenanalyse)",
    "bplan-schwaig-x-umweltbericht-2024": "Umweltbericht (environmental report), 2024 version",
    "beschlussauszug-2025": "Beschlussauszug 2025 (resolution extract)",
    "zusammenfassende-erklaerung-bbp": "Zusammenfassende Erklärung, Bebauungsplan (summary statement)",
    "zusammenfassende-erklaerung-fnp": "Zusammenfassende Erklärung, Flächennutzungsplan (summary statement)",
}
DOC_GROUPS = [
    ("plans", "Development plans (Bauleitplanung)"),
    ("statutes", "Statutes, ordinances and fees"),
    ("minutes", "Minutes extracts"),
    ("council", "Council and committees"),
    ("other", "Other notices"),
]


def doc_group(doc_id: str) -> str:
    if doc_id.startswith(("bplan-", "bbp-", "so-energie", "zusammenfassende", "bek-aufstellung")):
        return "plans"
    if "niederschrift" in doc_id or "beschlussauszug" in doc_id:
        return "minutes"
    if "satzung" in doc_id or "verordnung" in doc_id or doc_id == "gag-broschuere":
        return "statutes"
    if re.match(r"(mitglieder|ausschuesse|gemeinderat-|buergermeister|jugendbeauftragte|schulverband|geschaeftsordnung)", doc_id):
        return "council"
    return "other"


def doc_title(doc_id: str, roles: dict) -> str:
    if doc_id in roles:
        return roles[doc_id][1]
    if doc_id in DOC_TITLES:
        return DOC_TITLES[doc_id]
    m = re.match(r"niederschrift-auszug-(\d+)", doc_id)
    if m:
        return f"Auszug aus der Niederschrift (minutes extract) no. {m.group(1)}"
    return doc_id.replace("-", " ").capitalize()


# ---- glossary ----------------------------------------------------------------------
KIND_GLOSS = {
    "beschluss": "The council passed a formal resolution. The newsletter says \"beschloss\", \"beschließt\", \"entschied\" or similar.",
    "vergabe": "The council awarded a contract (works, supplies or services) to a company.",
    "zustimmung": "The council agreed to or approved a proposal, application or request.",
    "billigung": "The council approved a draft (typically a plan draft) so that the procedure can continue. Not yet the final decision.",
    "einvernehmen": "Gemeindliches Einvernehmen: the municipality's statutory consent to a building project that the district office (Landratsamt) decides on (section 36 BauGB).",
    "befürwortung": "The council spoke in favour of something that another body decides.",
    "bestätigung": "The council confirmed an earlier decision, an election result or an appointment.",
    "ablehnung": "The council rejected the proposal or application.",
    "vertagung": "The item was postponed to a later meeting.",
    "kenntnisnahme": "The council was informed and took note. No decision was taken.",
    "keineangabe": "The newsletter text does not say what (if anything) was decided. The archive does not guess.",
}
GLOSSARY = [
    ("gemeinderat", "Gemeinderat", "municipal council", "The elected council of the municipality, chaired by the first mayor (Erster Bürgermeister)."),
    ("top", "TOP (Tagesordnungspunkt)", "agenda item", "One numbered item of a council meeting. TOP numbers are taken from the newsletter as printed."),
    ("sitzung", "Gemeinderatssitzung", "council meeting", "A meeting of the council. The newsletter reports the public part under \"Infos aus der Gemeinderatssitzung\"."),
    ("klosterkurier", "Aldersbacher Klosterkurier", "municipal newsletter", "The quarterly official newsletter of Aldersbach and the primary source of this archive."),
    ("niederschrift", "Niederschrift", "minutes", "The official record of a meeting. Only a few extracts (Auszüge) are published online."),
    ("bebauungsplan", "Bebauungsplan (B-Plan)", "development plan", "Legally binding plan that sets what may be built on which plots in a defined area."),
    ("vbbp", "Vorhabenbezogener Bebauungsplan", "project-based development plan", "A development plan drawn up together with a specific investor and project."),
    ("fnp", "Flächennutzungsplan (F-Plan, FNP)", "land-use plan", "Preparatory plan for the whole municipality showing intended land uses. Changes are made via numbered Deckblätter."),
    ("deckblatt", "Deckblatt", "amendment sheet", "A numbered amendment to the Flächennutzungsplan or a Bebauungsplan."),
    ("aufstellungsbeschluss", "Aufstellungsbeschluss", "resolution to draw up a plan", "The council's formal start of a planning procedure."),
    ("vorentwurf", "Vorentwurf / Entwurf", "preliminary draft / draft", "Draft versions of a plan that are put out for participation."),
    ("auslegung", "Öffentliche Auslegung", "public display", "The plan draft is made available to the public and authorities, who can submit comments within a deadline."),
    ("abwaegung", "Abwägung", "weighing of comments", "The council's formal assessment of every comment received during participation, with a decision on how each is handled."),
    ("satzung", "Satzung / Satzungsbeschluss", "statute / adoption", "A by-law of the municipality. Adopting a development plan as Satzung makes it legally binding."),
    ("bauantrag", "Bauantrag / Bauvoranfrage", "building application / preliminary enquiry", "Applications to build. The council gives or refuses its Einvernehmen; the district office decides."),
    ("flurstueck", "Flurstück, Fl.Nr., Gemarkung", "parcel, parcel number, cadastral district", "Cadastral identifiers of a plot of land. Parcel pins on the maps are resolved via BayernAtlas (ALKIS)."),
    ("staedtebaufoerderung", "Städtebauförderung", "urban development funding", "State and federal funding programme for town-centre renewal."),
    ("ratsinfo", "Ratsinformationssystem", "council information system", "Online system for agendas and minutes. Aldersbach decided to introduce AKDB \"Session.Net\" on 29.07.2026."),
]


# ---- build -------------------------------------------------------------------------
def build(copy_files: bool = True):
    items, docs = load()
    for it in items:
        it["_kind"] = decision_kind(it)

    ARCHIVE.mkdir(exist_ok=True)
    for d in GENERATED_DIRS:
        shutil.rmtree(ARCHIVE / d, ignore_errors=True)
    for f in LEGACY_FILES:
        (ARCHIVE / f).unlink(missing_ok=True)
    (ARCHIVE / "assets").mkdir()
    (ARCHIVE / "data").mkdir()
    # wappen-aldersbach.svg: Wikimedia Commons "DEU Aldersbach COA.svg" (public domain); also the favicon
    for f in ("style.css", "app.js", "map.js", "wappen-aldersbach.svg"):
        shutil.copy2(SITE_SRC / f, ARCHIVE / "assets" / f)
    (ARCHIVE / ".nojekyll").write_text("", encoding="utf-8")
    if copy_files:
        n, total = copy_pdfs(items, docs)
        print(f"files: {n} copied, {total - n} unchanged")

    doc_by_id = {d["id"]: d for d in docs}
    meetings: dict = {}
    for it in items:
        meetings.setdefault(it["meeting_date"], []).append(it)
    sorted_dates = sorted(meetings, key=date_key)
    for d in sorted_dates:
        meetings[d].sort(key=lambda o: o["_tk"])
    items_by_id = {it["id"]: it for it in items}

    def matches(tl):
        kw = re.compile(tl["keywords"], re.I)
        return [it for it in items if kw.search(it["source_text_display"] + " " + it["subject"] + " " + it["decision"])]

    dossier_items = {tl["slug"]: matches(tl) for tl in TIMELINES}
    dossier_for: dict = {}
    for tl in TIMELINES:
        for it in dossier_items[tl["slug"]]:
            dossier_for.setdefault(it["id"], []).append(tl)
    doc_roles = {doc_id: (tl, role) for tl in TIMELINES for doc_id, _, role in tl["docs"]}

    COV.update(items=len(items), meetings=len(meetings), docs=len(docs),
               first=sorted_dates[0], last=sorted_dates[-1])

    # ---- data files ----------------------------------------------------------------
    geo_items = []
    for it in items:
        pins = [{"lat": l["lat"], "lon": l["lon"], "name": l["name"],
                 "approx": str(l.get("precision", "exact")).startswith("approximate"),
                 "local": bool(l.get("in_aldersbach", True))}
                for l in it.get("locations", []) if l.get("resolved")]
        if pins:
            geo_items.append({"id": it["id"], "p": decision_path(it), "d": it["meeting_date"], "t": it["top"],
                              "s": it["subject"], "tp": it["topic"], "pg": issue_pdf(it, "", has_highlight(it)),
                              "geo": pins})
    geo_ids = {g["id"] for g in geo_items}
    geo_count = sum(len(g["geo"]) for g in geo_items)
    (ARCHIVE / "data/map-data.js").write_text(
        "window.ARCHIVE_GEO = " + json.dumps({"items": geo_items}, ensure_ascii=False, separators=(",", ":")) + ";",
        encoding="utf-8")

    order = {it["id"]: i for i, it in enumerate(items)}
    index = {
        "kinds": {k: list(v) for k, v in KINDS.items()},
        "kindOrder": KIND_DISPLAY_ORDER,
        "items": [{
            "p": decision_path(it), "m": f"meetings/{meeting_file(it['meeting_date'])}",
            "d": it["meeting_date"], "y": it["meeting_date"][-4:], "t": it["top"], "o": order[it["id"]],
            "tp": it["topic"], "k": it["_kind"], "s": it["subject"], "x": it["decision"],
            "tx": it["source_text_display"], "l": " ".join(l["name"] for l in it.get("locations", [])),
        } for it in items],
    }
    (ARCHIVE / "data/search-index.js").write_text(
        "window.ARCHIVE_INDEX = " + json.dumps(index, ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")

    # ---- decision pages --------------------------------------------------------------
    place_map: dict = {}
    for it in items:
        for l in it.get("locations", []):
            place_map.setdefault(l["name"].lower(), []).append(it["id"])

    for it in items:
        root = "../"
        k = it["_kind"]
        label, en, tone = KINDS[k]
        date = it["meeting_date"]
        siblings = meetings[date]
        pos = [o["id"] for o in siblings].index(it["id"])
        prev_it = siblings[pos - 1] if pos > 0 else None
        next_it = siblings[pos + 1] if pos + 1 < len(siblings) else None

        rel, seen = [], {it["id"]}
        for l in it.get("locations", []):
            for oid in place_map.get(l["name"].lower(), []):
                if oid not in seen:
                    seen.add(oid)
                    rel.append(items_by_id[oid])
        rel.sort(key=lambda o: o["_dk"], reverse=True)
        rel = rel[:8]

        vote = it["facts"].get("vote")
        amounts = amounts_of(it)
        places_txt = ", ".join(str(p) for p in it["facts"].get("places", []))
        facts = [("Decision kind", f'{badge(k, root)} <span class="muted small">{esc(en)}</span>')]
        if vote:
            facts.append(("Vote as printed", f'<em lang="de">{esc(vote)}</em>'))
        if amounts:
            facts.append(("Amounts", esc(amounts)))
        if places_txt:
            facts.append(("Places named", f'<span lang="de">{esc(places_txt)}</span>'))
        facts.append(("Topic", topic_chip(it["topic"], root)))
        facts_html = "".join(f"<dt>{a}</dt><dd>{b}</dd>" for a, b in facts)

        locs = it.get("locations", [])
        loc_html = ""
        if locs:
            mp = (f'<div class="bamap small" data-map="items" data-items="{esc(json.dumps([it["id"]]))}">'
                  '<div class="bamap-note">Map loads when visible (needs internet)</div></div>'
                  if it["id"] in geo_ids else "")
            loc_html = (f'<section class="section"><h2>Locations</h2>{place_chips(locs)}'
                        f'<p class="meta" style="margin-top:.5rem">Names as printed in the source, resolved via OpenStreetMap '
                        f'and BayernAtlas. * = approximate position.</p>{mp}</section>')

        issue_label = ISSUE_LABELS.get(it["issue"], it["issue"])
        cite = (f"Aldersbach municipal council, meeting of {date}, TOP {it['top']}: {it['subject']} "
                f"Source: {issue_label}, p. {it['page_start']}.")
        hl_btn = (f'<a class="btn primary" href="{issue_pdf(it, root, True)}">{icon("marker")}Highlighted PDF, p. {it["page_start"]}</a>'
                  if has_highlight(it) else "")
        prov = f"""<section class="prov" aria-labelledby="prov-h">
<h2 id="prov-h">Source and verification</h2>
<p>Printed in <strong>{esc(issue_label)}</strong>, page {it['page_start']}, section "Infos aus der Gemeinderatssitzung vom {esc(date)}".
The highlighted copy marks the cited passage in yellow; the original is untouched.</p>
<div class="btn-row">{hl_btn}<a class="btn" href="{issue_pdf(it, root)}">{icon("file")}Original PDF</a>
<button class="btn" type="button" data-cite="{esc(cite)}">{icon("copy")}Copy citation</button>
<button class="btn" type="button" onclick="window.print()">{icon("print")}Print</button></div>
<p class="check">{icon("check")}Verified: every line, the quote and every fact match the source text literally.</p>
<p class="meta">Published online at <a href="{esc(it['issue_url'])}">{esc(it['issue_url'])}</a><br>Item id <code>{esc(it['id'])}</code></p>
</section>"""

        def mini(lst, current=None):
            if not lst:
                return '<p class="none">None.</p>'
            return '<ul class="mini">' + "".join(
                f'<li{CUR if current and o["id"] == current else ""}><a href="{decision_slug(o)}.html">'
                f'<span class="k">{"TOP " + esc(o["top"]) if current else esc(o["meeting_date"])}</span>'
                f'<span>{ui(o["subject"])}</span></a></li>' for o in lst) + "</ul>"

        dossiers = dossier_for.get(it["id"], [])
        dossier_html = ("".join(f'<p style="margin:.2rem 0"><a href="../verlaeufe/{d["slug"]}.html">{esc(d["title"])}</a></p>'
                                for d in dossiers) if dossiers else '<p class="none">None.</p>')
        pager = '<nav class="pager" aria-label="Agenda">'
        if prev_it:
            pager += (f'<a class="prev" href="{decision_slug(prev_it)}.html"><small>Previous item, TOP {esc(prev_it["top"])}</small>'
                      f'<span>{ui(prev_it["subject"])}</span></a>')
        if next_it:
            pager += (f'<a class="next" href="{decision_slug(next_it)}.html"><small>Next item, TOP {esc(next_it["top"])}</small>'
                      f'<span>{ui(next_it["subject"])}</span></a>')
        pager += "</nav>"

        body = f"""<div class="detail-grid">
<article>
<header class="doc-head">
<div class="meta-line"><span class="top-no">TOP {esc(it['top'])}</span><span>Council meeting
<a href="../meetings/{meeting_file(date)}">{esc(long_date(date))}</a></span></div>
<h1>{ui(it['subject'])}</h1>
</header>
<div class="callout tone-{tone}"><p class="eyebrow">{esc(label)} &middot; what was decided</p><p>{ui(it['decision'])}</p></div>
<dl class="facts">{facts_html}</dl>
<blockquote class="quote" lang="de">{esc(it['quote'])}<footer>Quote from the source text, verbatim</footer></blockquote>
<details class="src"><summary>Originaltext (German, verbatim)</summary><div class="verbatim" lang="de">{esc(it['source_text'])}</div></details>
{loc_html}
{prov}
{pager}
</article>
<aside class="side" aria-label="Context">
<div class="card"><h2>Same meeting, {esc(date)}</h2>{mini(siblings, it["id"])}</div>
<div class="card"><h2>Same places</h2>{mini(rel)}</div>
<div class="card"><h2>Dossiers</h2>{dossier_html}</div>
</aside>
</div>"""
        page(f"decisions/{decision_slug(it)}.html", f"TOP {it['top']}, {date}: {it['subject'][:70]}", body,
             active="decisions/index.html", desc=it["decision"][:200], maps=bool(locs),
             crumbs=[("meetings/index.html", "Meetings"), (f"meetings/{meeting_file(date)}", f"Meeting {date}"),
                     (None, f"TOP {it['top']}")])

    # ---- decisions index -------------------------------------------------------------
    parts = []
    for y in sorted({d[-4:] for d in sorted_dates}, reverse=True):
        parts.append(f'<h2 class="year-h">{y}</h2>')
        for d in [d for d in reversed(sorted_dates) if d.endswith(y)]:
            its = meetings[d]
            parts.append(f'<div class="group-h"><h3>{esc(long_date(d))}</h3>'
                         f'<a href="../meetings/{meeting_file(d)}">Meeting page</a></div>'
                         f'<ol class="list">{"".join(row_link(it, "../") for it in its)}</ol>')
    kinds_used = {}
    for it in items:
        kinds_used[it["_kind"]] = kinds_used.get(it["_kind"], 0) + 1
    legend = " ".join(f'{badge(k, "../")} <span class="muted small">{kinds_used[k]}</span>'
                      for k in KIND_DISPLAY_ORDER if k in kinds_used)
    page("decisions/index.html", "All decisions", f"""<p class="eyebrow">Decisions</p>
<h1>All {len(items)} agenda items</h1>
<p class="lead">One permalink per agenda item, newest first. Each badge is derived from the vote phrase printed in the source, never guessed.</p>
<p class="btn-row" style="margin:1rem 0 .5rem">{legend}</p>
<p class="meta">Looking for something specific? <a href="../search.html">Search with filters</a>.</p>
{"".join(parts)}""", active="decisions/index.html")

    # ---- meeting pages -------------------------------------------------------------
    for i0, date in enumerate(sorted_dates):
        its = meetings[date]
        root = "../"
        issues = sorted({it["issue"] for it in its})
        pg = sorted({it["page_start"] for it in its})
        first = its[0]
        hl = (f'<a class="btn primary" href="{root}files/highlights/{first["issue_file"].split("/")[-1]}#page={pg[0]}">'
              f'{icon("marker")}Highlighted PDF</a>' if has_highlight(first) else "")
        topics_here: dict = {}
        for it in its:
            topics_here[it["topic"]] = topics_here.get(it["topic"], 0) + 1
        chips = " ".join(topic_chip(t, root, n) for t, n in sorted(topics_here.items(), key=lambda kv: -kv[1]))
        pg_ids = [it["id"] for it in its if it["id"] in geo_ids]
        mp = (f'<section class="section"><div class="map-toolbar"><h2 style="margin:0">Where</h2>{map_legend()}</div>'
              f'<div class="bamap medium" data-map="items" data-local-only data-items="{esc(json.dumps(pg_ids))}">'
              '<div class="bamap-note">Map loads when visible (needs internet)</div></div></section>' if pg_ids else "")
        prev_d = sorted_dates[i0 - 1] if i0 > 0 else None
        next_d = sorted_dates[i0 + 1] if i0 + 1 < len(sorted_dates) else None
        pager = '<nav class="pager" aria-label="Meetings">'
        if prev_d:
            pager += f'<a class="prev" href="{meeting_file(prev_d)}"><small>Previous meeting</small><span>{esc(long_date(prev_d))}</span></a>'
        if next_d:
            pager += f'<a class="next" href="{meeting_file(next_d)}"><small>Next meeting</small><span>{esc(long_date(next_d))}</span></a>'
        pager += "</nav>"
        body = f"""<p class="eyebrow">Council meeting</p>
<h1>{esc(long_date(date))}</h1>
<p class="lead">{plural(len(its), 'agenda item')} reported in {esc(', '.join(ISSUE_LABELS.get(i, i) for i in issues))},
page{'s' if len(pg) > 1 else ''} {esc(', '.join(map(str, pg)))}.</p>
<div class="btn-row">{hl}<a class="btn" href="{issue_pdf(first, root).split('#')[0]}#page={pg[0]}">{icon("file")}Original PDF</a></div>
<p class="btn-row" style="margin-top:1rem">{chips}</p>
{mp}
<section class="section"><h2>Agenda</h2><ol class="agenda">{"".join(entry(it, root) for it in its)}</ol></section>
{pager}"""
        page(f"meetings/{meeting_file(date)}", f"Council meeting {date}", body, active="meetings/index.html",
             desc=f"{len(its)} agenda items of the Aldersbach council meeting on {date}.", maps=bool(pg_ids),
             crumbs=[("meetings/index.html", "Meetings"), (None, date)])

    parts = []
    for y in sorted({d[-4:] for d in sorted_dates}, reverse=True):
        cards = []
        for d in [d for d in reversed(sorted_dates) if d.endswith(y)]:
            its = meetings[d]
            tops: dict = {}
            for it in its:
                tops[it["topic"]] = tops.get(it["topic"], 0) + 1
            top3 = ", ".join(t for t, _ in sorted(tops.items(), key=lambda kv: -kv[1])[:3])
            decided = sum(1 for it in its if KINDS[it["_kind"]][2] in ("decide", "approve", "reject"))
            cards.append(f'<a class="card" href="{meeting_file(d)}"><div class="card-top"><span>{WEEKDAYS[Date(*reversed([int(x) for x in d.split(".")])).weekday()]}</span></div>'
                         f'<h3 style="font-size:1.35rem">{esc(d)}</h3>'
                         f'<p>{plural(len(its), "agenda item")}, {decided} with a stated decision</p>'
                         f'<p class="card-foot">{esc(top3)}</p></a>')
        parts.append(f'<h2 class="year-h">{y}</h2><div class="grid">{"".join(cards)}</div>')
    page("meetings/index.html", "Meetings", f"""<p class="eyebrow">Meetings</p>
<h1>Council meetings</h1>
<p class="lead">{len(sorted_dates)} meetings from {sorted_dates[0]} to {sorted_dates[-1]}, as reported in the Klosterkurier.
Each meeting page lists every agenda item with the verbatim German text.</p>
{"".join(parts)}""", active="meetings/index.html")

    # ---- topic pages ---------------------------------------------------------------
    topic_cards = []
    for topic in TOPIC_ORDER:
        its = sorted([it for it in items if it["topic"] == topic], key=lambda it: (tuple(-x for x in it["_dk"]), it["_tk"]))
        parts = []
        for y in sorted({it["meeting_date"][-4:] for it in its}, reverse=True):
            parts.append(f'<h2 class="year-h">{y}</h2><ol class="list">'
                         + "".join(row_link(it, "../") for it in its if it["meeting_date"].endswith(y)) + "</ol>")
        page(f"topics/{topic_slug(topic)}.html", topic, f"""<p class="eyebrow">Topic</p>
<h1>{esc(topic)}</h1>
<p class="lead">{esc(TOPIC_EN[topic])}. {plural(len(its), 'agenda item')}, newest first.</p>
{"".join(parts) or "<p>No items.</p>"}""", active="topics/index.html",
             crumbs=[("topics/index.html", "Topics"), (None, topic)])
        latest = its[0] if its else None
        topic_cards.append(
            f'<a class="card" href="{topic_slug(topic)}.html"><div class="card-top"><span>{plural(len(its), "item")}</span></div>'
            f'<h3>{esc(topic)}</h3><p>{esc(TOPIC_EN[topic])}</p>'
            + (f'<p class="card-foot clamp-3">Latest ({esc(latest["meeting_date"])}): {ui(latest["subject"])}</p>' if latest else "")
            + "</a>")
    page("topics/index.html", "Topics", f"""<p class="eyebrow">Topics</p>
<h1>Browse by topic</h1>
<p class="lead">Every agenda item carries one of ten topic tags.</p>
<div class="grid">{"".join(topic_cards)}</div>""", active="topics/index.html")

    # ---- dossiers ----------------------------------------------------------------
    dossier_cards = []
    for tl in TIMELINES:
        root = "../"
        matched = sorted(dossier_items[tl["slug"]], key=lambda it: (it["_dk"], it["_tk"]))
        lis = "".join(
            f'<li><span class="when">{esc(it["meeting_date"])} <span class="top-no">TOP {esc(it["top"])}</span>{badge(it["_kind"])}</span>'
            f'<a class="what" href="../{decision_path(it)}">{ui(it["subject"])}</a></li>' for it in matched)
        dlis = []
        for doc_id, dlabel, role in tl["docs"]:
            d = doc_by_id.get(doc_id)
            if not d:
                print(f"WARNING: timeline '{tl['slug']}' references unknown document id '{doc_id}'")
                continue
            dlis.append(f'<li class="doc"><span class="when">{esc(dlabel)} &middot; {d["pages_est"]} pages</span>'
                        f'<a class="what" href="{doc_href(d, root)}">{esc(role)}</a></li>')
        status = tl.get("status", "open")
        latest = matched[-1] if matched else None
        body = f"""<p class="eyebrow">Dossier</p>
<h1>{esc(tl['title'])}</h1>
<div class="banner {status}"><span class="status {status}">{status}</span><p lang="de">{esc(tl.get('status_note', ''))}</p></div>
<p class="lead">{esc(tl['intro'])}</p>
<div class="split" style="margin-top:2rem">
<section><h2>Council decisions over time ({len(matched)})</h2>
{f'<ol class="timeline">{lis}</ol>' if lis else '<p class="muted">No agenda items matched yet.</p>'}</section>
<section><h2>Documents ({len(dlis)})</h2>
{f'<ol class="timeline">{"".join(dlis)}</ol>' if dlis else '<p class="muted">No documents collected for this dossier.</p>'}</section>
</div>"""
        page(f"verlaeufe/{tl['slug']}.html", tl["title"], body, active="verlaeufe/index.html", desc=tl["intro"][:200],
             crumbs=[("verlaeufe/index.html", "Dossiers"), (None, tl["title"][:48] + ("..." if len(tl["title"]) > 48 else ""))])
        dossier_cards.append((tl, matched, len(dlis), latest))

    def dossier_card(tl, matched, ndocs, latest, root):
        st = tl.get("status", "open")
        return (f'<a class="card" href="{root}verlaeufe/{tl["slug"]}.html"><div class="card-top"><span class="status {st}">{st}</span>'
                f'<span>{plural(len(matched), "decision")}, {plural(ndocs, "document")}</span></div>'
                f'<h3>{esc(tl["title"])}</h3><p class="clamp-3" lang="de">{esc(tl.get("status_note", ""))}</p>'
                + (f'<p class="card-foot">Latest: {esc(latest["meeting_date"])}, TOP {esc(latest["top"])}</p>' if latest else "")
                + "</a>")

    page("verlaeufe/index.html", "Dossiers", f"""<p class="eyebrow">Dossiers (Verläufe)</p>
<h1>Subjects that span several meetings</h1>
<p class="lead">Each dossier collects the council decisions and documents on one subject in chronological order, with its current status.</p>
<div class="grid wide">{"".join(dossier_card(*c, "../") for c in dossier_cards)}</div>""", active="verlaeufe/index.html")

    # ---- documents -------------------------------------------------------------------
    groups = []
    for key, title in DOC_GROUPS:
        ds = sorted([d for d in docs if doc_group(d["id"]) == key], key=lambda d: doc_title(d["id"], doc_roles).lower())
        if not ds:
            continue
        rows = []
        for d in ds:
            t = doc_title(d["id"], doc_roles)
            via = d.get("retrieved_via") or "live"
            via_txt = ("aldersbach.de (live)" if via == "live" else
                       f"Wayback Machine snapshot {via.split(':')[-1][:4]}-{via.split(':')[-1][4:6]}-{via.split(':')[-1][6:8]}"
                       if via.startswith("wayback:") else via)
            dossier = doc_roles.get(d["id"])
            dchip = (f'<a href="verlaeufe/{dossier[0]["slug"]}.html">Dossier: {esc(dossier[0]["title"][:44])}'
                     f'{"..." if len(dossier[0]["title"]) > 44 else ""}</a>' if dossier else "")
            search_text = f'{t} {d["id"]} {title} {dossier[0]["title"] if dossier else ""}'
            rows.append(f'<li class="doc-row" data-doc="{esc(search_text)}">'
                        f'<a class="t" href="{doc_href(d, "")}">{esc(t)}</a>'
                        f'<span class="sub"><span>{d["pages_est"]} pages</span><span>{esc(via_txt)}</span>{dchip}<code>{esc(d["id"])}</code></span>'
                        f'<span class="act"><a class="btn" href="{doc_href(d, "")}">{icon("file")}PDF</a>'
                        f'<a class="btn" href="{esc(d["url"])}" title="Original location">{icon("external")}<span class="sr-only">Original URL</span></a></span></li>')
        groups.append(f'<section class="section" data-doc-group><div class="group-h"><h2>{esc(title)}</h2>'
                      f'<span class="meta">{len(ds)}</span></div><ol class="list">{"".join(rows)}</ol></section>')
    page("documents.html", "Documents", f"""<p class="eyebrow">Documents</p>
<h1>Council documents</h1>
<p class="lead">{len(docs)} PDFs collected from aldersbach.de and, for the pre-relaunch site, from the Wayback Machine:
statutes, development-plan files, minutes extracts and committee lists. Original filenames are kept.</p>
<div class="filters"><input class="input" id="doc-filter" type="search" placeholder="Filter documents" aria-label="Filter documents" style="flex:1 1 260px">
<span class="count" id="doc-count">{len(docs)} documents</span></div>
{"".join(groups)}""", active="documents.html")

    # ---- all items (no-JS, everything on one page) -------------------------------------
    parts = []
    for d in sorted_dates:
        parts.append(f'<section class="section"><div class="group-h"><h2>{esc(long_date(d))}</h2>'
                     f'<a href="meetings/{meeting_file(d)}">Meeting page</a></div>'
                     f'<ol class="agenda">{"".join(entry(it, "") for it in meetings[d])}</ol></section>')
    page("all-items.html", "All items on one page", f"""<p class="eyebrow">Everything</p>
<h1>All {len(items)} agenda items on one page</h1>
<p class="lead">Oldest first, with the full German source text. This page works without JavaScript; use your browser's find (Ctrl+F).</p>
{"".join(parts)}""", active="")

    # ---- search ----------------------------------------------------------------------
    page("search.html", "Search", f"""<div id="search-page" class="search-page">
<p class="eyebrow">Search</p>
<h1>Search all decisions</h1>
<form class="hero-search" role="search" data-local>
<label class="omni-field">{icon("search")}<span class="sr-only">Search terms</span>
<input id="sq" name="q" type="search" autocomplete="off" spellcheck="false" placeholder="e.g. Walchsing, 447/7, Kindergarten, 30.07.2025"></label>
<button class="btn primary" type="submit">Search</button></form>
<div class="filters">
<select class="select" id="f-topic" aria-label="Topic"><option value="">All topics</option></select>
<select class="select" id="f-year" aria-label="Year"><option value="">All years</option></select>
<select class="select" id="f-kind" aria-label="Decision kind"><option value="">All decision kinds</option></select>
<select class="select" id="f-sort" aria-label="Sort"><option value="date">Newest first</option><option value="relevance">Best match</option></select>
<span class="count" id="count" aria-live="polite">Loading index...</span></div>
<div id="results"></div>
<noscript><div class="card"><p>Search needs JavaScript. Without it, use <a href="all-items.html">all items on one page</a> and your browser's find.</p></div></noscript>
</div>""", active="", desc="Full-text search across all council decisions.")

    # ---- glossary --------------------------------------------------------------------
    kinds_html = "".join(
        f'<div id="{kind_anchor(k)}"><dt lang="de">{badge(k)} <span class="en">{esc(v[1])}</span></dt>'
        f'<dd>{esc(KIND_GLOSS[k])} <span class="muted">({kinds_used.get(k, 0)} items)</span></dd></div>'
        for k, v in KINDS.items())
    terms_html = "".join(
        f'<div id="{a}"><dt><span lang="de">{esc(t)}</span> <span class="en">{esc(en)}</span></dt><dd>{esc(x)}</dd></div>'
        for a, t, en, x in GLOSSARY)
    page("glossary.html", "Glossary", f"""<div class="prose">
<p class="eyebrow">Glossary</p>
<h1>German council terms, explained</h1>
<p class="lead">The archive keeps German legal and planning terms as printed. Here is what they mean.</p>
<h2>Decision kinds</h2>
<p>Every agenda item gets one badge, derived from the vote phrase the newsletter prints. If the text names no decision, the archive says so.</p>
<dl class="gloss">{kinds_html}</dl>
<h2>Terms</h2>
<dl class="gloss">{terms_html}</dl>
</div>""", active="", desc="Plain-English explanations of German council and planning terms.")

    # ---- about -----------------------------------------------------------------------
    issue_rows = []
    for iss, lab in ISSUE_LABELS.items():
        ds = sorted({it["meeting_date"] for it in items if it["issue"] == iss}, key=date_key)
        n = sum(1 for it in items if it["issue"] == iss)
        if ds:
            links = ", ".join(f'<a href="meetings/{meeting_file(d)}">{d}</a>' for d in ds)
            issue_rows.append(f"<tr><td>{esc(lab)}</td><td>{links}</td><td>{n}</td></tr>")
    page("about.html", "About", f"""<div class="prose">
<p class="eyebrow">About</p>
<h1>About this archive</h1>
<p class="lead">A citizen asks: what was decided about X, when, and how did it develop? This archive answers in English,
with the verbatim German source one click away.</p>
<h2>What it is</h2>
<p>An independent, non-official archive of the decisions of the Gemeinderat Aldersbach (Landkreis Passau, Bavaria),
covering {len(sorted_dates)} meetings from {sorted_dates[0]} to {sorted_dates[-1]}: {len(items)} agenda items,
{len(docs)} documents and {geo_count} map locations.</p>
<h2>Sources</h2>
<p>The primary source is the section "Infos aus der Gemeinderatssitzung" in the quarterly municipal newsletter
<em>Aldersbacher Klosterkurier</em>. Older issues were recovered from the Wayback Machine, current ones from the
municipal website and the Heimat-Info platform.</p>
<div class="table-scroll"><table><thead><tr><th>Issue</th><th>Meetings covered</th><th>Items</th></tr></thead>
<tbody>{"".join(issue_rows)}</tbody></table></div>
<p>Secondary sources are {len(docs)} council documents from aldersbach.de (see <a href="documents.html">Documents</a>).</p>
<h2>How it was made</h2>
<ul>
<li>Text and page geometry were extracted from the PDFs; advertisements and layout noise were removed by geometric rules.</li>
<li>For each agenda item a local language model wrote the English subject and decision, a topic tag and the facts,
derived only from the German source text, never from another summary.</li>
<li>Every quote and every fact was then checked literally against the extracted page text. All {len(items)} items pass.</li>
<li>Decision-kind badges come from the printed vote phrase ("beschloss", "stimmte zu", "Kenntnisnahme", ...).
See the <a href="glossary.html">glossary</a>.</li>
<li>Place names printed in the text were resolved via OpenStreetMap; parcel numbers (Flurstücke) via BayernAtlas (ALKIS).
Approximate pins are marked with *.</li>
<li>The highlighted PDF copies mark each cited passage in yellow; the original PDFs are kept untouched next to them.</li>
</ul>
<h2>Known gaps</h2>
<ul>
<li>The newsletter prints summaries, not minutes. Votes appear only when the text names them; vote counts are never given.</li>
<li>Meetings before 12.12.2024 are not covered.</li>
<li>Some TOP numbers are missing in print (29.01.2025 jumps from TOP 14 to 16; 25.03.2026 reports only TOP 01 to 06).</li>
<li>Klosterkurier 4/2026 is announced for 10.12.2026 and not yet included.</li>
</ul>
<h2>Official council information system</h2>
<p>On 29.07.2026 the council decided to introduce the AKDB "Session.Net" council information system. It was not
online when this archive was built. Once it is, this archive can switch to the official agendas and minutes.</p>
<p class="meta">Built {STAMP}. No tracking, no cookies, no external fonts. Maps load tiles from basemap.de or OpenStreetMap only when shown.</p>
</div>""", active="about.html", desc="Sources, methodology, verification and known gaps of the archive.")

    # ---- home ----------------------------------------------------------------------
    page("map.html", "Map", f"""<p class="eyebrow">Map</p>
<h1>Where the council decided things</h1>
<p class="lead">{geo_count} places named in {len(geo_items)} agenda items. Click a pin for the decision.</p>
<div class="map-toolbar"><select class="select" id="map-topic" aria-label="Filter map by topic"><option value="">All topics</option></select>{map_legend()}</div>
<div class="bamap tall" data-map="all"><div class="bamap-note">The map needs an internet connection for the background tiles.</div></div>""",
         active="map.html", maps=True, desc="Map of all places named in the council decisions.")

    # ---- home (deliberately short: search first, then what is new and what is open) ----
    root = ""
    last_d = sorted_dates[-1]
    latest_its = meetings[last_d]
    open_threads = [c for c in dossier_cards if c[0].get("status") == "open"]
    examples = " ".join(f'<a class="chip" href="search.html?q={q}">{q}</a>' for q in ("Walchsing", "Glasfaser", "Schwaig X", "Kindergarten"))
    threads = "".join(
        f'<li><a class="thread-link" href="verlaeufe/{tl["slug"]}.html"><span class="subj">{esc(tl["title"])}</span>'
        f'<span class="meta">{plural(len(matched), "decision")}'
        + (f', latest {esc(latest["meeting_date"])}' if latest else "") + "</span></a></li>"
        for tl, matched, _, latest in open_threads)
    body = f"""<section class="hero">
<h1>Gemeinderat Aldersbach</h1>
<p class="lead">Council meetings {sorted_dates[0]} to {sorted_dates[-1]}, as reported in the Aldersbacher Klosterkurier.</p>
{omni_form(root, "hq", big=True).replace('class="omni"', 'class="omni hero-search"')}
<div class="hero-hints">Try {examples}</div>
</section>

<div class="split home-split">
<section>
<div class="section-head"><h2>Latest meeting, {esc(last_d)}</h2>
<a href="meetings/{meeting_file(last_d)}">All {len(latest_its)} items &rarr;</a></div>
<ol class="list">{"".join(row_link(it, root) for it in latest_its[:5])}</ol>
</section>
<section>
<div class="section-head"><h2>Open threads</h2><a href="verlaeufe/index.html">All dossiers &rarr;</a></div>
<ol class="list">{threads}</ol>
</section>
</div>"""
    page("index.html", "Home", body, home=True)

    print(f"archive built: {len(meetings)} meetings, {len(TOPIC_ORDER)} topics, {len(TIMELINES)} dossiers, "
          f"{len(docs)} docs, {len(items)} items")


def map_legend() -> str:
    return ('<div class="legend"><span><i style="background:var(--pin-exact)"></i>exact</span>'
            '<span><i style="background:var(--pin-approx)"></i>approximate *</span>'
            '<span><i style="background:var(--pin-ext)"></i>outside Aldersbach</span></div>')


if __name__ == "__main__":
    build(copy_files="--no-pdfs" not in sys.argv)
