from __future__ import annotations

import heapq
import math
from itertools import combinations

COST_BASE = 1.00
COST_SUPERSTAR = 0.50


def combination_features(combo: tuple[int, ...]) -> dict[str, int]:
    even = sum(number % 2 == 0 for number in combo)
    low = sum(number <= 31 for number in combo)
    decades = len({(number - 1) // 10 for number in combo})
    consecutive_pairs = sum(b - a == 1 for a, b in zip(combo, combo[1:]))
    return {"sum": sum(combo), "even": even, "low": low, "decades": decades, "consecutive_pairs": consecutive_pairs, "span": combo[-1] - combo[0]}


def passes_structural_filters(combo: tuple[int, ...], minimum_sum: int, maximum_sum: int, maximum_low_numbers: int, minimum_decades: int) -> bool:
    features = combination_features(combo)
    return minimum_sum <= features["sum"] <= maximum_sum and features["even"] in (2, 3, 4) and features["low"] <= maximum_low_numbers and features["decades"] >= minimum_decades


def combination_quality(combo: tuple[int, ...], scores: dict[int, float]) -> float:
    features = combination_features(combo)
    return sum(scores[number] for number in combo) + (0.06 if features["even"] == 3 else 0.02) + features["decades"] * 0.015 + (features["span"] / 89.0) * 0.04 - features["consecutive_pairs"] * 0.025


def rank_candidate_sestine(scores: dict[int, float], top_pool_size: int, limit: int, minimum_sum: int, maximum_sum: int, maximum_low_numbers: int, minimum_decades: int) -> list[tuple[float, tuple[int, ...]]]:
    pool = sorted(scores, key=scores.get, reverse=True)[:top_pool_size]
    heap: list[tuple[float, tuple[int, ...]]] = []
    for raw_combo in combinations(pool, 6):
        combo = tuple(sorted(raw_combo))
        if not passes_structural_filters(combo, minimum_sum, maximum_sum, maximum_low_numbers, minimum_decades):
            continue
        item = (combination_quality(combo, scores), combo)
        if len(heap) < limit:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)
    return sorted(heap, key=lambda item: (item[0], item[1]), reverse=True)


def system_cost(number_of_lines: int, with_superstar: bool) -> float:
    return number_of_lines * (COST_BASE + (COST_SUPERSTAR if with_superstar else 0.0))


def euro(value: float) -> str:
    return f"{value:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".") + " €"


def generate_integral_system(scores: dict[int, float], pool_size: int) -> tuple[list[int], list[tuple[int, ...]]]:
    pool = sorted(sorted(scores, key=scores.get, reverse=True)[:pool_size])
    return pool, list(combinations(pool, 6))


def generate_base_variant_system(scores: dict[int, float], base_count: int, variant_count: int) -> tuple[list[int], list[int], list[tuple[int, ...]]]:
    required_variants = 6 - base_count
    if variant_count < required_variants:
        raise ValueError(f"Con {base_count} basi servono almeno {required_variants} varianti.")
    ranked = sorted(scores, key=scores.get, reverse=True)
    bases = sorted(ranked[:base_count])
    variants = ranked[base_count:base_count + variant_count]
    lines = [tuple(sorted((*bases, *variant_combo))) for variant_combo in combinations(variants, required_variants)]
    lines.sort(key=lambda combo: combination_quality(combo, scores), reverse=True)
    return bases, sorted(variants), lines


def generate_reduced_system(scores: dict[int, float], pool_size: int, maximum_lines: int) -> tuple[list[int], list[tuple[int, ...]], float]:
    pool = sorted(scores, key=scores.get, reverse=True)[:pool_size]
    candidates = [(combination_quality(tuple(sorted(raw)), scores), tuple(sorted(raw))) for raw in combinations(pool, 6) if passes_structural_filters(tuple(sorted(raw)), 200, 340, 4, 4)]
    if not candidates:
        candidates = [(combination_quality(tuple(sorted(raw)), scores), tuple(sorted(raw))) for raw in combinations(pool, 6)]
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    max_quality = candidates[0][0] or 1.0
    selected: list[tuple[int, ...]] = []
    covered_pairs: set[tuple[int, int]] = set()
    remaining = candidates.copy()
    while remaining and len(selected) < maximum_lines:
        best_index, best_objective = 0, -math.inf
        for index, (quality, combo) in enumerate(remaining):
            combo_pairs = set(combinations(combo, 2))
            new_pair_ratio = len(combo_pairs - covered_pairs) / 15.0
            max_overlap = max((len(set(combo) & set(chosen)) for chosen in selected), default=0)
            objective = 0.55 * (quality / max_quality) + 0.30 * new_pair_ratio + 0.15 * (1.0 - max_overlap / 6.0)
            if objective > best_objective:
                best_objective, best_index = objective, index
        _, chosen = remaining.pop(best_index)
        selected.append(chosen)
        covered_pairs.update(combinations(chosen, 2))
    possible_pairs = math.comb(pool_size, 2)
    return sorted(pool), selected, (len(covered_pairs) / possible_pairs if possible_pairs else 0.0)
