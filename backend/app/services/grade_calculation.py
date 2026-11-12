"""Exact arithmetic shared by M7 views and exports."""
from decimal import ROUND_HALF_UP, Decimal


def normalize_score(score: Decimal | None, maximum: Decimal) -> Decimal | None:
    if maximum <= 0:
        raise ValueError("Điểm tối đa phải lớn hơn 0.")
    if score is None:
        return None
    if not score.is_finite() or score < 0 or score > maximum:
        raise ValueError("Điểm không hợp lệ.")
    return score * Decimal(10) / maximum


def weighted_total(values: list[tuple[Decimal | None, Decimal]]) -> Decimal:
    total = Decimal(0)
    for score, weight in values:
        if not weight.is_finite() or not 0 <= weight <= 100:
            raise ValueError("Trọng số phải từ 0 đến 100.")
        if score is not None and (not score.is_finite() or not 0 <= score <= 10):
            raise ValueError("Điểm phải từ 0 đến 10.")
        total += (score if score is not None else Decimal(0)) * weight / 100
    return total.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
