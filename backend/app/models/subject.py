from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.department import Department


class Subject(Base):
    __tablename__ = "subjects"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)

    department: Mapped["Department | None"] = relationship(back_populates="subjects")
