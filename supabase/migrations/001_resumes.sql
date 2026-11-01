create table if not exists public.resumes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade default auth.uid(),
  title text not null check (char_length(title) between 1 and 200),
  content jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists resumes_user_id_idx on public.resumes(user_id);
alter table public.resumes enable row level security;
create policy resumes_select_own on public.resumes for select to authenticated using ((select auth.uid()) = user_id);
create policy resumes_insert_own on public.resumes for insert to authenticated with check ((select auth.uid()) = user_id);
create policy resumes_update_own on public.resumes for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy resumes_delete_own on public.resumes for delete to authenticated using ((select auth.uid()) = user_id);
grant select, insert, update, delete on public.resumes to authenticated;
revoke all on public.resumes from anon;
