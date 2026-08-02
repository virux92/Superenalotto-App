from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from services.archive_service import normalize_archive_dataframe, validate_number


def dataframe_to_history(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    """Converte l'archivio nel formato del motore, con estrazione più recente per prima."""
    newest_first = dataframe.sort_values("data", ascending=False)
    history: list[dict[str, Any]] = []

    for row in newest_first.itertuples(index=False):
        numbers = [int(getattr(row, f"n{index}")) for index in range(1, 7)]
        jolly = None if pd.isna(row.jolly) else int(row.jolly)
        history.append(
            {
                "date": pd.Timestamp(row.data),
                "year": int(row.anno),
                "contest": int(row.concorso),
                "label": (
                    f"{int(row.anno)} — Conc. {int(row.concorso)} "
                    f"({pd.Timestamp(row.data):%d/%m})"
                ),
                "numbers": numbers,
                "jolly": jolly,
                "superstar": int(row.superstar),
            }
        )
    return history


def _validate_draw_numbers(
    numbers: list[int], jolly: int | None, superstar: int
) -> tuple[list[int], int | None, int]:
    """Valida sestina, Jolly e SuperStar con le regole di una singola estrazione."""
    validated_numbers = [
        int(validate_number(number, f"N{index}"))
        for index, number in enumerate(numbers, start=1)
    ]
    if len(set(validated_numbers)) != 6:
        raise ValueError("I sei numeri devono essere tutti differenti.")

    validated_jolly = validate_number(jolly, "Jolly", allow_empty=True)
    if validated_jolly is not None and int(validated_jolly) in set(validated_numbers):
        raise ValueError("Il Jolly deve essere diverso dai sei numeri estratti.")

    validated_superstar = int(validate_number(superstar, "SuperStar"))
    return validated_numbers, validated_jolly, validated_superstar


def _neighbor_dates(
    dataframe: pd.DataFrame, year: int, contest: int
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Restituisce le date dei concorsi immediatamente precedente e successivo."""
    ordered = dataframe.sort_values(["anno", "concorso"]).reset_index(drop=True)
    matches = ordered.index[
        (ordered["anno"] == int(year)) & (ordered["concorso"] == int(contest))
    ].tolist()
    if len(matches) != 1:
        raise ValueError(f"Concorso {contest} del {year} non trovato in modo univoco.")

    position = int(matches[0])
    previous_date = (
        pd.Timestamp(ordered.iloc[position - 1]["data"]) if position > 0 else None
    )
    next_date = (
        pd.Timestamp(ordered.iloc[position + 1]["data"])
        if position + 1 < len(ordered)
        else None
    )
    return previous_date, next_date


def add_extraction(
    dataframe: pd.DataFrame,
    draw_date: date,
    contest: int,
    numbers: list[int],
    jolly: int | None,
    superstar: int,
) -> pd.DataFrame:
    """Aggiunge una nuova estrazione alla sessione dopo controlli completi."""
    year = draw_date.year
    if ((dataframe["anno"] == year) & (dataframe["concorso"] == contest)).any():
        raise ValueError(f"Il concorso {contest} del {year} è già presente.")

    timestamp = pd.Timestamp(draw_date)
    if (dataframe["data"] == timestamp).any():
        raise ValueError(f"Esiste già un'estrazione in data {draw_date:%d/%m/%Y}.")

    latest_date = pd.Timestamp(dataframe["data"].max())
    if timestamp <= latest_date:
        raise ValueError(
            "La nuova estrazione deve avere una data successiva all'ultima presente "
            f"({latest_date:%d/%m/%Y})."
        )

    validated_numbers, validated_jolly, validated_superstar = _validate_draw_numbers(
        numbers, jolly, superstar
    )

    expected_next = (
        int(dataframe.loc[dataframe["anno"] == year, "concorso"].max()) + 1
        if (dataframe["anno"] == year).any()
        else 1
    )
    if contest != expected_next:
        raise ValueError(
            f"Per il {year} il prossimo concorso atteso è {expected_next}, non {contest}."
        )

    new_row = {
        "data": timestamp,
        "anno": year,
        "concorso": int(contest),
        **{
            f"n{index}": number
            for index, number in enumerate(sorted(validated_numbers), start=1)
        },
        "jolly": validated_jolly,
        "superstar": validated_superstar,
    }

    updated = pd.concat([dataframe, pd.DataFrame([new_row])], ignore_index=True)
    return normalize_archive_dataframe(updated)


def update_extraction(
    dataframe: pd.DataFrame,
    year: int,
    contest: int,
    draw_date: date,
    numbers: list[int],
    jolly: int | None,
    superstar: int,
) -> pd.DataFrame:
    """Corregge un concorso esistente senza cambiarne anno e numero."""
    year = int(year)
    contest = int(contest)
    mask = (dataframe["anno"] == year) & (dataframe["concorso"] == contest)
    if int(mask.sum()) != 1:
        raise ValueError(f"Concorso {contest} del {year} non trovato in modo univoco.")
    if draw_date.year != year:
        raise ValueError(
            f"La data deve appartenere al {year}, anno del concorso selezionato."
        )

    timestamp = pd.Timestamp(draw_date)
    duplicate_date = dataframe.loc[~mask, "data"].eq(timestamp).any()
    if duplicate_date:
        raise ValueError(f"Esiste già un'altra estrazione in data {draw_date:%d/%m/%Y}.")

    previous_date, next_date = _neighbor_dates(dataframe, year, contest)
    if previous_date is not None and timestamp <= previous_date:
        raise ValueError(
            "La data deve essere successiva al concorso precedente "
            f"({previous_date:%d/%m/%Y})."
        )
    if next_date is not None and timestamp >= next_date:
        raise ValueError(
            "La data deve essere precedente al concorso successivo "
            f"({next_date:%d/%m/%Y})."
        )

    validated_numbers, validated_jolly, validated_superstar = _validate_draw_numbers(
        numbers, jolly, superstar
    )

    updated = dataframe.copy()
    row_index = updated.index[mask][0]
    sorted_numbers = sorted(validated_numbers)
    updated.loc[row_index, "data"] = timestamp
    for index, number in enumerate(sorted_numbers, start=1):
        updated.loc[row_index, f"n{index}"] = number
    updated.loc[row_index, "jolly"] = validated_jolly
    updated.loc[row_index, "superstar"] = validated_superstar

    return normalize_archive_dataframe(updated)
