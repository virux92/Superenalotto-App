-- ORION v2.7.5 / FORGE 2
-- Memoria persistente champion/challenger e protezioni di integrità.
-- L'app tenta di applicare automaticamente queste definizioni.
-- Eseguire manualmente in Supabase SQL Editor soltanto se l'interfaccia
-- segnala un errore DDL o di persistenza.

create table if not exists public.forge_experiments_v2 (
    experiment_key text primary key,
    archive_signature text not null,
    forge_version text not null,
    model_id text not null,
    status text not null,
    quality double precision null,
    configuration jsonb not null default '{}'::jsonb,
    metrics jsonb not null default '{}'::jsonb,
    checks jsonb not null default '{}'::jsonb,
    reason text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists forge_experiments_v2_archive_idx
    on public.forge_experiments_v2
    (archive_signature, forge_version, status, quality desc);

create table if not exists public.forge_state (
    id smallint primary key default 1 check (id = 1),
    mode text not null default 'shadow',
    champion_model jsonb not null default '{}'::jsonb,
    challenger_model jsonb null,
    prospective_minimum integer not null default 100,
    note text null,
    updated_at timestamptz not null default now()
);

create table if not exists public.forge_predictions (
    prediction_key text primary key,
    archive_signature text not null,
    forge_version text not null,
    source_year integer not null,
    source_contest integer not null,
    source_date date not null,
    role text not null check (role in ('champion', 'challenger')),
    model_id text not null,
    model_config jsonb not null default '{}'::jsonb,
    n1 smallint not null,
    n2 smallint not null,
    n3 smallint not null,
    n4 smallint not null,
    n5 smallint not null,
    n6 smallint not null,
    status text not null default 'pending'
        check (status in ('pending', 'evaluated', 'void')),
    target_year integer null,
    target_contest integer null,
    target_date date null,
    hits smallint null,
    created_at timestamptz not null default now(),
    evaluated_at timestamptz null,
    constraint forge_predictions_numbers_ordered
        check (n1 < n2 and n2 < n3 and n3 < n4 and n4 < n5 and n5 < n6)
);

create index if not exists forge_predictions_pending_idx
    on public.forge_predictions (status, source_date, role, model_id);

create index if not exists forge_predictions_pair_idx
    on public.forge_predictions
    (archive_signature, status, role, model_id);

create unique index if not exists forge_predictions_one_pending_role_idx
    on public.forge_predictions
    (forge_version, source_year, source_contest, role)
    where status = 'pending';

update public.forge_state
set prospective_minimum = 100,
    updated_at = now()
where prospective_minimum < 100;

alter table public.forge_state
alter column prospective_minimum set default 100;

create or replace function public.invalidate_forge_predictions_on_draw_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    cutoff_date date;
    previous_max date;
begin
    if tg_op = 'INSERT' then
        select max(data_estrazione)
        into previous_max
        from public.estrazioni
        where id <> new.id;

        if previous_max is null or new.data_estrazione > previous_max then
            return new;
        end if;
        cutoff_date := new.data_estrazione;
    elsif tg_op = 'UPDATE' then
        if row(
            old.data_estrazione, old.concorso,
            old.n1, old.n2, old.n3, old.n4, old.n5, old.n6,
            old.jolly, old.superstar
        ) is not distinct from row(
            new.data_estrazione, new.concorso,
            new.n1, new.n2, new.n3, new.n4, new.n5, new.n6,
            new.jolly, new.superstar
        ) then
            return new;
        end if;
        cutoff_date := least(old.data_estrazione, new.data_estrazione);
    else
        cutoff_date := old.data_estrazione;
    end if;

    update public.forge_predictions
    set status = 'void',
        target_year = null,
        target_contest = null,
        target_date = null,
        hits = null,
        evaluated_at = null
    where status in ('pending', 'evaluated')
      and (
            source_date >= cutoff_date
            or target_date >= cutoff_date
      );

    if tg_op = 'DELETE' then
        return old;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_invalidate_forge_predictions
on public.estrazioni;

create trigger trg_invalidate_forge_predictions
after insert or update or delete on public.estrazioni
for each row
execute function public.invalidate_forge_predictions_on_draw_change();
