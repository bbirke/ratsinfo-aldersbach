# Ratsinfo-Archiv Aldersbach

An independent citizen archive of the decisions of the Gemeinderat Aldersbach
(Landkreis Passau), reconstructed from the municipal newsletter "Aldersbacher
Klosterkurier" and documents from aldersbach.de. English summaries, German
source text verbatim, every item linked to the printed PDF page.

The published site is the static folder [`archive/`](archive/). It has no
server-side parts and also works when opened from disk (`archive/index.html`).

## Layout

| Path | What |
|---|---|
| `archive/` | Generated static site (published to GitHub Pages). Do not hand-edit, except `archive/vendor/` |
| `tools/build_archive.py` | Builds `archive/` from `data/` |
| `tools/site/` | Hand-edited stylesheet, scripts and coat of arms, copied to `archive/assets/` |
| `tools/*.py` | Collection, extraction, verification and geocoding pipeline |
| `data/` | Extracted items (`items.jsonl`), document list, geocoding cache |
| `CONCEPT.md` | Information architecture and design concept |

`sources/` (raw PDFs and pages, about 380 MB) is not in the repository. The
build copies every PDF the site links to into `archive/files/`.

## Rebuild and publish

```bash
python tools/build_archive.py
```

Use `--no-pdfs` to regenerate the pages without re-copying PDFs. Commit the
changed `archive/` and push to `main`; the workflow in
`.github/workflows/pages.yml` deploys it to GitHub Pages.

Preview locally:

```bash
python -m http.server 8777 --directory archive
```

## Credits

Coat of arms: Wikimedia Commons, "DEU Aldersbach COA.svg" (public domain).
Maps: Leaflet, basemap.de / OpenStreetMap contributors, BayernAtlas (ALKIS).
