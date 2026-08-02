from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

NUMBER_COLUMNS = [f"n{index}" for index in range(1, 7)]


@dataclass(frozen=True)
class RecommendationEvaluation:
    summary: dict[str, Any]
    details: list[dict[str, Any]]


def normalize_ticket_numbers(numbers: Iterable[object]) -> tuple[int, ...]:
    normalized = tuple(sorted(int(number) for number in numbers))
    if len(normalized) != 6:
        raise ValueError("La schedina deve contenere esattamente 6 numeri.")
    if len(set(normalized)) != 6:
        raise ValueError("I 6 numeri della schedina devono essere diversi.")
    if not all(1 <= number <= 90 for number in normalized):
        raise ValueError("I numeri della schedina devono essere compresi tra 1 e 90.")
    return normalized


def recommendation_numbers(recommendation: Mapping[str, Any]) -> tuple[int, ...]:
    return normalize_ticket_numbers(recommendation[column] for column in NUMBER_COLUMNS)


def result_label(hit_count: int, jolly_hit: bool) -> str:
    if hit_count == 6:
        return "6"
    if hit_count == 5 and jolly_hit:
        return "5+1"
    if hit_count == 5:
        return "5"
    if hit_count == 4:
        return "4"
    if hit_count == 3:
        return "Terno (3)"
    if hit_count == 2:
        return "Ambo (2)"
    if hit_count == 1:
        return "1 numero"
    return "Nessun numero"


def _best_result_key(detail: Mapping[str, Any]) -> tuple[int, int]:
    return int(detail["Punti"]), int(bool(detail["Jolly centrato"]))


def _empty_summary(
    recommendation: Mapping[str, Any], numbers: Sequence[int], reason: str
) -> dict[str, Any]:
    draw_count = int(recommendation["numero_concorsi"])
    return {
        "ID": int(recommendation["id"]),
        "Nome": str(recommendation.get("nome") or f"Schedina {recommendation['id']}"),
        "Sestina": " - ".join(map(str, numbers)),
        "SuperStar": recommendation.get("superstar"),
        "Dal concorso": f"{int(recommendation['concorso_inizio'])}/{int(recommendation['anno_inizio'])}",
        "Concorsi previsti": draw_count,
        "Concorsi valutati": 0,
        "Concorsi in attesa": draw_count,
        "Risultati 2+": 0,
        "Miglior risultato": reason,
        "Stato": "In attesa",
    }


def evaluate_recommendation(
    recommendation: Mapping[str, Any], archive: pd.DataFrame
) -> RecommendationEvaluation:
    """Confronta una schedina con i concorsi a partire da quello indicato.

    I risultati sono calcolati ogni volta sull'archivio corrente. In questo modo una
    correzione a un'estrazione aggiorna automaticamente anche lo storico della schedina.
    """
    numbers = recommendation_numbers(recommendation)
    draw_count = int(recommendation["numero_concorsi"])
    if draw_count < 1:
        raise ValueError("Il numero di concorsi da monitorare deve essere almeno 1.")

    ordered = archive.sort_values(["data", "concorso"]).reset_index(drop=True)
    start_mask = (
        ordered["anno"].astype(int).eq(int(recommendation["anno_inizio"]))
        & ordered["concorso"].astype(int).eq(int(recommendation["concorso_inizio"]))
    )
    matching_indexes = ordered.index[start_mask].tolist()
    if not matching_indexes:
        summary = _empty_summary(
            recommendation,
            numbers,
            "Concorso iniziale non ancora disponibile",
        )
        return RecommendationEvaluation(summary=summary, details=[])

    selected = ordered.iloc[matching_indexes[0] : matching_indexes[0] + draw_count]
    details: list[dict[str, Any]] = []
    ticket_set = set(numbers)
    ticket_superstar = recommendation.get("superstar")
    if pd.isna(ticket_superstar):
        ticket_superstar = None

    for _, draw in selected.iterrows():
        extracted = {int(draw[column]) for column in NUMBER_COLUMNS}
        hits = sorted(ticket_set.intersection(extracted))
        jolly = None if pd.isna(draw.get("jolly")) else int(draw["jolly"])
        superstar = None if pd.isna(draw.get("superstar")) else int(draw["superstar"])
        jolly_hit = jolly is not None and jolly in ticket_set
        superstar_hit = (
            ticket_superstar is not None
            and superstar is not None
            and int(ticket_superstar) == superstar
        )
        hit_count = len(hits)
        details.append(
            {
                "ID schedina": int(recommendation["id"]),
                "Nome": str(recommendation.get("nome") or f"Schedina {recommendation['id']}"),
                "Data": pd.Timestamp(draw["data"]),
                "Anno": int(draw["anno"]),
                "Concorso": int(draw["concorso"]),
                "Sestina giocata": " - ".join(map(str, numbers)),
                "Numeri estratti": " - ".join(str(int(draw[column])) for column in NUMBER_COLUMNS),
                "Punti": hit_count,
                "Numeri centrati": ", ".join(map(str, hits)) if hits else "—",
                "Jolly": jolly,
                "Jolly centrato": bool(jolly_hit),
                "SuperStar giocato": ticket_superstar,
                "SuperStar estratto": superstar,
                "SuperStar centrato": bool(superstar_hit),
                "Risultato": result_label(hit_count, jolly_hit),
                "Esito 2+": "Sì" if hit_count >= 2 else "No",
            }
        )

    evaluated = len(details)
    pending = max(0, draw_count - evaluated)
    two_plus = sum(int(detail["Punti"] >= 2) for detail in details)
    best = max(details, key=_best_result_key) if details else None
    if pending == 0:
        status = "Conclusa"
    elif evaluated:
        status = "In corso"
    else:
        status = "In attesa"

    summary = {
        "ID": int(recommendation["id"]),
        "Nome": str(recommendation.get("nome") or f"Schedina {recommendation['id']}"),
        "Sestina": " - ".join(map(str, numbers)),
        "SuperStar": ticket_superstar,
        "Dal concorso": f"{int(recommendation['concorso_inizio'])}/{int(recommendation['anno_inizio'])}",
        "Concorsi previsti": draw_count,
        "Concorsi valutati": evaluated,
        "Concorsi in attesa": pending,
        "Risultati 2+": two_plus,
        "Miglior risultato": best["Risultato"] if best else "In attesa",
        "Stato": status,
    }
    return RecommendationEvaluation(summary=summary, details=details)


def build_monitoring_tables(
    recommendations: pd.DataFrame, archive: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if recommendations.empty:
        return pd.DataFrame(), pd.DataFrame()

    summaries: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for recommendation in recommendations.to_dict(orient="records"):
        evaluation = evaluate_recommendation(recommendation, archive)
        summaries.append(evaluation.summary)
        details.extend(evaluation.details)

    summary_frame = pd.DataFrame(summaries).sort_values("ID", ascending=False)
    detail_frame = pd.DataFrame(details)
    if not detail_frame.empty:
        detail_frame = detail_frame.sort_values(
            ["Data", "Concorso", "ID schedina"], ascending=[False, False, False]
        )
    return summary_frame, detail_frame


def suggest_next_target(archive: pd.DataFrame) -> tuple[int, int]:
    latest = archive.sort_values(["data", "concorso"]).iloc[-1]
    return int(latest["anno"]), int(latest["concorso"]) + 1
