-- FORGE 3.0.0: laboratorio SuperStar separato e temporalmente integro.
-- Migrazione additiva e idempotente; FORGE v2 resta disponibile per audit.

create table if not exists public.forge_superstar_experiments (
    experiment_key text primary key,
    archive_signature text not null,
    forge_version text not null,
    model_id text not null,
    label text not null,
    family text not null,
    selected_for_holdout boolean not null default false,
    configuration jsonb not null default '{}'::jsonb,
    metrics jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists forge_superstar_experiments_archive_idx
    on public.forge_superstar_experiments
    (archive_signature, forge_version, selected_for_holdout, model_id);

create table if not exists public.forge_superstar_state (
    id smallint primary key default 1 check (id = 1),
    mode text not null default 'shadow' check (mode in ('shadow', 'promoted')),
    champion_model jsonb not null default '{}'::jsonb,
    challenger_model jsonb null,
    prospective_minimum integer not null default 100 check (prospective_minimum >= 100),
    note text null,
    updated_at timestamptz not null default now()
);

insert into public.forge_superstar_state (
    id, mode, champion_model, challenger_model, prospective_minimum, note
) values (
    1,
    'shadow',
    '{"model_id":"SUPERSTAR-LEGACY-V1","label":"SuperStar ORION protetto","family":"legacy_orion","parameters":{},"eligible_for_promotion":true}'::jsonb,
    null,
    100,
    'Il backtest storico seleziona lo shadow; solo dati prospettici promuovono.'
)
on conflict (id) do update set
    prospective_minimum = greatest(
        public.forge_superstar_state.prospective_minimum,
        excluded.prospective_minimum
    );

create table if not exists public.forge_superstar_predictions (
    prediction_key text primary key,
    archive_signature text not null,
    forge_version text not null,
    source_year integer not null,
    source_contest integer not null,
    source_date date not null,
    role text not null check (role in ('champion', 'challenger')),
    model_id text not null,
    model_config jsonb not null default '{}'::jsonb,
    predicted_superstar smallint not null check (predicted_superstar between 1 and 90),
    status text not null default 'pending' check (status in ('pending', 'evaluated', 'void')),
    target_year integer null,
    target_contest integer null,
    target_date date null,
    target_superstar smallint null check (target_superstar between 1 and 90),
    superstar_hit boolean null,
    created_at timestamptz not null default now(),
    evaluated_at timestamptz null
);

create index if not exists forge_superstar_predictions_pair_idx
    on public.forge_superstar_predictions
    (forge_version, status, role, model_id, target_date);

create unique index if not exists forge_superstar_one_pending_role_idx
    on public.forge_superstar_predictions
    (forge_version, source_year, source_contest, role)
    where status = 'pending';

-- Recupera soltanto osservazioni realmente congelate prima del target. Una
-- coppia champion/challenger con lo stesso valore vale una volta sola.
insert into public.forge_superstar_predictions (
    prediction_key, archive_signature, forge_version,
    source_year, source_contest, source_date,
    role, model_id, model_config, predicted_superstar,
    status, target_year, target_contest, target_date,
    target_superstar, superstar_hit, created_at, evaluated_at
)
select distinct on (
    source_year, source_contest, target_year, target_contest
)
    'legacy-superstar:' || prediction_key,
    archive_signature,
    '3.0.0',
    source_year, source_contest, source_date,
    'champion', 'SUPERSTAR-LEGACY-V1',
    '{"family":"legacy_orion","backfilled_from":"forge_predictions"}'::jsonb,
    predicted_superstar,
    'evaluated', target_year, target_contest, target_date,
    target_superstar, superstar_hit, created_at, evaluated_at
from public.forge_predictions
where status = 'evaluated'
  and predicted_superstar is not null
  and target_superstar is not null
  and superstar_hit is not null
  and created_at < ((target_date + time '20:00') at time zone 'Europe/Rome')
order by source_year, source_contest, target_year, target_contest,
         (role = 'champion') desc, created_at
on conflict (prediction_key) do nothing;

create or replace function public.invalidate_forge_superstar_on_draw_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    cutoff_date date;
    previous_max date;
    identity_changed boolean;
    date_changed boolean;
    superstar_changed boolean;
begin
    if tg_op = 'INSERT' then
        select max(data_estrazione) into previous_max
        from public.estrazioni where id <> new.id;
        if previous_max is null or new.data_estrazione > previous_max then
            return new;
        end if;
        cutoff_date := new.data_estrazione;
    elsif tg_op = 'DELETE' then
        cutoff_date := old.data_estrazione;
    else
        identity_changed := row(old.anno, old.concorso)
            is distinct from row(new.anno, new.concorso);
        date_changed := old.data_estrazione is distinct from new.data_estrazione;
        superstar_changed := old.superstar is distinct from new.superstar;

        if identity_changed then
            cutoff_date := least(old.data_estrazione, new.data_estrazione);
        else
            if date_changed then
                update public.forge_superstar_predictions
                set source_date = new.data_estrazione
                where source_year = old.anno and source_contest = old.concorso;

                update public.forge_superstar_predictions
                set target_date = new.data_estrazione
                where status = 'evaluated'
                  and target_year = old.anno and target_contest = old.concorso;
            end if;

            -- La sestina e il Jolly non entrano nei modelli SuperStar.
            if not superstar_changed then
                return new;
            end if;

            update public.forge_superstar_predictions as prediction
            set target_year = new.anno,
                target_contest = new.concorso,
                target_date = new.data_estrazione,
                target_superstar = new.superstar,
                superstar_hit = prediction.predicted_superstar = new.superstar,
                evaluated_at = now()
            where prediction.status = 'evaluated'
              and prediction.target_year = old.anno
              and prediction.target_contest = old.concorso;

            update public.forge_superstar_predictions
            set status = 'void',
                target_year = null,
                target_contest = null,
                target_date = null,
                target_superstar = null,
                superstar_hit = null,
                evaluated_at = null
            where status = 'pending'
              and source_date >= new.data_estrazione;
            return new;
        end if;
    end if;

    update public.forge_superstar_predictions
    set status = 'void',
        target_year = null,
        target_contest = null,
        target_date = null,
        target_superstar = null,
        superstar_hit = null,
        evaluated_at = null
    where status in ('pending', 'evaluated')
      and (source_date >= cutoff_date or target_date >= cutoff_date);

    if tg_op = 'DELETE' then return old; end if;
    return new;
end;
$$;

revoke execute on function public.invalidate_forge_superstar_on_draw_change()
from public, anon, authenticated;

drop trigger if exists trg_invalidate_forge_superstar on public.estrazioni;
create trigger trg_invalidate_forge_superstar
after insert or update or delete on public.estrazioni
for each row execute function public.invalidate_forge_superstar_on_draw_change();

alter table public.forge_superstar_experiments enable row level security;
alter table public.forge_superstar_state enable row level security;
alter table public.forge_superstar_predictions enable row level security;

revoke all on table public.forge_superstar_experiments from anon, authenticated;
revoke all on table public.forge_superstar_state from anon, authenticated;
revoke all on table public.forge_superstar_predictions from anon, authenticated;
grant select, insert, update, delete on table public.forge_superstar_experiments to service_role;
grant select, insert, update, delete on table public.forge_superstar_state to service_role;
grant select, insert, update, delete on table public.forge_superstar_predictions to service_role;
