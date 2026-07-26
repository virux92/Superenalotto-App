from __future__ import annotations

from contextlib import contextmanager
import json
from typing import Iterator, Mapping

import pandas as pd
import psycopg
from psycopg.rows import dict_row
import streamlit as st


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


def import_draws(dataframe: pd.DataFrame, source: str = "import_csv_iniziale") -> dict[str, int]:
    required = [
        "data", "anno", "concorso", "n1", "n2", "n3", "n4", "n5", "n6", "jolly", "superstar"
    ]
    missing = [column for column in required if column not in dataframe.columns]
    if missing:
        raise ValueError("Colonne mancanti: " + ", ".join(missing))

    frame = dataframe[required].copy()
    frame["data"] = pd.to_datetime(frame["data"], errors="raise").dt.date

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
    for row in frame.to_dict(orient="records"):
        numbers = sorted(int(row[f"n{i}"]) for i in range(1, 7))
        if len(set(numbers)) != 6 or not all(1 <= number <= 90 for number in numbers):
            raise ValueError(f"Numeri non validi per {row['anno']} concorso {row['concorso']}.")

        record: dict[str, object] = {
            "data": row["data"],
            "concorso": int(row["concorso"]),
            "fonte": source,
            "jolly": None if pd.isna(row["jolly"]) else int(row["jolly"]),
            "superstar": None if pd.isna(row["superstar"]) else int(row["superstar"]),
        }
        record.update({f"n{i}": numbers[i - 1] for i in range(1, 7)})
        records.append(record)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(sql, records)
            cursor.execute(
                """
                insert into public.log_operazioni (livello, categoria, azione, messaggio, dettagli)
                values ('info', 'archivio', 'importazione_estrazioni', %s, %s::jsonb)
                """,
                (
                    f"Importate o aggiornate {len(records)} estrazioni",
                    json.dumps({"origine": source}, ensure_ascii=False),
                ),
            )
        connection.commit()

    return {"processed": len(records)}


def upsert_draw(draw: Mapping[str, object], source: str = "inserimento_manuale") -> dict[str, int]:
    """Inserisce o aggiorna una singola estrazione usando gli stessi controlli dell'import."""
    return import_draws(pd.DataFrame([dict(draw)]), source=source)


def delete_draw(year: int, contest: int, source: str = "eliminazione_manuale") -> dict[str, int]:
    """Elimina un concorso esistente e registra l'operazione.

    La UI espone questa funzione soltanto per l'ultima estrazione dell'archivio,
    evitando buchi nella sequenza annuale.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
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
