from __future__ import annotations

import unittest

import pandas as pd

from services.recommendation_service import (
    build_monitoring_tables,
    evaluate_recommendation,
    normalize_ticket_numbers,
)


class RecommendationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.archive = pd.DataFrame(
            [
                {
                    "data": pd.Timestamp("2026-07-24"),
                    "anno": 2026,
                    "concorso": 119,
                    "n1": 1,
                    "n2": 2,
                    "n3": 50,
                    "n4": 60,
                    "n5": 70,
                    "n6": 80,
                    "jolly": 90,
                    "superstar": 11,
                },
                {
                    "data": pd.Timestamp("2026-07-25"),
                    "anno": 2026,
                    "concorso": 120,
                    "n1": 10,
                    "n2": 20,
                    "n3": 51,
                    "n4": 61,
                    "n5": 71,
                    "n6": 81,
                    "jolly": 89,
                    "superstar": 12,
                },
            ]
        )
        self.ticket = {
            "id": 1,
            "nome": "Stessa schedina",
            "n1": 1,
            "n2": 2,
            "n3": 10,
            "n4": 20,
            "n5": 30,
            "n6": 40,
            "superstar": None,
            "anno_inizio": 2026,
            "concorso_inizio": 119,
            "numero_concorsi": 5,
        }

    def test_same_ticket_can_score_two_ambos_in_consecutive_draws(self) -> None:
        evaluation = evaluate_recommendation(self.ticket, self.archive)
        self.assertEqual(len(evaluation.details), 2)
        self.assertEqual([row["Punti"] for row in evaluation.details], [2, 2])
        self.assertEqual([row["Risultato"] for row in evaluation.details], ["Ambo (2)", "Ambo (2)"])
        self.assertEqual(evaluation.summary["Risultati 2+"], 2)
        self.assertEqual(evaluation.summary["Concorsi in attesa"], 3)
        self.assertEqual(evaluation.summary["Stato"], "In corso")

    def test_future_start_is_reported_as_pending(self) -> None:
        future_ticket = dict(self.ticket, concorso_inizio=121)
        evaluation = evaluate_recommendation(future_ticket, self.archive)
        self.assertEqual(evaluation.details, [])
        self.assertEqual(evaluation.summary["Concorsi valutati"], 0)
        self.assertEqual(evaluation.summary["Concorsi in attesa"], 5)
        self.assertEqual(evaluation.summary["Stato"], "In attesa")

    def test_build_tables_keeps_draw_level_history(self) -> None:
        recommendations = pd.DataFrame([self.ticket])
        summary, details = build_monitoring_tables(recommendations, self.archive)
        self.assertEqual(len(summary), 1)
        self.assertEqual(len(details), 2)
        self.assertEqual(int(summary.iloc[0]["Risultati 2+"]), 2)

    def test_number_validation_sorts_and_rejects_duplicates(self) -> None:
        self.assertEqual(normalize_ticket_numbers([40, 1, 20, 2, 30, 10]), (1, 2, 10, 20, 30, 40))
        with self.assertRaisesRegex(ValueError, "diversi"):
            normalize_ticket_numbers([1, 1, 2, 3, 4, 5])


if __name__ == "__main__":
    unittest.main()
