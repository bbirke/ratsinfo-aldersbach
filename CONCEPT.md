# Concept — „Ratsinfo-Archiv Aldersbach" website / web UI

Status: approved concept, not yet implemented (implementation on request).
Scope of this document: information architecture, page blueprints, core
features, design system, pipeline impact, phases.

---

## 1. Vision and users

A citizen asks: *"What was decided about X, when, and how did it develop?"*
and gets an answer in English with the verbatim German source one click away.

Primary users:
- **Citizens** without background knowledge (need glossary, plain-English
  summaries, location context, honest "this was only information, no decision"
  signalling).
- **Local journalists / council watchers** (need permalinks, search, provenance,
  chronological dossiers).
- **Councillors / administration** (need coverage overview and a citable archive
  until the official Ratsinformationssystem goes online).

## 2. Principles

1. **Static-first, serverless.** Every entity has a real `.html` file. Works
   from `file://` today and can be dropped on GitHub Pages / any webserver
   unchanged tomorrow.
2. **Provenance-first.** Every statement links to the Klosterkurier issue and
   printed page (`…pdf#page=N`) **with the cited passage visually marked in the
   PDF** (pre-generated highlight overlays, see 5.5); verification status
   (215/215 literal checks) is published in About.
3. **English summaries, German sources.** Never derive a summary from another
   summary; decision verbs stay German (Beschluss vs. Kenntnisnahme, billigt
   vs. beschließt).
4. **No-JS degradation.** Maps, chips and search enhance the experience; all
   critical content is plain HTML.
5. **One command to rebuild.** `build_archive.py` generates the whole site from
   `data/`; nothing hand-edited inside `archive/` except static assets.

## 3. Information architecture

| Entity | Page | URL pattern | Notes |
|---|---|---|---|
| Decision (atom) | **detail page per item** (new) | `decisions/2025-07-30-top13-glasfaser.html` | canonical permalink per agenda item |
| Meeting | detail page | `meetings/2025-07-30.html` | agenda, map, issue link, prev/next |
| Topic | list page | `topics/bauleitplanung.html` | 10 fixed tags |
| Dossier (Verlauf) | narrative page | `verlaeufe/glasfaser-breitband.html` | timeline + OPEN/CLOSED status |
| Place | **list + detail pages** (new) | `places/walchsing.html` | auto-generated from the 321 resolved pins |
| Document | library | `documents.html` | type facets: Satzung, B-Plan, minutes extract, committee, misc |
| Glossary | **new** | `glossary.html` | German terms with plain-English explanations |
| About | **new** | `about.html` | methodology, verification, gaps, update workflow |

Global elements: header with **omnibox search** (opens with `/`), breadcrumbs
on all detail pages, footer with coverage + last-update stamp.

## 4. Page blueprints

### 4.1 Home
1. Header: title, one-line mission, omnibox, last-update stamp.
2. **Recently decided** — last 6 items as cards with decision-kind badge.
3. **Open threads** — dossiers whose outcome is pending (Glasfaser operator
   selection, Schwaig X 2. Auslegung, issue 4/2026).
4. **Decision map** preview card (existing component).
5. **Browse** cards: Meetings · Topics · Dossiers · Places · Documents ·
   Glossary · All items.
6. Coverage box (20 meetings, 215 items, 60 documents) → About.

### 4.2 Decision detail page (the atom)
- Header: date, TOP, badges (topic, decision-kind, approximate-locations note).
- English **subject** and **decision** as the primary content block.
- Facts table: vote phrase (verbatim), EUR amounts, places.
- **Locations** line + singleton mini map (existing component).
- **Originaltext** collapsible (verbatim German lines).
- **Provenance box**: issue label, page, item id, verification status, and two
  links: *Original PDF* (`…pdf#page=N`, untouched copy) and *Highlighted PDF*
  (pre-generated copy with the cited passage marked, opens at the right page).
- **Context sidebar**: prev/next item of the same meeting; other decisions on
  the same place(s); other items mentioning the same Flurstück/plan; dossier
  membership.
- Breadcrumb: Home › Meeting › this decision.

### 4.3 Meeting page
Agenda list with decision-kind icons, compact map (existing), issue deep link,
prev/next meeting navigation.

### 4.4 Dossier page
Status banner (OPEN/CLOSED + one-line state), chronological timeline
(decision-kind icons), related documents, related places.

### 4.5 Place page
All decisions touching the place, grouped by year; mini map; synonyms listed
(e.g. Walchsing incl. „Anwesen Vogler", „Apostelbrücke").

### 4.6 Documents library
Table with type facets + full-text search; provenance per document (live URL vs
Wayback snapshot).

### 4.7 Glossary
Term pairs, e.g. Bebauungsplan (development plan), Aufstellungsbeschluss
(resolution to draw up a plan), Abwägung (weighing of objections),
Kenntnisnahme (taking note — no decision), Satzung (statute), TOP (agenda item),
Wirtschaftlichkeitslücke (viability gap funding model). Linked from badges.

## 5. Core features

### 5.1 Decision-kind taxonomy (derived, honest)
Derived in the build from the verified `vote` phrase — never invented:
**Beschluss · Zustimmung · Billigung · Einvernehmen · Beteiligung ·
Kenntnisnahme/informational · none stated**. Rendered as colour-coded badges on
every list; filterable in search; usable as map/marker styling.

### 5.2 Omnibox search
- Searches: summary text, decision, German original text, places, parcel
  numbers (Fl.Nr.), dates (DD.MM.YYYY), TOP numbers.
- Result list grouped by meeting, highlighted snippets, facets: topic, year,
  decision-kind, place.
- Keyboard: `/` focuses, arrow keys navigate, Enter opens.
- Prebuilt index (`search-index.js`); brute-force acceptable at current size.

### 5.3 Connectedness rules
- Same place (shared pin within ~250 m or identical name key).
- Same Flurstück / same plan name (regex over source text).
- Same meeting (chronological neighbours).
- Same topic + year ("related reading").
- Dossier membership (keyword-defined, curated per dossier).

### 5.4 Maps
Keep the built "one map, many windows" component: clustered decision map on
home, recyclable mini map per card, compact meeting map, map on place pages.
Tile fallback chain (basemap.de → OSM-DE → CARTO → OSM.org), vendored Leaflet.

### 5.5 Cited-passage highlighting in PDFs (pre-generated, Option A)

Built-in PDF viewers have no cross-browser highlight API (`#page=N` works
everywhere; text highlighting is Chrome-only and imprecise). Instead the build
generates highlighted PDF copies **at build time**:

- The extraction pipeline already stores per-item geometry (page + line boxes,
  column bounds). `extract_text.py` is extended to emit the full item bounding
  box per page (x0/y0/x1/y1 in PDF points).
- `tools/make_highlights.py` (PyMuPDF) draws a translucent yellow rectangle
  plus the TOP label over each item's passage and writes one highlighted copy
  per Klosterkurier issue to `sources/highlights/<issue>.pdf` (originals stay
  untouched).
- Item links point to the highlighted copy with the existing `#page=N`
  fragment; the untouched original remains linked in the provenance box.
- Optional variant (decide at implementation): additionally emit per-item
  **one-page excerpt PDFs** for a "cited passage" chip (instant open, small
  file).
- Works in every browser's native viewer, no JavaScript, no server,
  print-friendly. Dependency: `pip install pymupdf` (build-time only).
- Opened questions at implementation: highlight style (fill opacity, border,
  TOP label placement) and whether dossiers/documents also get highlight
  treatment (only Klosterkurier items have item-level geometry; documents keep
  plain `#page` links).

## 6. Design system

- Civic-clean: type-first hierarchy, one accent colour, generous whitespace.
- Dark mode via `prefers-color-scheme`.
- Print stylesheet: decision pages print as citation slips (summary + provenance).
- Accessibility: landmarks, skip link, focus styles, labelled collapsibles,
  contrast-checked badges.
- Microcopy: EN UI; German source terms preserved; "approximate" pins marked `*`.

## 7. Pipeline impact (all in `build_archive.py`)

- New derived field: `decision_kind` (from verified vote phrase; curated regex).
- New generated trees: `decisions/*.html`, `places/*.html`, `glossary.html`,
  `about.html`; `search-index.js`; relatedness index (JSON) for context sidebars.
- New build step: `tools/make_highlights.py` → `sources/highlights/<issue>.pdf`
  (needs `extract_text.py` to store full item bounding boxes; adds PyMuPDF as a
  build-time dependency).
- Homepage/home templates replaced per blueprints above.
- Data additions later: parsed member lists (people pages), RSS feed
  (`feed.xml`), DE/EN UI toggle.

## 8. Phases

**Phase 1 — core structure**
decision detail pages · global header/omnibox/breadcrumbs · decision-kind
badges + facet · redesigned home · upgraded search results · open-threads
board · **cited-passage highlighting (5.5)**: bbox extension, highlight
build step, link swap. *Acceptance: every item has a permalink; omnibox on
all pages; badges everywhere; every item links to a highlighted PDF copy that
opens at the right page with the passage marked; home matches blueprint.*

**Phase 2 — breadth**
place pages · documents library facets · glossary · print styles · dark mode.

**Phase 3 — depth**
person pages (from Mitglieder PDFs) · RSS feed · DE UI toggle · update workflow
for new issues (e.g. issue 4/2026 intake: collect → extract → verify → build,
one command).

## 9. Non-goals / guards

- No build tooling (webpack & Co.) — Python + plain files only.
- No tracking, no cookies, no external fonts.
- Tile providers remain fallback-chained; maps stay lazy-loaded.
- A dynamic pdf.js viewer with live highlight overlays is **deferred** to the
  hosted-website phase (it requires HTTP serving because browsers block XHR to
  local files); until then the pre-generated highlighted PDFs (5.5) are the
  mechanism.
- The official Ratsinformationssystem (Session.Net, decided 29.07.2026) is not
  yet online; the site is explicitly positioned as a citizen archive that can
  switch to official minutes later (documented in About).
