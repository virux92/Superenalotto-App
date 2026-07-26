from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


def synthetic_archive(draw_count: int = 80) -> pd.DataFrame:
    rows = []
    start = date(2025, 1, 1)
    for index in range(draw_count):
        numbers = sorted({((index * 7 + offset * 13) % 90) + 1 for offset in range(6)})
        while len(numbers) < 6:
            numbers.append((numbers[-1] % 90) + 1)
            numbers = sorted(set(numbers))
        rows.append(
            {
                "data": pd.Timestamp(start + timedelta(days=index)),
                "anno": 2025,
                "concorso": index + 1,
                **{f"n{position}": number for position, number in enumerate(numbers, 1)},
                "jolly": pd.NA if index % 17 == 0 else ((index * 3) % 90) + 1,
                "superstar": ((index * 5) % 90) + 1,
            }
        )
    return pd.DataFrame(rows)
