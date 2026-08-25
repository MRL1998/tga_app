-- TGA-Aufnahme · Supabase MVP-Schema
-- Ausführen im Supabase SQL-Editor (einmalig). Auth nutzt das eingebaute auth.users.

-- ========== Projekte ==========
create table projects (
  id          uuid primary key default gen_random_uuid(),
  owner       uuid not null references auth.users(id) on delete cascade,
  type        text not null default 'gebaeude' check (type in ('gebaeude','bereich')),
  name        text not null default '',
  bereich     text default '',
  strasse     text default '',
  plz         text default '',
  ort         text default '',
  baujahr     text default '',
  plan_path   text,                       -- Storage-Pfad des Grundriss-Plans
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- ========== Räume (Pins) ==========
create table rooms (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  num         text not null default '',
  name        text not null default '',
  raumtyp     text default '',            -- Küche | Bad | Zimmer | Flur/Eingang
  xp          double precision not null default 50,   -- Prozent auf dem Plan
  yp          double precision not null default 50,
  notes       text default '',
  nv          jsonb not null default '{}'::jsonb,     -- "nicht vorhanden"-Markierungen je Objektklasse
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- ========== Objekt-Instanzen (inkl. Sub-Objekte via parent_id) ==========
create table objects (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  room_id     uuid references rooms(id) on delete cascade,   -- null = Gebäude-Ebene
  parent_id   uuid references objects(id) on delete cascade, -- Baugruppen-Baum
  objektklasse text not null,
  objekttyp    text not null,
  gewerk       text default '',
  label        text default '',
  copied_from  uuid,
  sort         int not null default 0,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index on objects (project_id);
create index on objects (room_id);
create index on objects (parent_id);

-- ========== Antworten (eine Zeile je Frage-Titel) ==========
create table answers (
  object_id   uuid not null references objects(id) on delete cascade,
  titel       text not null,              -- stabiler Fragen-Schlüssel aus dem Fragekatalog
  wert        jsonb,                      -- String, Zahl oder Array (Mehrfachauswahl)
  updated_at  timestamptz not null default now(),
  primary key (object_id, titel)
);

-- ========== Medien (Fotos, Sprachmemos) ==========
create table media (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  object_id   uuid references objects(id) on delete cascade,
  room_id     uuid references rooms(id) on delete cascade,
  frage_titel text,                       -- bei Foto-Pflichtfragen: zugehörige Frage
  kind        text not null check (kind in ('foto','audio')),
  storage_path text not null,             -- Pfad im Storage-Bucket 'media'
  caption     text default '',
  created_at  timestamptz not null default now()
);
create index on media (project_id);

-- ========== Kataloge (versioniert, von Tobias pflegbar) ==========
create table catalogs (
  id          bigint generated always as identity primary key,
  version     text not null,
  payload     jsonb not null,             -- Inhalt von data/catalogs.json
  created_at  timestamptz not null default now()
);

-- ========== updated_at automatisch pflegen ==========
create or replace function touch_updated_at() returns trigger as $$
begin new.updated_at = now(); return new; end;
$$ language plpgsql;
create trigger t_projects before update on projects for each row execute function touch_updated_at();
create trigger t_rooms    before update on rooms    for each row execute function touch_updated_at();
create trigger t_objects  before update on objects  for each row execute function touch_updated_at();

-- ========== Row Level Security: jeder sieht nur eigene Projekte ==========
alter table projects enable row level security;
alter table rooms    enable row level security;
alter table objects  enable row level security;
alter table answers  enable row level security;
alter table media    enable row level security;
alter table catalogs enable row level security;

create policy p_projects on projects for all
  using (owner = auth.uid()) with check (owner = auth.uid());

create policy p_rooms on rooms for all
  using (exists (select 1 from projects p where p.id = project_id and p.owner = auth.uid()))
  with check (exists (select 1 from projects p where p.id = project_id and p.owner = auth.uid()));

create policy p_objects on objects for all
  using (exists (select 1 from projects p where p.id = project_id and p.owner = auth.uid()))
  with check (exists (select 1 from projects p where p.id = project_id and p.owner = auth.uid()));

create policy p_answers on answers for all
  using (exists (select 1 from objects o join projects p on p.id = o.project_id
                 where o.id = object_id and p.owner = auth.uid()))
  with check (exists (select 1 from objects o join projects p on p.id = o.project_id
                 where o.id = object_id and p.owner = auth.uid()));

create policy p_media on media for all
  using (exists (select 1 from projects p where p.id = project_id and p.owner = auth.uid()))
  with check (exists (select 1 from projects p where p.id = project_id and p.owner = auth.uid()));

create policy p_catalogs_read on catalogs for select using (true);  -- Kataloge liest jeder Angemeldete

-- ========== Storage ==========
-- Im Dashboard einen privaten Bucket 'media' anlegen (Fotos + Audio).
-- Zugriffspolicy: Pfadschema {project_id}/... , Prüfung analog p_media.
