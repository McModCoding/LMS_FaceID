"""
utils/clock.py
Đồng hồ duy nhất cho mọi so sánh thời gian nghiệp vụ (Asia/Ho_Chi_Minh).
Có thể thay thế trong test bằng cách dùng `override_clock`.
"""

from __future__ import annotations

import zoneinfo
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime

_VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

# Hàm có thể bị test ghi đè
_clock_fn: Callable[[], datetime] | None = None


def now_local() -> datetime:
    """Trả thời gian hiện tại theo múi giờ Asia/Ho_Chi_Minh."""
    if _clock_fn is not None:
        return _clock_fn()
    return datetime.now(_VN)


@contextmanager
def override_clock(fixed_dt: datetime):
    """
    Context manager để cố định đồng hồ trong test.

    Ví dụ::

        with override_clock(datetime(2026, 9, 1, 8, 0, tzinfo=VN_TZ)):
            result = open_session(...)
    """
    global _clock_fn
    old = _clock_fn
    _clock_fn = lambda: fixed_dt  # noqa: E731
    try:
        yield
    finally:
        _clock_fn = old


VN_TZ = _VN
