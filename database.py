from __future__ import annotations

from contextlib import contextmanager
import json
from typing import Iterator, Mapping

import pandas as pd
import psycopg
from psycopg.rows import dict_row
import streamlit as st

from services.archive_service import normalize_archive_dataframe


class DatabaseConfigurationError(RuntimeError):
    """Raised when the database secret is missing or malformed."""


def get_database_url() -> str:
    try:
        url = str(st.secrets["database"]["url"]).strip()
    except (KeyError, TypeError) as exc:
        raise DatabaseConfigurationError(
            "Manca il secret [database].url nelle impostazioni di Streamlit."
        ) from exc

    if not url.startswith(("postgresql://", "postgres://")):
        raise DatabaseConfigurationError("La stringa database non è una URI PostgreSQL valida.")
    return url


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(
        get_database_url(),
        connect_timeout=15,
        application_name="superenalotto_streamlit",
        row_factory=dict_row,
    )
    try:
        yield connection
    finally:
        connection.close()


def database_health() -> dict[str, object]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select current_database() as database, now() as server_time")
            server = cursor.fetchone()
            cursor.execute(
                """
                select count(*)::int as table_count
                from information_schema.tables
                where table_schema = 'public'
                """
            )
            table_count = cursor.fetchone()["table_count"]
            cursor.execute("select count(*)::int as draw_count from public.estrazioni")
            draw_count = cursor.fetchone()["draw_count"]
    return {
        "database": server["database"],
        "server_time": server["server_time"],
        "table_count": table_count,
        "draw_count": draw_count,
    }


def fetch_draws() -> pd.DataFrame:
    """Legge l'archivio senza passare da pandas.read_sql.

    L'uso diretto del cursore psycopg evita incompatibilità tra versioni di
    pandas/psycopg e garantisce che i nomi delle colonne siano separati dai dati.
    """
    query = """
        select
            data_estrazione as data,
            anno,
            concorso,
            n1, n2, n3, n4, n5, n6,
            jolly,
            superstar
        from public.estrazioni
        order by data_estrazione, concorso
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    columns = [
        "data", "anno", "concorso", "n1", "n2", "n3", "n4", "n5", "n6", "jolly", "superstar"
    ]
    return pd.DataFrame(rows, columns=columns)


def _write_draw_records(
    dataframe: pd.DataFrame, source: str, log_action: str
) -> dict[str, int]:
    """Scrive righe già validate nell'archivio Supabase."""
    sql = """
        insert into public.estrazioni (
            data_estrazione, concorso,
            n1, n2, n3, n4, n5, n6,
            jolly, superstar, fonte
        ) values (
            %(data)s, %(concorso)s,
            %(n1)s, %(n2)s, %(n3)s, %(n4)s, %(n5)s, %(n6)s,
            %(jolly)s, %(superstar)s, %(fonte)s
        )
        on conflict (anno, concorso) do update set
            data_estrazione = excluded.data_estrazione,
            n1 = excluded.n1,
            n2 = excluded.n2,
            n3 = excluded.n3,
            n4 = excluded.n4,
            n5 = excluded.n5,
            n6 = excluded.n6,
            jolly = excluded.jolly,
            superstar = excluded.superstar,
            fonte = excluded.fonte
    """

    records: list[dict[str, object]] = []
    for row in dataframe.to_dict(orient="records"):
        record: dict[str, object] = {
            "data": pd.Timestamp(row["data"]).date(),
            "concorso": int(row["concorso"]),
            "fonte": source,
            "jolly": None if pd.isna(row["jolly"]) else int(row["jolly"]),
            "superstar": int(row["superstar"]),
        }
        record.update({f"n{i}": int(row[f"n{i}"]) for i in range(1, 7)})
        records.append(record)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(sql, records)
            cursor.execute(
                """
                insert into public.log_operazioni (livello, categoria, azione, messaggio, dettagli)
                values ('info', 'archivio', %s, %s, %s::jsonb)
                """,
                (
                    log_action,
                    f"Importate o aggiornate {len(records)} estrazioni",
                    json.dumps({"origine": source}, ensure_ascii=False),
                ),
            )
        connection.commit()

    return {"processed": len(records)}


def import_draws(
    dataframe: pd.DataFrame, source: str = "import_csv_iniziale"
) -> dict[str, int]:
    """Importa un archivio completo dopo la validazione centrale."""
    canonical = normalize_archive_dataframe(dataframe)
    return _write_draw_records(canonical, source, "importazione_estrazioni")


def upsert_draw(
    draw: Mapping[str, object], source: str = "inserimento_manuale"
) -> dict[str, int]:
    """Inserisce o aggiorna una riga validando l'intero archivio risultante."""
    existing = fetch_draws()
    incoming = pd.DataFrame([dict(draw)])

    if existing.empty:
        candidate = incoming
    else:
        incoming_year = int(incoming.iloc[0]["anno"])
        incoming_contest = int(incoming.iloc[0]["concorso"])
        keep_mask = ~(
            (existing["anno"].astype(int) == incoming_year)
            & (existing["concorso"].astype(int) == incoming_contest)
        )
        candidate = pd.concat([existing.loc[keep_mask], incoming], ignore_index=True)

    canonical = normalize_archive_dataframe(candidate)
    validated_row = canonical.loc[
        (canonical["anno"] == int(incoming.iloc[0]["anno"]))
        & (canonical["concorso"] == int(incoming.iloc[0]["concorso"]))
    ]
    if len(validated_row) != 1:
        raise ValueError("L'estrazione da salvare non è stata validata in modo univoco.")

    return _write_draw_records(validated_row, source, "salvataggio_estrazione")


def delete_draw(year: int, contest: int, source: str = "eliminazione_manuale") -> dict[str, int]:
    """Elimina un concorso esistente e registra l'operazione.

    Il controllo viene applicato anche a livello database, così una chiamata
    diretta non può creare buchi nella sequenza annuale.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select anno, concorso
                from public.estrazioni
                order by data_estrazione desc, anno desc, concorso desc
                limit 1
                for update
                """
            )
            latest = cursor.fetchone()
            if latest is None:
                raise ValueError("L'archivio è vuoto.")
            if (int(latest["anno"]), int(latest["concorso"])) != (
                int(year),
                int(contest),
            ):
                raise ValueError(
                    "Per sicurezza è possibile eliminare soltanto l'ultima estrazione "
                    f"({int(latest['concorso'])}/{int(latest['anno'])})."
                )

            cursor.execute(
                """
                delete from public.estrazioni
                where anno = %s and concorso = %s
                returning data_estrazione, anno, concorso
                """,
                (int(year), int(contest)),
            )
            deleted = cursor.fetchone()
            if deleted is None:
                raise ValueError(f"Concorso {contest} del {year} non trovato.")

            cursor.execute(
                """
                insert into public.log_operazioni
                    (livello, categoria, azione, messaggio, dettagli)
                values ('warning', 'archivio', 'eliminazione_estrazione', %s, %s::jsonb)
                """,
                (
                    f"Eliminato concorso {int(contest)} del {int(year)}",
                    json.dumps(
                        {
                            "origine": source,
                            "anno": int(year),
                            "concorso": int(contest),
                            "data": str(deleted["data_estrazione"]),
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        connection.commit()

    return {"deleted": 1}


@st.cache_resource(show_spinner=False)
def ensure_recommendations_table() -> None:
    """Crea la tabella delle schedine monitorate al primo utilizzo."""
    sql = """
        create table if not exists public.schedine_monitorate (
            id bigint generated by default as identity primary key,
            created_at timestamptz not null default now(),
            nome text not null default 'Schedina consigliata',
            n1 smallint not null check (n1 between 1 and 90),
            n2 smallint not null check (n2 between 1 and 90),
            n3 smallint not null check (n3 between 1 and 90),
            n4 smallint not null check (n4 between 1 and 90),
            n5 smallint not null check (n5 between 1 and 90),
            n6 smallint not null check (n6 between 1 and 90),
            superstar smallint null check (superstar between 1 and 90),
            anno_inizio integer not null check (anno_inizio >= 2020),
            concorso_inizio integer not null check (concorso_inizio >= 1),
            numero_concorsi integer not null default 1 check (numero_concorsi between 1 and 100),
            fonte text not null default 'generatore_app',
            note text null,
            attiva boolean not null default true,
            constraint schedine_monitorate_numeri_ordinati
                check (n1 < n2 and n2 < n3 and n3 < n4 and n4 < n5 and n5 < n6)
        );
        create index if not exists schedine_monitorate_target_idx
            on public.schedine_monitorate (anno_inizio, concorso_inizio);
    """
    table_sql, index_sql = [statement.strip() for statement in sql.split(";") if statement.strip()]
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(table_sql)
            cursor.execute(index_sql)
        connection.commit()


def save_recommendation(
    numbers: list[int] | tuple[int, ...],
    superstar: int | None,
    start_year: int,
    start_contest: int,
    draw_count: int,
    name: str = "Schedina consigliata",
    source: str = "generatore_app",
    notes: str | None = None,
) -> dict[str, int]:
    from services.recommendation_service import normalize_ticket_numbers

    normalized = normalize_ticket_numbers(numbers)
    superstar_value = None if superstar is None else int(superstar)
    if superstar_value is not None and not 1 <= superstar_value <= 90:
        raise ValueError("Il SuperStar deve essere compreso tra 1 e 90.")
    if int(start_year) < 2020 or int(start_contest) < 1:
        raise ValueError("Anno o numero del concorso iniziale non validi.")
    if not 1 <= int(draw_count) <= 100:
        raise ValueError("Puoi monitorare da 1 a 100 concorsi.")

    ensure_recommendations_table()
    sql = """
        insert into public.schedine_monitorate (
            nome, n1, n2, n3, n4, n5, n6, superstar,
            anno_inizio, concorso_inizio, numero_concorsi, fonte, note
        ) values (
            %(nome)s, %(n1)s, %(n2)s, %(n3)s, %(n4)s, %(n5)s, %(n6)s, %(superstar)s,
            %(anno_inizio)s, %(concorso_inizio)s, %(numero_concorsi)s, %(fonte)s, %(note)s
        )
        returning id
    """
    record: dict[str, object] = {
        "nome": (name or "Schedina consigliata").strip(),
        "superstar": superstar_value,
        "anno_inizio": int(start_year),
        "concorso_inizio": int(start_contest),
        "numero_concorsi": int(draw_count),
        "fonte": source,
        "note": (notes or "").strip() or None,
    }
    record.update({f"n{index}": normalized[index - 1] for index in range(1, 7)})

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, record)
            created = cursor.fetchone()
            cursor.execute(
                """
                insert into public.log_operazioni (livello, categoria, azione, messaggio, dettagli)
                values ('info', 'schedine', 'salvataggio_schedina', %s, %s::jsonb)
                """,
                (
                    f"Salvata schedina monitorata #{int(created['id'])}",
                    json.dumps(
                        {
                            "numeri": list(normalized),
                            "anno_inizio": int(start_year),
                            "concorso_inizio": int(start_contest),
                            "numero_concorsi": int(draw_count),
                            "fonte": source,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        connection.commit()
    return {"id": int(created["id"])}


def fetch_recommendations(active_only: bool = False) -> pd.DataFrame:
    ensure_recommendations_table()
    where_clause = "where attiva is true" if active_only else ""
    query = f"""
        select
            id, created_at, nome,
            n1, n2, n3, n4, n5, n6,
            superstar, anno_inizio, concorso_inizio,
            numero_concorsi, fonte, note, attiva
        from public.schedine_monitorate
        {where_clause}
        order by id desc
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
    columns = [
        "id", "created_at", "nome", "n1", "n2", "n3", "n4", "n5", "n6",
        "superstar", "anno_inizio", "concorso_inizio", "numero_concorsi",
        "fonte", "note", "attiva",
    ]
    return pd.DataFrame(rows, columns=columns)


def delete_recommendation(recommendation_id: int) -> dict[str, int]:
    ensure_recommendations_table()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from public.schedine_monitorate where id = %s returning id",
                (int(recommendation_id),),
            )
            deleted = cursor.fetchone()
            if deleted is None:
                raise ValueError(f"Schedina #{int(recommendation_id)} non trovata.")
            cursor.execute(
                """
                insert into public.log_operazioni (livello, categoria, azione, messaggio, dettagli)
                values ('warning', 'schedine', 'eliminazione_schedina', %s, %s::jsonb)
                """,
                (
                    f"Eliminata schedina monitorata #{int(recommendation_id)}",
                    json.dumps({"id": int(recommendation_id)}, ensure_ascii=False),
                ),
            )
        connection.commit()
    return {"deleted": 1}


@st.cache_resource(show_spinner=False)
def ensure_forge_v2_tables() -> None:
    """Crea la memoria persistente di FORGE 2 senza alterare il registro legacy."""
    statements = [
        """
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
        )
        """,
        """
        create index if not exists forge_experiments_v2_archive_idx
            on public.forge_experiments_v2
            (archive_signature, forge_version, status, quality desc)
        """,
        """
        create table if not exists public.forge_state (
            id smallint primary key default 1 check (id = 1),
            mode text not null default 'shadow',
            champion_model jsonb not null default '{}'::jsonb,
            challenger_model jsonb null,
            prospective_minimum integer not null default 100,
            note text null,
            updated_at timestamptz not null default now()
        )
        """,
        """
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
            predicted_superstar smallint null check (predicted_superstar between 1 and 90),
            status text not null default 'pending'
                check (status in ('pending', 'evaluated', 'void')),
            target_year integer null,
            target_contest integer null,
            target_date date null,
            hits smallint null,
            target_superstar smallint null check (target_superstar between 1 and 90),
            superstar_hit boolean null,
            created_at timestamptz not null default now(),
            evaluated_at timestamptz null,
            constraint forge_predictions_numbers_ordered
                check (n1 < n2 and n2 < n3 and n3 < n4 and n4 < n5 and n5 < n6)
        )
        """,
        """
        alter table public.forge_predictions
            add column if not exists predicted_superstar smallint null,
            add column if not exists target_superstar smallint null,
            add column if not exists superstar_hit boolean null
        """,
        """
        create index if not exists forge_predictions_pending_idx
            on public.forge_predictions (status, source_date, role, model_id)
        """,
        """
        create index if not exists forge_predictions_pair_idx
            on public.forge_predictions
            (archive_signature, status, role, model_id)
        """,
        """
        create unique index if not exists forge_predictions_one_pending_role_idx
            on public.forge_predictions
            (forge_version, source_year, source_contest, role)
            where status = 'pending'
        """,
        """
        update public.forge_state
        set prospective_minimum = 100,
            updated_at = now()
        where prospective_minimum < 100
        """,
        """
        alter table public.forge_state
        alter column prospective_minimum set default 100
        """,
        """
        create or replace function public.invalidate_forge_predictions_on_draw_change()
        returns trigger
        language plpgsql
        security definer
        set search_path = public
        as $$
        declare
            cutoff_date date;
            previous_max date;
            numbers_changed boolean;
            superstar_changed boolean;
            structure_changed boolean;
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
            elsif tg_op = 'DELETE' then
                cutoff_date := old.data_estrazione;
            else
                structure_changed := row(
                    old.data_estrazione, old.anno, old.concorso
                ) is distinct from row(
                    new.data_estrazione, new.anno, new.concorso
                );
                numbers_changed := row(
                    old.n1, old.n2, old.n3, old.n4, old.n5, old.n6
                ) is distinct from row(
                    new.n1, new.n2, new.n3, new.n4, new.n5, new.n6
                );
                superstar_changed := old.superstar is distinct from new.superstar;

                if structure_changed then
                    cutoff_date := least(old.data_estrazione, new.data_estrazione);
                else
                    -- Jolly e campi non predittivi non toccano FORGE.
                    if not numbers_changed and not superstar_changed then
                        return new;
                    end if;

                    if numbers_changed then
                        update public.forge_predictions as prediction
                        set target_year = new.anno,
                            target_contest = new.concorso,
                            target_date = new.data_estrazione,
                            hits = (
                                case when prediction.n1 in (new.n1, new.n2, new.n3, new.n4, new.n5, new.n6) then 1 else 0 end
                                + case when prediction.n2 in (new.n1, new.n2, new.n3, new.n4, new.n5, new.n6) then 1 else 0 end
                                + case when prediction.n3 in (new.n1, new.n2, new.n3, new.n4, new.n5, new.n6) then 1 else 0 end
                                + case when prediction.n4 in (new.n1, new.n2, new.n3, new.n4, new.n5, new.n6) then 1 else 0 end
                                + case when prediction.n5 in (new.n1, new.n2, new.n3, new.n4, new.n5, new.n6) then 1 else 0 end
                                + case when prediction.n6 in (new.n1, new.n2, new.n3, new.n4, new.n5, new.n6) then 1 else 0 end
                            )::smallint,
                            target_superstar = new.superstar,
                            superstar_hit = case
                                when prediction.predicted_superstar is null
                                     or new.superstar is null then null
                                else prediction.predicted_superstar = new.superstar
                            end,
                            evaluated_at = now()
                        where prediction.status = 'evaluated'
                          and prediction.target_year = old.anno
                          and prediction.target_contest = old.concorso;
                    else
                        update public.forge_predictions as prediction
                        set target_superstar = new.superstar,
                            superstar_hit = case
                                when prediction.predicted_superstar is null
                                     or new.superstar is null then null
                                else prediction.predicted_superstar = new.superstar
                            end
                        where prediction.status = 'evaluated'
                          and prediction.target_year = old.anno
                          and prediction.target_contest = old.concorso;
                    end if;

                    -- Le sole previsioni ancora future dipendenti dal dato
                    -- corretto vengono conservate per audit come void.
                    update public.forge_predictions
                    set status = 'void',
                        target_year = null,
                        target_contest = null,
                        target_date = null,
                        hits = null,
                        target_superstar = null,
                        superstar_hit = null,
                        evaluated_at = null
                    where status = 'pending'
                      and source_date >= new.data_estrazione;

                    return new;
                end if;
            end if;

            update public.forge_predictions
            set status = 'void',
                target_year = null,
                target_contest = null,
                target_date = null,
                hits = null,
                target_superstar = null,
                superstar_hit = null,
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
        $$
        """,
        """
        revoke execute on function
            public.invalidate_forge_predictions_on_draw_change()
        from public, anon, authenticated
        """,
        """
        drop trigger if exists trg_invalidate_forge_predictions
        on public.estrazioni
        """,
        """
        create trigger trg_invalidate_forge_predictions
        after insert or update or delete on public.estrazioni
        for each row
        execute function public.invalidate_forge_predictions_on_draw_change()
        """,
    ]
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
        connection.commit()


def fetch_forge_experiments_v2(
    archive_signature: str,
    forge_version: str,
) -> list[dict[str, object]]:
    ensure_forge_v2_tables()
    query = """
        select experiment_key, archive_signature, forge_version, model_id,
               status, quality, configuration, metrics, checks, reason,
               created_at, updated_at
        from public.forge_experiments_v2
        where archive_signature = %s and forge_version = %s
        order by quality desc nulls last, model_id
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (str(archive_signature), str(forge_version)))
            rows = cursor.fetchall()
    return [dict(row) for row in rows]


def save_forge_experiment_v2(record: Mapping[str, object]) -> dict[str, str]:
    ensure_forge_v2_tables()
    query = """
        insert into public.forge_experiments_v2 (
            experiment_key, archive_signature, forge_version, model_id,
            status, quality, configuration, metrics, checks, reason
        ) values (
            %(experiment_key)s, %(archive_signature)s, %(forge_version)s,
            %(model_id)s, %(status)s, %(quality)s,
            %(configuration)s::jsonb, %(metrics)s::jsonb,
            %(checks)s::jsonb, %(reason)s
        )
        on conflict (experiment_key) do update set
            status = excluded.status,
            quality = excluded.quality,
            configuration = excluded.configuration,
            metrics = excluded.metrics,
            checks = excluded.checks,
            reason = excluded.reason,
            updated_at = now()
        returning experiment_key
    """
    payload = {
        "experiment_key": str(record["experiment_key"]),
        "archive_signature": str(record["archive_signature"]),
        "forge_version": str(record["forge_version"]),
        "model_id": str(record["model_id"]),
        "status": str(record["status"]),
        "quality": record.get("quality"),
        "configuration": json.dumps(record.get("configuration", {}), ensure_ascii=False),
        "metrics": json.dumps(record.get("metrics", {}), ensure_ascii=False, default=str),
        "checks": json.dumps(record.get("checks", {}), ensure_ascii=False),
        "reason": record.get("reason"),
    }
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, payload)
            saved = cursor.fetchone()
        connection.commit()
    return {"experiment_key": str(saved["experiment_key"])}


def fetch_forge_state() -> dict[str, object] | None:
    ensure_forge_v2_tables()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, mode, champion_model, challenger_model,
                       prospective_minimum, note, updated_at
                from public.forge_state where id = 1
                """
            )
            row = cursor.fetchone()
    return None if row is None else dict(row)


def save_forge_state(record: Mapping[str, object]) -> dict[str, object]:
    ensure_forge_v2_tables()
    query = """
        insert into public.forge_state (
            id, mode, champion_model, challenger_model,
            prospective_minimum, note
        ) values (
            1, %(mode)s, %(champion_model)s::jsonb,
            %(challenger_model)s::jsonb, %(prospective_minimum)s, %(note)s
        )
        on conflict (id) do update set
            mode = excluded.mode,
            champion_model = excluded.champion_model,
            challenger_model = excluded.challenger_model,
            prospective_minimum = excluded.prospective_minimum,
            note = excluded.note,
            updated_at = now()
        returning mode, updated_at
    """
    challenger = record.get("challenger_model")
    payload = {
        "mode": str(record.get("mode", "shadow")),
        "champion_model": json.dumps(
            record.get("champion_model", {}), ensure_ascii=False, default=str
        ),
        "challenger_model": (
            None
            if challenger is None
            else json.dumps(challenger, ensure_ascii=False, default=str)
        ),
        "prospective_minimum": int(record.get("prospective_minimum", 100)),
        "note": record.get("note"),
    }
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, payload)
            saved = cursor.fetchone()
        connection.commit()
    return dict(saved)


def save_forge_prediction(record: Mapping[str, object]) -> dict[str, object]:
    ensure_forge_v2_tables()
    numbers = tuple(sorted(int(value) for value in record["numbers"]))
    if len(numbers) != 6 or len(set(numbers)) != 6:
        raise ValueError("La previsione FORGE deve contenere sei numeri distinti.")
    predicted_superstar = record.get("predicted_superstar")
    if predicted_superstar is not None:
        predicted_superstar = int(predicted_superstar)
        if not 1 <= predicted_superstar <= 90:
            raise ValueError("Il SuperStar previsto deve essere compreso tra 1 e 90.")
    reactivate_query = """
        update public.forge_predictions as prediction
        set archive_signature = %(archive_signature)s,
            forge_version = %(forge_version)s,
            source_year = %(source_year)s,
            source_contest = %(source_contest)s,
            source_date = %(source_date)s,
            role = %(role)s,
            model_id = %(model_id)s,
            model_config = %(model_config)s::jsonb,
            n1 = %(n1)s,
            n2 = %(n2)s,
            n3 = %(n3)s,
            n4 = %(n4)s,
            n5 = %(n5)s,
            n6 = %(n6)s,
            predicted_superstar = %(predicted_superstar)s,
            status = 'pending',
            target_year = null,
            target_contest = null,
            target_date = null,
            hits = null,
            target_superstar = null,
            superstar_hit = null,
            evaluated_at = null
        where prediction.prediction_key = %(prediction_key)s
          and prediction.status = 'void'
          and not exists (
              select 1
              from public.forge_predictions as active
              where active.status = 'pending'
                and active.forge_version = %(forge_version)s
                and active.source_year = %(source_year)s
                and active.source_contest = %(source_contest)s
                and active.role = %(role)s
          )
        returning prediction_key
    """
    insert_query = """
        insert into public.forge_predictions (
            prediction_key, archive_signature, forge_version,
            source_year, source_contest, source_date,
            role, model_id, model_config,
            n1, n2, n3, n4, n5, n6, predicted_superstar
        ) values (
            %(prediction_key)s, %(archive_signature)s, %(forge_version)s,
            %(source_year)s, %(source_contest)s, %(source_date)s,
            %(role)s, %(model_id)s, %(model_config)s::jsonb,
            %(n1)s, %(n2)s, %(n3)s, %(n4)s, %(n5)s, %(n6)s,
            %(predicted_superstar)s
        )
        on conflict do nothing
        returning prediction_key
    """
    payload: dict[str, object] = {
        "prediction_key": str(record["prediction_key"]),
        "archive_signature": str(record["archive_signature"]),
        "forge_version": str(record["forge_version"]),
        "source_year": int(record["source_year"]),
        "source_contest": int(record["source_contest"]),
        "source_date": record["source_date"],
        "role": str(record["role"]),
        "model_id": str(record["model_id"]),
        "model_config": json.dumps(
            record.get("model_config", {}), ensure_ascii=False, default=str
        ),
        "predicted_superstar": predicted_superstar,
    }
    payload.update({f"n{index}": numbers[index - 1] for index in range(1, 7)})
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(reactivate_query, payload)
            saved = cursor.fetchone()
            if saved is None:
                cursor.execute(insert_query, payload)
                saved = cursor.fetchone()
        connection.commit()
    return {
        "prediction_key": (
            str(saved["prediction_key"]) if saved else str(record["prediction_key"])
        ),
        "inserted": saved is not None,
    }


def fetch_pending_forge_predictions(
    forge_version: str,
) -> list[dict[str, object]]:
    ensure_forge_v2_tables()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select prediction_key, archive_signature, forge_version,
                       source_year, source_contest, source_date,
                       role, model_id, model_config,
                       n1, n2, n3, n4, n5, n6, predicted_superstar,
                       status, created_at
                from public.forge_predictions
                where status = 'pending' and forge_version = %s
                order by source_date, created_at
                """,
                (str(forge_version),),
            )
            rows = cursor.fetchall()
    return [dict(row) for row in rows]


def void_obsolete_pending_forge_predictions(
    *,
    forge_version: str,
    source_year: int,
    source_contest: int,
    keep_prediction_keys: list[str] | tuple[str, ...],
) -> list[dict[str, object]]:
    """Mette a void i pending che non appartengono alla coppia corrente."""
    ensure_forge_v2_tables()
    query = """
        update public.forge_predictions
        set status = 'void',
            target_year = null,
            target_contest = null,
            target_date = null,
            hits = null,
            target_superstar = null,
            superstar_hit = null,
            evaluated_at = null
        where status = 'pending'
          and forge_version = %s
          and source_year = %s
          and source_contest = %s
          and not (prediction_key = any(%s))
        returning prediction_key, archive_signature, role, model_id
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    str(forge_version),
                    int(source_year),
                    int(source_contest),
                    [str(key) for key in keep_prediction_keys],
                ),
            )
            rows = cursor.fetchall()
        connection.commit()
    return [dict(row) for row in rows]


def evaluate_forge_prediction(
    prediction_key: str,
    *,
    target_year: int,
    target_contest: int,
    target_date: object,
    hits: int,
    target_superstar: int | None,
    superstar_hit: bool | None,
) -> dict[str, str]:
    ensure_forge_v2_tables()
    query = """
        update public.forge_predictions
        set status = 'evaluated',
            target_year = %s,
            target_contest = %s,
            target_date = %s,
            hits = %s,
            target_superstar = %s,
            superstar_hit = %s,
            evaluated_at = now()
        where prediction_key = %s and status = 'pending'
        returning prediction_key
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    int(target_year),
                    int(target_contest),
                    target_date,
                    int(hits),
                    None if target_superstar is None else int(target_superstar),
                    superstar_hit,
                    str(prediction_key),
                ),
            )
            saved = cursor.fetchone()
        connection.commit()
    return {"prediction_key": str(saved["prediction_key"])} if saved else {}


def fetch_evaluated_forge_predictions(
    forge_version: str,
) -> list[dict[str, object]]:
    ensure_forge_v2_tables()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select prediction_key, archive_signature, forge_version,
                       role, model_id,
                       source_year, source_contest, source_date,
                       target_year, target_contest, target_date, hits,
                       predicted_superstar, target_superstar, superstar_hit,
                       model_config, evaluated_at
                from public.forge_predictions
                where status = 'evaluated' and forge_version = %s
                order by source_date, role
                """,
                (str(forge_version),),
            )
            rows = cursor.fetchall()
    return [dict(row) for row in rows]
