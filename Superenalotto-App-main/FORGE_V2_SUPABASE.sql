-- ORION v2.7.4 / FORGE 2
-- Memoria persistente champion/challenger.
-- L'app tenta di creare automaticamente queste tabelle.
-- Eseguire manualmente in Supabase SQL Editor solo se l'interfaccia segnala
-- un errore di persistenza o l'utente del database non dispone dei permessi DDL.

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
    prospective_minimum integer not null default 30,
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
