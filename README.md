# TGA-Aufnahme (tga_app)

Selbst-Erfassungs-App für Gebäudeaufnahmen (TGA / Energieberatung / BIM-Vorbereitung).
Facility Manager, Verwalter oder Mieter nehmen ein Gebäude selbst auf – Raum für Raum,
Objekt für Objekt, mit Fotos und Sprachmemos – sodass eine Vor-Ort-Begehung durch den
Planer entfallen kann.

**Ablauf in der App:** Anmelden → Projektübersicht → Projekt anlegen (Gebäude + Adresse,
oder nur Bereich) → Gebäude-Fragen (Hülle) → Plan hochladen → Raum-Punkte setzen →
je Raum: Raumtyp → Objekt-Checkliste → Fragen mit Folgelogik. Oberfläche komplett DE/EN.

## Struktur

| Pfad | Inhalt |
|---|---|
| `index.html` | Die komplette App, statisch, ohne Build – **generiert**, nicht direkt editieren |
| `app_template.html` | Quelltext der App mit Platzhalter `/*__KATALOGE__*/` |
| `data/*.csv` | Die 4 Fachkataloge (Quelle der Wahrheit, gepflegt von Tobias): Objektkatalog, Fragekatalog, Klusterkatalog, Raumtyp-Zuordnung |
| `data/catalogs.json` | Kompilierte Kataloge (generiert) |
| `tools/build_catalogs.py` | CSVs → `catalogs.json` → `index.html` |
| `supabase/schema.sql` | Normalisiertes Zielschema (projects, rooms, objects, answers, media) |
| `supabase/02_cloud.sql` | Cloud-Backup (project_blobs) + Storage-Policies – MVP-Sync |
| `supabase/03_catalogs.sql` | Katalog-Tabellen (1:1 zu den CSVs, laufend erweiterbar) |
| `supabase/04_seed_catalogs.sql` | Generierter CSV-Import (via `tools/csv_to_seed.py`) |

## Entwickeln

```bash
# Kataloge geändert? Neu bauen:
python3 tools/build_catalogs.py

# Lokal testen: index.html im Browser öffnen (kein Server nötig)
```

App-Code wird in `app_template.html` geändert, danach Build-Skript laufen lassen.

## Datenmodell (Kurzform)

```
Projekt (Adresse, Typ Gebäude/Bereich)
└─ Gebäude-Objekte (Hülle: Wandtypen, Dach, …)
└─ Raum (Pin auf dem Plan, Raumtyp)
   └─ Objekt-Instanz (Objektklasse + Objekttyp aus dem Katalog, mehrfach möglich)
      └─ Sub-Objekte (Baugruppen-Baum über Erlaubte_Elternklasse)
      └─ Antworten (Schlüssel = Fragen-Titel; Folgefragen über «Titel»-Bedingungen)
      └─ Medien (Fotos, Sprachmemos)
```

Fragen vererben sich über 3 Ebenen: `(Basis)` → Objektklasse → Objekttyp.
Aufnahmetiefe über `Min_LOD` (Schnell 200 / Standard 300 / Detail 400).

## Stand & Roadmap (MVP mit Supabase)

- [x] App offline-fähig (localStorage-Struktur + IndexedDB-Medien), Export/Import als JSON
- [x] Login (lokal) + Projektübersicht, Mehrprojekt-Verwaltung
- [x] Supabase-Projekt angelegt; SQL-Reihenfolge: `schema.sql` → `02_cloud.sql` → `03_catalogs.sql` → `04_seed_catalogs.sql`; Bucket `media` (privat)
- [x] Katalogschema v2 (`05_catalogs_v2.sql`): alle 11 CSVs, stabile `frage_id`, `kat_raumtypen`/`kat_bereichstypen`/`kat_nutzungsprofile_18599`/`kat_hilfetext_override`/`kat_meta`, Prüf-View `v_katalog_check`
- [x] Katalog-Import als Python-CLI (`tools/tga_tools`) statt `csv_to_seed.py` – siehe „Kataloge nach Supabase“
- [x] Oberfläche auf das Modernist-Design (Archivo, 2px-Raster, gelber Akzent) umgestellt – Tokens + Override-Layer oben in `app_template.html`
- [x] Login auf Supabase Auth (E-Mail/Passwort) + Cloud-Backup je Projekt
- [ ] Sync-Schicht: lokale Warteschlange → Postgres/Storage (offline-first bleibt)
- [ ] Deployment als statische Site (Cloudflare Pages / Netlify) + eigene Domain, PWA
- [ ] Katalog-Pflege: CSV-Upload oder Admin-Maske, Kataloge aus `catalogs`-Tabelle laden

## Kataloge nach Supabase (v2)

```bash
# einmalig in Supabase → SQL-Editor: supabase/05_catalogs_v2.sql ausführen (idempotent)
pip install "psycopg[binary]"
cd tools
python -m tga_tools katalog check                       # nur validieren (Fehler/Warnungen/Hinweise)
python -m tga_tools katalog import --sql ../supabase/05_seed_catalogs_v2.sql   # Seed-Datei für den SQL-Editor
python -m tga_tools katalog import --dsn "$DATABASE_URL"                        # oder direkt schreiben
```
`DATABASE_URL` = Supabase → Project Settings → Database → Connection string (URI, Session-Pooler). Kann auch in `.env` im Repo-Root stehen.
„Fehler“ (Duplikate, unbekannter Kluster/Antworttyp) brechen ab; „Warnungen“ sind die offenen CSV-Korrekturen aus `offene-fragen` A2 und landen in `v_katalog_check`. `frage_id` = `F-` + sha256(quelle|Objektklasse|Objekttyp|Raumtyp|Fragen_Klasse|Titel)[:10]; eine Spalte `Frage_ID` in der CSV hat Vorrang.

## Deployment (statisch)

Das Repo ist direkt deploybar: jede statische Hosting-Plattform, Root-Verzeichnis,
`index.html` als Einstieg. Kein Build-Schritt auf der Plattform nötig.
