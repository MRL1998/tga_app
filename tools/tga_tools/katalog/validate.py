"""Validierung vor dem Schreiben. 'fehler' bricht den Import ab (ohne --force),
'warnung' wird nur gemeldet – dieselben Regeln liefert nachher v_katalog_check in der DB."""
import re
from collections import Counter
from .reader import ANTWORTTYPEN

PSEUDO_KLASSEN = {"", "(Basis)"}
ELTERN_SONDER = {"Raum", "Gebäude", "Bereich", "alle Objekte"}


def _split(s):
    return [x.strip() for x in (s or "").split(";") if x.strip()]


def validate(k):
    probs = []                               # (schwere, tabelle, schluessel, problem)
    add = lambda s, t, key, msg: probs.append((s, t, key, msg))

    kluster = {r["kluster"] for r in k["kluster"]}
    klassen = {r["objektklasse"] for r in k["objekte"]}
    typen = {(r["objektklasse"], r["objekttyp"]) for r in k["objekte"]}
    typnamen = {r["objekttyp"] for r in k["objekte"]}
    raumtypen = {r["raumtyp"] for r in k["raumtypen"]}
    bereichstypen = {r["bereichstyp"] for r in k["bereichstypen"]}
    titel = {f["titel"] for f in k["fragen"]}

    # --- harte Fehler: würden den Insert sprengen ---------------------------------
    for tab, key in [("objekte", lambda r: (r["objektklasse"], r["objekttyp"])),
                     ("fragen", lambda r: r["frage_id"]),
                     ("raumtypen", lambda r: r["raumtyp"]),
                     ("bereichstypen", lambda r: r["bereichstyp"]),
                     ("zuordnung", lambda r: (r["raumtyp"], r["bereichstyp"], r["objektklasse"])),
                     ("nutzungsprofile", lambda r: r["nr"]),
                     ("hilfetext_override", lambda r: (r["frage"], r["kontext_objekttyp"]))]:
        for key_, n in Counter(key(r) for r in k[tab]).items():
            if n > 1:
                add("fehler", "kat_" + tab, str(key_), f"{n}× vorhanden (Duplikat)")

    for f in k["fragen"]:
        if f["kluster"] and f["kluster"] not in kluster and not f["kluster"].startswith("«"):
            add("fehler", "kat_fragen", f["frage_id"], f'{f["titel"]}: Kluster "{f["kluster"]}" unbekannt')
        if f["antworttyp"] not in ANTWORTTYPEN:
            add("fehler", "kat_fragen", f["frage_id"], f'{f["titel"]}: Antworttyp "{f["antworttyp"]}" unbekannt')
        if f["min_lod"] not in (200, 300, 350, 400):
            add("fehler", "kat_fragen", f["frage_id"], f'{f["titel"]}: Min_LOD {f["min_lod"]} ungültig')

    # --- Warnungen: fachliche Inkonsistenzen (siehe offene-fragen A2) --------------
    for f in k["fragen"]:
        key = f'{f["titel"]} [{f["quelle_datei"]}]'
        if f["objektklasse"] not in klassen and f["objektklasse"] not in PSEUDO_KLASSEN:
            add("warnung", "kat_fragen", key, f'Objektklasse "{f["objektklasse"]}" nicht im Objektkatalog')
        if f["objekttyp"] and (f["objektklasse"], f["objekttyp"]) not in typen:
            add("warnung", "kat_fragen", key, f'Objekttyp "{f["objekttyp"]}" nicht in Klasse "{f["objektklasse"]}"')
        if f["quelle"] == "raum" and f["raumtyp"] and f["raumtyp"] not in raumtypen:
            add("warnung", "kat_fragen", key, f'Raumtyp "{f["raumtyp"]}" nicht in Raumtypen.csv')
        if f["aenderungsdatum"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", f["aenderungsdatum"]):
            add("warnung", "kat_fragen", key, f'Änderungsdatum "{f["aenderungsdatum"]}" nicht ISO (JJJJ-MM-TT)')
        if f["kluster"] and f["kluster"].startswith("«"):
            add("hinweis", "kat_fragen", key, f'Kluster-Platzhalter {f["kluster"]} – zur Laufzeit vom Gewerk ableiten')
        import json
        spec = json.loads(f["bedingung_spec"])
        if spec["op"] == "unbekannt":
            add("warnung", "kat_fragen", key, f'Bedingung nicht parsebar: {spec["raw"]}')
        elif spec.get("titel") and spec["titel"] not in titel:
            add("warnung", "kat_fragen", key, f'Bedingung «{spec["titel"]}» hat keine Zielfrage')
        m = re.fullmatch(r"«([^»]+)»", f["standard_antwort"])
        if m and m.group(1) not in titel:
            add("warnung", "kat_fragen", key, f'Standard Antwort «{m.group(1)}» hat keine Zielfrage')

    for z in k["zuordnung"]:
        key = f'{z["raumtyp"]}|{z["bereichstyp"]}|{z["objektklasse"]}'
        if z["raumtyp"] not in raumtypen:
            add("warnung", "kat_raumtyp_zuordnung", key, f'Raumtyp "{z["raumtyp"]}" unbekannt')
        if z["bereichstyp"] != "alle" and z["bereichstyp"] not in bereichstypen:
            add("warnung", "kat_raumtyp_zuordnung", key, f'Bereichstyp "{z["bereichstyp"]}" unbekannt')
        if z["objektklasse"] not in klassen:
            add("warnung", "kat_raumtyp_zuordnung", key, f'Objektklasse "{z["objektklasse"]}" unbekannt')

    for r in k["raumtypen"]:
        for b in _split(r["verfuegbar_in_bereichstyp"]):
            if b not in bereichstypen:
                add("warnung", "kat_raumtypen", r["raumtyp"], f'Verfügbar_in_Bereichstyp "{b}" unbekannt')
    for b in k["bereichstypen"]:
        for rt in _split(b["raumtyp_vorfilter"]):
            if not rt.startswith("(") and rt not in raumtypen:
                add("warnung", "kat_bereichstypen", b["bereichstyp"], f'Raumtyp_Vorfilter "{rt}" unbekannt')

    for o in k["objekte"]:
        for e in _split(o["erlaubte_elternklasse"]):
            if e not in ELTERN_SONDER and e not in klassen and e not in typnamen and e not in bereichstypen:
                add("warnung", "kat_objekte", f'{o["objektklasse"]}|{o["objekttyp"]}', f'Erlaubte_Elternklasse "{e}" unbekannt')

    for h in k["hilfetext_override"]:
        key = f'{h["frage"]}|{h["kontext_objekttyp"]}'
        if h["frage"] not in titel:
            add("warnung", "kat_hilfetext_override", key, f'Frage "{h["frage"]}" existiert nicht')
        if h["kontext_objekttyp"] not in typnamen:
            add("warnung", "kat_hilfetext_override", key, f'Objekttyp "{h["kontext_objekttyp"]}" existiert nicht')

    order = {"fehler": 0, "warnung": 1, "hinweis": 2}
    probs.sort(key=lambda p: (order[p[0]], p[1], p[2]))
    return probs
