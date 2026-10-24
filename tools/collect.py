"""Collect all Klosterkurier issues (2025+2026) and council-relevant documents.

Live-first, Wayback-fallback. Every artifact lands in sources/ and the manifest.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import net  # noqa: E402
from net import fetch, save  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

WB = "http://web.archive.org/web/{ts}id_/{url}"


def fetch_pdf(original_url: str, ts: str | None, relpath: str, label: str) -> bool:
    """Try live URL, then Wayback (id_ raw). Saves with provenance metadata."""
    if net.already_saved(original_url):
        print("skip (already in manifest):", label)
        return True
    body, headers, via = None, None, None
    try:
        st, h, b = fetch(original_url, timeout=180)
        if st == 200 and b[:5] == b"%PDF-":
            body, headers, via = b, h, "live"
        else:
            print(f"  live {st} (len={len(b)}), falling back to Wayback")
    except Exception as e:
        print(f"  live failed: {type(e).__name__}; falling back to Wayback")
    if body is None and ts:
        wb_url = WB.format(ts=ts, url=original_url)
        for attempt in range(3):
            try:
                st, h, b = fetch(wb_url, timeout=600)
                if st == 200 and b[:5] == b"%PDF-":
                    body, headers = b, h
                    via = f"wayback:{ts}"
                    break
                print(f"  wayback {st} (len={len(b)}) attempt {attempt + 1}")
            except Exception as e:
                print(f"  wayback failed: {type(e).__name__} attempt {attempt + 1}")
            time.sleep(6)
    if body is None:
        print(f"FAILED: {label} <- {original_url}")
        return False
    extra = {
        "label": label,
        "retrieved_via": via,
    }
    save(original_url, relpath, body, headers or {}, extra)
    return True


# ---- Klosterkurier issues (2025 + 2026) -------------------------------------------
ISSUES = [
    ("klosterkurier-2025-01.pdf", "https://www.aldersbach.de/images/infoblatt/AKK_1-25_web.pdf", "20250313094641"),
    ("klosterkurier-2025-02.pdf", "https://www.aldersbach.de/images/infoblatt/AKK_2-25.pdf", "20250606094726"),
    ("klosterkurier-2025-03.pdf", "https://www.aldersbach.de/images/infoblatt/AKK_3-25_web.pdf", "20250926095943"),
    ("klosterkurier-2025-04.pdf", "https://www.aldersbach.de/images/infoblatt/AKK_4-25_web.pdf", "20251210075648"),
    ("klosterkurier-2026-01.pdf", "https://www.aldersbach.de/wp-content/uploads/2026/03/AKK1-26_web.pdf", "20260318102208"),
]
# already collected live from the blob in probe10: 2026-02, 2026-03

# ---- council-relevant documents, live on aldersbach.de (WP) ------------------------
WP = "https://www.aldersbach.de/wp-content/uploads"
DOCS_LIVE = [
    ("geschaeftsordnung-2026-2032.pdf", f"{WP}/2026/10/Geschaeftsordnung-Gemeinderat-Aldersbach-2026-2032.pdf"),
    ("gemeinderat-mitglieder-2026-04.pdf", f"{WP}/2026/04/Gemeinderat.pdf"),
    ("buergermeister-2026-04.pdf", f"{WP}/2026/04/Brgermeister.pdf"),
    ("ausschuesse-2026-32.pdf", f"{WP}/2026/10/Ausschuesse-2026-32.pdf"),
    ("gemeinderat-fraktionen-2026-32.pdf", f"{WP}/2026/09/Gemeindera_Fraktionen_2026-32.pdf"),
    ("mitglieder-bau-umweltausschuss.pdf", f"{WP}/2026/10/Mitglieder-Bau-und-Umweltausschuss.pdf"),
    ("mitglieder-haupt-finanzausschuss.pdf", f"{WP}/2026/10/Mitglieder-Haupt-und-Finanzausschuss.pdf"),
    ("mitglieder-kindergartenausschuss.pdf", f"{WP}/2026/10/Mitglieder-Kindergartenausschuss.pdf"),
    ("mitglieder-rechnungspruefungsausschuss.pdf", f"{WP}/2026/10/Mitglieder-Rechnungspruefungsausschuss.pdf"),
    ("mitglieder-schulverbandsversammlung-aldersbach.pdf", f"{WP}/2026/10/Mitglieder-Schulverbandsversammlung-Aldersbach.pdf"),
    ("mitglieder-sport-kulturausschuss.pdf", f"{WP}/2026/10/Mitglieder-Sport-und-Kulturausschuss.pdf"),
    ("jugendbeauftragte.pdf", f"{WP}/2026/10/Jugendbeauftragte.pdf"),
    ("schulverbandsversammlung-aidenbach.pdf", f"{WP}/2026/04/SchulverbandsversammlungAidenbach.pdf"),
    ("realsteuerhebesatzung.pdf", f"{WP}/2026/04/Realsteuerhebesatzung.pdf"),
    ("stellplatzsatzung.pdf", f"{WP}/2026/04/Stellplatzsatzung.pdf"),
    ("hundesteuersatzung.pdf", f"{WP}/2026/04/hundesteuersatzung-1.pdf"),
    ("wasserabgabesatzung.pdf", f"{WP}/2026/04/WAS_Wasserabgabesatzung-1.pdf"),
    ("entwaesserungssatzung.pdf", f"{WP}/2026/04/SatzungfrdieffentlicheEntwsserungseinrichtungderGemeindeAldersbachEntwsserungssatzungEWS.pdf"),
    ("beitrags-gebuehrensatzung.pdf", f"{WP}/2026/04/BeitragsundGebhrensatzung.pdf"),
    ("beitrags-gebuehrensatzung-entwaesserung-4.pdf", f"{WP}/2026/04/BeitragsundGebhrensatzungzurEntwsserungssatzung4.pdf"),
    ("reinigungs-sicherungsverordnung.pdf", f"{WP}/2026/04/VerordnungberdieReinhaltungundReinigungderffentlichenStraen.pdf"),
    ("aufhebung-verordnung-verbrennen-abfaelle.pdf", f"{WP}/2026/04/aufhebung_der_verordnung_ber_das_verbrennen_abfllen.pdf"),
    ("bekanntmachung-pv-freiflaechen.pdf", f"{WP}/2026/01/BekanntmachungBewerbungFreiflchenphotovoltaikanlagen.pdf"),
    ("gag-broschuere.pdf", f"{WP}/2026/01/Broschuere_2025_compressed.pdf"),
    ("vergabekriterien-2025-12-11.pdf", f"{WP}/2026/10/Vergabekriterien-Stand-11.12.2025.pdf"),
    # Bebauungsplan Schwaig X (2026 final package)
    ("bplan-schwaig-x-satzung.pdf", f"{WP}/2026/10/Bebauungsplan-Schwaig-X.pdf"),
    ("bplan-schwaig-x-begruendung.pdf", f"{WP}/2026/10/Bebauungsplan-Schwaig-X-Begruendung.pdf"),
    ("bplan-schwaig-x-umweltbericht.pdf", f"{WP}/2026/10/Umweltbericht-Bebauungsplan-Schwaig-X-mit-int.-GOP.pdf"),
    ("bplan-schwaig-x-beschluss-abwaegung.pdf", f"{WP}/2026/10/Beschluss-Abwaegung.pdf"),
    ("bplan-schwaig-x-beschluss-2-auslegung.pdf", f"{WP}/2026/10/Beschluss-2.-Auslegung.pdf"),
    ("bplan-schwaig-x-bekanntmachung-2-auslegung.pdf", f"{WP}/2026/10/Bekanntmachung-Schwaig-X-2.-Auslegung.pdf"),
    ("bplan-schwaig-x-lageplan.pdf", f"{WP}/2026/10/Lageplan-Schwaig-X.pdf"),
    ("bplan-schwaig-x-schallbericht.pdf", f"{WP}/2026/10/Schalltechnischer-Bericht-Schwaig-X.pdf"),
    ("bplan-schwaig-x-geotechnik-2026.pdf", f"{WP}/2026/10/Geotechnischer_Bericht_01.09.2026.pdf"),
    ("bplan-schwaig-x-geotechnik-2022.pdf", f"{WP}/2026/10/Geotechnischer_Bericht_24.11.2022.pdf"),
    ("bplan-schwaig-x-starkregenanalyse.pdf", f"{WP}/2026/10/Starkregenanalyse-Gesamt.pdf"),
    ("bplan-schwaig-x-verkehrsuntersuchung.pdf", f"{WP}/2026/10/Verkehrsuntersuchung.pdf"),
    ("bplan-schwaig-x-umweltinfos-aushang.pdf", f"{WP}/2026/10/Schwaig_X_Umweltbezogene_Informationen_Aushang-Kopie.pdf"),
]

# ---- council-relevant documents from the old site (Wayback) ------------------------
OLD = "https://www.aldersbach.de/images"
DOCS_WAYBACK = [
    ("niederschrift-auszug-1.pdf", f"{OLD}/AuszugausderNiederschrift.pdf", "20250401110016"),
    ("niederschrift-auszug-2.pdf", f"{OLD}/AuszugausderNiederschrift1.pdf", "20241126024757"),
    ("niederschrift-auszug-3.pdf", f"{OLD}/AuszugausderNiederschrift2-1.pdf", "20241204002258"),
    ("niederschrift-auszug-4.pdf", f"{OLD}/AuszugausderNiederschrift3.pdf", "20241126022225"),
    ("niederschrift-auszug-5.pdf", f"{OLD}/AuszugausderNiederschrift1-1.pdf", "20250901214433"),
    ("niederschrift-auszug-6.pdf", f"{OLD}/AuszugausderNiederschrift-1.pdf", "20250901221037"),
    ("beschlussauszug-2025.pdf", f"{OLD}/Beschlussauszug.pdf", "20250801101719"),
    ("bplan-schwaig-x-bekanntmachung-aufstellung-2024.pdf", f"{OLD}/BekanntmachungSchwaigX.pdf", "20241126034146"),
    ("bplan-schwaig-x-bekanntmachung-1-auslegung.pdf", f"{OLD}/BekanntmachungSchwaigX-1.pdf", "20250425115842"),
    ("bplan-schwaig-x-beschluss-1-auslegung-bplan.pdf", f"{OLD}/Beschluss1.AuslegungBPlan.pdf", "20250425115756"),
    ("bplan-schwaig-x-beschluss-1-auslegung-fplan.pdf", f"{OLD}/Beschluss1.AuslegungFPlan.pdf", "20250425115811"),
    ("bplan-schwaig-x-vorentwurf.pdf", f"{OLD}/VorentwurfBebauungsplanSchwaigX-1.pdf", "20260130101235"),
    ("bplan-schwaig-x-begruendung-2024.pdf", f"{OLD}/BegrndungzumBebauungsplanSchwaigX-1.pdf", "20241126020420"),
    ("bplan-schwaig-x-umweltbericht-2024.pdf", f"{OLD}/UmweltberichtzumBebauungsplanSchwaigX.pdf", "20260130115214"),
    ("bplan-schwaig-x-starkregen-ergebnis.pdf", f"{OLD}/ErgebnissederStarkregenanalysezumBebauungsplanSchwaigX-1.pdf", "20241206211030"),
    ("bplan-schwaig-x-schallbericht-2025.pdf", f"{OLD}/SchalltechnischerBerichtSchwaigX-1.PDF", "20260203110201"),
    ("so-energie-batteriespeicher-bekanntmachung.pdf", f"{OLD}/BekanntmachungSOEnergieBatteriespeicheranlage.pdf", "20251025080702"),
    ("so-energie-batteriespeicher-satzung.pdf", f"{OLD}/SOEnergieBatteriespeicheranlageamUmspannwerkOriginal.pdf", "20260130135638"),
    ("bbp-uttigkofen-eggerting-vorentwurf.pdf", f"{OLD}/20250129BBPGEUttigkofenEggertingVorentwurf.pdf", "20260203122429"),
    ("bbp-uttigkofen-eggerting-begruendung.pdf", f"{OLD}/20250129BBPGEUttigkofenEggertingVorentwurfBegrndungVORABZUG20250210.pdf", "20260130171122"),
    ("bek-aufstellungsbeschluss-2025.pdf", f"{OLD}/BekanntmachungAufstellungsbeschluss.pdf", "20250701130502"),
    ("zusammenfassende-erklaerung-bbp.pdf", f"{OLD}/ZusammenfassendeErklrungBBP.pdf", "20260130115942"),
    ("zusammenfassende-erklaerung-fnp.pdf", f"{OLD}/ZusammenfassendeErklrungFNP.pdf", "20260130112826"),
]


def main():
    ok = 0
    total = 0
    jobs = [("klosterkurier", f, u, t) for f, u, t in ISSUES]
    jobs += [("aldersbach-docs", f, u, None) for f, u in DOCS_LIVE]
    jobs += [("aldersbach-docs-wb", f, u, t) for f, u, t in DOCS_WAYBACK]
    for group, fname, url, ts in jobs:
        total += 1
        target = "klosterkurier/" + fname if group == "klosterkurier" else "aldersbach/" + fname
        if fetch_pdf(url, ts, target, fname):
            ok += 1
        time.sleep(0.5)
    print(f"\nDONE: {ok}/{total} artifacts collected")
    # report failures
    if ok < total:
        print("Some artifacts failed - see FAILED lines above.")


if __name__ == "__main__":
    main()
