-- Cloud-Backup (MVP): ganzes Projekt als JSON-Blob je Nutzer.
-- Nach schema.sql ausführen. Später wird dies durch die normalisierte Sync-Schicht abgelöst.

create table project_blobs (
  project_id  text primary key,               -- App-interne Projekt-ID
  owner       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name        text default '',
  payload     jsonb not null,
  updated_at  timestamptz not null default now()
);
create trigger t_blobs before update on project_blobs for each row execute function touch_updated_at();
alter table project_blobs enable row level security;
create policy p_blobs on project_blobs for all
  using (owner = auth.uid()) with check (owner = auth.uid());

-- Storage: privater Bucket 'media' (im Dashboard anlegen), Pfadschema {auth.uid()}/{project_id}/{media_id}
create policy media_rw on storage.objects for all
  using  (bucket_id = 'media' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'media' and (storage.foldername(name))[1] = auth.uid()::text);
