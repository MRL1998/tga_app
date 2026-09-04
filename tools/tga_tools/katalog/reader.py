"""Liest die 11 Katalog-CSVs (Semikolon, UTF-8 mit BOM) und normalisiert sie
auf die Spalten der kat_*-Tabellen. Keine DB-Abhängigkeit."""
import csv, hashlib, json, pathlib, re

FRAGEN_KLASSEN = {"Aufenthalt", "Nassraum", "Erschließung", "Lager", "Technik", "Außen"}

FRAGE_DATEIEN = [                       # (Datei, quelle)
    ("Fragekatalog_GESAMT.csv", "objekt"),
    ("Fragekatalog_Raeume_GESAMT.csv", "raum"),
    ("Fragekatalog_Bereich_Zone18599.csv", "bereich_zone18599"),
    ("Fragekatalog_Bereich_Lueftungsbereich.csv", "bereich_lueftung"),
]

ANTWORTTYPEN = {"Einzelauswahl", "Mehrfachauswahl", "Zahl", "Ganzzahl", "Jahr", "Text",
                "Ja/Nein", "Foto-Upload", "Objektreferenz_TGA", "Referenz"}


def _rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            yield {k.strip(): (v or "").strip() for k, v in r.items() if k is not None}


def ja(v):
    return (v or "").strip().lower() in ("ja", "true", "1", "x")


def num(v):
    v = (v or "").strip()
    return int(v) if re.fullmatch(r"-?\d+", v) else None


def frage_id(quelle, objektklasse, objekttyp, raumtyp, fragen_klasse, titel):
    """Deterministischer Schlüssel – identisch zur Formel in 05_catalogs_v2.sql."""
    key = "|".join([quelle, objektklasse, objekttyp, raumtyp, fragen_klasse, titel])
    return "F-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]


def parse_bedingung(s):
    """'immer' | «Titel» = Wert | «Titel» ungleich Wert | Elternklasse ∈ {A; B}  -> jsonb-Spec."""
    s = (s or "").strip()
    if not s or s.lower() == "immer":
        return {"op": "immer"}
    m = re.fullmatch(r"«([^»]+)»\s*(=|ungleich)\s*(.+)", s)
    if m:
        return {"op": "eq" if m.group(2) == "=" else "ne", "titel": m.group(1).strip(), "wert": m.group(3).strip()}
    m = re.fullmatch(r"Elternklasse\s*∈\s*\{(.+)\}", s)
    if m:
        return {"op": "eltern_in", "klassen": [x.strip() for x in m.group(1).split(";") if x.strip()]}
    return {"op": "unbekannt", "raw": s}


def parse_referenz(antworttyp, optionen):
    """'(Objektreferenz_TGA | Ziel=Rohr | Klasse=gleich | Filter=Funktion,Gewerk,Raum | Raum=DD | +neu)'"""
    if antworttyp not in ("Objektreferenz_TGA", "Referenz"):
        return None
    s = (optionen or "").strip().strip("()")
    spec = {"typ": antworttyp, "neu_erlaubt": False}
    for part in [p.strip() for p in s.split("|")]:
        if part == "+neu":
            spec["neu_erlaubt"] = True
        elif "=" in part:
            k, v = part.split("=", 1)
            k = k.strip().lower()
            spec[k] = [x.strip() for x in v.split(",")] if k == "filter" else v.strip()
    return spec


def read_all(data_dir):
    d = pathlib.Path(data_dir)
    out = {}

    out["kluster"] = [{
        "kluster": r["Kluster"], "im_bericht": ja(r.get("im_Bericht")),
        "reihenfolge_bericht": r.get("Reihenfolge_Bericht", ""), "beschreibung": r.get("Beschreibung", ""),
        "gewerke": r.get("Gewerke", ""),
    } for r in _rows(d / "Klusterkatalog.csv") if r.get("Kluster")]

    out["objekte"] = [{
        "objektklasse": r["Objektklasse"], "objekttyp": r["Objekttyp"],
        "objektart": r.get("Objektart") or "Objekt", "gewerk": r.get("Gewerk", ""),
        "erlaubte_elternklasse": r.get("Erlaubte_Elternklasse", ""),
        "basis_ausschluss": r.get("Basis_Ausschluss", ""),
        "eltern_alle": r.get("Erlaubte_Elternklasse", "").strip() == "alle Objekte",
        "aktiv": ja(r.get("Aktiv", "Ja")), "notiz": r.get("Notiz", ""),
    } for r in _rows(d / "Objektkatalog_GESAMT.csv") if r.get("Objekttyp")]

    fragen = []
    for fn, quelle in FRAGE_DATEIEN:
        p = d / fn
        if not p.exists():
            continue
        for r in _rows(p):
            if not r.get("Titel"):
                continue
            raumtyp = r.get("Raumtyp", "")
            fk = r.get("Fragen_Klasse", "")
            if not fk and raumtyp in FRAGEN_KLASSEN:      # Übergang: Klasse steht noch in Spalte Raumtyp
                fk, raumtyp = raumtyp, ""
            objektklasse, objekttyp, titel = r.get("Objektklasse", ""), r.get("Objekttyp", ""), r["Titel"]
            fid = r.get("Frage_ID") or frage_id(quelle, objektklasse, objekttyp, raumtyp, fk, titel)
            fragen.append({
                "frage_id": fid, "quelle": quelle, "quelle_datei": fn,
                "objektklasse": objektklasse, "objekttyp": objekttyp, "titel": titel, "frage": r.get("Frage", ""),
                "ebene": r.get("Ebene") or "Objekt", "metabereichtyp": r.get("Metabereichtyp", ""),
                "bereichtyp": r.get("Bereichtyp", ""), "raumtyp": raumtyp, "fragen_klasse": fk,
                "antworttyp": r.get("Antworttyp", ""), "antwortoptionen": r.get("Antwortoptionen", ""),
                "standard_antwort": r.get("Standard Antwort", ""), "einheit": r.get("Einheit", ""),
                "bedingung": r.get("Bedingung") or "immer",
                "bedingung_spec": json.dumps(parse_bedingung(r.get("Bedingung")), ensure_ascii=False),
                "referenz_spec": (lambda s: json.dumps(s, ensure_ascii=False) if s else None)(
                    parse_referenz(r.get("Antworttyp", ""), r.get("Antwortoptionen", ""))),
                "pflicht": ja(r.get("Pflicht")), "foto_pflicht": ja(r.get("Foto_Pflicht")),
                "hilfetext": r.get("HilfeText", ""), "kluster": r.get("Kluster") or None,
                "reihenfolge": num(r.get("Reihenfolge")), "activ": ja(r.get("Activ", "Ja")),
                "fragekatalog": r.get("Fragekatalog", ""), "autor": r.get("Autor", ""),
                "version": r.get("Version", ""), "aenderungsdatum": r.get("Änderungsdatum", ""),
                "min_lod": num(r.get("Min_LOD")) or 200, "zielgruppe": r.get("Zielgruppe", ""),
                "fototyp": r.get("Fototyp", ""), "hilfemedien": r.get("HilfeMedien", ""),
                "objektart": r.get("Objektart", ""),
            })
    out["fragen"] = fragen

    out["raumtypen"] = [{
        "raumtyp": r["Raumtyp"], "raumklasse": r.get("Raumklasse", ""), "fragen_klasse": r.get("Fragen_Klasse", ""),
        "nutzung": r.get("Nutzung", ""), "lueftungszone": r.get("Lüftungszone", ""),
        "verfuegbar_in_bereichstyp": r.get("Verfügbar_in_Bereichstyp", ""), "beheizung": r.get("Beheizung", ""),
        "objektklassen_vorfilter": r.get("Objektklassen_Vorfilter (vorläufig)", ""), "notiz": r.get("Notiz", ""),
        "aktiv": ja(r.get("Aktiv", "Ja")),
    } for r in _rows(d / "Raumtypen.csv") if r.get("Raumtyp")]

    out["bereichstypen"] = [{
        "bereichstyp": r["Bereichstyp"], "metabereich_vorbelegung": r.get("Metabereich_Vorbelegung", ""),
        "beheizung": r.get("Beheizung", ""), "raumtyp_vorfilter": r.get("Raumtyp_Vorfilter (vorläufig)", ""),
        "beschreibung": r.get("Beschreibung", ""), "aktiv": ja(r.get("Aktiv", "Ja")), "notiz": r.get("Notiz", ""),
    } for r in _rows(d / "Bereichstypen.csv") if r.get("Bereichstyp")]

    out["zuordnung"] = [{
        "raumtyp": r["Raumtyp"], "bereichstyp": r.get("Bereichstyp") or "alle", "objektklasse": r["Objektklasse"],
        "vorauswahl": r.get("Vorauswahl") or "Standard", "anzahl_typisch": r.get("Anzahl_typisch", ""),
        "prompt_wenn_fehlt": ja(r.get("Prompt_wenn_fehlt")), "notiz": r.get("Notiz", ""),
    } for r in _rows(d / "Raumtyp_Objekt_Zuordnung.csv") if r.get("Raumtyp")]

    out["nutzungsprofile"] = [{
        "nr": num(r["Nr"]), "nutzungsprofil": r["Nutzungsprofil"], "aktiv": ja(r.get("Aktiv", "Ja")), "notiz": r.get("Notiz", ""),
    } for r in _rows(d / "DIN1859910_Nutzungsprofile.csv") if num(r.get("Nr"))]

    out["hilfetext_override"] = [{
        "frage": r["Frage"], "kontext_objekttyp": r["Kontext_Objekttyp"],
        "hilfetext_override": r.get("HilfeText_Override", ""), "hilfemedien_override": r.get("HilfeMedien_Override", ""),
        "aktiv": ja(r.get("Aktiv", "Ja")),
    } for r in _rows(d / "Override_HilfeText.csv") if r.get("Frage")]

    return out
