#!/usr/bin/env python3
"""Erzeugt supabase/04_seed_catalogs.sql aus den 4 Katalog-CSVs in data/.

Aufruf:  python3 tools/csv_to_seed.py
Danach:  Inhalt von supabase/04_seed_catalogs.sql im Supabase-SQL-Editor ausführen.
Das Skript ist idempotent: es leert die Katalog-Tabellen und füllt sie neu –
so bleibt die CSV die Quelle der Wahrheit und kann beliebig erweitert werden.
"""
import csv, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT  = ROOT / "supabase" / "04_seed_catalogs.sql"

def load(fn):
    with open(DATA / fn, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))

def q(v):                       # SQL-String-Literal
    return "'" + (v or "").replace("'", "''") + "'"

def b(v):                       # Ja/Nein -> boolean
    return "true" if (v or "").strip() == "Ja" else "false"

def n(v):                       # Zahl oder NULL
    v = (v or "").strip()
    return v if v.lstrip("-").isdigit() else "null"

def main():
    lines = ["-- GENERIERT von tools/csv_to_seed.py – nicht von Hand editieren.",
             "-- Quelle: data/*.csv. Reihenfolge: erst 03_catalogs.sql ausführen.",
             "begin;",
             "truncate kat_fragen, kat_raumtyp_zuordnung, kat_objekte, kat_kluster;"]

    for r in load("Klusterkatalog.csv"):
        if not (r.get("Kluster") or "").strip(): continue
        lines.append(f"insert into kat_kluster values ({q(r['Kluster'])},{b(r['im_Bericht'])},"
                     f"{q(r['Reihenfolge_Bericht'])},{q(r['Beschreibung'])});")

    for r in load("Objektkatalog_GESAMT.csv"):
        if not (r.get("Objekttyp") or "").strip(): continue
        lines.append(f"insert into kat_objekte values ({q(r['Objektklasse'])},{q(r['Objekttyp'])},"
                     f"{q(r['Objektart'])},{q(r['Gewerk'])},{q(r['Erlaubte_Elternklasse'])},"
                     f"{b(r.get('Aktiv','Ja'))},{q(r['Notiz'])}) on conflict do nothing;")

    cols = ("objektklasse,objekttyp,titel,frage,ebene,metabereichtyp,bereichtyp,raumtyp,antworttyp,"
            "antwortoptionen,standard_antwort,einheit,bedingung,pflicht,foto_pflicht,hilfetext,kluster,"
            "reihenfolge,activ,fragekatalog,autor,version,aenderungsdatum,min_lod,zielgruppe,fototyp,"
            "hilfemedien,objektart")
    for r in load("Fragekatalog_GESAMT.csv"):
        if not (r.get("Titel") or "").strip(): continue
        vals = ",".join([
            q(r["Objektklasse"]), q(r["Objekttyp"]), q(r["Titel"]), q(r["Frage"]),
            q(r["Ebene"]), q(r["Metabereichtyp"]), q(r["Bereichtyp"]), q(r["Raumtyp"]),
            q(r["Antworttyp"]), q(r["Antwortoptionen"]), q(r["Standard Antwort"]), q(r["Einheit"]),
            q(r["Bedingung"] or "immer"), b(r["Pflicht"]), b(r["Foto_Pflicht"]), q(r["HilfeText"]),
            q(r["Kluster"]), n(r["Reihenfolge"]), b(r.get("Activ","Ja")), q(r["Fragekatalog"]),
            q(r["Autor"]), q(r["Version"]), q(r["Änderungsdatum"]), n(r["Min_LOD"]),
            q(r["Zielgruppe"]), q(r["Fototyp"]), q(r["HilfeMedien"]), q(r["Objektart"]),
        ])
        lines.append(f"insert into kat_fragen ({cols}) values ({vals}) on conflict do nothing;")

    for r in load("Raumtyp_Objekt_Zuordnung.csv"):
        if not (r.get("Raumtyp") or "").strip(): continue
        lines.append(f"insert into kat_raumtyp_zuordnung values ({q(r['Raumtyp'])},{q(r['Bereichstyp'])},"
                     f"{q(r['Objektklasse'])},{q(r['Vorauswahl'])},{q(r['Anzahl_typisch'])},"
                     f"{b(r['Prompt_wenn_fehlt'])},{q(r['Notiz'])}) on conflict do nothing;")

    lines.append("commit;")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {OUT.name} geschrieben ({len(lines)-3} Statements, {round(OUT.stat().st_size/1024)} KB)")

if __name__ == "__main__":
    main()
