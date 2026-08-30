from __future__ import annotations

import math
from itertools import combinations
from typing import Iterable, Sequence

from core.combinations import combination_quality, passes_structural_filters


def portfolio_metrics(
    lines: Sequence[tuple[int, ...]], pool: Iterable[int]
) -> dict[str, float | int]:
    pool_values = sorted(set(int(value) for value in pool))
    covered_pairs = {
        pair for line in lines for pair in combinations(sorted(line), 2)
    }
    possible_pairs = math.comb(len(pool_values), 2) if len(pool_values) >= 2 else 0
    overlaps = [
        len(set(left) & set(right))
        for index, left in enumerate(lines)
        for right in lines[index + 1 :]
    ]
    return {
        "pair_coverage": len(covered_pairs) / possible_pairs if possible_pairs else 0.0,
        "covered_pairs": len(covered_pairs),
        "possible_pairs": possible_pairs,
        "maximum_overlap": max(overlaps, default=0),
        "average_overlap": sum(overlaps) / len(overlaps) if overlaps else 0.0,
        "unique_lines": len(set(lines)),
    }


def _candidate_lines(scores: dict[int, float], pool: list[int]) -> list[tuple[float, tuple[int, ...]]]:
    candidates = [
        (combination_quality(combo, scores), combo)
        for combo in (tuple(sorted(raw)) for raw in combinations(pool, 6))
        if passes_structural_filters(combo, 200, 340, 4, 4)
    ]
    if not candidates:
        candidates = [
            (combination_quality(combo, scores), combo)
            for combo in (tuple(sorted(raw)) for raw in combinations(pool, 6))
        ]
    return sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)


def _greedy_portfolio(
    candidates: list[tuple[float, tuple[int, ...]]], maximum_lines: int
) -> list[tuple[int, ...]]:
    maximum_quality = candidates[0][0] or 1.0
    selected: list[tuple[int, ...]] = []
    covered_pairs: set[tuple[int, int]] = set()
    remaining = list(candidates)
    while remaining and len(selected) < maximum_lines:
        best_index = 0
        best_objective = -math.inf
        for index, (quality, combo) in enumerate(remaining):
            pairs = set(combinations(combo, 2))
            new_pair_ratio = len(pairs - covered_pairs) / 15.0
            overlap = max(
                (len(set(combo) & set(chosen)) for chosen in selected), default=0
            )
            objective = (
                0.50 * quality / maximum_quality
                + 0.35 * new_pair_ratio
                + 0.15 * (1.0 - overlap / 6.0)
            )
            if objective > best_objective:
                best_objective = objective
                best_index = index
        _, chosen = remaining.pop(best_index)
        selected.append(chosen)
        covered_pairs.update(combinations(chosen, 2))
    return selected


def _cp_sat_portfolio(
    candidates: list[tuple[float, tuple[int, ...]]], maximum_lines: int
) -> list[tuple[int, ...]] | None:
    """Ottimizzazione esatta opzionale; ritorna None se OR-Tools non è presente."""
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return None

    shortlist = candidates[: min(500, len(candidates))]
    model = cp_model.CpModel()
    selected = [model.new_bool_var(f"line_{index}") for index in range(len(shortlist))]
    model.add(sum(selected) == min(maximum_lines, len(shortlist)))
    pair_to_indices: dict[tuple[int, int], list[int]] = {}
    for index, (_, line) in enumerate(shortlist):
        for pair in combinations(line, 2):
            pair_to_indices.setdefault(pair, []).append(index)
    pair_covered = {}
    for pair, indices in pair_to_indices.items():
        variable = model.new_bool_var(f"pair_{pair[0]}_{pair[1]}")
        pair_covered[pair] = variable
        model.add_max_equality(variable, [selected[index] for index in indices])
    quality_terms = [
        int(round(quality * 1000)) * selected[index]
        for index, (quality, _) in enumerate(shortlist)
    ]
    model.maximize(5000 * sum(pair_covered.values()) + sum(quality_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 2.0
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [
        shortlist[index][1]
        for index, variable in enumerate(selected)
        if solver.value(variable)
    ]


def optimize_ticket_portfolio(
    scores: dict[int, float], pool_size: int, maximum_lines: int
) -> tuple[list[int], list[tuple[int, ...]], dict[str, float | int | str]]:
    """Massimizza qualità e copertura; CP-SAT con fallback deterministico."""
    if maximum_lines <= 0:
        raise ValueError("Il portafoglio deve contenere almeno una schedina.")
    pool = sorted(scores, key=scores.get, reverse=True)[: int(pool_size)]
    candidates = _candidate_lines(scores, pool)
    lines = _cp_sat_portfolio(candidates, int(maximum_lines))
    method = "CP-SAT"
    if lines is None:
        lines = _greedy_portfolio(candidates, int(maximum_lines))
        method = "greedy-deterministico"
    lines.sort(key=lambda combo: combination_quality(combo, scores), reverse=True)
    metrics = dict(portfolio_metrics(lines, pool))
    metrics["optimizer"] = method
    return sorted(pool), lines, metrics
