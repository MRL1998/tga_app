"""Befehle: katalog check | katalog import [--dsn | --sql DATEI]"""
import datetime, pathlib, subprocess, sys
from collections import Counter
from .reader import read_all
from .validate import validate

# Tabellen in Insert-Reihenfolge (FK kat_fragen.kluster -> kat_kluster)
TABELLEN = [
    ("kat_kluster", "kluster", ["kluster", "im_bericht", "reihenfolge_bericht", "beschreibung", "gewerke"]),
    ("kat_objekte", "objekte", ["objektklasse", "objekttyp", "objektart", "gewerk", "erlaubte_elternklasse",
                                "basis_ausschluss", "eltern_alle", "aktiv", "notiz"]),
    ("kat_fragen", "fragen", ["frage_id", "quelle", "objektklasse", "objekttyp", "titel", "frage", "ebene",
                              "metabereichtyp", "bereichtyp", "raumtyp", "fragen_klasse", "antworttyp",
                              "antwortoptionen", "standard_antwort", "einheit", "bedingung", "bedingung_spec",
                              "referenz_spec", "pflicht", "foto_pflicht", "hilfetext", "kluster", "reihenfolge",
                              "activ", "fragekatalog", "autor", "version", "aenderungsdatum", "min_lod",
                              "zielgruppe", "fototyp", "hilfemedien", "objektart"]),
    ("kat_raumtypen", "raumtypen", ["raumtyp", "raumklasse", "fragen_klasse", "nutzung", "lueftungszone",
                                    "verfuegbar_in_bereichstyp", "beheizung", "objektklassen_vorfilter", "notiz", "aktiv"]),
    ("kat_bereichstypen", "bereichstypen", ["bereichstyp", "metabereich_vorbelegung", "beheizung", "raumtyp_vorfilter",
                                            "beschreibung", "aktiv", "notiz"]),
    ("kat_raumtyp_zuordnung", "zuordnung", ["raumtyp", "bereichstyp", "objektklasse", "vorauswahl", "anzahl_typisch",
                                            "prompt_wenn_fehlt", "notiz"]),
    ("kat_nutzungsprofile_18599", "nutzungsprofile", ["nr", "nutzungsprofil", "aktiv", "notiz"]),
    ("kat_hilfetext_override", "hilfetext_override", ["frage", "kontext_objekttyp", "hilfetext_override",
                                                      "hilfemedien_override", "aktiv"]),
]
JSON_SPALTEN = {"bedingung_spec", "referenz_spec"}


def _git_commit(root):
    try:
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def _report(probs):
    c = Counter(p[0] for p in probs)
    for s, t, key, msg in probs:
        print(f"  [{s:7}] {t:24} {key}: {msg}")
    print(f"\n{c.get('fehler', 0)} Fehler · {c.get('warnung', 0)} Warnungen · {c.get('hinweis', 0)} Hinweise")
    return c.get("fehler", 0)


def _meta(a, data_dir):
    root = pathlib.Path(data_dir).parent
    return [
        ("katalog_version", a.version or datetime.date.today().isoformat()),
        ("importiert_am", datetime.datetime.now().isoformat(timespec="seconds")),
        ("quelle", str(data_dir)),
        ("quelle_commit", _git_commit(root)),
        ("importer", "tga_tools katalog import"),
    ]


def _sql_literal(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def write_sql(k, meta, path):
    lines = ["-- GENERIERT von tools/tga_tools (katalog import --sql). Nicht von Hand editieren.",
             "-- Voraussetzung: 05_catalogs_v2.sql wurde ausgeführt.", "begin;",
             "truncate " + ", ".join(t for t, _, _ in TABELLEN) + ", kat_meta;"]
    for tab, key, cols in TABELLEN:
        for r in k[key]:
            vals = ",".join(_sql_literal(r[c]) + ("::jsonb" if c in JSON_SPALTEN and r[c] is not None else "") for c in cols)
            lines.append(f"insert into {tab} ({','.join(cols)}) values ({vals});")
    for kk, v in meta:
        lines.append(f"insert into kat_meta (key, value) values ({_sql_literal(kk)}, {_sql_literal(v)});")
    lines.append("commit;")
    pathlib.Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"SQL geschrieben: {path} ({len(lines)-4} Inserts, {round(pathlib.Path(path).stat().st_size/1024)} KB)")


def write_db(k, meta, dsn):
    import psycopg
    from psycopg.types.json import Jsonb
    import json
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("truncate " + ", ".join(t for t, _, _ in TABELLEN) + ", kat_meta")
            for tab, key, cols in TABELLEN:
                sql = f"insert into {tab} ({','.join(cols)}) values ({','.join(['%s'] * len(cols))})"
                rows = [tuple(Jsonb(json.loads(r[c])) if c in JSON_SPALTEN and r[c] is not None else r[c] for c in cols)
                        for r in k[key]]
                cur.executemany(sql, rows)
                print(f"  {tab:28} {len(rows):5} Zeilen")
            cur.executemany("insert into kat_meta (key, value) values (%s, %s)", meta)
            cur.execute("select schwere, count(*) from v_katalog_check group by 1")
            check = dict(cur.fetchall())
        conn.commit()
    print(f"\nImport abgeschlossen. v_katalog_check: {check or 'leer'}")


def run(a):
    k = read_all(a.data)
    print("Gelesen aus", a.data)
    for tab, key, _ in TABELLEN:
        print(f"  {tab:28} {len(k[key]):5}")
    print()
    fehler = _report(validate(k))

    if a.kcmd == "check":
        return 1 if fehler else 0

    if fehler and not a.force:
        print("\nAbbruch: Fehler vorhanden (mit --force trotzdem schreiben).")
        return 1
    if a.dry_run:
        print("\n--dry-run: nichts geschrieben.")
        return 0

    meta = _meta(a, a.data)
    if a.sql:
        write_sql(k, meta, a.sql)
        return 0
    if not a.dsn:
        print("\nKeine Verbindung: --dsn angeben, DATABASE_URL in .env setzen oder --sql DATEI verwenden.", file=sys.stderr)
        return 2
    write_db(k, meta, a.dsn)
    return 0
