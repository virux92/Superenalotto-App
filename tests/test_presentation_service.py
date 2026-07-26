from services.presentation_service import build_candidate_profile, coherence_label


def test_coherence_labels() -> None:
    assert coherence_label(0.80) == "Alta"
    assert coherence_label(0.55) == "Media"
    assert coherence_label(0.20) == "Bassa"


def test_candidate_profile_checks_structure() -> None:
    state = {
        "score": {number: (91 - number) / 90 for number in range(1, 91)},
        "agreement": {number: 0.75 for number in range(1, 91)},
        "structural": {
            "minimum_sum": 20,
            "maximum_sum": 300,
            "maximum_low_numbers": 6,
            "minimum_decades": 1,
        },
    }
    profile = build_candidate_profile((1, 2, 3, 4, 5, 6), state)
    assert profile["structural_ok"] is True
    assert profile["top_twelve_count"] == 6
    assert profile["average_agreement"] == 0.75
