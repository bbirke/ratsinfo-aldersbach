# Aldersbach Gemeinderat — Decision Archive (README)

An independent, searchable archive of what the municipal council (*Gemeinderat*) of
**Aldersbach** (Landkreis Passau, Bavaria; ~4,500 inhabitants) decided between
**12.12.2024 and 02.09.2026**, built so a citizen can ask "what was decided about X,
when, and how did it develop?" and get an answer with a link to the official source.

* All summaries and pages are in **English**; every German source text and every
  quote is kept **verbatim in German**.
* German legal/planning terms (Bebauungsplan, Aufstellungsbeschluss, Satzung,
  Abwägung, TOP, Beschluss vs. Kenntnisnahme, billigt vs. beschließt) are kept and
  glossed in English where useful.
* Every summary is derived **only** from the German source text — never from
  another summary.

## How to use

* **[index.html](index.html)** — the hub: full-text search with facets
  (topic / year / decision kind), the clustered **decision map**, recently
  decided items, and the **open threads** board. Press <kbd>/</kbd> anywhere to
  search; the header search works on every page.
* **[decisions/index.html](decisions/index.html)** — **one page per agenda item**
  (215 permalinks): English summary, decision, facts, locations + map chip,
  verbatim German text, provenance, and context (same meeting, same places,
  dossiers). Every decision-kind badge (Beschluss, Zustimmung, Kenntnisnahme,
  Ablehnung, …) is derived from the verified vote phrase in the source text.
* **[meetings/index.html](meetings/index.html)** — one page per council meeting
  (20 meetings), each item with the collapsible German "Originaltext" and links
  to the **original PDF** and the **highlighted PDF** (cited passages marked).
* **[topics/index.html](topics/index.html)** — the ten topic tags, newest first.
* **[verlaeufe/index.html](verlaeufe/index.html)** — timelines for subjects that
  span several meetings/documents, with OPEN/CLOSED status.
* **[documents.html](documents.html)** — all 60 collected council documents.

In every item the collapsible block "Originaltext (Deutsch, wörtlich)" contains the
verbatim German paragraphs as printed and links to the source PDF at the exact page
(`…pdf#page=N`). Decision pages additionally link a **highlighted PDF copy** where
the cited passage is marked with a yellow overlay (generated at build time from the
extractor's item geometry; originals untouched).

## Sources

### Primary source: "Aldersbacher Klosterkurier"

The official quarterly newsletter of the municipality prints a section
**"Infos aus der Gemeinderatssitzung vom DD.MM.YYYY"** with per-agenda-item (TOP)
summaries. Seven issues were collected (2025–2026); all PDFs are in
`sources/klosterkurier/`, checksums and URLs in `sources/manifest.jsonl`.

| Issue | Meeting dates covered | File | Origin |
|---|---|---|---|
| 1/2025 (März 2025) | 12.12.2024, 29.01.2025, 19.02.2025 | klosterkurier-2025-01.pdf | Wayback Machine (original: aldersbach.de/images/infoblatt/AKK_1-25_web.pdf, snapshot 2025-03-13) |
| 2/2025 (Juni 2025) | 17.03., 16.04., 19.05.2025 | klosterkurier-2025-02.pdf | Wayback (AKK_2-25.pdf, snapshot 2025-06-06) |
| 3/2025 (September 2025) | 25.06., 30.07., 10.09.2025 | klosterkurier-2025-03.pdf | Wayback (AKK_3-25_web.pdf, snapshot 2025-09-26) |
| 4/2025 (Dezember 2025) | 16.10., 12.11.2025 | klosterkurier-2025-04.pdf | Wayback (AKK_4-25_web.pdf, snapshot 2025-12-10) |
| 1/2026 (März 2026) | 11.12.2025, 28.01., 25.02.2026 | klosterkurier-2026-01.pdf | Wayback (aldersbach.de/wp-content/uploads/2026/03/AKK1-26_web.pdf, snapshot 2026-03-18) |
| 2/2026 (Juni 2026) | 25.03., 29.04., 21.05.2026 | klosterkurier-2026-02.pdf | live: heimatinfo.blob.core.windows.net/public/de86e7a0-1efa-4835-962f-1ff6c26e0b9a.pdf |
| 3/2026 (September 2026) | 24.06., 29.07., 02.09.2026 | klosterkurier-2026-03.pdf | live: …/public/ce5180c3-1219-415c-80b3-15f5d211e247.pdf (same issue also at …/9f19bc65-416f-4a1c-85ae-c6474b89a6e1.pdf) |

How the older issues were found: the pre-relaunch municipal website (Joomla) still
listed the issues under `/images/infoblatt/…`; after the 2026 relaunch those paths
disappeared, but the Wayback Machine had archived the PDFs. The relaunch site
(WordPress) also published issue 1-2026 under `/wp-content/uploads/2026/03/`.
The two 2026 issues are published on the Heimat-Info platform
(heimat-info.de, organization "Aldersbacher Klosterkurier") and were fetched from
its Azure blob storage; an internal JSON API of that platform
(heimatinfo-api-platform.azurewebsites.net) confirmed the issue list.

### Secondary sources: aldersbach.de and Wayback Machine

60 council-relevant documents in `sources/aldersbach/` (see documents.html):
Satzungen (water, sewage, dog tax, Realsteuer, Stellplatz), Geschäftsordnung des
Gemeinderats 2026–2032, the full Bebauungsplan "Schwaig X" package incl.
Umweltbericht, Abwägung and Auslegung documents, minutes extracts
("Auszug aus der Niederschrift"), committee membership lists, Vergabekriterien,
and more. Everything is recorded in `sources/manifest.jsonl` with URL, fetch date,
SHA-256 and retrieval path (live vs. Wayback snapshot).

Polite-crawling rules were followed: ≥ 1 s between requests to the same host,
identifying User-Agent, public pages only, no logins, no form submissions.

## Coverage

* **20 council meetings** covered: 12.12.2024 – 02.09.2026, complete from the first
  issue available (1/2025) through 3/2026. All 215 agenda items printed in the
  "Infos aus der Gemeinderatssitzung" sections were extracted.
* **Documents**: 60 council PDFs (2022–2026), most notably the complete
  Bebauungsplan "Schwaig X" trail and the six "Auszug aus der Niederschrift"
  minutes extracts.

### Known gaps

1. **Before 12.12.2024**: no 2025/2026 archive scope, but older issues exist —
   e.g. AKK_3-24.pdf (3/2024) and GB_* Gemeindeblatt issues (2021–2024) are visible
   in the Wayback CDX index under `aldersbach.de/images/infoblatt/`.
2. **TOP numbers printed but not present**: the 29.01.2025 meeting in issue 1/2025
   has no TOP 15 in print (numbering jumps 14 → 16). The 25.03.2026 meeting reports
   only TOP 01–06 in the magazine.
3. **The newsletter prints summaries, not minutes.** Votes are only stated when the
   editorial text names them ("beschloss", "stimmte zu", "Kenntnisnahme", …);
   roll-call votes and results are never given. Where the text names no decision,
   the archive says so explicitly.
4. **Baugrundstücke/Grundstücksthemen** are covered as reported by the magazine;
   no separate land-sale documents were collected.
5. **Klosterkurier 4/2026** is announced for 10.12.2026 (not yet published when
   this archive was built).
6. Duplicate file: issue 3/2026 exists twice on the blob storage (two GUIDs, same
   content); only one copy is kept (see manifest).

## About the official council information system

On **29.07.2026** (TOP 01) the council decided to buy the AKDB add-on
**„Session.Net"** (Ratsinformationssystem) for its existing "Session" meeting
management software: one-time gross price 8.147,69 € plus 38,08 €/month.
**It was not yet online when this archive was built.** Once it goes online, this
archive can be switched to the official minutes and agendas; the Heimat-Info app
(introduced 24.06.2026, TOP 03) already publishes the Klosterkurier issues.

## Locations

Each agenda item carries a "Locations" line derived **only** from the place names
printed in the German source text (streets, Ortsteile, Baugebiete, facilities).
These names were resolved to coordinates via **OpenStreetMap / Nominatim**
(one-time lookups, cached in `data/geocache.json`, ≥ 1.5 s spacing, identifying
User-Agent). Clicking a location opens OpenStreetMap centred on it.

* `*` marks an **approximate** pin (e.g. a Baugebiet mapped to its access street,
  a plan area mapped to the municipality centroid) — the note on each entry says
  how it was anchored.
* **Cadastral parcels (Flurstücke)** referenced in the source texts (e.g.
  „Fl.Nr. 447/7", „Flur-Nr. 507, Gemarkung Pörndorf", „Flur-Nr. 1250, Gemarkung
  Haidenburg") are resolved to the exact parcel centroid via the **BayernAtlas
  API** (`services.atlas.bayern.de`, ALKIS data, EPSG:3857 → WGS84) — tooltips
  name the parcel; the tooltip text explains what was matched.
* Names not found in OpenStreetMap are shown as plain text instead of a pin.
* External references (neighbouring municipalities, company seats such as
  Passau, Cham or Aidenbach) are listed separately under "Also mentioned".
* Coverage: 177 of 215 items mention at least one place; 176 have at least one
  clickable map location; 38 items concern matters without a printed place
  (budget, personnel, general administration).

## Maps

Concept: **"one map, many windows"** — at most two live map instances exist per
page, no matter how many items are listed.

1. **Decision map** (starting page): all 321 location pins, clustered;
   clicking a pin/cluster shows the decision with links to the item and the
   source PDF page; filterable by topic. Loaded lazily only when scrolled into
   view (tiles come from OpenStreetMap, so it needs an internet connection).
2. **Item cards**: a small `🗺 Map` chip. Clicking it moves a single recyclable
   mini map into that card (only that item's pins) and back — the map is never
   duplicated per item.
3. **Meeting pages**: a compact map above the items with that meeting's pins;
   clicking a marker scrolls to the item card.

Implementation: Leaflet + Leaflet.markercluster from unpkg CDN, loaded on
first use; `archive/map-data.js` carries the pin data; plain OSM links keep
working without internet. Parcel pins (BayernAtlas/ALKIS) and approximate pins
(`*`) are colour-distinguished.

## Methodology (reproducible pipeline)

1. `tools/net.py`, `tools/collect.py` — polite collection, manifest with SHA-256.
2. `tools/extract_text.py` — `pdftotext -bbox-layout`; geometric rules separate
   body text from advertisements (column anchors, line height, TOP markers);
   215 TOP blocks with page references.
3. `tools/extract_items.py` — per item, a local LLM (GLM-5.3-Flash-NVFP4-NVIDIA-TP4
   via `http://192.168.178.10:8015/v1`, ≤ 8 parallel, reasoning "low") produces the
   English subject/decision, topic tag, language-neutral facts and one verbatim
   German quote, derived only from the source text.
4. `tools/verify.py`, `tools/repair_items.py` — every quote and every fact is
   checked literally against the extracted page text; failures trigger a repair
   pass. Final score: **215/215** on all checks (lines verbatim, quote literal,
   facts literal, topic valid).
5. `tools/build_archive.py` — builds this static site; no JavaScript required
   except the search filter.

## Landkreis Passau (phase 2, checked only)

The Landkreis Passau Kreistag runs Somacos "Session" at
`https://buergerinfo.landkreis-passau.de/`. robots.txt: **absent (404, no
restrictions)**. OParl: **not offered** at the standard paths (/oparl, /oparl/v1.1,
/api/oparl/v1.1 → 404). Volume in the 13 month calendar views Oct 2025 – Oct 2026:
**38 meetings** (7 Kreistag, 8 Kreisausschuss, 23 Fachausschüsse), meetings link
via `si0057.asp?__ksinr=…`. No deeper crawling was performed — awaiting your
decision (see report).
