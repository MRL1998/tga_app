-- Katalog-Tabellen: 1:1-Abbild der 4 CSVs aus data/.
-- Diese Tabellen pflegst du laufend weiter (Dashboard-Table-Editor oder CSV-Reimport
-- über tools/csv_to_seed.py -> 04_seed_catalogs.sql).
-- Lesen: jeder angemeldete Nutzer. Schreiben: nur Dashboard/Service-Role (keine Write-Policy).

create table kat_kluster (
  kluster             text primary key,
  im_bericht          boolean not null default true,
  reihenfolge_bericht text default '',
  beschreibung        text default ''
);

create table kat_objekte (
  objektklasse          text not null,
  objekttyp             text not null,
  objektart             text not null default 'Objekt',    -- Objekt | Sub-Objekt
  gewerk                text default '',
  erlaubte_elternklasse text default '',                   -- ";"-getrennt wie in der CSV
  aktiv                 boolean not null default true,
  notiz                 text default '',
  primary key (objektklasse, objekttyp)
);

create table kat_fragen (
  objektklasse     text not null default '',
  objekttyp        text not null default '',
  titel            text not null,
  frage            text not null,
  ebene            text default 'Objekt',
  metabereichtyp   text default '',
  bereichtyp       text default '',
  raumtyp          text default '',
  antworttyp       text not null,
  antwortoptionen  text default '',                        -- ";"-getrennt
  standard_antwort text default '',
  einheit          text default '',
  bedingung        text not null default 'immer',
  pflicht          boolean not null default false,
  foto_pflicht     boolean not null default false,
  hilfetext        text default '',
  kluster          text references kat_kluster(kluster),
  reihenfolge      int,
  activ            boolean not null default true,
  fragekatalog     text default '',
  autor            text default '',
  version          text default '',
  aenderungsdatum  text default '',
  min_lod          int default 200,
  zielgruppe       text default '',
  fototyp          text default '',
  hilfemedien      text default '',
  objektart        text default '',
  primary key (objektklasse, objekttyp, titel)
);

create table kat_raumtyp_zuordnung (
  raumtyp          text not null,
  bereichstyp      text not null default 'alle',
  objektklasse     text not null,
  vorauswahl       text default 'Standard',                -- Standard | Optional
  anzahl_typisch   text default '',
  prompt_wenn_fehlt boolean not null default false,
  notiz            text default '',
  primary key (raumtyp, bereichstyp, objektklasse)
);

alter table kat_kluster            enable row level security;
alter table kat_objekte            enable row level security;
alter table kat_fragen             enable row level security;
alter table kat_raumtyp_zuordnung  enable row level security;

create policy r_kluster  on kat_kluster           for select to authenticated using (true);
create policy r_objekte  on kat_objekte           for select to authenticated using (true);
create policy r_fragen   on kat_fragen            for select to authenticated using (true);
create policy r_zuordnung on kat_raumtyp_zuordnung for select to authenticated using (true);
