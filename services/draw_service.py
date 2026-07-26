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

    validated_numbers = [
        int(validate_number(number, f"N{index}"))
        for index, number in enumerate(numbers, start=1)
    ]
    if len(set(validated_numbers)) != 6:
        raise ValueError("I sei numeri devono essere tutti differenti.")

    validated_jolly = validate_number(jolly, "Jolly", allow_empty=True)
    validated_superstar = int(validate_number(superstar, "SuperStar"))

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
