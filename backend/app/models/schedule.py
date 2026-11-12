from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.class_ import Class


class Schedule(Base):
    __tablename__ = "schedules"

    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False, index=True)
    # 0 = Thứ Hai, 1 = Thứ Ba, ..., 6 = Chủ Nhật
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    # Room: cắt khoảng trắng, chuẩn hóa chữ hoa ở service
    room: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    class_: Mapped["Class"] = relationship("Class", backref="schedules")
