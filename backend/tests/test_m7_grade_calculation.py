from decimal import Decimal as D

import pytest

from app.services.grade_calculation import normalize_score, weighted_total


def test_acceptance_example_and_missing_score():
    assert weighted_total([(D(8), D(10)), (D(7), D(30)), (D(9), D(60))]) == D("8.3")
    assert weighted_total([(None, D(40)), (D(8), D(60))]) == D("4.8")


def test_half_up_and_normalization_without_intermediate_rounding():
    assert weighted_total([(D("8.25"), D(100))]) == D("8.3")
    assert normalize_score(D(7), D(20)) == D("3.5")
    assert normalize_score(None, D(10)) is None


@pytest.mark.parametrize("score,maximum", [(D(-1), D(10)), (D(11), D(10)), (D(0), D(0))])
def test_invalid_source_score(score, maximum):
    with pytest.raises(ValueError):
        normalize_score(score, maximum)
