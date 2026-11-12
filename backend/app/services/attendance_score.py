"""Công thức điểm chuyên cần dùng chung cho báo cáo và xuất Excel."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def calculate_attendance_score(
    *,
    present_count: int | Decimal,
    late_count: int | Decimal,
    excused_count: int | Decimal,
    total_count: int | Decimal,
    weight_present: float | Decimal,
    weight_late: float | Decimal,
    weight_excused: float | Decimal,
) -> Decimal | None:
    """Trả điểm chuyên cần thang 10, làm tròn một chữ số theo HALF_UP."""
    if not total_count:
        return None

    weighted_total = (
        Decimal(str(present_count)) * Decimal(str(weight_present))
        + Decimal(str(late_count)) * Decimal(str(weight_late))
        + Decimal(str(excused_count)) * Decimal(str(weight_excused))
    )
    return (Decimal("10") * weighted_total / Decimal(str(total_count))).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
