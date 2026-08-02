from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

import pandas as pd

try:
    import streamlit as st
except ModuleNotFoundError:  # consente test del motore senza dipendenza UI
    st = None


def cache_data(**cache_options: Any):
    if st is not None:
        return st.cache_data(**cache_options)

    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        return function

    return decorator

NUMBER_MIN = 1
NUMBER_MAX = 90
REQUIRED_COLUMNS = [
    "data", "anno", "concorso", "n1", "n2", "n3", "n4", "n5", "n6", "jolly", "superstar"
]


def validate_number(value: Any, field_name: str, allow_empty: bool = False) -> int | None:
    if allow_empty and (value is None or pd.isna(value) or str(value).strip() == ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} non valido.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} deve essere un numero intero.") from exc
    if not NUMBER_MIN <= number <= NUMBER_MAX:
        raise ValueError(f"{field_name} deve essere compreso tra 1 e 90.")
    return number


def normalize_archive_dataframe(raw_dataframe: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw_dataframe, pd.DataFrame):
        raise TypeError("La sorgente dati non ha restituito un DataFrame valido.")

    dataframe = raw_dataframe.copy()
    dataframe.columns = [
        str(column).strip().lstrip("\ufeff").lower()
        for column in dataframe.columns
    ]

    if "data" in dataframe.columns:
        data_as_text = dataframe["data"].astype(str).str.strip().str.lower()
        dataframe = dataframe.loc[data_as_text.ne("data")].copy()

    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError("Colonne mancanti: " + ", ".join(missing_columns))

    dataframe = dataframe[REQUIRED_COLUMNS].copy()
    if dataframe.empty:
        raise ValueError("L'archivio è vuoto.")

    dataframe["data"] = pd.to_datetime(dataframe["data"], errors="raise")
    dataframe["anno"] = pd.to_numeric(dataframe["anno"], errors="raise").astype(int)
    dataframe["concorso"] = pd.to_numeric(
        dataframe["concorso"], errors="raise"
    ).astype(int)

    for column in [f"n{index}" for index in range(1, 7)] + ["superstar"]:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="raise").astype(int)
    dataframe["jolly"] = pd.to_numeric(
        dataframe["jolly"], errors="coerce"
    ).astype("Int64")

    duplicate_contests = dataframe.duplicated(
        subset=["anno", "concorso"], keep=False
    )
    if duplicate_contests.any():
        duplicated = dataframe.loc[
            duplicate_contests, ["anno", "concorso"]
        ].head(5)
        details = ", ".join(
            f"{row.anno}/Conc.{row.concorso}" for row in duplicated.itertuples()
        )
        raise ValueError(f"Concorsi duplicati: {details}.")

    duplicate_dates = dataframe.duplicated(subset=["data"], keep=False)
    if duplicate_dates.any():
        dates = dataframe.loc[duplicate_dates, "data"].dt.strftime("%d/%m/%Y").head(5)
        raise ValueError("Date duplicate: " + ", ".join(dates))

    for row_number, row in enumerate(dataframe.itertuples(index=False), start=2):
        if row.data.year != row.anno:
            raise ValueError(
                f"Anno incoerente alla riga {row_number}: "
                f"data {row.data:%d/%m/%Y}, anno indicato {row.anno}."
            )
        numbers = [getattr(row, f"n{index}") for index in range(1, 7)]
        for index, number in enumerate(numbers, start=1):
            validate_number(number, f"N{index} alla riga {row_number}")
        if len(set(numbers)) != 6:
            raise ValueError(f"Numeri duplicati nella sestina alla riga {row_number}.")
        if numbers != sorted(numbers):
            raise ValueError(
                f"Numeri non in ordine crescente alla riga {row_number}: {numbers}."
            )
        validate_number(row.superstar, f"SuperStar alla riga {row_number}")
        validate_number(row.jolly, f"Jolly alla riga {row_number}", allow_empty=True)

    for year, group in dataframe.groupby("anno"):
        contests = sorted(group["concorso"].tolist())
        expected = list(range(1, max(contests) + 1))
        if contests != expected:
            missing = sorted(set(expected) - set(contests))
            preview = ", ".join(map(str, missing[:10]))
            raise ValueError(
                f"Nel {year} mancano concorsi nella sequenza: {preview}"
                + ("..." if len(missing) > 10 else "")
            )

    return dataframe.sort_values(["data", "anno", "concorso"]).reset_index(drop=True)


def read_csv_flexible(file_or_path: Any) -> pd.DataFrame:
    try:
        dataframe = pd.read_csv(file_or_path, sep=None, engine="python")
    except UnicodeDecodeError:
        if hasattr(file_or_path, "seek"):
            file_or_path.seek(0)
        dataframe = pd.read_csv(
            file_or_path, sep=None, engine="python", encoding="latin-1"
        )
    return normalize_archive_dataframe(dataframe)


@cache_data(show_spinner=False)
def load_repository_archive(path_text: str) -> pd.DataFrame:
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(
            "File estrazioni.csv non trovato. Caricalo nella stessa cartella di app.py."
        )
    return read_csv_flexible(path)


@cache_data(show_spinner=False, ttl=300)
def load_primary_archive(
    path_text: str, _database_loader: Callable[[], pd.DataFrame]
) -> tuple[pd.DataFrame, str, str | None]:
    database_error: str | None = None
    try:
        database_frame = _database_loader()
        if not database_frame.empty:
            return normalize_archive_dataframe(database_frame), "Supabase", None
        database_error = "La tabella estrazioni di Supabase è vuota."
    except Exception as exc:
        database_error = f"{type(exc).__name__}: {exc}"

    repository_frame = load_repository_archive(path_text)
    return repository_frame, "CSV del repository (fallback)", database_error


def archive_to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    output = normalize_archive_dataframe(dataframe)
    output["data"] = pd.to_datetime(output["data"]).dt.strftime("%Y-%m-%d")
    return output.to_csv(index=False).encode("utf-8-sig")


def archive_sha256(dataframe: pd.DataFrame) -> str:
    canonical = normalize_archive_dataframe(dataframe).copy()
    canonical["data"] = canonical["data"].dt.strftime("%Y-%m-%d")
    payload = canonical.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def archive_snapshot(dataframe: pd.DataFrame) -> dict[str, Any]:
    canonical = normalize_archive_dataframe(dataframe)
    return {
        "rows": len(canonical),
        "date_min": canonical["data"].min(),
        "date_max": canonical["data"].max(),
        "missing_jolly": int(canonical["jolly"].isna().sum()),
        "sha256": archive_sha256(canonical),
    }
