-- ============================================================================
-- 05_catalogs_v2.sql · Katalogschema v2 (Stand 2026-09-04)
-- Nimmt ALLE 11 CSVs aus data/ auf. Idempotent: kann beliebig oft ausgeführt
-- werden (create if not exists / add column if not exists / create or replace).
-- Reihenfolge: nach schema.sql, 02_cloud.sql, 03_catalogs.sql.
-- Befüllen: python -m tga_tools katalog import  (tools/tga_tools) – NICHT mehr
-- 04_seed_catalogs.sql.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Bestehende Tabellen erweitern
-- ---------------------------------------------------------------------------
alter table kat_kluster add column if not exists gewerke text default '';   -- ';'-getrennt

alter table kat_objekte add column if not exists basis_ausschluss text default '';  -- '' | Identifikation | Typenschild
alter table kat_objekte add column if not exists eltern_alle boolean not null default false; -- Erlaubte_Elternklasse = 'alle Objekte'

-- kat_fragen: neuer stabiler Schlüssel frage_id + Herkunft + Fragen_Klasse + geparste Specs
alter table kat_fragen add column if not exists frage_id       text;
alter table kat_fragen add column if not exists quelle         text not null default 'objekt';  -- objekt | raum | bereich_zone18599 | bereich_lueftung
alter table kat_fragen add column if not exists fragen_klasse  text not null default '';        -- Aufenthalt | Nassraum | Erschließung | Lager | Technik | Außen
alter table kat_fragen add column if not exists referenz_spec  jsonb;   -- geparst aus Antwortoptionen bei Objektreferenz_TGA
alter table kat_fragen add column if not exists bedingung_spec jsonb;   -- geparst aus Bedingung: {"op":"immer"} | {"op":"eq","titel":..,"wert":..} | {"op":"ne",..} | {"op":"eltern_in","klassen":[..]}
-- Kluster-FK weg: 12 Fragen tragen den Platzhalter «Gewerk» (Kluster wird zur Laufzeit aus dem Gewerk des
-- Eltern-Objekts abgeleitet). Prüfung unbekannter Kluster übernimmt v_katalog_check.
alter table kat_fragen drop constraint if exists kat_fragen_kluster_fkey;

-- Primärschlüssel umstellen: (objektklasse, objekttyp, titel) -> frage_id
-- Raumfragen haben objektklasse='' und objekttyp='' bei unterschiedlichem Raumtyp – alter PK trägt nicht mehr.
do $$
begin
  -- Bestandszeilen (aus 04_seed) bekommen einen berechneten Schlüssel, damit NOT NULL greift
  update kat_fragen
     set frage_id = 'F-' || left(encode(sha256(convert_to(
           coalesce(quelle,'objekt') || '|' || objektklasse || '|' || objekttyp || '|' || coalesce(raumtyp,'') || '|' || coalesce(fragen_klasse,'') || '|' || titel, 'UTF8')), 'hex'), 10)
   where frage_id is null;

  if exists (select 1 from pg_constraint where conname = 'kat_fragen_pkey'
             and conrelid = 'kat_fragen'::regclass
             and pg_get_constraintdef(oid) like 'PRIMARY KEY (objektklasse, objekttyp, titel)') then
    alter table kat_fragen drop constraint kat_fragen_pkey;
  end if;
  if not exists (select 1 from pg_constraint where conname = 'kat_fragen_pkey' and conrelid = 'kat_fragen'::regclass) then
    alter table kat_fragen alter column frage_id set not null;
    alter table kat_fragen add constraint kat_fragen_pkey primary key (frage_id);
  end if;
end $$;

-- fachlicher Schlüssel bleibt eindeutig (ein Scope = eine Frage je Titel)
create unique index if not exists kat_fragen_scope_uidx
  on kat_fragen (quelle, objektklasse, objekttyp, raumtyp, fragen_klasse, titel);
create index if not exists kat_fragen_ebene_idx on kat_fragen (ebene, objektklasse, objekttyp);
create index if not exists kat_fragen_raum_idx  on kat_fragen (quelle, raumtyp, fragen_klasse) where quelle = 'raum';

-- ---------------------------------------------------------------------------
-- 2. Neue Katalogtabellen
-- ---------------------------------------------------------------------------
create table if not exists kat_raumtypen (
  raumtyp                   text primary key,
  raumklasse                text default '',
  fragen_klasse             text default '',          -- Aufenthalt | Nassraum | Erschließung | Lager | Technik | Außen | ''
  nutzung                   text default '',          -- WG | NWG | WG/NWG
  lueftungszone             text default '',
  verfuegbar_in_bereichstyp text default '',          -- ';'-getrennt, Namen aus kat_bereichstypen
  beheizung                 text default '',
  objektklassen_vorfilter   text default '',          -- vorläufig (Freitext)
  notiz                     text default '',
  aktiv                     boolean not null default true
);

create table if not exists kat_bereichstypen (
  bereichstyp             text primary key,
  metabereich_vorbelegung text default '',
  beheizung               text default '',            -- beheizt | gering beheizt | unbeheizt | außen
  raumtyp_vorfilter       text default '',            -- vorläufig, ';'-getrennt
  beschreibung            text default '',
  aktiv                   boolean not null default true,
  notiz                   text default ''
);

create table if not exists kat_nutzungsprofile_18599 (
  nr             int primary key,
  nutzungsprofil text not null,
  aktiv          boolean not null default true,
  notiz          text default ''
);

create table if not exists kat_hilfetext_override (
  frage               text not null,                  -- Titel der Frage
  kontext_objekttyp   text not null,                  -- Objekttyp, für den der Override gilt
  hilfetext_override  text default '',
  hilfemedien_override text default '',
  aktiv               boolean not null default true,
  primary key (frage, kontext_objekttyp)
);

create table if not exists kat_meta (
  key   text primary key,                             -- katalog_version | importiert_am | quelle | importer
  value text not null default ''
);

-- kat_raumtyp_zuordnung: keine harten FKs (Bereichstyp 'alle' + Namensabweichungen), Prüfung über v_katalog_check

-- ---------------------------------------------------------------------------
-- 3. RLS: lesen für authenticated, schreiben nur Service-Role
-- ---------------------------------------------------------------------------
alter table kat_raumtypen             enable row level security;
alter table kat_bereichstypen         enable row level security;
alter table kat_nutzungsprofile_18599 enable row level security;
alter table kat_hilfetext_override    enable row level security;
alter table kat_meta                  enable row level security;

do $$
declare t text;
begin
  foreach t in array array['kat_raumtypen','kat_bereichstypen','kat_nutzungsprofile_18599','kat_hilfetext_override','kat_meta'] loop
    if not exists (select 1 from pg_policies where tablename = t and policyname = 'r_' || t) then
      execute format('create policy %I on %I for select to authenticated using (true)', 'r_' || t, t);
    end if;
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- 4. Konsistenz-View: nach jedem Import muss sie leer sein
-- ---------------------------------------------------------------------------
create or replace view v_katalog_check as
with
klassen as (select distinct objektklasse from kat_objekte),
typen   as (select objektklasse, objekttyp from kat_objekte),
bt      as (select bereichstyp from kat_bereichstypen),
rt      as (select raumtyp from kat_raumtypen),
-- Pseudo-Klassen, die bewusst nicht im Objektkatalog stehen
pseudo  as (select unnest(array['','(Basis)']) as name)
select * from (
  -- Fragen, deren Objektklasse es nicht gibt
  select 'fehler' as schwere, 'kat_fragen' as tabelle, f.frage_id as schluessel,
         'Objektklasse "' || f.objektklasse || '" nicht im Objektkatalog' as problem
    from kat_fragen f
   where f.objektklasse not in (select objektklasse from klassen)
     and f.objektklasse not in (select name from pseudo)
  union all
  -- Fragen, deren Objekttyp es (in dieser Klasse) nicht gibt
  select 'fehler', 'kat_fragen', f.frage_id,
         'Objekttyp "' || f.objekttyp || '" nicht in Klasse "' || f.objektklasse || '"'
    from kat_fragen f
   where f.objekttyp <> ''
     and not exists (select 1 from typen t where t.objektklasse = f.objektklasse and t.objekttyp = f.objekttyp)
  union all
  -- Fragen mit unbekanntem Kluster (kein FK mehr, siehe oben)
  select 'fehler', 'kat_fragen', f.frage_id, 'Kluster "' || f.kluster || '" nicht im Klusterkatalog'
    from kat_fragen f
   where f.kluster is not null and f.kluster not like '«%'
     and f.kluster not in (select kluster from kat_kluster)
  union all
  select 'hinweis', 'kat_fragen', f.frage_id, 'Kluster "' || f.kluster || '" ist Platzhalter (zur Laufzeit vom Gewerk ableiten)'
    from kat_fragen f where f.kluster like '«%'
  union all
  -- Raumfragen mit Raumtyp, den es nicht gibt
  select 'fehler', 'kat_fragen', f.frage_id, 'Raumtyp "' || f.raumtyp || '" nicht in kat_raumtypen'
    from kat_fragen f
   where f.quelle = 'raum' and f.raumtyp <> '' and f.raumtyp not in (select raumtyp from rt)
  union all
  -- Bedingung referenziert einen Titel, den es nirgends gibt
  select 'warnung', 'kat_fragen', f.frage_id,
         'Bedingung «' || (f.bedingung_spec->>'titel') || '» hat keine Zielfrage'
    from kat_fragen f
   where f.bedingung_spec->>'titel' is not null
     and not exists (select 1 from kat_fragen z where z.titel = f.bedingung_spec->>'titel')
  union all
  -- Standard Antwort referenziert «Titel» ohne Zielfrage
  select 'warnung', 'kat_fragen', f.frage_id, 'Standard Antwort ' || f.standard_antwort || ' hat keine Zielfrage'
    from kat_fragen f
   where f.standard_antwort like '«%»'
     and not exists (select 1 from kat_fragen z where z.titel = trim(both '«»' from f.standard_antwort))
  union all
  -- Zuordnung: unbekannter Raumtyp / Bereichstyp / Objektklasse
  select 'fehler', 'kat_raumtyp_zuordnung', z.raumtyp || '|' || z.bereichstyp || '|' || z.objektklasse,
         'Raumtyp "' || z.raumtyp || '" nicht in kat_raumtypen'
    from kat_raumtyp_zuordnung z where z.raumtyp not in (select raumtyp from rt)
  union all
  select 'fehler', 'kat_raumtyp_zuordnung', z.raumtyp || '|' || z.bereichstyp || '|' || z.objektklasse,
         'Bereichstyp "' || z.bereichstyp || '" nicht in kat_bereichstypen'
    from kat_raumtyp_zuordnung z where z.bereichstyp <> 'alle' and z.bereichstyp not in (select bereichstyp from bt)
  union all
  select 'fehler', 'kat_raumtyp_zuordnung', z.raumtyp || '|' || z.bereichstyp || '|' || z.objektklasse,
         'Objektklasse "' || z.objektklasse || '" nicht im Objektkatalog'
    from kat_raumtyp_zuordnung z where z.objektklasse not in (select objektklasse from klassen)
  union all
  -- Raumtyp verfügbar in Bereichstyp, den es nicht gibt
  select 'fehler', 'kat_raumtypen', r.raumtyp, 'Verfügbar_in_Bereichstyp "' || x || '" nicht in kat_bereichstypen'
    from kat_raumtypen r, unnest(string_to_array(r.verfuegbar_in_bereichstyp, ';')) as x
   where trim(x) <> '' and trim(x) not in (select bereichstyp from bt)
  union all
  -- Bereichstyp-Vorfilter nennt Raumtypen, die es nicht gibt
  select 'warnung', 'kat_bereichstypen', b.bereichstyp, 'Raumtyp_Vorfilter "' || x || '" nicht in kat_raumtypen'
    from kat_bereichstypen b, unnest(string_to_array(b.raumtyp_vorfilter, ';')) as x
   where trim(x) <> '' and trim(x) not like '(%' and trim(x) not in (select raumtyp from rt)
  union all
  -- Elternklasse, die weder Klasse noch Typ noch Ebene noch Bereichstyp ist
  select 'fehler', 'kat_objekte', o.objektklasse || '|' || o.objekttyp,
         'Erlaubte_Elternklasse "' || x || '" unbekannt'
    from kat_objekte o, unnest(string_to_array(o.erlaubte_elternklasse, ';')) as x
   where trim(x) <> ''
     and trim(x) not in ('Raum','Gebäude','Bereich','alle Objekte')
     and trim(x) not in (select objektklasse from klassen)
     and trim(x) not in (select objekttyp from kat_objekte)
     and trim(x) not in (select bereichstyp from bt)
  union all
  -- Override auf nicht existierende Frage / Objekttyp
  select 'fehler', 'kat_hilfetext_override', h.frage || '|' || h.kontext_objekttyp,
         'Frage "' || h.frage || '" existiert nicht'
    from kat_hilfetext_override h where not exists (select 1 from kat_fragen f where f.titel = h.frage)
  union all
  select 'fehler', 'kat_hilfetext_override', h.frage || '|' || h.kontext_objekttyp,
         'Objekttyp "' || h.kontext_objekttyp || '" existiert nicht'
    from kat_hilfetext_override h where not exists (select 1 from kat_objekte o where o.objekttyp = h.kontext_objekttyp)
  union all
  -- Fragen zu inaktiven Objekttypen
  select 'hinweis', 'kat_fragen', f.frage_id, 'Objekttyp "' || f.objekttyp || '" ist inaktiv'
    from kat_fragen f join kat_objekte o on o.objektklasse = f.objektklasse and o.objekttyp = f.objekttyp
   where not o.aktiv and f.activ
) x
order by case schwere when 'fehler' then 0 when 'warnung' then 1 else 2 end, tabelle, schluessel;

grant select on v_katalog_check to authenticated;

-- ---------------------------------------------------------------------------
-- 5. Katalog-Fassade für die App: alles, was der Client beim Start lädt
-- ---------------------------------------------------------------------------
create or replace view v_katalog_fragen_aktiv as
  select frage_id, quelle, ebene, objektklasse, objekttyp, raumtyp, fragen_klasse, bereichtyp, metabereichtyp,
         titel, frage, antworttyp, antwortoptionen, standard_antwort, einheit, bedingung, bedingung_spec,
         referenz_spec, pflicht, foto_pflicht, fototyp, hilfetext, hilfemedien, kluster, reihenfolge,
         min_lod, zielgruppe, objektart
    from kat_fragen where activ;
grant select on v_katalog_fragen_aktiv to authenticated;
