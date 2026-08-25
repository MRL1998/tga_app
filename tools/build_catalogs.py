#!/usr/bin/env python3
"""Baut data/catalogs.json aus den 4 Katalog-CSVs und injiziert sie in index.html.

Aufruf:  python3 tools/build_catalogs.py
Quelle der Wahrheit sind die CSVs in data/ (Semikolon-getrennt, UTF-8).
Nach Katalog-Änderungen: Skript laufen lassen, index.html committen.
"""
import csv, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

def load(fn):
    with open(DATA / fn, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))

def main():
    obj = load("Objektkatalog_GESAMT.csv")
    fra = load("Fragekatalog_GESAMT.csv")
    klu = load("Klusterkatalog.csv")

    # --- Objektkatalog: [klasse, typ, art(O/S), gewerk, parents[]] ---
    O = []
    for r in obj:
        if r.get("Aktiv", "Ja") != "Ja" or not r["Objekttyp"]:
            continue
        parents = [p.strip() for p in r["Erlaubte_Elternklasse"].split(";") if p.strip()]
        O.append([r["Objektklasse"], r["Objekttyp"],
                  "S" if r["Objektart"] == "Sub-Objekt" else "O", r["Gewerk"], parents])
    # Nachträge (im Fragekatalog referenziert, im Objektkatalog offen)
    O.append(["Heizungsregelung", "Kesselsteuerung (integriert)", "S", "Heizung", ["Wärmeerzeuger", "Regelung"]])
    O.append(["Wärmespeicher", "Elektro-Heizstab", "S", "Heizung", ["Wärmespeicher", "Trinkwarmwasserspeicher"]])

    K = {r["Kluster"]: (int(r["Reihenfolge_Bericht"]) if r["Reihenfolge_Bericht"].strip().isdigit() else 999)
         for r in klu}

    F = []
    for r in fra:
        if r.get("Activ", "Ja") != "Ja":
            continue
        ao = [o.strip() for o in (r["Antwortoptionen"] or "").split(";") if o.strip()]
        q = {"t": r["Titel"], "q": r["Frage"], "k": r["Objektklasse"], "y": r["Objekttyp"],
             "at": r["Antworttyp"], "ao": ao, "u": (r["Einheit"] or "").strip(),
             "b": (r["Bedingung"] or "immer").strip(),
             "p": r["Pflicht"] == "Ja", "fp": r["Foto_Pflicht"] == "Ja",
             "h": (r["HilfeText"] or "").strip(), "kl": r["Kluster"],
             "r": int(r["Reihenfolge"]) if (r["Reihenfolge"] or "").strip().isdigit() else 999,
             "lod": int(r["Min_LOD"]) if (r["Min_LOD"] or "").strip().isdigit() else 200,
             "z": r["Zielgruppe"], "e": r["Ebene"], "ft": (r["Fototyp"] or "").strip().strip("-")}
        if not q["u"] or q["u"] == "-": q.pop("u")
        if not q["h"]: q.pop("h")
        if not q["ft"]: q.pop("ft")
        F.append(q)

    # Default-Objektklassen je App-Raumtyp (S=Standard, O=Optional)
    D = {
        "Bad": {"S": ["Sanitärobjekte", "Heizflächen – statisch", "Bauphysik – Türen"],
                "O": ["Bauphysik – Fenster", "Heizflächen – Flächenheizung", "Abwasser-Sonderbauteile",
                      "TWW-Erzeugung", "Elektro-Endstellen", "Abwasserinstallation"]},
        "Küche": {"S": ["Sanitärobjekte", "Elektro-Endstellen", "Bauphysik – Türen"],
                  "O": ["Bauphysik – Fenster", "Heizflächen – statisch", "Wärmeerzeuger",
                        "TWW-Erzeugung", "Abwasser-Sonderbauteile", "Gaszähler"]},
        "Zimmer": {"S": ["Heizflächen – statisch", "Bauphysik – Fenster", "Bauphysik – Türen", "Elektro-Endstellen"],
                   "O": ["Heizflächen – Flächenheizung", "Kälteübergabe", "Heizungsregelung"]},
        "Flur/Eingang": {"S": ["Bauphysik – Türen", "Elektro-Endstellen"],
                         "O": ["Heizflächen – statisch", "Elektroverteilung", "Elektroinstallation",
                               "Bauphysik – Fenster", "Wohnungsstation"]},
    }

    geb = set()
    for k, t, a, g, ps in O:
        if a == "O" and any(p in ("Gebäude", "Bereich", "Außenanlage") or p.startswith("Bereich") for p in ps):
            geb.add(k)
    GEB = {"S": ["Bauphysik – Hülle (opak)"], "O": sorted(geb - {"Bauphysik – Hülle (opak)"})}

    out = {"O": O, "F": F, "K": K, "D": D, "GEB": GEB,
           "ALIAS": {"Sanitärobjekt": "Sanitärobjekte", "Regelung": "Heizungsregelung",
                     "Heizungsinstallation": "Heizungsinstallation"}}
    js = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    (DATA / "catalogs.json").write_text(js, encoding="utf-8")

    tpl = (ROOT / "app_template.html").read_text(encoding="utf-8")
    if "/*__KATALOGE__*/" not in tpl:
        sys.exit("Platzhalter /*__KATALOGE__*/ fehlt in app_template.html")
    out = tpl.replace("/*__KATALOGE__*/", js, 1)
    cfg = ROOT / "supabase" / "config.json"
    if cfg.exists():
        out = out.replace("/*__SB__*/null", "/*__SB__*/" + cfg.read_text(encoding="utf-8").strip(), 1)
    (ROOT / "index.html").write_text(out, encoding="utf-8")
    print(f"OK: {len(O)} Objekte, {len(F)} Fragen, {len(K)} Kluster -> index.html ({round(len(js)/1024)} KB Kataloge)")

if __name__ == "__main__":
    main()
