# Änderungen 2026-09-04

## supabase/05_catalogs_v2.sql (neu, idempotent)
- kat_kluster + gewerke; kat_objekte + basis_ausschluss, eltern_alle
- kat_fragen: + frage_id (neuer PK), quelle, fragen_klasse, referenz_spec jsonb, bedingung_spec jsonb; alter PK (objektklasse, objekttyp, titel) → Unique-Index über (quelle, objektklasse, objekttyp, raumtyp, fragen_klasse, titel); Kluster-FK entfernt («Gewerk»-Platzhalter)
- neu: kat_raumtypen, kat_bereichstypen, kat_nutzungsprofile_18599, kat_hilfetext_override, kat_meta
- Views: v_katalog_check (Referenzfehler), v_katalog_fragen_aktiv (App-Fassade)
- Bestandsdaten aus 04_seed werden beim Upgrade behalten (frage_id wird berechnet) – geprüft gegen 03 + 04 lokal

## supabase/05_seed_catalogs_v2.sql (generiert)
- aus tools/tga_tools, Stand data/ 03.09.2026 16:21; ersetzt 04_seed_catalogs.sql

## tools/tga_tools (neu)
- `katalog check` / `katalog import [--sql | --dsn] [--dry-run] [--force] [--version]`
- Validierung: Duplikate, Kluster, Antworttyp, Min_LOD = Fehler; Referenzen/Datumsformat = Warnung
- Ergebnis auf aktuellem Stand: 0 Fehler, 85 Warnungen (= offene CSV-Korrekturen), 12 Hinweise

## app_template.html / index.html
- Design-Tokens auf Modernist (Design-Datei „Gebäudeaufnahme – Verwaltungs-App“), Archivo via Google Fonts, Override-Layer am Ende des <style>-Blocks; keine JS-/Strukturänderung
- Dark-Mode-Tokens auf Tinte/Papier invertiert, Akzent bleibt

## Nicht geändert
- data/*.csv (Korrekturen aus Plan §3 stehen aus), schema.sql, 02, 03, 04
