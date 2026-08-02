from core.combinations import (
    generate_base_variant_system,
    generate_integral_system,
    generate_reduced_system,
    system_cost,
)


def _scores() -> dict[int, float]:
    return {number: float(91 - number) for number in range(1, 91)}


def test_configured_system_costs() -> None:
    assert system_cost(8, False) == 8.0
    assert system_cost(8, True) == 12.0
    assert system_cost(15, False) == 15.0
    assert system_cost(15, True) == 22.5
    assert system_cost(7, True) == 10.5


def test_simple_profiles_generate_expected_line_counts() -> None:
    scores = _scores()

    _, compact_lines, _ = generate_reduced_system(scores, 12, 8)
    assert len(compact_lines) == 8

    _, _, balanced_lines = generate_base_variant_system(scores, 2, 6)
    assert len(balanced_lines) == 15

    _, integral_lines = generate_integral_system(scores, 7)
    assert len(integral_lines) == 7
