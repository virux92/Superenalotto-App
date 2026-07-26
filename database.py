from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

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
        return pd.read_sql_query(query, connection)


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
                    '{"origine":"estrazioni.csv"}',
                ),
            )
        connection.commit()

    return {"processed": len(records)}
